#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_ndvi.py
ดึงข้อมูล NDVI รายจังหวัด ประเทศไทย จาก NASA MODIS via Google Earth Engine
→ บันทึกที่ data/ndvi.json

Source: MODIS/061/MOD13A3 — Monthly NDVI Composite (1km)
Auth:   GEE Service Account (GEE_SERVICE_ACCOUNT_KEY env var)
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ee
import json
import os
from datetime import date, timedelta
from riceutils import init_gee, GAUL_NAME_MAP as NAME_MAP


def get_last_month_dates():
    """คืน (start, end) ของเดือนที่แล้ว เช่น ('2025-03-01', '2025-03-31')"""
    today = date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


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

    # ── Thailand provinces (FAO GAUL 2015 + Bueng Kan supplement) ──────────
    # FAO GAUL 2015 มีแค่ 76 จังหวัด — ไม่มีบึงกาฬ (แยกจากหนองคายปี 2554)
    gaul_provinces = (
        ee.FeatureCollection("FAO/GAUL/2015/level1")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )

    # บึงกาฬ — approximate boundary (ใช้ได้กับ MODIS 1km resolution)
    # พิกัดจาก GADM 4.1 / OpenStreetMap boundary (ตัดทอนให้กระชับ)
    bueng_kan_poly = ee.Geometry.Polygon([[
        [103.378, 17.979], [103.380, 18.121], [103.416, 18.215],
        [103.453, 18.319], [103.498, 18.416], [103.558, 18.502],
        [103.594, 18.582], [103.640, 18.643], [103.723, 18.693],
        [103.810, 18.681], [103.875, 18.640], [103.952, 18.620],
        [104.030, 18.598], [104.113, 18.562], [104.193, 18.507],
        [104.230, 18.438], [104.218, 18.350], [104.170, 18.263],
        [104.082, 18.210], [103.990, 18.174], [103.900, 18.110],
        [103.840, 18.035], [103.760, 17.970], [103.680, 17.952],
        [103.590, 17.960], [103.500, 17.960], [103.420, 17.970],
        [103.378, 17.979],
    ]])
    bueng_kan_feat = ee.Feature(bueng_kan_poly, {
        "ADM1_NAME": "Bung Kan",
        "ADM0_NAME": "Thailand",
    })
    provinces = gaul_provinces.merge(ee.FeatureCollection([bueng_kan_feat]))
    print("✓ Provinces: GAUL 76 + Bueng Kan = 77 total")

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
