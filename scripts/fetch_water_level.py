#!/usr/bin/env python3
"""
Fetch real-time river/canal water-level stations from ThaiWater (HII/สสน.).
Free, no API key. ~754 telemetry stations updated continuously.

แสดงเป็นจุด (point overlay) บนแผนที่ Rice Map ให้ชาวนาเห็นระดับน้ำในแม่น้ำ/คลอง
จุดจริงใกล้นาตัวเอง (ไม่ใช่ค่าเฉลี่ยรายจังหวัด)

situation_level: 5=ล้นตลิ่ง 4=มาก 3=ปกติ 2=น้อย 1=น้อยวิกฤต

Output: data/water-level.json
"""
import json, os, sys
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from riceutils import http, km_outside, load_province_bbox, loc, num2

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
OUTPUT  = "data/water-level.json"

# ต้นทางติดชื่อจังหวัดผิดกับบางสถานี — เจอที่ห่างจากจังหวัดที่อ้างถึง 385 กม.
# ("บ้านมีชัย" ระบุหนองคาย แต่พิกัดอยู่กลางประเทศ) ถ้าปล่อยไว้ หมุดจะไปโผล่ผิดจังหวัด
# และการนับ "สถานีเฝ้าระวังในจังหวัดนี้" จะผิดตาม · 50 กม. เผื่อสถานีที่อยู่ชายขอบจริงๆ
MAX_KM_OUTSIDE = 50


def main():
    print(f"Fetching ThaiWater stations from {API_URL} ...")
    r = http().get(API_URL, timeout=60)
    r.raise_for_status()
    rows = r.json()["waterlevel_data"]["data"]
    print(f"  total rows: {len(rows)}")

    bbox_by_prov, th2en, _ = load_province_bbox()
    stations, dropped = [], []
    for r in rows:
        st = r.get("station") or {}
        lat = num2(st.get("tele_station_lat"))
        lon = num2(st.get("tele_station_long"))
        if lat is None or lon is None:
            continue   # ข้ามสถานีที่ไม่มีพิกัด
        name = st.get("tele_station_name") or {}
        geo  = r.get("geocode") or {}

        # พิกัดต้องอยู่ในจังหวัดที่ต้นทางระบุจริง ไม่งั้นหมุดไปโผล่ผิดที่
        prov_th = loc(geo.get("province_name"), "th")
        prov_en = loc(geo.get("province_name"), "en") or th2en.get(prov_th, "")
        bbox = bbox_by_prov.get(prov_en)
        if bbox:
            off = km_outside(lat, lon, bbox)
            if off > MAX_KM_OUTSIDE:
                dropped.append((name.get("th") or "?", prov_th, round(off)))
                continue

        level = r.get("situation_level")

        # สถานีที่ต้นทางไม่ส่ง situation_level (628/1422) จะส่ง diff_wl_bank เป็นค่าระดับ
        # น้ำทะเลปานกลางแทนส่วนต่างจากตลิ่ง แล้วติดป้าย "ล้นตลิ่ง (ม.)" มาด้วย — เช่นสถานี
        # ริมโขงที่รายงาน "ล้นตลิ่ง 215 เมตร" ค่าพวกนี้เชื่อไม่ได้ ตัดทิ้งไปเลยดีกว่าปล่อยให้
        # หน้าเว็บขึ้นว่า "ไม่มีข้อมูล · ล้นตลิ่ง" พร้อมกัน
        trusted_bank = level is not None
        msl = num2(r.get("waterlevel_msl"))
        msl_prev = num2(r.get("waterlevel_msl_previous"))

        stations.append({
            "id":          r.get("id"),
            "name_th":     name.get("th") or "",
            "name_en":     name.get("en") or "",
            "lat":         lat,
            "lon":         lon,
            "river":       r.get("river_name") or "",
            "level":       level,
            "pct":         num2(r.get("storage_percent")),
            # ระดับน้ำทะเลปานกลาง + ค่าก่อนหน้า — ใช้ดู "กำลังขึ้น/ลง" ได้แม้ไม่มี level
            # (สถานีแม่น้ำโขงมีแค่ค่านี้ ซึ่งเป็นตัวเดียวที่บอกแนวโน้มน้ำโขงหนุนได้)
            "msl":         msl,
            "msl_prev":    msl_prev,
            "diff":        num2(r.get("diff_wl_bank")) if trusted_bank else None,
            "diff_text":   (r.get("diff_wl_bank_text") or "") if trusted_bank else "",
            "dt":          r.get("waterlevel_datetime") or "",
            "agency":      loc((r.get("agency") or {}).get("agency_shortname"), "th"),
            "province_th": prov_th,
            "province_en": loc(geo.get("province_name"), "en"),
            "amphoe_th":   loc(geo.get("amphoe_name"), "th"),
            "amphoe_en":   loc(geo.get("amphoe_name"), "en"),
        })

    counts = Counter(s["level"] for s in stations if s["level"] is not None)
    counts_by_level = {str(k): counts[k] for k in sorted(counts)}
    n_alert = sum(1 for s in stations if (s["level"] or 0) >= 4)

    output = {
        "_meta": {
            "updated_at":  datetime.now(timezone.utc).isoformat(),
            "source":      "ThaiWater (สสน./HII) — api-v3.thaiwater.net",
            "source_en":   "Hydro-Informatics Institute (HII) — ThaiWater open data",
            "total":       len(stations),
            "n_alert":     n_alert,
            "counts_by_level": counts_by_level,
            "note": "ระดับน้ำในแม่น้ำ/คลอง realtime รายสถานี · 5=ล้นตลิ่ง 4=มาก 3=ปกติ 2=น้อย 1=น้อยวิกฤต",
        },
        "stations": stations,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    if dropped:
        print(f"  ⚠️ ตัดออก {len(dropped)} สถานี — พิกัดห่างจังหวัดที่ระบุเกิน {MAX_KM_OUTSIDE} กม.")
        for nm, pv, km in sorted(dropped, key=lambda x: -x[2])[:5]:
            print(f"      {nm[:24]} (ระบุ {pv}) ห่าง {km} กม.")
    print(f"  by situation_level: {counts_by_level}")
    print(f"  alert (level 4-5): {n_alert}")
    print(f"\nSaved {len(stations)} stations → {OUTPUT}")


if __name__ == "__main__":
    main()
