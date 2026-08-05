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
from datetime import date
from riceutils import load_sample_points

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DAYS       = 7           # next N days forecast
OUTPUT     = "data/rain-forecast.json"
API_URL    = "https://api.open-meteo.com/v1/forecast"
BATCH_SIZE = 40          # sample points per request
MAX_RETRY  = 3
TIMEOUT    = 60          # seconds per batch request
PCTL       = 90          # percentile ข้ามจุดตัวอย่างรายวัน (100 = max)


def percentile(values, p):
    """Linear-interpolation percentile (นิยามเดียวกับ numpy default)"""
    # ponytail: stdlib quantiles แทนสูตรเขียนเอง — พิสูจน์แล้วค่าตรงกันทุกกรณี 2-6 จุด
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[p - 1]


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
    sample_pts = load_sample_points()
    today      = date.today().isoformat()
    names      = sorted(sample_pts.keys())

    # flatten: [(province, {'lat','lon'}), ...] เรียงตามจังหวัดเพื่อความ deterministic
    flat = [(name, pt) for name in names for pt in sample_pts[name]]

    # per-province daily series ของแต่ละจุด: {name: [[7 วัน], [7 วัน], ...]}
    series       = {name: [] for name in names}
    shared_dates = None
    failed_provs = set()

    total_batches = (len(flat) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Fetching {len(flat)} sample points across {len(names)} provinces "
          f"in {total_batches} batch(es) of ≤{BATCH_SIZE} ...")

    for i in range(0, len(flat), BATCH_SIZE):
        batch = flat[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"Batch {batch_num}/{total_batches}: {batch[0][0]} … {batch[-1][0]} ({len(batch)} pts)")

        try:
            data = fetch_batch(batch)
            for j, (name, _pt) in enumerate(batch):
                daily  = data[j]["daily"]
                dates  = daily["time"][:DAYS]
                values = [v if v is not None else 0.0
                          for v in daily["precipitation_sum"][:DAYS]]
                if shared_dates is None:
                    shared_dates = dates
                series[name].append(values)
        except Exception as e:
            print(f"  ✗ batch {batch_num} failed: {e}", file=sys.stderr)
            failed_provs.update(name for name, _ in batch)

        if i + BATCH_SIZE < len(flat):
            time.sleep(1)   # 1s pause between batches

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

    if not provinces_out:
        print("ERROR: No data fetched!", file=sys.stderr)
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

    ok      = len(provinces_out)
    missing = sorted(set(names) - set(provinces_out))
    print(f"\n✅ Saved {ok} provinces → {OUTPUT}")
    if failed_provs:
        print(f"⚠️  Batches failed touching: {', '.join(sorted(failed_provs))}", file=sys.stderr)
    if missing:
        print(f"⚠️  Missing provinces ({len(missing)}): {', '.join(missing)}", file=sys.stderr)
        if len(missing) > ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
