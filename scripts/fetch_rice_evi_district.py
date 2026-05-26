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
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import calendar
import ee
import json
import os
from datetime import date, timedelta

# ── Province name mapping: GAUL → rice-map ───────────────────────────────────
PROV_MAP = {
    "Bangkok":                  "Bangkok Metropolis",
    "Buriram":                  "Buri Ram",
    "Chainat":                  "Chai Nat",
    "Chonburi":                 "Chon Buri",
    "Kampaeng Phet":            "Kamphaeng Phet",
    "Lopburi":                  "Lop Buri",
    "Nong Bua Lamphu":          "Nong Bua Lam Phu",
    "Phachinburi":              "Prachin Buri",
    "Phra Nakhon Si Ayudhya":   "Phra Nakhon Si Ayutthaya",
    "Prachuap Khilikhan":       "Prachuap Khiri Khan",
    "Samut Prakarn":            "Samut Prakan",
    "Samut Songkham":           "Samut Songkhram",
    "Si Saket":                 "Si Sa Ket",
    "Sisaket":                  "Si Sa Ket",
    "Singburi":                 "Sing Buri",
    "Suphanburi":               "Suphan Buri",
    "Trad":                     "Trat",
}

PHENOLOGY_MONTHS = 12


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


def init_gee():
    key_data = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    if key_data:
        key_dict = json.loads(key_data)
        credentials = ee.ServiceAccountCredentials(
            email=key_dict["client_email"],
            key_data=key_dict["private_key"],
        )
        ee.Initialize(credentials, project="agriculture-monitoring-497007")
        print("✓ Authenticated via Service Account")
    else:
        ee.Initialize(project="agriculture-monitoring-497007")
        print("✓ Authenticated via default credentials")


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


def build_flood_confirmation(current_start, n_months=12):
    history = get_history_months(current_start, n_months)
    flood_imgs = []
    for s, e in history:
        col = (ee.ImageCollection("MODIS/061/MOD13A3")
               .filterDate(s, e)
               .select(["EVI", "sur_refl_b02", "sur_refl_b07"]))
        if col.size().getInfo() == 0:
            continue
        img  = col.first().multiply(0.0001)
        evi  = img.select("EVI")
        nir  = img.select("sur_refl_b02")
        swir = img.select("sur_refl_b07")
        lswi = nir.subtract(swir).divide(nir.add(swir))
        flood_imgs.append(lswi.gt(evi).rename("flooded"))

    if not flood_imgs:
        return ee.Image(0).rename("flooded"), "no data"

    flood_any = (ee.ImageCollection(flood_imgs)
                 .reduce(ee.Reducer.anyNonZero())
                 .rename("flooded"))
    window_str = f"{history[0][0][:7]} to {history[-1][0][:7]}"
    return flood_any, window_str


def classify_evi(evi_val):
    if evi_val is None:  return None
    if evi_val < 0.15:   return "fallow"
    if evi_val < 0.25:   return "early"
    if evi_val < 0.40:   return "growing"
    if evi_val < 0.55:   return "heading"
    return "peak"


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

    # ── Hybrid Mask + Phenology ───────────────────────────────────────────────
    union_mask, glad_mask, mask_source = load_rice_mask()
    print(f"Building phenology mask ({PHENOLOGY_MONTHS} months)...")
    flood_confirmation, pheno_window = build_flood_confirmation(start, PHENOLOGY_MONTHS)

    scan_evi      = evi_img.updateMask(union_mask)
    flood_in_scan = flood_confirmation.updateMask(union_mask)
    _glad_src     = glad_mask if glad_mask is not None else ee.Image(0)
    glad_indicator = _glad_src.updateMask(union_mask)
    print(f"✓ Applied {mask_source} + phenology ({pheno_window})")

    # ── FAO GAUL 2015 level2 — Thailand districts ────────────────────────────
    districts = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )
    print("✓ Loaded FAO GAUL level2 (813 districts)")

    # ── Combined reduceRegions ────────────────────────────────────────────────
    combined_img = (
        scan_evi.rename("EVI")
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
        ["ADM1_NAME", "ADM2_NAME", "EVI_mean", "EVI_count", "flooded_sum", "glad_sum"]
    ).getInfo()["features"]
    print(f"  Got {len(features)} districts from GEE")

    # ── Build nested output ───────────────────────────────────────────────────
    provinces_data = {}
    null_districts = []

    for f in features:
        props       = f["properties"]
        prov_gaul   = props.get("ADM1_NAME", "")
        dist_name   = props.get("ADM2_NAME", "")
        evi_val     = props.get("EVI_mean")
        scan_count  = int(props.get("EVI_count",    0) or 0)
        conf_count  = int(props.get("flooded_sum",  0) or 0)

        prov_mapped = PROV_MAP.get(prov_gaul, prov_gaul)
        if prov_mapped not in provinces_data:
            provinces_data[prov_mapped] = {}

        if evi_val is not None and scan_count > 0:
            evi_r      = round(float(evi_val), 4)
            confidence = round(min(conf_count / scan_count, 1.0), 3)
            rice_rai   = int(conf_count * 625)
            provinces_data[prov_mapped][dist_name] = {
                "evi":        evi_r,
                "stage":      classify_evi(evi_r),
                "rice_rai":   rice_rai,
                "confidence": confidence,
            }
        else:
            provinces_data[prov_mapped][dist_name] = {
                "evi": None, "stage": None, "rice_rai": 0, "confidence": None,
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
            "method":            f"Hybrid Union Mask + Phenology ({PHENOLOGY_MONTHS}mo LSWI>EVI)",
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
