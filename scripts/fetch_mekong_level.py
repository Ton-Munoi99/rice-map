#!/usr/bin/env python3
"""
Mekong mainstream water levels from the MRC near-real-time telemetry API.

Why this exists: the flood layer is driven by rainfall, but the Mekong rises from
upstream flow. A riverside province can be dry and still flood — in Aug 2569 the
news reported Nakhon Phanom at 12.01 m against a 12.00 m critical level while our
own alerts only saw local rain. ThaiWater has no mainstream Mekong gauge, so that
whole mechanism was invisible.

MRC publishes it, with the thresholds the Thai authorities quote: floodStage for
Nakhon Phanom is 12.0, exactly the figure in that report. It also supplies alarmStage
and a station status, which ThaiWater omits for 628 of its stations.

Upstream stations (China / Lao PDR) are kept as well. They lead the Thai reach by
days and are the only early signal for a rise that has not arrived yet.

API: no key, no registration, ~15-minute cadence.
Output: data/mekong-level.json

Run: python scripts/fetch_mekong_level.py
"""
import csv
import json
import math
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from riceutils import km_outside, load_province_bbox

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_URL = ("https://api.mrcmekong.org/api/v1/time-series/telemetry/recent/stations")
TIMEOUT = 60

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(_ROOT, "data", "mekong-level.json")
GEO_PATH = os.path.join(_ROOT, "data", "districts-geo.json")
CSV_PATH = os.path.join(_ROOT, "rice-data.csv")

# ยอมให้สถานีอยู่นอกกรอบจังหวัดได้เท่านี้ — สถานีวัดโขงตั้งริมน้ำซึ่งเป็นเส้นเขตแดน
# จึงมักหลุดกรอบไปเล็กน้อย แต่ถ้าหลุดมากแปลว่าแมปผิดจังหวัด
MAX_KM_OUTSIDE = 30

def province_for(lat, lon, bboxes):
    """จังหวัดจากพิกัดจริง — ไม่เดาจากชื่อสถานี

    กรอบจังหวัดซ้อนกันได้ (หนองคายกินพื้นที่บึงกาฬ) เวลาจุดตกอยู่ในหลายกรอบพร้อมกัน
    ระยะห่างเป็น 0 เท่ากันหมด จึงตัดสินด้วยกรอบที่จุดศูนย์กลางใกล้กว่า = จำเพาะกว่า
    """
    scored = []
    for p, b in bboxes.items():
        d = km_outside(lat, lon, b)
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        to_center = math.hypot((cx - lon) * 111 * math.cos(math.radians(lat)),
                               (cy - lat) * 111)
        scored.append((d, to_center, p))
    scored.sort()
    d, _, p = scored[0]
    return p if d <= MAX_KM_OUTSIDE else None


def status_of(wl, alarm, flood):
    """คำนวณเองจากระดับ+เกณฑ์ ไม่พึ่ง lastStatus อย่างเดียว เพราะบางสถานีเป็น NA
    ทั้งที่มีทั้งค่าและเกณฑ์ครบ"""
    if wl is None:
        return "nodata"
    if flood is not None and wl >= flood:
        return "flood"
    if alarm is not None and wl >= alarm:
        return "alarm"
    if alarm is None and flood is None:
        return "nothreshold"
    return "normal"


def fetch():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "RiceMap/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def main():
    try:
        rows = fetch()
    except Exception as e:
        print(f"[ERROR] MRC API fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    bboxes, _, th_by_en = load_province_bbox()
    mekong = [s for s in rows if (s.get("river") or "") == "Mekong"]
    print(f"MRC: {len(rows)} stations, {len(mekong)} on the Mekong mainstream")

    out, n_thai, unmapped = [], 0, []
    for s in mekong:
        lat, lon = s.get("latitude"), s.get("longitude")
        if lat is None or lon is None:
            continue
        wl = s.get("waterLevel")
        alarm = s.get("alarmStage")
        flood = s.get("floodStage")
        is_thai = s.get("country") == "Thailand"

        prov_en = province_for(lat, lon, bboxes) if is_thai else None
        if is_thai:
            n_thai += 1
            if not prov_en:
                unmapped.append(s.get("name"))

        out.append({
            "id": s.get("stationId"),
            "name": s.get("name"),
            "country": s.get("country"),
            "province_en": prov_en,
            "province_th": th_by_en.get(prov_en) if prov_en else None,
            "lat": lat,
            "lon": lon,
            "level_m": wl,
            "alarm_m": alarm,
            "flood_m": flood,
            # เหลืออีกกี่เมตรถึงระดับวิกฤต — ติดลบ = เลยไปแล้ว
            "to_flood_m": round(flood - wl, 2) if (wl is not None and flood is not None) else None,
            "status": status_of(wl, alarm, flood),
            "rain_24h": s.get("rainFall24H"),
            "msl_m": s.get("meanSeaLevel"),
            "measured_at": s.get("lastMeasurement"),
        })

    # เรียงตามน้ำไหล: จีน → ลาว/ไทย → กัมพูชา → เวียดนาม (ละติจูดมากไปน้อย)
    out.sort(key=lambda x: -(x["lat"] or 0))

    thai = [s for s in out if s["country"] == "Thailand"]
    n_flood = sum(1 for s in out if s["status"] == "flood")
    n_alarm = sum(1 for s in out if s["status"] == "alarm")

    result = {
        "_meta": {
            "source": "Mekong River Commission (MRC) — near real-time telemetry",
            "source_url": "https://monitoring.mrcmekong.org/",
            "api": API_URL,
            "updated": max((s["measured_at"] or "") for s in out) if out else "",
            "total": len(out),
            "thai_stations": len(thai),
            "flood": n_flood,
            "alarm": n_alarm,
            "note": ("ระดับน้ำโขงสายหลักจาก MRC พร้อมเกณฑ์เตือน/วิกฤตของแต่ละสถานี · "
                     "โขงขึ้นจากการไหลของต้นน้ำ ไม่ใช่ฝนในพื้นที่ — layer เตือนน้ำท่วมที่อิงฝน "
                     "จับกลไกนี้ไม่ได้ · สถานีเหนือไทย (จีน/ลาว) นำหน้าไทยหลายวัน ใช้ดูล่วงหน้าได้"),
            "note_en": ("Mekong mainstream levels from MRC with each station's alarm and flood "
                        "stage. The Mekong rises from upstream flow, not local rain, so the "
                        "rainfall-driven flood layer cannot see it. Stations upstream of Thailand "
                        "lead the Thai reach by days."),
        },
        "stations": out,
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  Thai stations: {n_thai} (mapped to a province: {sum(1 for s in thai if s['province_en'])})")
    if unmapped:
        print(f"  [WARN] ไม่พบจังหวัดในระยะ {MAX_KM_OUTSIDE} กม.: {unmapped}", file=sys.stderr)
    print(f"  status: flood={n_flood} alarm={n_alarm}")
    for s in thai:
        mark = {"flood": "!!", "alarm": " !"}.get(s["status"], "  ")
        print(f"   {mark} {s['name'][:18]:20} {s['province_th'] or '-':12} "
              f"{s['level_m']} m (flood {s['flood_m']}) {s['status']}")
    print(f"\nWrote {OUTPUT}")


if __name__ == "__main__":
    main()
