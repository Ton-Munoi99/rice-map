#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_rain_gsmap.py
ดึงข้อมูลฝนสะสม 7 วัน รายจังหวัด จาก JAXA GSMaP v8 Operational via Google Earth Engine
ใช้ spatial average ทั้งพื้นที่จังหวัด (ดีกว่า centroid point)

Source: JAXA/GPM_L3/GSMaP/v8/operational (Near Real-Time, ~4hr lag, ~0.1° = 11 km)
Auth:   GEE Service Account (GEE_SERVICE_ACCOUNT_KEY env var)
Output: data/rain-gsmap.json
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ee
import json
import os
from datetime import date, datetime, timedelta, timezone
from riceutils import bkk_today, init_gee, build_provinces, GAUL_NAME_MAP as NAME_MAP


COLLECTION = "JAXA/GPM_L3/GSMaP/v8/operational"
BAND       = "hourlyPrecipRate"   # mm/hr, 1-hour cadence
SCALE      = 11132                # GSMaP native resolution: 0.1° ≈ 11.132 km at equator


# ── Find latest available date in GSMaP catalog ──────────────────────────────
def get_gsmap_window(gsmap_col):
    """
    Find the most recent complete 7-day window available in GEE.
    GSMaP Operational lag: ~4 hours + GEE ingestion ~0–12 hr ≈ < 1 day total.
    Returns (start_str, end_str, dates_list) — all ISO date strings.
    end_str = exclusive upper bound for filterDate.
    """
    latest_ts = (
        gsmap_col.sort("system:time_start", False)
        .first()
        .get("system:time_start")
        .getInfo()
    )
    latest_dt = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
    end_day   = latest_dt.date()                    # most recent complete day
    start_day = end_day - timedelta(days=7)

    dates = [(start_day + timedelta(days=i)).isoformat() for i in range(7)]
    print(f"GSMaP window: {start_day} → {end_day}  (latest image: {latest_dt.strftime('%Y-%m-%d %H:%M UTC')})")
    return start_day.isoformat(), end_day.isoformat(), dates


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_gee()

    # GSMaP v8: hourlyPrecipRate band (mm/hr), 1-hour cadence
    gsmap = ee.ImageCollection(COLLECTION).select(BAND)

    start_str, end_str, dates = get_gsmap_window(gsmap)

    provinces = build_provinces()
    print(f"✓ Provinces: GAUL 76 + Bueng Kan = 77 total")

    # ── Build 7-band image: one band per day ─────────────────────────────────
    # Daily total mm = sum of 24 hourly images
    # Each image: mm/hr × 1 hr = mm per 1-hour interval → sum 24 = daily mm
    print("Building daily rainfall bands (7 bands)...")
    bands = []
    for i, day_str in enumerate(dates):
        day_end = (date.fromisoformat(day_str) + timedelta(days=1)).isoformat()
        daily_mm = (
            gsmap
            .filterDate(day_str, day_end)
            .sum()          # mm/hr × 1hr = mm; sum 24 hourly images → daily total mm
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

    # Get raw features (no .select() filter — avoids silent property name mismatches)
    features = result.getInfo()["features"]
    print(f"  Got {len(features)} provinces from GEE")

    # Debug: show actual GEE output property keys (from first feature)
    if features:
        sample = {k: v for k, v in features[0]["properties"].items() if k != "ADM1_NAME"}
        print(f"  GEE property sample: { {k: sample[k] for k in list(sample)[:4]} }")

    # ── Build output ─────────────────────────────────────────────────────────
    provinces_out = {}
    null_provinces = []

    for f in features:
        props     = f["properties"]
        gaul_name = props.get("ADM1_NAME", "")
        mapped    = NAME_MAP.get(gaul_name, gaul_name)

        values = []
        for i in range(7):
            # GEE multi-band mean reducer → try "{band}_mean" first, then "{band}"
            v = props.get(f"d{i}_mean") if props.get(f"d{i}_mean") is not None \
                else props.get(f"d{i}")
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
            "source":       "JAXA GSMaP v8 Operational via Google Earth Engine",
            "dataset":      COLLECTION,
            "resolution":   "~0.1° (11 km) — spatial average per province polygon",
            "lag_hours":    "~4",
            "period_start": start_str,
            "period_end":   end_str,
            "updated":      bkk_today(),
            "days":         7,
            "dates":        dates,
            "note": (
                f"ฝนสะสม 7 วัน (spatial average ทั้งจังหวัด) จาก JAXA GSMaP v8 Operational "
                "ผ่าน Google Earth Engine · Near Real-Time (~4 ชม.) · ดีกว่า centroid เพราะครอบคลุมทั้งพื้นที่จังหวัด"
            ),
        },
        "provinces": dict(sorted(provinces_out.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = "data/rain-gsmap.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved {len(provinces_out)} provinces → {out_path}")


if __name__ == "__main__":
    main()
