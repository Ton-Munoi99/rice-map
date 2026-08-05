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
import json, os, re, sys, time
import requests
from datetime import date
from riceutils import load_centroids

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DAYS       = 7           # 6 past days + today = 7 total
OUTPUT     = "data/disease-risk.json"
API_URL    = "https://api.open-meteo.com/v1/forecast"
BATCH_SIZE = 40          # provinces per request (2 requests for 77 provinces)
MAX_RETRY  = 3
TIMEOUT    = 60          # seconds per batch request




# ── Fetch one batch of provinces in a single API call ───────────────────────
def fetch_batch(batch_names, centroids):
    lats = ",".join(str(centroids[n]["lat"]) for n in batch_names)
    lons = ",".join(str(centroids[n]["lon"]) for n in batch_names)

    params = {
        "latitude":      lats,
        "longitude":     lons,
        "daily":         "temperature_2m_min,temperature_2m_max,relative_humidity_2m_mean,wind_speed_10m_max,precipitation_hours",
        "past_days":     6,   # 6 past days
        "forecast_days": 1,   # + today = 7 total
        "timezone":      "Asia/Bangkok",
    }

    for attempt in range(MAX_RETRY):
        try:
            r = requests.get(API_URL, params=params, timeout=TIMEOUT)
            if r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"  429 rate-limit → wait {wait}s ...", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            # Single location → dict; multiple → list
            if isinstance(data, dict):
                data = [data]
            return data
        except requests.exceptions.Timeout:
            wait = 15 * (attempt + 1)
            print(f"  timeout (attempt {attempt+1}/{MAX_RETRY}) → retry in {wait}s ...", flush=True)
            time.sleep(wait)
        except Exception:
            if attempt < MAX_RETRY - 1:
                time.sleep(5)
            else:
                raise
    raise RuntimeError(f"batch failed after {MAX_RETRY} attempts")


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
    today     = date.today().isoformat()
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
            data = fetch_batch(batch, centroids)
            for j, name in enumerate(batch):
                daily = data[j]["daily"]
                times = daily.get("time", [])
                if times:
                    if period_start is None:
                        period_start = times[0]
                    period_end = times[-1]

                if not times:
                    provinces_out[name] = {
                        "days_blast": 0, "days_bph": 0,
                        "days_sheath": 0, "days_strong_wind": 0,
                    }
                    print(f"  ⚠ {name}: no data (zeros)")
                    continue

                risk = compute_risk(daily)
                provinces_out[name] = risk
                print(
                    f"  ✓ {name}: blast={risk['days_blast']} bph={risk['days_bph']} "
                    f"sheath={risk['days_sheath']} wind={risk['days_strong_wind']}"
                )

        except Exception as e:
            print(f"  ✗ batch {batch_num} failed: {e}", file=sys.stderr)
            errors.extend(batch)
            # Fill zeros for failed batch
            for name in batch:
                if name not in provinces_out:
                    provinces_out[name] = {
                        "days_blast": 0, "days_bph": 0,
                        "days_sheath": 0, "days_strong_wind": 0,
                    }

        if i + BATCH_SIZE < len(names):
            time.sleep(1)   # 1s pause between batches

    if not provinces_out:
        print("ERROR: No data fetched!", file=sys.stderr)
        sys.exit(1)

    result = {
        "_meta": {
            "updated":      today,
            "period_start": period_start or today,
            "period_end":   period_end or today,
            "days":         DAYS,
            "source":       "Open-Meteo Forecast API — api.open-meteo.com",
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

    ok  = len(provinces_out)
    err = len(errors)
    print(f"\n✅ Saved {ok} provinces → {OUTPUT}")
    if errors:
        print(f"⚠️  Failed ({err}): {', '.join(errors)}", file=sys.stderr)
        if err > ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
