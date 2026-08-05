#!/usr/bin/env python3
"""
Compute province-level climatological NORMAL (5-year average) for the
นาปี season (Jun–Nov) using Open-Meteo Archive API (free, no key).

Uses the 5 most recently completed seasons as a baseline reference,
displayed on the map as "ค่าปกติ 5 ปี / 5-yr Climatological Normal".
Useful for comparing with the current/upcoming season.

Output: data/weather-forecast.json
"""
import json, os, re, sys, time, requests
from datetime import date, datetime
from riceutils import load_centroids

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEASON_MONTH_START = 6   # June
SEASON_MONTH_END   = 11  # November
N_YEARS = 5              # number of past seasons to average

today = date.today()
# Find the 5 most recently completed Jun–Nov seasons
current_season_year = today.year if today.month >= SEASON_MONTH_START else today.year - 1
# Completed seasons: current_season_year-1, current_season_year-2, … (5 years)
base_years = list(range(current_season_year - N_YEARS, current_season_year))  # e.g. 2020–2024

OUTPUT     = "data/weather-forecast.json"
API_URL    = "https://archive-api.open-meteo.com/v1/archive"
BATCH_SIZE = 40   # provinces per request


def _season_totals(daily):
    """รวมค่าฤดูกาลของ 1 จังหวัด 1 ปี (ไม่ round — round ตอน average)"""
    def s(vals): return sum(v for v in vals if v is not None)
    def m(vals):
        v = [x for x in vals if x is not None]
        return sum(v) / len(v) if v else None
    return {
        "rain": s(daily["precipitation_sum"]),
        "et0":  s(daily["et0_fao_evapotranspiration"]),
        "temp": m(daily["temperature_2m_mean"]),
    }


# ── Fetch one season for a batch of provinces in one API call ───────────────
def fetch_season_batch(batch_names, centroids, year):
    lats = ",".join(str(centroids[n]["lat"]) for n in batch_names)
    lons = ",".join(str(centroids[n]["lon"]) for n in batch_names)
    params = {
        "latitude":  lats, "longitude": lons,
        "start_date": f"{year}-{SEASON_MONTH_START:02d}-01",
        "end_date":   f"{year}-{SEASON_MONTH_END:02d}-30",
        "daily":  "precipitation_sum,temperature_2m_mean,et0_fao_evapotranspiration",
        "timezone": "Asia/Bangkok",
    }
    for attempt in range(3):
        try:
            r = requests.get(API_URL, params=params, timeout=60)
            r.raise_for_status()
            results = r.json()
            if isinstance(results, dict):
                results = [results]
            return {n: _season_totals(res["daily"]) for n, res in zip(batch_names, results)}
        except Exception as e:
            if attempt == 2:
                print(f"  batch {year} ERROR – {e}", file=sys.stderr)
                return {}
            time.sleep(2)


def _average_normal(rains, et0s, temps, lat, lon):
    """เฉลี่ย N ปี → output schema เดิม"""
    rain_avg = round(sum(rains) / len(rains), 1)
    et0_avg  = round(sum(et0s)  / len(et0s),  1)
    temp_avg = round(sum(temps) / len(temps),  2) if temps else None
    return {
        "forecast_rainfall_mm": rain_avg,
        "forecast_et0_mm":      et0_avg,
        "forecast_wb_mm":       round(rain_avg - et0_avg, 1),
        "rainfall_p10_mm":      round(min(rains), 1),
        "rainfall_p90_mm":      round(max(rains), 1),
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

    # โหลดข้อมูลเดิม — ข้ามจังหวัดที่มีข้อมูลแล้ว รันเฉพาะที่ null
    existing = {}
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, encoding="utf-8") as fh:
                existing = json.load(fh).get("provinces", {})
        except Exception:
            pass

    provinces = dict(existing)
    skipped = sum(1 for v in existing.values() if v is not None)
    print(f"  Reusing {skipped} existing, fetching {len(centroids)-skipped} missing...")

    # ดึงเฉพาะจังหวัดที่ยังไม่มี — batch ต่อปี (N_YEARS × 2 batch = ~10 requests แทน 385)
    todo = [n for n in centroids if provinces.get(n) is None]
    acc = {n: {"rains": [], "et0s": [], "temps": []} for n in todo}
    for yr in base_years:
        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i:i + BATCH_SIZE]
            res = fetch_season_batch(batch, centroids, yr)
            for name in batch:
                d = res.get(name)
                if d:
                    acc[name]["rains"].append(d["rain"])
                    acc[name]["et0s"].append(d["et0"])
                    if d["temp"] is not None:
                        acc[name]["temps"].append(d["temp"])
            time.sleep(0.3)
        print(f"  year {yr} done")

    for name in todo:
        a = acc[name]
        if len(a["rains"]) == N_YEARS:   # ครบทุกปีเท่านั้น
            c = centroids[name]
            provinces[name] = _average_normal(a["rains"], a["et0s"], a["temps"], c["lat"], c["lon"])
        else:
            provinces[name] = None
            print(f"  {name}: incomplete ({len(a['rains'])}/{N_YEARS} yrs)", file=sys.stderr)

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
