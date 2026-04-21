#!/usr/bin/env python3
"""
Fetch province-level weather from Open-Meteo (free, no API key).
Rice growing season (นาปี): June 1 – November 30

Variables fetched per province:
  - precipitation_sum       → season total rainfall (mm)
  - et0_fao_evapotranspiration → FAO-56 Penman-Monteith ET0 (mm)
  - temperature_2m_mean     → mean daily temperature (°C)
  - water_balance           → rainfall – ET0  (positive = surplus, negative = drought)

Output: data/weather-province.json
"""
import json, re, sys, time, requests, io
from datetime import date, datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SEASON_MONTH_START = 6   # June
SEASON_MONTH_END   = 11  # November

today = date.today()
year = today.year if today.month >= SEASON_MONTH_START else today.year - 1
start_date = f"{year}-{SEASON_MONTH_START:02d}-01"
_full_end   = f"{year}-{SEASON_MONTH_END:02d}-30"
end_date    = min(today.isoformat(), _full_end)   # don't request future dates

OUTPUT = "data/weather-province.json"


# ── Load province centroids from thailand-data.js GeoJSON ──────────────────
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


# ── Fetch one province ──────────────────────────────────────────────────────
def fetch_province(lat, lon):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "precipitation_sum,temperature_2m_mean,et0_fao_evapotranspiration",
        "timezone": "Asia/Bangkok",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    daily = r.json()["daily"]

    def s(vals): return round(sum(v for v in vals if v is not None), 1)
    def m(vals):
        v = [x for x in vals if x is not None]
        return round(sum(v) / len(v), 2) if v else None

    rain = s(daily["precipitation_sum"])
    et0  = s(daily["et0_fao_evapotranspiration"])
    temp = m(daily["temperature_2m_mean"])
    wb   = round(rain - et0, 1)

    return {
        "season_rainfall_mm": rain,
        "season_et0_mm": et0,
        "season_temp_c": temp,
        "water_balance_mm": wb,
        "days_covered": len([v for v in daily["precipitation_sum"] if v is not None]),
    }


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"Season: {start_date} → {end_date}")
    centroids = load_centroids()
    print(f"Provinces found: {len(centroids)}")

    provinces = {}
    for i, (name, c) in enumerate(centroids.items()):
        try:
            data = fetch_province(c["lat"], c["lon"])
            data["lat"] = c["lat"]
            data["lon"] = c["lon"]
            provinces[name] = data
            wb = data["water_balance_mm"]
            tag = "💧 surplus" if wb > 150 else ("⚠️ deficit" if wb < 0 else "✓ balanced")
            print(f"  [{i+1:2}/{len(centroids)}] {name:25s} rain={data['season_rainfall_mm']:6.1f}mm  wb={wb:+.0f}mm  {tag}")
        except Exception as e:
            print(f"  [{i+1:2}/{len(centroids)}] {name}: ERROR – {e}", file=sys.stderr)
            provinces[name] = None
        time.sleep(0.12)   # polite delay

    output = {
        "_meta": {
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "season": f"{start_date} → {end_date}",
            "year": year,
            "season_label": f"นาปี {year + 543}  (มิ.ย.–พ.ย.)",
            "source": "Open-Meteo Archive API — archive-api.open-meteo.com",
            "variables": {
                "season_rainfall_mm": "Total precipitation Jun–Nov (mm)",
                "season_et0_mm": "Total FAO-56 ET0 Jun–Nov (mm)",
                "season_temp_c": "Mean daily temperature Jun–Nov (°C)",
                "water_balance_mm": "rainfall – ET0 (mm); positive = surplus, negative = drought stress",
            },
        },
        "provinces": provinces,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    ok = sum(1 for v in provinces.values() if v)
    print(f"\nSaved {ok}/{len(provinces)} provinces → {OUTPUT}")


if __name__ == "__main__":
    main()
