#!/usr/bin/env python3
"""
Fetch 7-day cumulative rainfall per province from Open-Meteo (free, no API key).
Runs daily via GitHub Actions at 07:00 UTC (14:00 BKK).

Province centroids are derived from thailand-data.js GeoJSON (same as fetch_weather.py).

Output: data/rain-daily.json
"""
import json, os, re, sys, time, io
import requests
from datetime import date

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DAYS       = 7           # past N days + today (7 total)
OUTPUT     = "data/rain-daily.json"
API_URL    = "https://api.open-meteo.com/v1/forecast"
RATE_SLEEP = 0.12        # seconds between requests (~8 req/s)


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


# ── Fetch one province: past 6 days + today = 7 values ──────────────────────
def fetch_rain(lat, lon):
    params = {
        "latitude":     lat,
        "longitude":    lon,
        "daily":        "rain_sum",
        "past_days":    DAYS - 1,   # 6 past days
        "forecast_days": 1,          # + today = 7 total
        "timezone":     "Asia/Bangkok",
    }
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    daily  = r.json()["daily"]
    dates  = daily["time"][:DAYS]
    values = [round(v, 1) if v is not None else 0.0
              for v in daily["rain_sum"][:DAYS]]
    return dates, values


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    centroids = load_centroids()
    today     = date.today().isoformat()

    provinces_out = {}
    shared_dates  = None
    errors        = []

    for name, c in sorted(centroids.items()):
        try:
            dates, values = fetch_rain(c["lat"], c["lon"])
            if shared_dates is None:
                shared_dates = dates
            rain_7d = round(sum(values), 1)
            provinces_out[name] = {
                "rain_7d": rain_7d,
                "values":  values,
            }
            print(f"  ✓ {name}: {rain_7d} mm ({len(values)} days)")
        except Exception as e:
            print(f"  ✗ {name}: {e}", file=sys.stderr)
            errors.append(name)
        time.sleep(RATE_SLEEP)

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

    print(f"\n✅ Saved {len(provinces_out)} provinces → {OUTPUT}")
    if errors:
        print(f"⚠️  Failed ({len(errors)}): {', '.join(errors)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
