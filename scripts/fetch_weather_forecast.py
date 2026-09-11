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
from datetime import date
from riceutils import bkk_today, load_centroids

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEASON_MONTH_START = 6   # June
SEASON_MONTH_END   = 11  # November
N_YEARS = 5              # number of past seasons to average

# ตั้งใจใช้เวลา runner ไม่ใช่ bkk_today() — ใช้คำนวณปีฤดูกาล ไม่ใช่ป้ายวันที่
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
    # ฝนรายเดือนด้วย ไม่ใช่แค่ยอดรวมฤดูกาล: ฝนนาปีไม่ได้ตกเท่ากันทุกสัปดาห์
    # (แม่ฮ่องสอน ก.ย. 107 มม./สัปดาห์ แต่ พ.ย. 13) ใครหารยอดฤดูกาลด้วย 26
    # สัปดาห์แบนๆ จะได้ฐานที่ต่ำเกินจริงในเดือนพีค และสูงเกินจริงปลายฤดู
    monthly = {}
    for t, v in zip(daily["time"], daily["precipitation_sum"]):
        monthly[int(t[5:7])] = monthly.get(int(t[5:7]), 0.0) + (v or 0)
    return {
        "rain": s(daily["precipitation_sum"]),
        "et0":  s(daily["et0_fao_evapotranspiration"]),
        "temp": m(daily["temperature_2m_mean"]),
        "monthly": monthly,
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
    # 40 จุด × 183 วัน × 3 ตัวแปร เป็น request ที่ "หนัก" สำหรับ Open-Meteo ฟรี
    # จึงเจอ 429 เป็นปกติ และโควตาไม่รีเซ็ตใน 2 วินาที — ต้องถอยยาวจริง ไม่ใช่ retry ถี่ๆ
    # (11 ก.ย. 69 retry 3 ครั้ง/2 วิ ได้ข้อมูลแค่ 3 ใน 5 ปี ทุกครั้งที่รัน)
    for wait in (0, 30, 90, 180, 300):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(API_URL, params=params, timeout=60)
            r.raise_for_status()
            results = r.json()
            if isinstance(results, dict):
                results = [results]
            return {n: _season_totals(res["daily"]) for n, res in zip(batch_names, results)}
        except Exception as e:
            err = e
    print(f"  batch {year} ERROR – {err}", file=sys.stderr)
    return {}


WEEKS_PER_MONTH = 365.25 / 12 / 7   # 4.345

def _average_normal(rains, et0s, temps, monthlies, lat, lon):
    """เฉลี่ย N ปี → output schema เดิม + ค่าปกติรายสัปดาห์แยกเดือน"""
    rain_avg = round(sum(rains) / len(rains), 1)
    et0_avg  = round(sum(et0s)  / len(et0s),  1)
    temp_avg = round(sum(temps) / len(temps),  2) if temps else None
    wk = {}
    for mth in range(SEASON_MONTH_START, SEASON_MONTH_END + 1):
        vals = [d[mth] for d in monthlies if mth in d]
        if vals:
            wk[str(mth)] = round(sum(vals) / len(vals) / WEEKS_PER_MONTH, 1)
    return {
        "forecast_rainfall_mm": rain_avg,
        # ค่าปกติ "รายสัปดาห์" ของแต่ละเดือนในฤดู — fetch_agri_warnings.py ใช้ตัวนี้
        # เป็นฐานเกณฑ์น้ำท่วม แทนการหารยอดฤดูกาลด้วย 26 สัปดาห์แบนๆ
        "rain_normal_weekly_mm": wk,
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

    # ข้อมูลเดิมที่ยังไม่มีค่าปกติรายเดือน ต้องดึงใหม่ (ฟิลด์เพิ่มหลังไฟล์ถูกสร้าง)
    # แต่เก็บของเดิมไว้เป็น fallback — ห้ามทิ้งข้อมูลที่ใช้ได้เพราะ API ล่มชั่วคราว
    previous = dict(existing)
    existing = {k: v for k, v in existing.items()
                if v is None or v.get("rain_normal_weekly_mm")}
    provinces = dict(existing)
    skipped = sum(1 for v in existing.values() if v is not None)
    print(f"  Reusing {skipped} existing, fetching {len(centroids)-skipped} missing...")

    # ดึงเฉพาะจังหวัดที่ยังไม่มี — batch ต่อปี (N_YEARS × 2 batch = ~10 requests แทน 385)
    todo = [n for n in centroids if provinces.get(n) is None]
    acc = {n: {"rains": [], "et0s": [], "temps": [], "monthlies": []} for n in todo}
    for yr in base_years:
        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i:i + BATCH_SIZE]
            res = fetch_season_batch(batch, centroids, yr)
            for name in batch:
                d = res.get(name)
                if d:
                    acc[name]["rains"].append(d["rain"])
                    acc[name]["et0s"].append(d["et0"])
                    acc[name]["monthlies"].append(d["monthly"])
                    if d["temp"] is not None:
                        acc[name]["temps"].append(d["temp"])
            time.sleep(2)
        print(f"  year {yr} done")

    for name in todo:
        a = acc[name]
        if len(a["rains"]) == N_YEARS:   # ครบทุกปีเท่านั้น
            c = centroids[name]
            provinces[name] = _average_normal(a["rains"], a["et0s"], a["temps"],
                                              a["monthlies"], c["lat"], c["lon"])
        else:
            # API ล่มกลางทาง → คืนค่าเดิมไป ไม่เขียน null ทับ: weather-forecast.json
            # เป็นฐานเกณฑ์น้ำท่วมของทั้ง layer เตือนภัย ถ้าโดนล้างเป็น null จะหล่นไป
            # ใช้เกณฑ์คงที่ fallback ทั้งประเทศแบบเงียบๆ (เคยเกิด 11 ก.ย. 69 ตอนเพิ่ม
            # ค่าปกติรายเดือน: 2 ใน 5 ปีโดน rate limit แล้วไฟล์กลายเป็น 0/77 ทันที)
            provinces[name] = previous.get(name)
            kept = "คงค่าเดิม" if provinces[name] else "ไม่มีค่าเดิม"
            print(f"  {name}: incomplete ({len(a['rains'])}/{N_YEARS} yrs) — {kept}",
                  file=sys.stderr)

    output = {
        "_meta": {
            "updated":    bkk_today(),
            "base_years": yr_range,
            "n_years":    N_YEARS,
            "season_label": f"ค่าปกติ 5 ปี นาปี {yr_range} · 5-yr Normal (Jun–Nov {yr_range})",
            "forecast_model": f"Climatological average of {yr_range}",
            "source":  "Open-Meteo Archive API — archive-api.open-meteo.com",
            "note":    f"ค่าเฉลี่ยนาปี {N_YEARS} ปี ({yr_range}) ใช้เป็นฐานเทียบกับฤดูกาลปัจจุบัน · {N_YEARS}-year climatological mean used as seasonal baseline reference",
            "rain_normal_weekly_note": "rain_normal_weekly_mm = ฝนปกติรายสัปดาห์ของแต่ละเดือน (คีย์ 6-11) · ใช้เป็นฐานเกณฑ์น้ำท่วมใน fetch_agri_warnings.py",
        },
        "provinces": provinces,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    ok = sum(1 for v in provinces.values() if v)
    print(f"\nSaved {ok}/{len(provinces)} provinces → {OUTPUT}")


if __name__ == "__main__":
    main()
