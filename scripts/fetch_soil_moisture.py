#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_soil_moisture.py
ดึงข้อมูลความชื้นในดิน (soil moisture) รายจังหวัด ประเทศไทย จาก NASA SMAP via Google Earth Engine
→ บันทึกที่ data/soil-moisture.json

Dataset: NASA/SMAP/SPL4SMGP/008 (SMAP L4 Global Daily)
Band:    sm_surface_wetness — relative wetness vs field capacity (0–1) × 100 = %
         เป็น product ที่ NASA/USDA ใช้ติดตามสภาพพืชผลทั่วโลก
         ครอบคลุม 77/77 จังหวัด ไม่มี null แม้แต่จังหวัดเมือง/ภูเขา/ชายฝั่ง
Auth:    GEE Service Account (GEE_SERVICE_ACCOUNT_KEY env var)
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ee
import json
import os
from datetime import date, datetime, timedelta, timezone
from riceutils import init_gee, build_provinces, GAUL_NAME_MAP as NAME_MAP

COLLECTION = "NASA/SMAP/SPL4SMGP/008"
BAND       = "sm_surface_wetness"  # relative wetness vs field capacity, 0–1
SCALE      = 11000                 # 11 km native resolution


# ── Find latest available window ──────────────────────────────────────────────
def get_window(col, window_days=7):
    latest_ts = (
        col.sort("system:time_start", False)
        .first()
        .get("system:time_start")
        .getInfo()
    )
    latest_dt     = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
    end_day       = latest_dt.date()
    start_day     = end_day - timedelta(days=window_days - 1)
    end_exclusive = end_day + timedelta(days=1)
    print(f"  Window ({window_days}d): {start_day} → {end_day} "
          f"(latest image: {latest_dt.strftime('%Y-%m-%d')})")
    return start_day.isoformat(), end_day.isoformat(), end_exclusive.isoformat()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_gee()
    provinces = build_provinces()
    print("✓ Provinces: GAUL 76 + Bueng Kan = 77 total")

    # ── Build 7-day mean image ────────────────────────────────────────────────
    print(f"\n[SMAP L4] {COLLECTION}")
    smap_col = ee.ImageCollection(COLLECTION).select([BAND])
    start_str, end_str, end_exc = get_window(smap_col, window_days=7)

    window = smap_col.filterDate(start_str, end_exc)
    n_img  = window.size().getInfo()
    print(f"  Images in 7-day window: {n_img}")

    if n_img == 0:
        print("  No data — falling back to 14-day window")
        start_str, end_str, end_exc = get_window(smap_col, window_days=14)
        window = smap_col.filterDate(start_str, end_exc)

    # Mean over window → rename → scale 0–100 → clamp
    img = window.mean().rename("sm").multiply(100).clamp(0, 100)

    # ── Spatial average per province ─────────────────────────────────────────
    print("  Running reduceRegions...")
    result   = img.reduceRegions(
        collection=provinces,
        reducer=ee.Reducer.mean(),
        scale=SCALE,
    )
    features = result.getInfo()["features"]
    print(f"  Got {len(features)} provinces from GEE")

    # ── Build output ──────────────────────────────────────────────────────────
    provinces_data = {}
    null_list = []

    for f in features:
        props     = f["properties"]
        gaul_name = props.get("ADM1_NAME", "")
        mapped    = NAME_MAP.get(gaul_name, gaul_name)
        val = props.get("mean") or props.get("sm_mean")

        if val is not None:
            provinces_data[mapped] = {"smp": round(float(val), 1)}
        else:
            provinces_data[mapped] = {"smp": None}
            null_list.append(gaul_name)

    smp_vals = [v["smp"] for v in provinces_data.values() if v["smp"] is not None]
    print(f"  Provinces with data: {len(smp_vals)}/77"
          + (f" · null: {null_list}" if null_list else " · no nulls ✓"))
    if smp_vals:
        print(f"  Range: {min(smp_vals):.1f}% – {max(smp_vals):.1f}%"
              f" · Avg: {sum(smp_vals)/len(smp_vals):.1f}%")

    # ── Save ──────────────────────────────────────────────────────────────────
    output = {
        "_meta": {
            "source":       "NASA SMAP L4 via Google Earth Engine",
            "dataset":      COLLECTION,
            "band":         f"{BAND} (relative wetness vs field capacity)",
            "unit":         "% ความชุ่มชื้น เทียบกับ field capacity (0% = แห้ง, 100% = อิ่มตัว)",
            "resolution":   "11 km — spatial average per province polygon",
            "period_start": start_str,
            "period_end":   end_str,
            "updated":      date.today().isoformat(),
            "note":         "ความชื้นในดินระดับผิว — 0% = แห้งสนิท, 100% = อิ่มตัว",
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
