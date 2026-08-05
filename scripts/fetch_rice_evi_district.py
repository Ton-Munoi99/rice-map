#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_rice_evi_district.py
ดึงข้อมูล Rice EVI รายอำเภอ ประเทศไทย จาก MODIS + Hybrid Mask + Phenology

Source:  MODIS/061/MOD13A3 — Monthly EVI + LSWI Composite (1km)
Mask:    GLAD LCLUC 2020 Rice ∪ MCD12Q1 Cropland (Phenology-gated)
Regions: FAO GAUL 2015 level2 (813 อำเภอ)
Output:  data/rice-evi-district.json
Format:
  { provinces: {
      "Chiang Mai": {
        "Mueang Chiang Mai": {
          "evi": 0.412, "stage": "growing",
          "rice_rai": 45000, "confidence": 0.94
        }
      }
  }}
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import calendar
import ee
import json
import os
from datetime import date, timedelta
from riceutils import init_gee, GAUL_NAME_MAP as PROV_MAP


PHENOLOGY_MONTHS = 12

# ── Rice-refinement thresholds (mirror scripts/fetch_rice_evi.py) ─────────────
FLOOD_EVI_MAX = 0.30   # น้ำท่วมขังต้องเกิดตอน canopy ยังโปร่ง (ตัดป่าเขียวทึบ)
PEAK_MIN      = 0.40   # ต้องมีเดือน canopy เขียวจริง (ตัดน้ำเปิด/บ่อกุ้ง/นาเกลือ)
AMP_MIN       = 0.25   # EVI แกว่งตามฤดูสูง (ตัดยาง/ปาล์ม/ป่า เขียวคงที่ทั้งปี)
MIN_EVI_MAX   = 0.20   # ต้องเคยโล่ง/น้ำขัง (min EVI ต่ำ) → ตัดพืชยืนต้นเขียวตลอดปี
GLAD_MIN_PIXELS  = 8    # GLAD-preferred: GLAD ต่ำกว่านี้ = คง union (GLAD ขาด)
GLAD_BONUS_RATIO = 3.0  # bonus เกินสัดส่วนนี้ของ GLAD = น่าสงสัยพืชอื่น → เชื่อ GLAD
RUBBER_ASSET     = ""   # asset ยาง (ปล่อยว่าง = ข้าม) — mirror province script
TREND_EPS     = 0.02   # |Δ EVI| ต่ำกว่านี้ = ทรงตัว (กัน noise รายเดือน)


def get_last_month_dates():
    today = date.today()
    first_this = today.replace(day=1)
    last_prev  = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


def get_history_months(current_start_iso, n=12):
    d = date.fromisoformat(current_start_iso)
    ranges = []
    for i in range(n, 0, -1):
        month = d.month - i
        year  = d.year
        while month <= 0:
            month += 12
            year  -= 1
        last_day = calendar.monthrange(year, month)[1]
        ranges.append((
            date(year, month, 1).isoformat(),
            date(year, month, last_day).isoformat(),
        ))
    return ranges


def load_rice_mask():
    """Hybrid Union Mask: GLAD rice ∪ MCD12Q1 cropland"""
    glad_mask = cropland_mask = None
    try:
        glad_mask = ee.Image("projects/glad/GLCLU2020/v2/LCLUC_2020").eq(24)
        print("✓ Loaded GLAD LCLUC 2020")
    except Exception as e:
        print(f"  ⚠️ GLAD not available: {e}")
    try:
        lc = ee.Image("MODIS/061/MCD12Q1/2022_01_01").select("LC_Type1")
        cropland_mask = lc.eq(12).Or(lc.eq(14))
        print("✓ Loaded MCD12Q1 Cropland")
    except Exception as e:
        print(f"  ⚠️ MCD12Q1 not available: {e}")

    if glad_mask is not None and cropland_mask is not None:
        return glad_mask.Or(cropland_mask), glad_mask, "GLAD ∪ MCD12Q1"
    elif glad_mask is not None:
        return glad_mask, glad_mask, "GLAD only"
    elif cropland_mask is not None:
        return cropland_mask, None, "MCD12Q1 only"
    else:
        return ee.Image(1), None, "No mask (all pixels)"


def load_exclusion_mask():
    """mask ปาล์ม/ยาง สำหรับลบออกจาก scan (mirror province script) — คืน (Image|None, desc)"""
    parts, names = [], []
    try:
        palm = (ee.ImageCollection("BIOPAMA/GlobalOilPalm/v1")
                .select("classification").mosaic().lt(3).unmask(0))
        parts.append(palm); names.append("oil palm (Descals)")
        print("✓ Loaded oil-palm exclusion")
    except Exception as e:
        print(f"  ⚠️ oil-palm layer unavailable: {e}")
    if RUBBER_ASSET:
        try:
            parts.append(ee.Image(RUBBER_ASSET).gt(0).unmask(0))
            names.append("rubber")
        except Exception as e:
            print(f"  ⚠️ rubber layer unavailable: {e}")
    if not parts:
        return None, "none"
    excl = parts[0]
    for p in parts[1:]:
        excl = excl.Or(p)
    return excl.unmask(0), " ∪ ".join(names)


def build_rice_phenology_mask(current_start, n_months=12):
    """Rice-confirmation mask: flood(canopy โปร่ง) + peak EVI + seasonal amplitude
    (mirror scripts/fetch_rice_evi.py) — ตัดพืชยืนต้น/พื้นที่น้ำออกจากนาข้าว"""
    history = get_history_months(current_start, n_months)
    evi_imgs, flood_imgs = [], []
    for s, e in history:
        img  = (ee.ImageCollection("MODIS/061/MOD13A3")
                .filterDate(s, e)
                .select(["EVI", "sur_refl_b02", "sur_refl_b07"])
                .mosaic()               # all-masked ถ้าไม่มีข้อมูล → safe
                .multiply(0.0001))
        evi  = img.select("EVI")
        nir  = img.select("sur_refl_b02")
        swir = img.select("sur_refl_b07")
        lswi = nir.subtract(swir).divide(nir.add(swir))
        flood_imgs.append(lswi.gt(evi).And(evi.lt(FLOOD_EVI_MAX)).rename("flooded"))
        evi_imgs.append(evi.rename("EVI"))

    if not flood_imgs:
        return ee.Image(0).rename("flooded"), "no data"

    flood_any = (ee.ImageCollection(flood_imgs)
                 .reduce(ee.Reducer.anyNonZero())
                 .rename("flooded"))
    evi_col   = ee.ImageCollection(evi_imgs)
    evi_max   = evi_col.max()
    evi_min   = evi_col.min()
    rice_confirm = (flood_any
                    .And(evi_max.gte(PEAK_MIN))
                    .And(evi_max.subtract(evi_min).gte(AMP_MIN))
                    .And(evi_min.lte(MIN_EVI_MAX))
                    .rename("flooded"))
    window_str = f"{history[0][0][:7]} to {history[-1][0][:7]}"
    return rice_confirm, window_str


def classify_evi(evi_val, evi_prev=None):
    """ระยะข้าวจาก EVI + ทิศทาง (mirror scripts/fetch_rice_evi.py)
    ค่าสูง = ออกรวง (ยอด canopy) ไม่ใช่สุกแก่ — สุกแก่ EVI ลดลง"""
    if evi_val is None:  return None
    if evi_val < 0.15:   return "fallow"
    rising = True if evi_prev is None else (evi_val - evi_prev) >= -TREND_EPS
    if evi_val < 0.25:   return "seedling" if rising else "harvest"
    if evi_val < 0.40:   return "tillering" if rising else "ripening"
    if evi_val < 0.55:   return "heading" if rising else "ripening"
    return "heading"


def main():
    init_gee()

    start, end = get_last_month_dates()
    month_label = start[:7]
    print(f"Fetching District Rice EVI: {start} → {end}")

    # ── MODIS EVI ────────────────────────────────────────────────────────────
    collection = (
        ee.ImageCollection("MODIS/061/MOD13A3")
        .filterDate(start, end)
        .select("EVI")
    )
    if collection.size().getInfo() == 0:
        prev_start = (date.fromisoformat(start).replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
        prev_end   = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        print(f"  No data for {start}–{end}, fallback to {prev_start}–{prev_end}")
        collection = (
            ee.ImageCollection("MODIS/061/MOD13A3")
            .filterDate(prev_start, prev_end)
            .select("EVI")
        )
        month_label = prev_start[:7]
        start, end  = prev_start, prev_end

    evi_img = collection.first().multiply(0.0001)

    # ── Previous-month EVI (สำหรับ trend ขึ้น/ลง) ──────────────────────────────
    prev_end_d   = date.fromisoformat(start) - timedelta(days=1)
    prev_start_d = prev_end_d.replace(day=1)
    prev_evi_img = (ee.ImageCollection("MODIS/061/MOD13A3")
                    .filterDate(prev_start_d.isoformat(), prev_end_d.isoformat())
                    .select("EVI").mosaic().multiply(0.0001))

    # ── Hybrid Mask + Phenology ───────────────────────────────────────────────
    union_mask, glad_mask, mask_source = load_rice_mask()
    exclusion_mask, excl_desc = load_exclusion_mask()
    if exclusion_mask is not None:
        union_mask = union_mask.And(exclusion_mask.Not())
        mask_source += f" − exclusion({excl_desc})"
        print(f"✓ Excluded perennial crops: {excl_desc}")
    print(f"Building rice phenology mask ({PHENOLOGY_MONTHS} months)...")
    flood_confirmation, pheno_window = build_rice_phenology_mask(start, PHENOLOGY_MONTHS)

    scan_evi      = evi_img.updateMask(union_mask)
    flood_in_scan = flood_confirmation.updateMask(union_mask)
    rice_evi      = evi_img.updateMask(flood_in_scan)       # ความเขียวเฉพาะนายืนยัน
    prev_rice     = prev_evi_img.updateMask(flood_in_scan)  # เดือนก่อน เฉพาะนายืนยัน
    _glad_src     = glad_mask if glad_mask is not None else ee.Image(0)
    glad_indicator = _glad_src.updateMask(union_mask)
    print(f"✓ Applied {mask_source} + rice phenology ({pheno_window})")

    # ── FAO GAUL 2015 level2 — Thailand districts ────────────────────────────
    districts = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )
    print("✓ Loaded FAO GAUL level2 (813 districts)")

    # ── Combined reduceRegions ────────────────────────────────────────────────
    combined_img = (
        scan_evi.rename("EVIscan")
        .addBands(rice_evi.rename("EVIrice"))
        .addBands(prev_rice.rename("EVIprev"))
        .addBands(flood_in_scan.float().rename("flooded"))
        .addBands(glad_indicator.float().rename("glad"))
    )
    result = combined_img.reduceRegions(
        collection=districts,
        reducer=(
            ee.Reducer.mean()
            .combine(reducer2=ee.Reducer.count(), sharedInputs=True)
            .combine(reducer2=ee.Reducer.sum(),   sharedInputs=True)
        ),
        scale=1000,
    )
    features = result.select(
        ["ADM1_NAME", "ADM2_NAME", "EVIrice_mean", "EVIprev_mean",
         "EVIscan_count", "flooded_sum", "glad_sum"]
    ).getInfo()["features"]
    print(f"  Got {len(features)} districts from GEE")

    # ── Build nested output ───────────────────────────────────────────────────
    provinces_data = {}
    null_districts = []

    for f in features:
        props       = f["properties"]
        prov_gaul   = props.get("ADM1_NAME", "")
        dist_name   = props.get("ADM2_NAME", "")
        evi_val     = props.get("EVIrice_mean")     # ความเขียวเฉพาะนายืนยัน
        evi_prev_v  = props.get("EVIprev_mean")
        scan_count  = int(props.get("EVIscan_count", 0) or 0)
        conf_count  = int(props.get("flooded_sum",  0) or 0)
        glad_count  = int(props.get("glad_sum",     0) or 0)

        prov_mapped = PROV_MAP.get(prov_gaul, prov_gaul)
        if prov_mapped not in provinces_data:
            provinces_data[prov_mapped] = {}

        if evi_val is not None and scan_count > 0 and conf_count > 0:
            evi_r      = round(float(evi_val), 4)
            evi_prev_r = round(float(evi_prev_v), 4) if evi_prev_v is not None else None
            trend      = round(evi_r - evi_prev_r, 4) if evi_prev_r is not None else None
            confidence = round(min(conf_count / scan_count, 1.0), 3)
            # GLAD-preferred (mirror province script): ตัด cropland-bonus ที่มากผิดปกติ
            bonus_count = max(0, conf_count - glad_count)
            if glad_count >= GLAD_MIN_PIXELS and bonus_count > GLAD_BONUS_RATIO * glad_count:
                rice_count, rice_basis = glad_count, "glad"
            else:
                rice_count, rice_basis = conf_count, "union"
            provinces_data[prov_mapped][dist_name] = {
                "evi":        evi_r,
                "evi_prev":   evi_prev_r,
                "trend":      trend,
                "stage":      classify_evi(evi_r, evi_prev_r),
                "rice_rai":   int(rice_count * 625),
                "rice_basis": rice_basis,
                "confidence": confidence,
            }
        else:
            provinces_data[prov_mapped][dist_name] = {
                "evi": None, "evi_prev": None, "trend": None,
                "stage": None, "rice_rai": 0, "rice_basis": None, "confidence": None,
            }
            null_districts.append(f"{prov_gaul}/{dist_name}")

    if null_districts:
        print(f"  ⚠️ Districts with no rice pixels: {len(null_districts)}")

    # ── Sort each province's districts by EVI descending ─────────────────────
    for prov in provinces_data:
        provinces_data[prov] = dict(
            sorted(provinces_data[prov].items(),
                   key=lambda x: (x[1]["evi"] or 0), reverse=True)
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    valid = [d for prov in provinces_data.values()
             for d in prov.values() if d["evi"] is not None]
    evi_vals = [d["evi"] for d in valid]
    total_districts = sum(len(d) for d in provinces_data.values())
    print(f"  Provinces: {len(provinces_data)} | Districts: {total_districts}")
    print(f"  EVI range: {min(evi_vals):.3f} – {max(evi_vals):.3f}")
    print(f"  EVI avg:   {sum(evi_vals)/len(evi_vals):.3f}")
    print(f"  No-data:   {len(null_districts)} districts")

    # ── Write output ──────────────────────────────────────────────────────────
    output = {
        "_meta": {
            "source":            "NASA MODIS MOD13A3 via Google Earth Engine",
            "mask":              mask_source,
            "method":            (f"Hybrid Union Mask + Rice phenology ({PHENOLOGY_MONTHS}mo: "
                                  f"flood<{FLOOD_EVI_MAX} + peak≥{PEAK_MIN} + amp≥{AMP_MIN} + minEVI≤{MIN_EVI_MAX}) · "
                                  f"EVI เฉพาะนายืนยัน · stage แยกด้วยทิศทาง EVI"),
            "regions":           "FAO GAUL 2015 level2",
            "resolution":        "1 km / monthly composite",
            "period":            f"{start} to {end}",
            "month":             month_label,
            "phenology_window":  pheno_window,
            "updated":           date.today().isoformat(),
            "provinces_covered": len(provinces_data),
            "districts_covered": total_districts,
            "districts_with_data": len(valid),
            "note":              "Rice EVI รายอำเภอ GAUL 813 อำเภอ",
        },
        "month": month_label,
        "provinces": dict(sorted(provinces_data.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "rice-evi-district.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(provinces_data)} provinces / {total_districts} districts → {out_path}")


if __name__ == "__main__":
    main()
