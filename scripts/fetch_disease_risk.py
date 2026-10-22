#!/usr/bin/env python3
"""
Fetch 7-day weather data per province from Open-Meteo (free, no API key) and
compute disease/pest risk indicators for rice.

Runs daily via GitHub Actions.

Disease risk thresholds (published scientific literature):
  Rice Blast        — temp_min < 22°C  AND rh_mean > 80%  AND precip_hours >= 1
  Brown Planthopper — 25 <= temp_max <= 30°C  AND rh_mean > 80%
  Sheath Blight     — temp_max > 30°C  AND rh_mean > 85%  AND precip_hours >= 1
  Strong Wind       — wind_max > 30 km/h  (Bacterial Blight proxy)

Output: data/disease-risk.json
"""
import json, os, sys, time
from riceutils import bkk_today, load_centroids, open_meteo

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DAYS       = 7           # 6 past days + today = 7 total
OUTPUT     = "data/disease-risk.json"
API_URL    = "https://api.open-meteo.com/v1/forecast"
BATCH_SIZE = 40          # provinces per request (2 requests for 77 provinces)
DAILY      = "temperature_2m_min,temperature_2m_max,relative_humidity_2m_mean,wind_speed_10m_max,precipitation_hours"


# ── Compute risk day-counts for one province ─────────────────────────────────
def compute_risk(daily):
    """Return dict of risk day counts from Open-Meteo daily data."""
    temp_min_arr    = daily.get("temperature_2m_min", [])
    temp_max_arr    = daily.get("temperature_2m_max", [])
    rh_arr          = daily.get("relative_humidity_2m_mean", [])
    wind_arr        = daily.get("wind_speed_10m_max", [])
    precip_hrs_arr  = daily.get("precipitation_hours", [])

    n = min(
        len(temp_min_arr), len(temp_max_arr), len(rh_arr),
        len(wind_arr), len(precip_hrs_arr), DAYS,
    )

    days_blast      = 0
    days_bph        = 0
    days_sheath     = 0
    days_strong_wind = 0

    for i in range(n):
        tmin   = temp_min_arr[i]
        tmax   = temp_max_arr[i]
        rh     = rh_arr[i]
        wind   = wind_arr[i]
        ph     = precip_hrs_arr[i]

        # Rice Blast: temp_min < 22 AND rh > 80 AND precip_hours >= 1
        if tmin is not None and rh is not None and ph is not None:
            if tmin < 22 and rh > 80 and ph >= 1:
                days_blast += 1

        # Brown Planthopper: 25 <= temp_max <= 30 AND rh > 80
        if tmax is not None and rh is not None:
            if 25 <= tmax <= 30 and rh > 80:
                days_bph += 1

        # Sheath Blight: temp_max > 30 AND rh > 85 AND precip_hours >= 1
        if tmax is not None and rh is not None and ph is not None:
            if tmax > 30 and rh > 85 and ph >= 1:
                days_sheath += 1

        # Strong Wind: wind_max > 30 km/h
        if wind is not None:
            if wind > 30:
                days_strong_wind += 1

    return {
        "days_blast":       days_blast,
        "days_bph":         days_bph,
        "days_sheath":      days_sheath,
        "days_strong_wind": days_strong_wind,
    }


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    centroids = load_centroids()
    today     = bkk_today()
    names     = sorted(centroids.keys())

    provinces_out = {}
    period_start  = None
    period_end    = None
    errors        = []

    total_batches = (len(names) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Fetching weather data for {len(names)} provinces in {total_batches} batch(es) of ≤{BATCH_SIZE} ...")

    for i in range(0, len(names), BATCH_SIZE):
        batch = names[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"\nBatch {batch_num}/{total_batches}: {batch[0]} … {batch[-1]} ({len(batch)} provinces)")

        try:
            data = open_meteo(API_URL, [centroids[n] for n in batch], daily=DAILY,
                              past_days=DAYS - 1, forecast_days=1)   # 6 วันที่ผ่านมา + วันนี้
            for j, name in enumerate(batch):
                daily = data[j]["daily"]
                times = daily.get("time", [])
                if not times:
                    # ไม่มีข้อมูล ≠ ไม่เสี่ยง — ห้ามเขียน 0 เพราะการ์ดจะขึ้น "เสี่ยงต่ำ" ทั้งที่ไม่รู้
                    errors.append(name)
                    print(f"  ⚠ {name}: no data — ไม่ใส่ในไฟล์", file=sys.stderr)
                    continue
                if period_start is None:
                    period_start = times[0]
                period_end = times[-1]

                risk = compute_risk(daily)
                provinces_out[name] = risk
                print(
                    f"  ✓ {name}: blast={risk['days_blast']} bph={risk['days_bph']} "
                    f"sheath={risk['days_sheath']} wind={risk['days_strong_wind']}"
                )

        except Exception as e:
            # เดิมเติม 0 ให้ทั้ง batch — การ์ดของจังหวัดพวกนั้นขึ้น "เสี่ยงต่ำ" ทุกโรคทั้งที่ดึงไม่ได้
            # ตอนนี้ไม่ใส่ในไฟล์ (การ์ดไม่แสดง) และบอกไว้ใน _meta.missing
            print(f"  ✗ batch {batch_num} failed: {e}", file=sys.stderr)
            errors.extend(n for n in batch if n not in provinces_out)

        if i + BATCH_SIZE < len(names):
            time.sleep(1)   # 1s pause between batches

    ok, err = len(provinces_out), len(errors)
    if not ok or err > ok:   # หายเกินครึ่ง = ต้นทางมีปัญหา เก็บไฟล์เดิมไว้ดีกว่าเขียนครึ่งเดียวทับ
        print(f"ERROR: ได้ {ok} จังหวัด หาย {err} — ไม่เขียนทับ {OUTPUT}", file=sys.stderr)
        sys.exit(1)

    result = {
        "_meta": {
            "updated":      today,
            "period_start": period_start or today,
            "period_end":   period_end or today,
            "days":         DAYS,
            "source":       "Open-Meteo Forecast API — api.open-meteo.com",
            "missing":      sorted(errors),   # จังหวัดที่ดึงไม่ได้รอบนี้ — ไม่มีในไฟล์ ไม่ใช่ "ไม่เสี่ยง"
            "thresholds": {
                "blast_temp_min_c":   22,
                "blast_rh_pct":       80,
                "bph_temp_range_c":   [25, 30],
                "bph_rh_pct":         80,
                "sheath_temp_max_c":  30,
                "sheath_rh_pct":      85,
                "blight_wind_kmh":    30,
            },
        },
        "provinces": provinces_out,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved {ok} provinces → {OUTPUT}")
    if errors:
        print(f"⚠️  Missing ({err}): {', '.join(errors)}", file=sys.stderr)


if __name__ == "__main__":
    main()
