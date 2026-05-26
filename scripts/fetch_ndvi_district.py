#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_ndvi_district.py
ดึงค่า NDVI เฉลี่ยรายอำเภอ ประเทศไทย จาก NASA MODIS via Google Earth Engine

Source:  MODIS/061/MOD13A3 — Monthly NDVI Composite (1km)
Regions: FAO GAUL 2015 level2 (813 อำเภอ)
Output:  data/ndvi-district.json
Format:  { provinces: { "Chiang Mai": { "Mueang Chiang Mai": 0.523, ... } } }
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ee
import json
import os
from datetime import date, timedelta

# ── Province name mapping: GAUL → rice-map (same as province scripts) ───────
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


def get_last_month_dates():
    today = date.today()
    first_this = today.replace(day=1)
    last_prev  = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


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


def main():
    init_gee()

    start, end = get_last_month_dates()
    month_label = start[:7]
    print(f"Fetching District NDVI: {start} → {end}")

    # ── MODIS MOD13A3 Monthly NDVI ──────────────────────────────────────────
    collection = (
        ee.ImageCollection("MODIS/061/MOD13A3")
        .filterDate(start, end)
        .select("NDVI")
    )
    count = collection.size().getInfo()
    if count == 0:
        prev_start = (date.fromisoformat(start).replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
        prev_end   = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        print(f"  No data for {start}–{end}, fallback to {prev_start}–{prev_end}")
        collection = (
            ee.ImageCollection("MODIS/061/MOD13A3")
            .filterDate(prev_start, prev_end)
            .select("NDVI")
        )
        month_label = prev_start[:7]
        start, end  = prev_start, prev_end

    ndvi_img = collection.first().multiply(0.0001)

    # ── FAO GAUL 2015 level2 — Thailand districts (813 features) ───────────
    districts = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )
    print("✓ Loaded FAO GAUL level2 (813 districts)")

    # ── Mean NDVI per district ───────────────────────────────────────────────
    result = ndvi_img.reduceRegions(
        collection=districts,
        reducer=ee.Reducer.mean(),
        scale=1000,
    )

    features = result.select(["ADM1_NAME", "ADM2_NAME", "mean"]).getInfo()["features"]
    print(f"  Got {len(features)} districts from GEE")

    # ── Build nested output: province → district → ndvi ─────────────────────
    provinces_data = {}
    null_districts = []

    for f in features:
        props      = f["properties"]
        prov_gaul  = props.get("ADM1_NAME", "")
        dist_name  = props.get("ADM2_NAME", "")
        ndvi_val   = props.get("mean")

        prov_mapped = PROV_MAP.get(prov_gaul, prov_gaul)

        if prov_mapped not in provinces_data:
            provinces_data[prov_mapped] = {}

        if ndvi_val is not None:
            provinces_data[prov_mapped][dist_name] = round(float(ndvi_val), 4)
        else:
            provinces_data[prov_mapped][dist_name] = None
            null_districts.append(f"{prov_gaul}/{dist_name}")

    if null_districts:
        print(f"  ⚠️ Districts with null NDVI: {null_districts[:10]}{'...' if len(null_districts)>10 else ''}")

    # ── Summary stats ────────────────────────────────────────────────────────
    all_vals = [v for prov in provinces_data.values() for v in prov.values() if v is not None]
    total_districts = sum(len(d) for d in provinces_data.values())
    print(f"  Provinces: {len(provinces_data)}")
    print(f"  Districts: {total_districts}")
    print(f"  NDVI range:  {min(all_vals):.3f} – {max(all_vals):.3f}")
    print(f"  NDVI avg:    {sum(all_vals)/len(all_vals):.3f}")

    # ── Sort districts within each province by NDVI descending ──────────────
    for prov in provinces_data:
        provinces_data[prov] = dict(
            sorted(provinces_data[prov].items(),
                   key=lambda x: (x[1] or 0), reverse=True)
        )

    # ── Write output ─────────────────────────────────────────────────────────
    output = {
        "_meta": {
            "source":            "NASA MODIS MOD13A3 via Google Earth Engine",
            "dataset":           "MODIS/061/MOD13A3",
            "regions":           "FAO GAUL 2015 level2",
            "resolution":        "1 km / monthly composite",
            "period":            f"{start} to {end}",
            "month":             month_label,
            "updated":           date.today().isoformat(),
            "provinces_covered": len(provinces_data),
            "districts_covered": total_districts,
            "note":              "ค่าเฉลี่ย NDVI รายอำเภอ GAUL 813 อำเภอ (ไม่รวมบึงกาฬ)",
        },
        "month": month_label,
        "provinces": dict(sorted(provinces_data.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "ndvi-district.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(provinces_data)} provinces / {total_districts} districts → {out_path}")


if __name__ == "__main__":
    main()
