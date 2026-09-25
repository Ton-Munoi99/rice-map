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
EXPECTED_PROVINCES = 77


MIN_IMAGES_PER_DAY = 24   # ภาพรายชั่วโมง — วันที่ได้ไม่ครบ 24 ภาพคือวันที่ยังไม่ครบ ฝนจะออกมาต่ำเกินจริง
MAX_SHIFT_DAYS = 3        # ถอยหน้าต่างหาวันที่ครบได้ไม่เกินเท่านี้ ก่อนจะยอมเก็บไฟล์เดิมไว้


def window_dates(end_day):
    """7 วันก่อน end_day (end_day เองไม่นับ เพราะเป็นวันที่ภาพล่าสุดยังเข้าไม่ครบ)"""
    start_day = end_day - timedelta(days=7)
    return [(start_day + timedelta(days=i)).isoformat() for i in range(7)]


def pick_complete_window(end_day, count_images):
    """ถอยหน้าต่างทีละวันจนทุกวันมีภาพครบ — คืน (dates, counts) หรือ (None, counts ล่าสุด)"""
    counts = []
    for shift in range(MAX_SHIFT_DAYS + 1):
        dates = window_dates(end_day - timedelta(days=shift))
        counts = count_images(dates)
        if all(c >= MIN_IMAGES_PER_DAY for c in counts):
            if shift:
                print(f"  ⚠️ ถอยหน้าต่าง {shift} วัน — วันล่าสุดภาพยังเข้าไม่ครบ")
            return dates, counts
        print(f"  ภาพต่อวัน {dict(zip(dates, counts))} — ยังไม่ครบ {MIN_IMAGES_PER_DAY}")
    return None, counts


def latest_image_day(gsmap_col):
    latest_ts = (
        gsmap_col.sort("system:time_start", False)
        .first()
        .get("system:time_start")
        .getInfo()
    )
    latest_dt = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
    print(f"GSMaP latest image: {latest_dt.strftime('%Y-%m-%d %H:%M UTC')}")
    return latest_dt.date()


def province_values(props):
    """ค่าฝนรายวัน 7 ค่าของจังหวัดหนึ่ง — None ถ้าวันนั้นไม่มีค่า (ห้ามแปลงเป็น 0 มม.)"""
    values = []
    for i in range(7):
        # GEE multi-band mean reducer → try "{band}_mean" first, then "{band}"
        v = props.get(f"d{i}_mean")
        if v is None:
            v = props.get(f"d{i}")
        values.append(round(float(v), 1) if v is not None else None)
    return values


def _selftest():
    end = date(2026, 9, 23)
    assert window_dates(end) == [f"2026-09-{d}" for d in range(16, 23)]
    # ครบทุกวัน → ใช้หน้าต่างเดิม
    ds, cs = pick_complete_window(end, lambda ds: [24] * 7)
    assert ds[-1] == "2026-09-22" and cs == [24] * 7
    # วันล่าสุดขาดภาพ → ถอยหนึ่งวัน
    calls = []
    def partial_last(ds):
        calls.append(ds[-1])
        return [24] * 6 + [18 if ds[-1] == "2026-09-22" else 24]
    ds, _ = pick_complete_window(end, partial_last)
    assert ds[-1] == "2026-09-21" and calls == ["2026-09-22", "2026-09-21"]
    # ไม่ครบเลย → None (เก็บไฟล์เดิม) และถอยไม่เกิน MAX_SHIFT_DAYS
    calls.clear()
    ds, _ = pick_complete_window(end, lambda ds: calls.append(1) or [24] * 6 + [0])
    assert ds is None and len(calls) == MAX_SHIFT_DAYS + 1
    # ค่าที่หายต้องเป็น None ไม่ใช่ 0 มม. — ส่วน 0.0 ที่มีจริงต้องคงเป็น 0.0
    props = {f"d{i}": 1.25 for i in range(7)}
    props["d3"] = 0.0
    assert province_values(props) == [1.2, 1.2, 1.2, 0.0, 1.2, 1.2, 1.2]
    del props["d5"]
    assert province_values(props)[5] is None
    assert province_values({"d0_mean": 2.0, **{f"d{i}": 1 for i in range(1, 7)}})[0] == 2.0
    print("selftest ok")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if "--selftest" in sys.argv:
        _selftest()
        return
    init_gee()

    # GSMaP v8: hourlyPrecipRate band (mm/hr), 1-hour cadence
    gsmap = ee.ImageCollection(COLLECTION).select(BAND)

    def count_images(ds):
        return ee.List([
            gsmap.filterDate(d, (date.fromisoformat(d) + timedelta(days=1)).isoformat()).size()
            for d in ds
        ]).getInfo()

    dates, counts = pick_complete_window(latest_image_day(gsmap), count_images)
    if dates is None:
        # คงไฟล์เดิมไว้ และไม่ exit 1 — ขั้นถัดไปของ workflow (พยากรณ์/คำเตือน) ยังต้องรันต่อ
        print("::warning::GSMaP ยังมีภาพไม่ครบทุกวันในหน้าต่าง — ไม่เขียนทับ rain-gsmap.json เดิม")
        return
    start_str = dates[0]
    end_str = (date.fromisoformat(dates[-1]) + timedelta(days=1)).isoformat()
    print(f"GSMaP window: {dates[0]} → {dates[-1]}  (images/day: {counts})")

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

    missing = []
    for f in features:
        props     = f["properties"]
        gaul_name = props.get("ADM1_NAME", "")
        mapped    = NAME_MAP.get(gaul_name, gaul_name)

        values = province_values(props)
        if any(v is None for v in values):
            missing.append(mapped)
            continue

        rain_7d = round(sum(values), 1)
        provinces_out[mapped] = {
            "rain_7d": rain_7d,
            "values":  values,
        }
        print(f"  ✓ {mapped}: {rain_7d} mm")

        if rain_7d == 0.0:
            null_provinces.append(mapped)

    if missing or len(provinces_out) < EXPECTED_PROVINCES:
        # เดิมค่าที่หายกลายเป็น 0 มม. — ทำให้ขึ้นเตือนแล้งผิด และกดค่า bias ของ scoreboard
        # ที่ปรับเกณฑ์เตือนน้ำท่วม จึงเก็บไฟล์เดิมไว้แทนการเขียนข้อมูลไม่ครบทับ
        print(f"::warning::GSMaP ไม่มีค่าบางวันใน {len(missing)} จังหวัด ({', '.join(missing[:10])}) "
              f"ได้ครบ {len(provinces_out)}/{EXPECTED_PROVINCES} — ไม่เขียนทับ rain-gsmap.json เดิม")
        return

    if null_provinces:
        print(f"  ℹ️  ฝน 0 มม. ทั้ง 7 วัน (ภาพครบ ค่าจริง): {', '.join(null_provinces)}")

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
            "images_per_day": counts,
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
