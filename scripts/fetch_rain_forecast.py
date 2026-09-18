#!/usr/bin/env python3
"""
Fetch 7-day FORECAST rainfall per province from Open-Meteo (free, no API key).
Runs daily via GitHub Actions at 07:00 UTC (14:00 BKK).

Multi-point sampling: แต่ละจังหวัดดึงพยากรณ์ ≤6 จุดกระจายในเขตจังหวัด
(deterministic grid — riceutils.load_sample_points) แล้วสรุปรายวันด้วย p90
ข้ามจุด เพื่อจับฝนกระจุกเฉพาะจุด (orographic เช่น กาญจนบุรี/ตาก แถบเทือกเขา
ชายแดน) ที่ centroid จุดเดียวมองไม่เห็น — p90 ไวกว่าค่าเฉลี่ยแต่ไม่ตื่นตูมเท่า max

Uses Open-Meteo batch API — ~440 points in ~11 API calls (~40 sec total).
Variable: precipitation_sum (rain + showers + snow, daily sum in mm)

Output: data/rain-forecast.json
Shape ไม่เปลี่ยนจากเดิม: provinces[name] = {rain_7d, values[7]} — downstream
(index.html, fetch_agri_warnings.py) ใช้ต่อได้โดยไม่ต้องแก้
"""
import json, os, re, statistics, sys, time
import requests
from riceutils import bkk_today, load_sample_points, percentile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DAYS       = 7           # next N days forecast
OUTPUT     = "data/rain-forecast.json"
API_URL    = "https://api.open-meteo.com/v1/forecast"
BATCH_SIZE = 40          # sample points per request
MAX_RETRY  = 3
TIMEOUT    = 60          # seconds per batch request
PCTL       = 90          # percentile ข้ามจุดตัวอย่างรายวัน (100 = max)


# ── Fetch one batch of sample points in a single API call ───────────────────
def fetch_batch(batch_pts):
    """batch_pts: list of (province, {'lat','lon'}) → list of Open-Meteo results"""
    lats = ",".join(str(pt["lat"]) for _, pt in batch_pts)
    lons = ",".join(str(pt["lon"]) for _, pt in batch_pts)

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
            # 5xx ถอยยาวเหมือน 429 — 17 ก.ย. 69 batch โดน 503 แล้ว retry ห่าง 5 วิ หมด 3 ครั้งทันที
            if r.status_code == 429 or r.status_code >= 500:
                wait = 60 * (attempt + 1)
                print(f"  {r.status_code} → wait {wait}s ...", flush=True)
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


def incomplete_provinces(series, sample_pts):
    """จังหวัดที่ได้จุดตัวอย่างไม่ครบ — ห้ามเขียนผลของจังหวัดพวกนี้

    ได้ไม่ครบแล้วยังคิด p90 ต่อ = ค่าจากจุดที่เหลือ ซึ่งไม่ใช่ตัวเลขเดียวกับวันอื่น
    ได้ศูนย์จุด = จังหวัดหายจากไฟล์ แล้วหายจาก layer เตือนภัยด้วย เพราะ
    fetch_agri_warnings.py วนตามจังหวัดในไฟล์นี้ (17 ก.ย. 69 หายไป 13 จังหวัด
    อีก 4 ได้ p90 จากจุดไม่ครบ ช่วงที่ ปภ. เตือนทั้งประเทศพอดี)"""
    return sorted(n for n, pts in sample_pts.items() if len(series.get(n, [])) != len(pts))


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    sample_pts = load_sample_points()
    today      = bkk_today()
    names      = sorted(sample_pts.keys())

    # flatten: [(province, {'lat','lon'}), ...] เรียงตามจังหวัดเพื่อความ deterministic
    flat = [(name, pt) for name in names for pt in sample_pts[name]]

    # per-province daily series ของแต่ละจุด: {name: [[7 วัน], [7 วัน], ...]}
    series       = {name: [] for name in names}
    shared_dates = None

    total_batches = (len(flat) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Fetching {len(flat)} sample points across {len(names)} provinces "
          f"in {total_batches} batch(es) of ≤{BATCH_SIZE} ...")

    pending = [(i // BATCH_SIZE + 1, flat[i : i + BATCH_SIZE]) for i in range(0, len(flat), BATCH_SIZE)]
    # รอบสอง: batch ที่ล้มลองใหม่หลังพัก — ต้นทางล่มชั่วคราวเป็นเรื่องปกติ
    for round_no, pause in ((1, 0), (2, 120)):
        if not pending:
            break
        if pause:
            print(f"retry {len(pending)} failed batch(es) after {pause}s ...", flush=True)
            time.sleep(pause)
        failed = []
        for batch_num, batch in pending:
            print(f"Batch {batch_num}/{total_batches}: {batch[0][0]} … {batch[-1][0]} ({len(batch)} pts)")
            try:
                data = fetch_batch(batch)
                if len(data) != len(batch):
                    raise RuntimeError(f"got {len(data)} results for {len(batch)} points")
                rows = []
                for j, (name, _pt) in enumerate(batch):
                    daily = data[j]["daily"]
                    rows.append((name, daily["time"][:DAYS],
                                 [v if v is not None else 0.0 for v in daily["precipitation_sum"][:DAYS]]))
                for name, dates, values in rows:   # เพิ่มทีเดียวทั้ง batch — ไม่ครึ่งๆ กลางๆ
                    if shared_dates is None:
                        shared_dates = dates
                    series[name].append(values)
            except Exception as e:
                print(f"  ✗ batch {batch_num} failed (round {round_no}): {e}", file=sys.stderr)
                failed.append((batch_num, batch))
            time.sleep(1)
        pending = failed

    # ── Aggregate: daily p90 across sample points per province ──────────────
    provinces_out = {}
    for name in names:
        pt_series = series[name]
        if not pt_series:
            continue  # ทุกจุดของจังหวัดนี้ fail
        n_days = min(DAYS, min(len(s) for s in pt_series))
        values = [round(percentile([s[d] for s in pt_series], PCTL), 1)
                  for d in range(n_days)]
        rain_7d = round(sum(values), 1)
        provinces_out[name] = {"rain_7d": rain_7d, "values": values}
        print(f"  ✓ {name}: {rain_7d} mm (p{PCTL} of {len(pt_series)} pts)")

    bad = incomplete_provinces(series, sample_pts)
    if bad:
        msg = (f"พยากรณ์ไม่ครบ {len(bad)}/{len(names)} จังหวัด ({', '.join(bad)}) — "
               f"ไม่เขียนทับ {OUTPUT} ให้ layer ใช้ไฟล์เดิมที่ครบ (ช่วงวันที่ติดอยู่ใน _meta.dates)")
        if os.path.exists(OUTPUT):
            print(f"::warning::{msg}")   # ขึ้นเตือนบนหน้า run ของ GitHub Actions
            print(msg, file=sys.stderr)
            return
        print(f"ERROR: {msg} และไม่มีไฟล์เดิม", file=sys.stderr)
        sys.exit(1)

    result = {
        "_meta": {
            "source":  "Open-Meteo",
            "updated": today,
            "days":    DAYS,
            "dates":   shared_dates or [],
            "method":  f"p{PCTL} of ≤6 sample points per province (deterministic grid)",
            "note":    (
                f"พยากรณ์ปริมาณฝนสะสม {DAYS} วันข้างหน้า รายจังหวัด "
                f"(p{PCTL} จากหลายจุดตัวอย่างในเขตจังหวัด — จับฝนกระจุกเฉพาะจุดได้) · "
                "Open-Meteo Forecast API · ฟรี ไม่ต้อง API key · อัปเดตทุกวัน"
            ),
        },
        "provinces": provinces_out,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved {len(provinces_out)}/{len(names)} provinces → {OUTPUT}")


def _selftest():
    pts = {"A": [1, 2, 3], "B": [1, 2]}
    assert incomplete_provinces({"A": [[0]] * 3, "B": [[0]] * 2}, pts) == []
    assert incomplete_provinces({"A": [[0]] * 2, "B": [[0]] * 2}, pts) == ["A"]   # จุดไม่ครบ
    assert incomplete_provinces({"A": [[0]] * 3}, pts) == ["B"]                     # หายทั้งจังหวัด
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
