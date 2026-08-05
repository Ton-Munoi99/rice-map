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
import json, os, re, sys, time, requests
from datetime import date, datetime
from riceutils import load_centroids

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEASON_MONTH_START = 6   # June
SEASON_MONTH_END   = 11  # November

today = date.today()
year = today.year if today.month >= SEASON_MONTH_START else today.year - 1
start_date = f"{year}-{SEASON_MONTH_START:02d}-01"
_full_end   = f"{year}-{SEASON_MONTH_END:02d}-30"
end_date    = min(today.isoformat(), _full_end)   # don't request future dates

OUTPUT     = "data/weather-province.json"
API_URL    = "https://archive-api.open-meteo.com/v1/archive"
BATCH_SIZE = 40   # provinces per request (2 requests for 77 provinces)


def _aggregate(daily, lat, lon):
    """สรุปค่ารวมฤดูกาลจาก daily block ของ 1 จังหวัด"""
    def s(vals): return round(sum(v for v in vals if v is not None), 1)
    def m(vals):
        v = [x for x in vals if x is not None]
        return round(sum(v) / len(v), 2) if v else None

    rain = s(daily["precipitation_sum"])
    et0  = s(daily["et0_fao_evapotranspiration"])
    temp = m(daily["temperature_2m_mean"])
    return {
        "season_rainfall_mm": rain,
        "season_et0_mm": et0,
        "season_temp_c": temp,
        "water_balance_mm": round(rain - et0, 1),
        "days_covered": len([v for v in daily["precipitation_sum"] if v is not None]),
        "lat": lat,
        "lon": lon,
    }


# ── Fetch a batch of provinces in one API call ──────────────────────────────
def fetch_batch(batch_names, centroids):
    lats = ",".join(str(centroids[n]["lat"]) for n in batch_names)
    lons = ",".join(str(centroids[n]["lon"]) for n in batch_names)
    params = {
        "latitude": lats, "longitude": lons,
        "start_date": start_date, "end_date": end_date,
        "daily": "precipitation_sum,temperature_2m_mean,et0_fao_evapotranspiration",
        "timezone": "Asia/Bangkok",
    }
    for attempt in range(3):
        try:
            r = requests.get(API_URL, params=params, timeout=60)
            r.raise_for_status()
            results = r.json()
            if isinstance(results, dict):  # single-location → list
                results = [results]
            return {n: _aggregate(res["daily"], centroids[n]["lat"], centroids[n]["lon"])
                    for n, res in zip(batch_names, results)}
        except Exception as e:
            if attempt == 2:
                print(f"  batch ERROR after 3 attempts – {e}", file=sys.stderr)
                return {}
            time.sleep(2)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"Season: {start_date} → {end_date}")
    centroids = load_centroids()
    print(f"Provinces found: {len(centroids)}")

    # โหลดข้อมูลเดิม (ถ้ามี) — ข้ามจังหวัดที่มีข้อมูลแล้ว รันเฉพาะที่ null
    existing = {}
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, encoding="utf-8") as f:
                existing = json.load(f).get("provinces", {})
        except Exception:
            pass

    provinces = dict(existing)
    skipped = sum(1 for v in existing.values() if v is not None)
    print(f"  Reusing {skipped} existing provinces, fetching the rest...")

    # ดึงเฉพาะจังหวัดที่ยังไม่มีข้อมูล แบบ batch (2 requests แทน 77)
    todo = [n for n in centroids if provinces.get(n) is None]
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        res = fetch_batch(batch, centroids)
        for name in batch:
            provinces[name] = res.get(name)  # None ถ้า batch ล้มเหลว
            d = provinces[name]
            if d:
                wb = d["water_balance_mm"]
                tag = "surplus" if wb > 150 else ("deficit" if wb < 0 else "balanced")
                print(f"  {name:25s} rain={d['season_rainfall_mm']:6.1f}mm  wb={wb:+.0f}mm  {tag}")
        time.sleep(0.5)

    output = {
        "_meta": {
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "season": f"{start_date} → {end_date}",
            "year": year,
            "season_label": f"นาปี {year + 543} (มิ.ย.–พ.ย.) · Main Season {year} (Jun–Nov)",
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
