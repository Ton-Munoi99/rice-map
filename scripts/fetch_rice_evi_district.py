#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_rice_evi_district.py
ดึงข้อมูล Rice EVI รายอำเภอ ประเทศไทย จาก MODIS + Hybrid Mask + Phenology

Source:  MODIS/061/MOD13Q1 — 16-day EVI (250m) · mask/phenology: MOD13A3 monthly (1km)
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
from riceutils import bkk_today, init_gee, GAUL_NAME_MAP as PROV_MAP
from riceutils import PHENOLOGY_MONTHS, FLOOD_EVI_MAX, PEAK_MIN, AMP_MIN, MIN_EVI_MAX, RUBBER_ASSET, load_rice_mask, load_exclusion_mask, get_history_months, build_rice_phenology_mask, latest_q1_periods, q1_evi_image
from rice_stage import TREND_EPS, classify_evi


# classify_evi ย้ายไป rice_stage.py (ใช้ร่วมกับสคริปต์ระดับจังหวัด)
def main():
    init_gee()

    # ── MOD13Q1 composite ราย 16 วัน ล่าสุด — ตรงกับสคริปต์ระดับจังหวัด ──────
    periods = latest_q1_periods(n=4)
    if not periods:
        raise RuntimeError("ไม่พบ composite MOD13Q1 ในช่วง 80 วันล่าสุด")
    # รวม 2 composite (~32 วัน) เพื่ออุดรูที่เมฆบัง — ครอบคลุมกลับมาใกล้รายเดือน
    start, end = periods[1][0], periods[0][1]
    month_label = start[:7]
    print(f"Fetching District Rice EVI (MOD13Q1 16-day): {start} → {end}")
    evi_img = q1_evi_image(start, end)

    # ── EVI ของ composite ก่อนหน้า (trend ขึ้น/ลง) ───────────────────────────
    if len(periods) > 3:
        prev_evi_img = q1_evi_image(periods[3][0], periods[2][1])
        print(f"  Previous window for trend: {periods[3][0]} → {periods[2][1]}")
    else:
        prev_evi_img = evi_img.updateMask(ee.Image(0))
        print("  ไม่มี composite ก่อนหน้า → trend = None")

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
            # ถอดกฎ GLAD-preferred ตามสคริปต์ระดับจังหวัด (ดูเหตุผลที่นั่น)
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
            "updated":           bkk_today(),
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
