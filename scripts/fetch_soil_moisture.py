#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_soil_moisture.py
ดึงข้อมูลความชื้นในดิน (soil moisture) รายจังหวัด ประเทศไทย จาก NASA SMAP via Google Earth Engine
→ บันทึกที่ data/soil-moisture.json

Source: NASA_USDA/HSL/SMAP10KM_soil_moisture — Daily Composite (10 km)
Band:   smp (surface moisture profile, fraction 0–1)
Auth:   GEE Service Account (GEE_SERVICE_ACCOUNT_KEY env var)
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ee
import json
import os
from datetime import date, datetime, timedelta, timezone

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

COLLECTION = "NASA_USDA/HSL/SMAP10KM_soil_moisture"
BAND       = "smp"    # surface moisture profile, fraction 0–1
SCALE      = 10000    # 10 km native resolution


# ── GEE Auth ─────────────────────────────────────────────────────────────────
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


# ── Province polygons (GAUL 76 + Bueng Kan) ──────────────────────────────────
def build_provinces():
    """สร้าง FeatureCollection จังหวัดไทย 77 จังหวัด (GAUL 76 + บึงกาฬ)"""
    gaul_provinces = (
        ee.FeatureCollection("FAO/GAUL/2015/level1")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )
    # บึงกาฬ — approximate boundary (ใช้ได้กับ SMAP 10km resolution)
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
    return gaul_provinces.merge(ee.FeatureCollection([bueng_kan_feat]))


# ── Find latest available date in SMAP catalog ───────────────────────────────
def get_smap_window(smap_col, window_days=7):
    """
    Find the most recent available date and build a rolling window.
    SMAP lag: ~2–3 days + GEE ingestion.
    Returns (start_str, end_str) — ISO date strings; end_str is inclusive.
    """
    latest_ts = (
        smap_col.sort("system:time_start", False)
        .first()
        .get("system:time_start")
        .getInfo()
    )
    latest_dt  = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
    end_day    = latest_dt.date()
    start_day  = end_day - timedelta(days=window_days - 1)
    # filterDate end is exclusive, so add 1 day
    end_exclusive = end_day + timedelta(days=1)

    print(f"SMAP window ({window_days}d): {start_day} → {end_day}  "
          f"(latest image: {latest_dt.strftime('%Y-%m-%d %H:%M UTC')})")
    return start_day.isoformat(), end_day.isoformat(), end_exclusive.isoformat()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_gee()

    # ── Build collection ─────────────────────────────────────────────────────
    smap_full = ee.ImageCollection(COLLECTION).select(BAND)

    start_str, end_str, end_exclusive = get_smap_window(smap_full, window_days=7)

    # Check how many images are in the 7-day window
    window_col = smap_full.filterDate(start_str, end_exclusive)
    img_count  = window_col.size().getInfo()
    print(f"  Images in 7-day window: {img_count}")

    if img_count == 0:
        print("  No data in 7-day window — falling back to 14 days")
        start_str, end_str, end_exclusive = get_smap_window(smap_full, window_days=14)
        window_col = smap_full.filterDate(start_str, end_exclusive)
        img_count  = window_col.size().getInfo()
        print(f"  Images in 14-day window: {img_count}")

    # Mean of window, then scale fraction 0–1 → percentage 0–100
    img = window_col.mean().multiply(100)

    # ── Province polygons ────────────────────────────────────────────────────
    provinces = build_provinces()
    print("✓ Provinces: GAUL 76 + Bueng Kan = 77 total")

    # ── Spatial average per province ─────────────────────────────────────────
    print("Running reduceRegions — spatial average over province polygons...")
    result = img.reduceRegions(
        collection=provinces,
        reducer=ee.Reducer.mean(),
        scale=SCALE,
    )

    features = result.getInfo()["features"]
    print(f"  Got {len(features)} provinces from GEE")

    # Debug: show actual GEE output property keys (from first feature)
    if features:
        sample = {k: v for k, v in features[0]["properties"].items()
                  if k not in ("ADM1_NAME", "ADM0_NAME")}
        print(f"  GEE property sample: { {k: sample[k] for k in list(sample)[:4]} }")

    # ── Build output ─────────────────────────────────────────────────────────
    provinces_data = {}
    null_provinces = []

    for f in features:
        props     = f["properties"]
        gaul_name = props.get("ADM1_NAME", "")
        mapped    = NAME_MAP.get(gaul_name, gaul_name)

        # GEE may return the reduced value as "mean", "smp_mean", or "smp"
        smp_val = props.get("mean")
        if smp_val is None:
            smp_val = props.get("smp_mean")
        if smp_val is None:
            smp_val = props.get("smp")

        if smp_val is not None:
            provinces_data[mapped] = {"smp": round(float(smp_val), 1)}
        else:
            provinces_data[mapped] = {"smp": None}
            null_provinces.append(gaul_name)

    if null_provinces:
        print(f"  ⚠️  provinces with null smp (no coverage?): {null_provinces}")

    smp_vals = [v["smp"] for v in provinces_data.values() if v["smp"] is not None]
    if smp_vals:
        print(f"  Province count: {len(smp_vals)} with data, {len(null_provinces)} null")
        print(f"  smp range: {min(smp_vals):.1f}% – {max(smp_vals):.1f}%")
        print(f"  smp avg:   {sum(smp_vals)/len(smp_vals):.1f}%")

    output = {
        "_meta": {
            "source":      "NASA SMAP 10km via Google Earth Engine",
            "dataset":     COLLECTION,
            "band":        BAND,
            "unit":        "% (surface moisture profile × 100)",
            "resolution":  "10 km — spatial average per province polygon",
            "period_start": start_str,
            "period_end":   end_str,
            "updated":      date.today().isoformat(),
            "note": "ความชื้นในดินระดับผิว — 0% = แห้งสนิท, 100% = อิ่มตัว",
        },
        "provinces": dict(sorted(provinces_data.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = "data/soil-moisture.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved {len(provinces_data)} provinces → {out_path}")


if __name__ == "__main__":
    main()
