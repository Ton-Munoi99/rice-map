#!/usr/bin/env python3
"""
Fetch 7-day cumulative rainfall per province from Open-Meteo (free, no API key).
Runs daily via GitHub Actions at 07:00 UTC (14:00 BKK).

Uses Open-Meteo batch API — all 77 provinces in 2 API calls (~10 sec total).

Output: data/rain-daily.json
"""
import json, os, re, sys, time
import requests
from datetime import date
from riceutils import load_centroids

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DAYS       = 7           # past N days + today (7 total)
OUTPUT     = "data/rain-daily.json"
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
        "daily":         "rain_sum",
        "past_days":     DAYS - 1,   # 6 past days
        "forecast_days": 1,           # + today = 7 total
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


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    centroids   = load_centroids()
    today       = date.today().isoformat()
    names       = sorted(centroids.keys())

    provinces_out = {}
    shared_dates  = None
    errors        = []

    total_batches = (len(names) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Fetching {len(names)} provinces in {total_batches} batch(es) of ≤{BATCH_SIZE} ...")

    for i in range(0, len(names), BATCH_SIZE):
        batch = names[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"\nBatch {batch_num}/{total_batches}: {batch[0]} … {batch[-1]} ({len(batch)} provinces)")

        try:
            data = fetch_batch(batch, centroids)
            for j, name in enumerate(batch):
                daily  = data[j]["daily"]
                dates  = daily["time"][:DAYS]
                values = [round(v, 1) if v is not None else 0.0
                          for v in daily["rain_sum"][:DAYS]]
                if shared_dates is None:
                    shared_dates = dates
                rain_7d = round(sum(values), 1)
                provinces_out[name] = {"rain_7d": rain_7d, "values": values}
                print(f"  ✓ {name}: {rain_7d} mm")
        except Exception as e:
            print(f"  ✗ batch {batch_num} failed: {e}", file=sys.stderr)
            errors.extend(batch)

        if i + BATCH_SIZE < len(names):
            time.sleep(1)   # 1s pause between batches

    if not provinces_out:
        print("ERROR: No data fetched!", file=sys.stderr)
        sys.exit(1)

    result = {
        "_meta": {
            "source":  "Open-Meteo",
            "updated": today,
            "days":    DAYS,
            "dates":   shared_dates or [],
            "note":    (
                f"ปริมาณฝนสะสม {DAYS} วันล่าสุด รายจังหวัด (centroid) · "
                "Open-Meteo Forecast API · ฟรี ไม่ต้อง API key · อัปเดตทุกวัน"
            ),
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
