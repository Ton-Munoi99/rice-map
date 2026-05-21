#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
"""
scripts/fetch_ndvi.py
ดึงข้อมูล NDVI รายจังหวัด ประเทศไทย จาก NASA MODIS via Google Earth Engine
→ บันทึกที่ data/ndvi.json

Source: MODIS/061/MOD13A3 — Monthly NDVI Composite (1km)
Auth:   GEE Service Account (GEE_SERVICE_ACCOUNT_KEY env var)
"""
import ee
import json
import os
import sys
from datetime import date, timedelta

# ── Province name mapping: GAUL → rice-map ─────────────────────────────────
NAME_MAP = {
    # GAUL name              → rice-map name
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
    "Bung Kan":                 "Bueng Kan",
    "Changwat Bueng Kan":       "Bueng Kan",
}


def get_last_month_dates():
    """คืน (start, end) ของเดือนที่แล้ว เช่น ('2025-03-01', '2025-03-31')"""
    today = date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


def init_gee():
    """Authenticate GEE ด้วย Service Account หรือ default credentials"""
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
        # local dev: ใช้ earthengine authenticate ก่อน
        ee.Initialize(project="agriculture-monitoring-497007")
        print("✓ Authenticated via default credentials")


def main():
    init_gee()

    start, end = get_last_month_dates()
    month_label = start[:7]  # e.g. "2025-03"
    print(f"Fetching NDVI: {start} → {end}")

    # ── MODIS MOD13A3 Monthly NDVI ──────────────────────────────────────────
    collection = (
        ee.ImageCollection("MODIS/061/MOD13A3")
        .filterDate(start, end)
        .select("NDVI")
    )
    count = collection.size().getInfo()
    if count == 0:
        # fallback: เดือนก่อนหน้า (MODIS มักล่าช้า ~1 เดือน)
        prev_start = (date.fromisoformat(start).replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
        prev_end   = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        print(f"  No data for {start}–{end}, fallback to {prev_start}–{prev_end}")
        collection = (
            ee.ImageCollection("MODIS/061/MOD13A3")
            .filterDate(prev_start, prev_end)
            .select("NDVI")
        )
        month_label = prev_start[:7]
        start, end = prev_start, prev_end

    modis = collection.first().multiply(0.0001)  # scale factor

    # ── Thailand provinces (FAO GAUL 2015) ──────────────────────────────────
    provinces = (
        ee.FeatureCollection("FAO/GAUL/2015/level1")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )

    # ── Compute mean NDVI per province ──────────────────────────────────────
    result = modis.reduceRegions(
        collection=provinces,
        reducer=ee.Reducer.mean(),
        scale=1000,
    )

    features = result.select(["ADM1_NAME", "mean"]).getInfo()["features"]
    print(f"  Got {len(features)} provinces from GEE")

    # ── Build output ─────────────────────────────────────────────────────────
    provinces_data = {}
    unmapped = []
    for f in features:
        props = f["properties"]
        gaul_name = props.get("ADM1_NAME", "")
        ndvi_val  = props.get("mean")

        mapped = NAME_MAP.get(gaul_name, gaul_name)
        if gaul_name != mapped:
            pass  # remapped silently

        if ndvi_val is not None:
            provinces_data[mapped] = round(float(ndvi_val), 4)
        else:
            provinces_data[mapped] = None  # cloud cover / no data
            unmapped.append(gaul_name)

    if unmapped:
        print(f"  ⚠️  provinces with null NDVI (cloud cover?): {unmapped}")

    ndvi_vals = [v for v in provinces_data.values() if v is not None]
    print(f"  NDVI range: {min(ndvi_vals):.3f} – {max(ndvi_vals):.3f}")
    print(f"  Average:    {sum(ndvi_vals)/len(ndvi_vals):.3f}")

    output = {
        "_meta": {
            "source":     "NASA MODIS MOD13A3 via Google Earth Engine",
            "source_url": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3",
            "dataset":    "MODIS/061/MOD13A3",
            "resolution": "1 km / monthly composite",
            "period":     f"{start} to {end}",
            "month":      month_label,
            "updated":    date.today().isoformat(),
            "provinces_covered": len(provinces_data),
            "note": "ค่าเฉลี่ย NDVI รายจังหวัด คำนวณจาก MODIS Terra Vegetation Indices รายเดือน",
        },
        "month": month_label,
        "provinces": dict(sorted(provinces_data.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "ndvi.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(provinces_data)} provinces → {out_path}")


if __name__ == "__main__":
    main()
