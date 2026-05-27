#!/usr/bin/env python3
"""
Fetch 7-day FORECAST rainfall per province from Open-Meteo (free, no API key).
Runs daily via GitHub Actions at 07:00 UTC (14:00 BKK).

Uses Open-Meteo batch API — all 77 provinces in 2 API calls (~10 sec total).
Variable: precipitation_sum (rain + showers + snow, daily sum in mm)

Output: data/rain-forecast.json
"""
import json, os, re, sys, time, io
import requests
from datetime import date

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DAYS       = 7           # next N days forecast
OUTPUT     = "data/rain-forecast.json"
API_URL    = "https://api.open-meteo.com/v1/forecast"
BATCH_SIZE = 40          # provinces per request (2 requests for 77 provinces)
MAX_RETRY  = 3
TIMEOUT    = 60          # seconds per batch request


# ── Load province centroids from thailand-data.js GeoJSON ───────────────────
def load_centroids():
    with open("thailand-data.js", encoding="utf-8") as f:
        js = f.read()
    js = re.sub(r"^window\.THAILAND_GEO\s*=\s*", "", js.strip().rstrip(";"))
    geo = json.loads(js)

    centroids = {}
    for feat in geo["features"]:
        name = feat["properties"]["name"]
        geom = feat["geometry"]
        all_pts = []
        if geom["type"] == "Polygon":
            for ring in geom["coordinates"]:
                all_pts.extend(ring)
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    all_pts.extend(ring)
        if all_pts:
            lons = [p[0] for p in all_pts]
            lats = [p[1] for p in all_pts]
            centroids[name] = {
                "lat": round(sum(lats) / len(lats), 4),
                "lon": round(sum(lons) / len(lons), 4),
            }
    return centroids


# ── Fetch one batch of provinces in a single API call ───────────────────────
def fetch_batch(batch_names, centroids):
    lats = ",".join(str(centroids[n]["lat"]) for n in batch_names)
    lons = ",".join(str(centroids[n]["lon"]) for n in batch_names)

    params = {
        "latitude":      lats,
        "longitude":     lons,
        "daily":         "precipitation_sum",  # rain + showers + snow (total precip)
        "forecast_days": DAYS,                 # next 7 days (today + 6 ahead)
        "timezone":      "Asia/Bangkok",
    }
    # NOTE: No past_days — we want pure forward forecast only.
    # forecast_days=7 returns today (day 0) through day 6.

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
                          for v in daily["precipitation_sum"][:DAYS]]
                if shared_dates is None:
                    shared_dates = dates
                rain_7d = round(sum(values), 1)
                provinces_out[name] = {"rain_7d": rain_7d, "values": values}
                print(f"  ✓ {name}: {rain_7d} mm (forecast)")
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
                f"พยากรณ์ปริมาณฝนสะสม {DAYS} วันข้างหน้า รายจังหวัด (centroid) · "
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
