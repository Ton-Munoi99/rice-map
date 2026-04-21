#!/usr/bin/env python3
"""
Compute province-level climatological NORMAL (5-year average) for the
นาปี season (Jun–Nov) using Open-Meteo Archive API (free, no key).

Uses the 5 most recently completed seasons as a baseline reference,
displayed on the map as "ค่าปกติ 5 ปี / 5-yr Climatological Normal".
Useful for comparing with the current/upcoming season.

Output: data/weather-forecast.json
"""
import json, re, sys, time, requests, io
from datetime import date, datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SEASON_MONTH_START = 6   # June
SEASON_MONTH_END   = 11  # November
N_YEARS = 5              # number of past seasons to average

today = date.today()
# Find the 5 most recently completed Jun–Nov seasons
current_season_year = today.year if today.month >= SEASON_MONTH_START else today.year - 1
# Completed seasons: current_season_year-1, current_season_year-2, … (5 years)
base_years = list(range(current_season_year - N_YEARS, current_season_year))  # e.g. 2020–2024

OUTPUT = "data/weather-forecast.json"


# ── Load province centroids ──────────────────────────────────────────────────
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


# ── Fetch one season for one province ────────────────────────────────────────
def fetch_season(lat, lon, year):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "start_date": f"{year}-{SEASON_MONTH_START:02d}-01",
        "end_date":   f"{year}-{SEASON_MONTH_END:02d}-30",
        "daily":  "precipitation_sum,temperature_2m_mean,et0_fao_evapotranspiration",
        "timezone": "Asia/Bangkok",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    daily = r.json()["daily"]

    def s(vals): return sum(v for v in vals if v is not None)
    def m(vals):
        v = [x for x in vals if x is not None]
        return sum(v) / len(v) if v else None

    return {
        "rain": s(daily["precipitation_sum"]),
        "et0":  s(daily["et0_fao_evapotranspiration"]),
        "temp": m(daily["temperature_2m_mean"]),
    }


# ── Average across N years ────────────────────────────────────────────────────
def fetch_normal(lat, lon):
    rains, et0s, temps = [], [], []
    for yr in base_years:
        d = fetch_season(lat, lon, yr)
        rains.append(d["rain"])
        et0s.append(d["et0"])
        if d["temp"] is not None:
            temps.append(d["temp"])
        time.sleep(0.05)

    rain_avg = round(sum(rains) / len(rains), 1)
    et0_avg  = round(sum(et0s)  / len(et0s),  1)
    temp_avg = round(sum(temps) / len(temps),  2) if temps else None
    wb_avg   = round(rain_avg - et0_avg, 1)

    # year-to-year spread as simple uncertainty indicator
    rain_min = round(min(rains), 1)
    rain_max = round(max(rains), 1)

    return {
        "forecast_rainfall_mm": rain_avg,
        "forecast_et0_mm":      et0_avg,
        "forecast_wb_mm":       wb_avg,
        "rainfall_p10_mm":      rain_min,
        "rainfall_p90_mm":      rain_max,
        "forecast_temp_c":      temp_avg,
        "n_members":            N_YEARS,
        "base_years":           base_years,
        "lat": lat,
        "lon": lon,
    }


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    yr_range = f"{base_years[0]}–{base_years[-1]}"
    next_season = current_season_year + 543  # next Thai year
    print(f"Computing 5-yr normal from: {yr_range}  (reference for นาปี {next_season})")
    centroids = load_centroids()
    print(f"Provinces: {len(centroids)}")

    provinces = {}
    for i, (name, c) in enumerate(centroids.items()):
        try:
            data = fetch_normal(c["lat"], c["lon"])
            provinces[name] = data
            rain = data["forecast_rainfall_mm"]
            wb   = data["forecast_wb_mm"]
            tag  = "💧 surplus" if wb > 150 else ("⚠️ deficit" if wb < 0 else "✓ balanced")
            span = f"[{data['rainfall_p10_mm']:.0f}–{data['rainfall_p90_mm']:.0f}]"
            print(f"  [{i+1:2}/{len(centroids)}] {name:25s} avg_rain={rain:6.1f}mm  wb={wb:+.0f}mm  {span}  {tag}")
        except Exception as e:
            print(f"  [{i+1:2}/{len(centroids)}] {name}: ERROR – {e}", file=sys.stderr)
            provinces[name] = None
        time.sleep(0.1)

    output = {
        "_meta": {
            "updated":    datetime.now().strftime("%Y-%m-%d"),
            "base_years": yr_range,
            "n_years":    N_YEARS,
            "season_label": f"ค่าปกติ 5 ปี นาปี {yr_range} · 5-yr Normal (Jun–Nov {yr_range})",
            "forecast_model": f"Climatological average of {yr_range}",
            "source":  "Open-Meteo Archive API — archive-api.open-meteo.com",
            "note":    f"ค่าเฉลี่ยนาปี {N_YEARS} ปี ({yr_range}) ใช้เป็นฐานเทียบกับฤดูกาลปัจจุบัน · {N_YEARS}-year climatological mean used as seasonal baseline reference",
        },
        "provinces": provinces,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    ok = sum(1 for v in provinces.values() if v)
    print(f"\nSaved {ok}/{len(provinces)} provinces → {OUTPUT}")


if __name__ == "__main__":
    main()
