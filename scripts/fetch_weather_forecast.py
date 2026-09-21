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
from riceutils import bkk_today, load_centroids, load_sample_points, percentile

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
    return {
        "rain": s(daily["precipitation_sum"]),
        "et0":  s(daily["et0_fao_evapotranspiration"]),
        "temp": m(daily["temperature_2m_mean"]),
        "monthly": monthly_totals(daily),
    }


def monthly_totals(daily):
    """ฝนรวมรายเดือนของจุดเดียว 1 ปี → {เดือน: มม.}"""
    out = {}
    for t, v in zip(daily["time"], daily["precipitation_sum"]):
        out[int(t[5:7])] = out.get(int(t[5:7]), 0.0) + (v or 0)
    return out


def daily_rain(daily):
    """ฝนรายวันของจุดเดียว 1 ปี → [(เดือน, มม.), ...] ตามลำดับวัน
    None นับเป็น 0 เหมือนฝั่ง fetch_rain_forecast.py"""
    return [(int(t[5:7]), v if v is not None else 0.0)
            for t, v in zip(daily["time"], daily["precipitation_sum"])]


def fetch_rain_points_batch(batch_pts, year):
    """ฝนรายวันของจุดตัวอย่าง (ขอแค่ precipitation ตัวเดียว — request เบากว่ามาก)
    batch_pts: [(province, {'lat','lon'}), ...] → {index: [(เดือน, มม.) รายวัน]}"""
    params = {
        "latitude":  ",".join(str(pt["lat"]) for _, pt in batch_pts),
        "longitude": ",".join(str(pt["lon"]) for _, pt in batch_pts),
        "start_date": f"{year}-{SEASON_MONTH_START:02d}-01",
        "end_date":   f"{year}-{SEASON_MONTH_END:02d}-30",
        "daily": "precipitation_sum",
        "timezone": "Asia/Bangkok",
    }
    for wait in (0, 30, 90, 180, 300):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(API_URL, params=params, timeout=60)
            r.raise_for_status()
            results = r.json()
            if isinstance(results, dict):
                results = [results]
            return {i: daily_rain(res["daily"]) for i, res in enumerate(results)}
        except Exception as e:
            err = e
    print(f"  rain-points batch {year} ERROR - {err}", file=sys.stderr)
    return {}


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
NORMAL_PCTL = 90   # ต้องเท่ากับ PCTL ใน fetch_rain_forecast.py — ดูเหตุผลใน weekly_normal()

# ป้ายวิธีคำนวณ ติดไว้กับ record ทุกจังหวัด — สคริปต์นี้ข้ามจังหวัดที่มีข้อมูลแล้ว
# (ดึงครบทีเดียวใช้ทั้งฤดู) ถ้าไม่มีป้ายนี้ พอเปลี่ยน "วิธี" คิดค่า ของเก่าจะถูกเก็บไว้
# เงียบๆ ตลอดไป — เกิดจริงแล้ว 11 ก.ย. 69: เปลี่ยนจาก centroid มาเป็น p90 แล้วรันใหม่
# ได้ "Reusing 77 existing, fetching 0" ไฟล์ไม่ขยับสักจังหวัด
# ⚠️ เปลี่ยนวิธีคิด rain_normal_weekly_mm เมื่อไหร่ ต้องขยับสตริงนี้ด้วย
NORMAL_METHOD = "p90-daily-sample-points+centroid-v3"


def is_current(rec):
    """record เดิมใช้ต่อได้ต่อเมื่อคิดด้วย *วิธี* เดียวกันและ *ชุดปี* เดียวกัน

    ป้ายวิธีอย่างเดียวไม่พอ: หน้าต่าง 5 ปีเลื่อนเองทุกวันที่ 1 มิ.ย. (base_years) พอถึง
    วันนั้น record เก่ายังติดป้ายวิธีเดิมจึงถูกใช้ต่อทั้ง 77 จังหวัด แต่ _meta.base_years
    ถูกเขียนใหม่เป็นช่วงปีใหม่ — ป้ายจะโกหกว่าเป็นค่าปกติของอีกชุดปีหนึ่ง"""
    return (rec.get("rain_normal_method") == NORMAL_METHOD
            and rec.get("base_years") == base_years)


def weekly_normal(per_year_points):
    """ค่าปกติฝนรายสัปดาห์แยกเดือน — สรุปข้ามจุดด้วย p90 "วิธีเดียวกับฝั่งพยากรณ์"

    per_year_points: {ปี: [ [(เดือน, มม.) รายวัน] ต่อจุดตัวอย่าง ]}

    ทำไมต้อง p90 ไม่ใช่ centroid: rain-forecast.json สรุปฝนพยากรณ์ของจังหวัดด้วย p90
    ข้ามจุดตัวอย่าง ≤6 จุด (จงใจ เพื่อจับฝนกระจุกแถบเทือกเขาที่ centroid มองไม่เห็น)
    ฐานที่วัดจาก centroid จุดเดียวจึงเอนไปทางเตือนเกิน และเอนไม่เท่ากันทุกจังหวัด

    ⚠️ ลำดับการรวมต้องตรงกับพยากรณ์ด้วย ไม่ใช่แค่ใช้ p90 เหมือนกัน: พยากรณ์ทำ
    "p90 ข้ามจุด ของแต่ละวัน → แล้วรวม 7 วัน" ถ้าฝั่งนี้ทำ "รวมรายเดือนของแต่ละจุด →
    แล้ว p90 ข้ามจุด" ผลจะต่ำกว่าเสมอ (p90 ของ 6 จุด = ค่าเฉลี่ย 2 อันดับบนสุด ซึ่ง
    subadditive: รวมของ p90 รายวัน ≥ p90 ของยอดรวม) และห่างขึ้นเมื่อฝนกระจุกคนละจุด
    คนละวัน — ฐานต่ำ = เตือนเกิน ซึ่งคือบั๊กที่ฟังก์ชันนี้มีไว้แก้ (รุ่น v2 ทำผิดลำดับนี้)
    """
    yearly = {}
    for pts in per_year_points.values():
        n_days = min(len(pt) for pt in pts)
        month_sum = {}
        for d in range(n_days):
            mth = pts[0][d][0]
            month_sum[mth] = (month_sum.get(mth, 0.0)
                              + percentile([pt[d][1] for pt in pts], NORMAL_PCTL))
        for mth, v in month_sum.items():
            yearly.setdefault(mth, []).append(v)
    return {str(mth): round(sum(v) / len(v) / WEEKS_PER_MONTH, 1)
            for mth, v in sorted(yearly.items())
            if SEASON_MONTH_START <= mth <= SEASON_MONTH_END}


def points_complete(per_year_points, n_points):
    """ครบทุกปี และทุกปีได้ครบทุกจุดตัวอย่างของจังหวัดนั้น

    ต้องเช็กก่อนบันทึก เพราะ record ที่บันทึกแล้วติดป้าย NORMAL_METHOD จะไม่ถูกดึงใหม่อีก
    เลย ถ้าปล่อยข้อมูลไม่ครบผ่าน: batch ล่มหนึ่งปี = ค่าปกติเฉลี่ยแค่ 4 ปี · จังหวัดที่จุด
    ถูกแบ่งอยู่สอง batch แล้ว batch หนึ่งล่ม = p90 จาก 2-3 จุด ซึ่งดึงฐานให้ต่ำ"""
    return (n_points > 0 and len(per_year_points) == N_YEARS
            and all(len(pts) == n_points for pts in per_year_points.values()))


def centroid_weekly_normal(monthlies):
    """ค่าปกติรายสัปดาห์แยกเดือน วัดที่ centroid จุดเดียว — คู่กับ weekly_normal() ที่เป็น p90

    ต้องมีสองชุดเพราะผู้ใช้สองรายวัดคนละวิธี และ "ฐานต้องวัดวิธีเดียวกับตัวตั้ง":
      · rain_normal_weekly_mm (p90)  → เทียบกับ rain-forecast.json ซึ่งเป็น p90 ของ ≤6 จุด
      · rain_normal_weekly_centroid_mm → เทียบกับ weather-province.json ซึ่งวัดที่ centroid
    ถ้าจับคู่ผิดข้าง ตัวเลขจะเอน ค่ากลาง 1.38x และแกว่ง 1.00x-2.54x แล้วแต่จังหวัด (ก.ย. ครบ 77 จังหวัด)
    """
    wk = {}
    for mth in range(SEASON_MONTH_START, SEASON_MONTH_END + 1):
        vals = [d[mth] for d in monthlies if mth in d]
        if vals:
            wk[str(mth)] = round(sum(vals) / len(vals) / WEEKS_PER_MONTH, 1)
    return wk


def _average_normal(rains, et0s, temps, wk, wk_cen, lat, lon):
    """เฉลี่ย N ปี → output schema เดิม + ค่าปกติรายสัปดาห์แยกเดือน"""
    rain_avg = round(sum(rains) / len(rains), 1)
    et0_avg  = round(sum(et0s)  / len(et0s),  1)
    temp_avg = round(sum(temps) / len(temps),  2) if temps else None
    return {
        "forecast_rainfall_mm": rain_avg,
        # ค่าปกติ "รายสัปดาห์" ของแต่ละเดือนในฤดู — fetch_agri_warnings.py ใช้ตัวนี้
        # เป็นฐานเกณฑ์น้ำท่วม แทนการหารยอดฤดูกาลด้วย 26 สัปดาห์แบนๆ
        "rain_normal_weekly_mm": wk,
        # ค่าปกติรายสัปดาห์ที่ centroid — การ์ดภูมิอากาศใช้ตัวนี้ เพราะ weather-province.json
        # วัดฝนจริงที่ centroid เหมือนกัน (ห้ามเอาไปเทียบกับพยากรณ์ p90 ดู centroid_weekly_normal)
        "rain_normal_weekly_centroid_mm": wk_cen,
        "rain_normal_method":     NORMAL_METHOD,
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

    # ข้อมูลเดิมที่คิดด้วยวิธีอื่น (หรือยังไม่มีค่าปกติรายเดือน) ต้องดึงใหม่
    # แต่เก็บของเดิมไว้เป็น fallback — ห้ามทิ้งข้อมูลที่ใช้ได้เพราะ API ล่มชั่วคราว
    previous = dict(existing)
    existing = {k: v for k, v in existing.items()
                if v is None or is_current(v)}
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
        print(f"  year {yr} done (season totals)")

    # รอบสอง: ฝนรายเดือนของ "จุดตัวอย่าง" (~424 จุด) สำหรับค่าปกติรายสัปดาห์
    # ขอแค่ precipitation ตัวเดียวจึงเบากว่ารอบแรกทั้งที่จุดเยอะกว่า 5 เท่า
    sample_pts = load_sample_points()
    flat = [(n, pt) for n in todo for pt in sample_pts.get(n, [])]
    pt_acc = {n: {} for n in todo}        # จังหวัด → {ปี: [ [(เดือน, มม.) รายวัน] ต่อจุด ]}
    for yr in base_years:
        for i in range(0, len(flat), BATCH_SIZE):
            batch = flat[i:i + BATCH_SIZE]
            res = fetch_rain_points_batch(batch, yr)
            for j, (name, _) in enumerate(batch):
                if j in res:
                    pt_acc[name].setdefault(yr, []).append(res[j])
            time.sleep(2)
        print(f"  year {yr} done (sample points)")

    for name in todo:
        a = acc[name]
        pts_ok = points_complete(pt_acc.get(name) or {}, len(sample_pts.get(name, [])))
        wk = weekly_normal(pt_acc[name]) if pts_ok else {}
        if len(a["rains"]) == N_YEARS and wk:   # ครบทุกปี และทุกจุดตัวอย่าง
            c = centroids[name]
            provinces[name] = _average_normal(a["rains"], a["et0s"], a["temps"],
                                              wk, centroid_weekly_normal(a["monthlies"]),
                                              c["lat"], c["lon"])
        else:
            # API ล่มกลางทาง → คืนค่าเดิมไป ไม่เขียน null ทับ: weather-forecast.json
            # เป็นฐานเกณฑ์น้ำท่วมของทั้ง layer เตือนภัย ถ้าโดนล้างเป็น null จะหล่นไป
            # ใช้เกณฑ์คงที่ fallback ทั้งประเทศแบบเงียบๆ (เคยเกิด 11 ก.ย. 69 ตอนเพิ่ม
            # ค่าปกติรายเดือน: 2 ใน 5 ปีโดน rate limit แล้วไฟล์กลายเป็น 0/77 ทันที)
            provinces[name] = previous.get(name)
            kept = "คงค่าเดิม" if provinces[name] else "ไม่มีค่าเดิม"
            got_pts = {yr: len(v) for yr, v in (pt_acc.get(name) or {}).items()}
            print(f"  {name}: incomplete (season {len(a['rains'])}/{N_YEARS} yrs · "
                  f"sample points {got_pts} of {len(sample_pts.get(name, []))}/yr) — {kept}",
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
            "rain_normal_weekly_note": (
                f"rain_normal_weekly_mm = ฝนปกติรายสัปดาห์ของแต่ละเดือน (คีย์ 6-11) · "
                f"สรุปข้ามจุดตัวอย่าง ≤6 จุด/จังหวัด ด้วย p{NORMAL_PCTL} วิธีเดียวกับ rain-forecast.json "
                f"(ถ้าใช้ centroid จุดเดียวจะเป็นการเทียบ p90 กับค่าจุดเดียว = เอนไปทางเตือนเกิน "
                f"ค่ากลาง 1.38x และแกว่ง 1.00x-2.54x แล้วแต่จังหวัด (ก.ย. ครบ 77 จังหวัด)) · "
                f"ใช้เป็นฐานเกณฑ์น้ำท่วมใน fetch_agri_warnings.py"),
        },
        "provinces": provinces,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    ok = sum(1 for v in provinces.values() if v)
    print(f"\nSaved {ok}/{len(provinces)} provinces → {OUTPUT}")


def _selftest():
    # ลำดับการรวม: ฝนกระจุกคนละจุดคนละวัน — จุด A ตก 10 วันแรก จุด B ตก 10 วันที่สอง
    # p90 ของ 2 จุด = 0.9 ของค่าสูง → รายวันได้ 9 ทั้งสองวัน รวม 18
    # ถ้ารวมรายจุดก่อน (ลำดับผิด v2) จะได้ p90(10, 10) = 10 → ฐานต่ำเกือบครึ่ง
    yr = {2024: [[(9, 10.0), (9, 0.0)], [(9, 0.0), (9, 10.0)]]}
    got = weekly_normal(yr)["9"]
    assert got == round(18 / WEEKS_PER_MONTH, 1), got
    assert got != round(10 / WEEKS_PER_MONTH, 1)
    # เดือนนอกฤดูไม่หลุดเข้ามา
    assert "12" not in weekly_normal({2024: [[(12, 5.0)], [(12, 5.0)]]})

    full = {y: [[(9, 1.0)]] * 6 for y in range(N_YEARS)}
    assert points_complete(full, 6)
    assert not points_complete({y: v for y, v in list(full.items())[:-1]}, 6)   # ขาดหนึ่งปี
    short = dict(full); short[0] = short[0][:3]
    assert not points_complete(short, 6)                                     # ปีหนึ่งได้แค่ 3 จุด
    assert not points_complete({}, 0)

    cur = {"rain_normal_method": NORMAL_METHOD, "base_years": base_years}
    assert is_current(cur)
    assert not is_current({**cur, "base_years": [y - 1 for y in base_years]})  # หน้าต่างเลื่อน
    assert not is_current({**cur, "rain_normal_method": "v2"})                 # เปลี่ยนวิธี
    assert not is_current({})                                                  # record เก่าไม่มีป้าย
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
