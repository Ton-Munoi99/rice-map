#!/usr/bin/env python3
"""
fetch_tmd_forecast.py
----------------------
พยากรณ์ฝนราย 48 ชั่วโมงข้างหน้า ความละเอียด 2 กม. จาก TMD NWP API (hourly, by region)

เสริม (ไม่แทน) เตือนภัยน้ำท่วม 7 วันที่มีอยู่ (fetch_agri_warnings.py) — TMD hourly
พยากรณ์ได้สูงสุดแค่ 48 ชั่วโมงเท่านั้น (เอกสารเขียนไว้ชัดทั้ง "สูงสุด 48 ชั่วโมง"
ในคำอธิบายและ duration parameter — ไม่ใช่ 72 ชม. ตามที่เคยเข้าใจผิดไว้ก่อนหน้า)

ต้องมี GitHub secret TMD_API_TOKEN (OAuth access token จาก data.tmd.go.th/nwpapi/register)
ไม่มี = script fail ทันที ไม่เขียนไฟล์ทับของเดิม

Endpoint: /nwpapi/v1/forecast/location/hourly/region — ดึงทีละภาค (6 ครั้ง) แทนที่จะ
ยิงทีละจังหวัด (77 ครั้ง) เพราะ API คืนทุกจังหวัดในภาคเดียวมาในคำขอเดียว

Run: TMD_API_TOKEN=xxx python scripts/fetch_tmd_forecast.py
"""
import json
import os
import sys
import time
from datetime import date

import requests

from riceutils import PROVINCE_TH_EN

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_URL   = "https://data.tmd.go.th/nwpapi/v1/forecast/location/hourly/region"
OUTPUT    = "data/tmd-forecast.json"
DURATION  = 48   # ชั่วโมง — ค่าสูงสุดที่ TMD hourly API รองรับ
REGIONS   = ["C", "N", "NE", "E", "S", "W"]
REGION_TH = {
    "C": "ภาคกลาง", "N": "ภาคเหนือ", "NE": "ภาคตะวันออกเฉียงเหนือ",
    "E": "ภาคตะวันออก", "S": "ภาคใต้", "W": "ภาคตะวันตก",
}
MAX_RETRY = 3
TIMEOUT   = 30


def fetch_region(region, token):
    """คืน JSON ของภาคเดียว — retry เมื่อ 429, พัง (raise) ทันทีเมื่อ 401 เพราะ retry ไม่ช่วย"""
    headers = {"accept": "application/json", "authorization": f"Bearer {token}"}
    params = {"region": region, "fields": "rain", "duration": DURATION}
    for attempt in range(MAX_RETRY):
        r = requests.get(API_URL, headers=headers, params=params, timeout=TIMEOUT)
        if r.status_code == 401:
            raise RuntimeError("401 Unauthorized — TMD_API_TOKEN ไม่ถูกต้องหรือหมดอายุ")
        if r.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"  429 rate-limit -> wait {wait}s ...", flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"region {region} failed after {MAX_RETRY} attempts (rate-limited)")


def main():
    token = os.environ.get("TMD_API_TOKEN")
    if not token:
        print("[ERROR] TMD_API_TOKEN ไม่ได้ตั้งค่า — ตั้งเป็น GitHub secret ก่อนรัน", file=sys.stderr)
        sys.exit(1)

    provinces_out = {}
    failed_regions = []

    for i, region in enumerate(REGIONS):
        print(f"Fetching {REGION_TH[region]} ({region}) ...")
        try:
            data = fetch_region(region, token)
        except Exception as e:
            print(f"  x {region}: {e}", file=sys.stderr)
            failed_regions.append(region)
            continue

        # ชื่อคีย์ไม่ตรงกันระหว่าง endpoint ของ TMD เอง (region: "WeatherForecast",
        # place/at: "WeatherForcasts" สะกดผิด) — รับทั้งสองแบบกันเหนียว
        items = data.get("WeatherForecast") or data.get("WeatherForcasts") or []
        if not items:
            # ยังไม่เคยเห็น response จริง — log โครงสร้างไว้เพื่อ debug รอบแรก
            print(f"  ! response keys: {list(data.keys())} | preview: {json.dumps(data, ensure_ascii=False)[:500]}",
                  file=sys.stderr)
        n_ok = 0
        for item in items:
            th_name = (item.get("location") or {}).get("province")
            en_name = PROVINCE_TH_EN.get(th_name)
            if not en_name:
                print(f"  ! ไม่รู้จักจังหวัด '{th_name}' — ข้าม", file=sys.stderr)
                continue
            hourly = [
                {"time": f.get("time"), "rain_mm": (f.get("data") or {}).get("rain") or 0.0}
                for f in item.get("forecasts", [])
            ]
            if not hourly:
                continue
            provinces_out[en_name] = {
                "rain_48h_mm": round(sum(h["rain_mm"] for h in hourly), 1),
                "rain_24h_mm": round(sum(h["rain_mm"] for h in hourly[:24]), 1),
                "hourly": hourly,
            }
            n_ok += 1
        print(f"  ok {n_ok} จังหวัด")

        if i < len(REGIONS) - 1:
            time.sleep(1)

    if not provinces_out:
        print("[ERROR] ไม่ได้ข้อมูลจังหวัดใดเลย", file=sys.stderr)
        sys.exit(1)

    result = {
        "_meta": {
            "updated": date.today().isoformat(),
            "source": "TMD NWP API — hourly forecast, 2km domain",
            "source_url": "https://data.tmd.go.th/nwpapi/doc/apidoc/location/forecast_hourly.html",
            "duration_hours": DURATION,
            "note_th": (
                f"พยากรณ์ฝนรายชั่วโมงล่วงหน้า {DURATION} ชั่วโมง (2 วัน) ความละเอียดพื้นที่ 2 กม. "
                "จากกรมอุตุนิยมวิทยา — เสริมเตือนภัยน้ำท่วม 7 วันที่มีอยู่ (ไม่ได้แทน เพราะ "
                f"TMD hourly พยากรณ์ได้สูงสุดแค่ {DURATION} ชม.)"
            ),
            "note_en": f"{DURATION}-hour hourly rain forecast (2km resolution) from Thai Meteorological Department.",
        },
        "provinces": provinces_out,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    missing = sorted(set(PROVINCE_TH_EN.values()) - set(provinces_out))
    print(f"\nSaved {len(provinces_out)} provinces -> {OUTPUT}")
    if failed_regions:
        print(f"WARNING: ภาคที่ดึงไม่สำเร็จ: {', '.join(failed_regions)}", file=sys.stderr)
    if missing:
        print(f"WARNING: จังหวัดที่ไม่มีข้อมูล ({len(missing)}): {', '.join(missing)}", file=sys.stderr)
    if failed_regions and len(failed_regions) >= len(REGIONS) // 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
