#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_rain_imerg.py
ดึงข้อมูลฝนสะสม 7 วัน รายจังหวัด จาก NASA GPM IMERG V07 via Google Earth Engine
ใช้ spatial average ทั้งพื้นที่จังหวัด (ดีกว่า centroid point)

Source: NASA/GPM_L3/IMERG_V07 (Late Run, ~0.1° = 11 km)
Auth:   GEE Service Account (GEE_SERVICE_ACCOUNT_KEY env var)
Output: data/rain-imerg.json
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

SCALE = 11132   # IMERG native resolution: 0.1° ≈ 11.132 km at equator


# ── GEE Auth (same pattern as fetch_ndvi.py) ────────────────────────────────
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


# ── Province polygons (same as fetch_ndvi.py: GAUL 76 + Bueng Kan) ──────────
def build_provinces():
    gaul_provinces = (
        ee.FeatureCollection("FAO/GAUL/2015/level1")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )
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


# ── Find latest available date in IMERG catalog ──────────────────────────────
def get_imerg_window(imerg_col):
    """
    Find the most recent complete 7-day window available in GEE.
    IMERG Late Run lag: ~14 hr + GEE ingestion ~1–3 days = ~2–4 day total lag.
    Returns (start_str, end_str, dates_list) — all ISO date strings.
    end_str = exclusive upper bound for filterDate.
    """
    latest_ts = (
        imerg_col.sort("system:time_start", False)
        .first()
        .get("system:time_start")
        .getInfo()
    )
    latest_dt = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
    end_day   = latest_dt.date()                    # most recent complete day
    start_day = end_day - timedelta(days=7)

    dates = [(start_day + timedelta(days=i)).isoformat() for i in range(7)]
    print(f"IMERG window: {start_day} → {end_day}  (latest image: {latest_dt.strftime('%Y-%m-%d %H:%M UTC')})")
    return start_day.isoformat(), end_day.isoformat(), dates


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_gee()

    # IMERG V07: precipitation band (mm/hr), 30-minute cadence
    imerg = ee.ImageCollection("NASA/GPM_L3/IMERG_V07").select("precipitation")

    start_str, end_str, dates = get_imerg_window(imerg)

    provinces = build_provinces()
    print(f"✓ Provinces: GAUL 76 + Bueng Kan = 77 total")

    # ── Build 7-band image: one band per day ─────────────────────────────────
    # Daily total mm = sum of 48 half-hourly images × 0.5 hr
    # Each image: mm/hr × 0.5 hr = mm per 30-min interval
    print("Building daily rainfall bands (7 bands)...")
    bands = []
    for i, day_str in enumerate(dates):
        day_end = (date.fromisoformat(day_str) + timedelta(days=1)).isoformat()
        daily_mm = (
            imerg
            .filterDate(day_str, day_end)
            .map(lambda img: img.multiply(0.5))   # mm/hr → mm per 30-min
            .sum()
            .rename(f"d{i}")
        )
        bands.append(daily_mm)
        print(f"  d{i}: {day_str}")

    # Stack 7 bands into one image → one reduceRegions call for all data
    stacked = bands[0]
    for b in bands[1:]:
        stacked = stacked.addBands(b)

    # ── Spatial average per province (one GEE server call) ───────────────────
    print("Running reduceRegions — spatial average over province polygons...")
    result = stacked.reduceRegions(
        collection=provinces,
        reducer=ee.Reducer.mean(),
        scale=SCALE,
    )

    select_props = ["ADM1_NAME"] + [f"d{i}_mean" for i in range(7)]
    features = result.select(select_props).getInfo()["features"]
    print(f"  Got {len(features)} provinces from GEE")

    # ── Build output ─────────────────────────────────────────────────────────
    provinces_out = {}
    null_provinces = []

    for f in features:
        props     = f["properties"]
        gaul_name = props.get("ADM1_NAME", "")
        mapped    = NAME_MAP.get(gaul_name, gaul_name)

        values = []
        for i in range(7):
            v = props.get(f"d{i}_mean")
            values.append(round(float(v), 1) if v is not None else 0.0)

        rain_7d = round(sum(values), 1)
        provinces_out[mapped] = {
            "rain_7d": rain_7d,
            "values":  values,
        }
        print(f"  ✓ {mapped}: {rain_7d} mm")

        if rain_7d == 0.0 and all(v == 0.0 for v in values):
            null_provinces.append(mapped)

    if null_provinces:
        print(f"  ⚠️  All-zero provinces (no data?): {', '.join(null_provinces)}")

    ok_vals = [v["rain_7d"] for v in provinces_out.values() if v["rain_7d"] > 0]
    if ok_vals:
        print(f"  Range: {min(ok_vals):.1f} – {max(ok_vals):.1f} mm  |  Avg: {sum(ok_vals)/len(ok_vals):.1f} mm")

    output = {
        "_meta": {
            "source":       "NASA GPM IMERG V07 (Late Run) via Google Earth Engine",
            "dataset":      "NASA/GPM_L3/IMERG_V07",
            "resolution":   "~0.1° (11 km) — spatial average per province polygon",
            "period_start": start_str,
            "period_end":   end_str,
            "updated":      date.today().isoformat(),
            "days":         7,
            "dates":        dates,
            "note": (
                f"ฝนสะสม 7 วัน (spatial average ทั้งจังหวัด) จาก NASA GPM IMERG V07 "
                "Late Run ผ่าน Google Earth Engine · แม่นกว่า centroid เพราะครอบคลุมทั้งพื้นที่จังหวัด"
            ),
        },
        "provinces": dict(sorted(provinces_out.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = "data/rain-imerg.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved {len(provinces_out)} provinces → {out_path}")


if __name__ == "__main__":
    main()
