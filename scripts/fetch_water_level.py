#!/usr/bin/env python3
"""
Fetch real-time river/canal water-level stations from ThaiWater (HII/สสน.).
Free, no API key. ~754 telemetry stations updated continuously.

แสดงเป็นจุด (point overlay) บนแผนที่ Rice Map ให้ชาวนาเห็นระดับน้ำในแม่น้ำ/คลอง
จุดจริงใกล้นาตัวเอง (ไม่ใช่ค่าเฉลี่ยรายจังหวัด)

situation_level: 5=ล้นตลิ่ง 4=มาก 3=ปกติ 2=น้อย 1=น้อยวิกฤต

Output: data/water-level.json
"""
import json, sys, io, requests
from datetime import datetime, timezone
from collections import Counter

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
OUTPUT  = "data/water-level.json"


def _num(v):
    """แปลงเป็น float แบบปลอดภัย — คืน None ถ้าแปลงไม่ได้"""
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _loc(d, lang):
    """ดึงค่าภาษาจาก localized dict {th,en} — คืน '' ถ้าไม่มี"""
    return (d or {}).get(lang, "") if isinstance(d, dict) else ""


def fetch_rows():
    """ดึงรายการสถานีจาก ThaiWater API (retry 3 ครั้ง)"""
    for attempt in range(3):
        try:
            r = requests.get(API_URL, timeout=60)
            r.raise_for_status()
            return r.json()["waterlevel_data"]["data"]
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  attempt {attempt+1} failed ({e}) — retrying...", file=sys.stderr)


def main():
    print(f"Fetching ThaiWater stations from {API_URL} ...")
    rows = fetch_rows()
    print(f"  total rows: {len(rows)}")

    stations = []
    for r in rows:
        st = r.get("station") or {}
        lat = _num(st.get("tele_station_lat"))
        lon = _num(st.get("tele_station_long"))
        if lat is None or lon is None:
            continue   # ข้ามสถานีที่ไม่มีพิกัด
        name = st.get("tele_station_name") or {}
        geo  = r.get("geocode") or {}
        stations.append({
            "id":          r.get("id"),
            "name_th":     name.get("th") or "",
            "name_en":     name.get("en") or "",
            "lat":         lat,
            "lon":         lon,
            "river":       r.get("river_name") or "",
            "level":       r.get("situation_level"),
            "pct":         _num(r.get("storage_percent")),
            "diff":        _num(r.get("diff_wl_bank")),
            "diff_text":   r.get("diff_wl_bank_text") or "",
            "dt":          r.get("waterlevel_datetime") or "",
            "agency":      _loc((r.get("agency") or {}).get("agency_shortname"), "th"),
            "province_th": _loc(geo.get("province_name"), "th"),
            "province_en": _loc(geo.get("province_name"), "en"),
            "amphoe_th":   _loc(geo.get("amphoe_name"), "th"),
            "amphoe_en":   _loc(geo.get("amphoe_name"), "en"),
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

    print(f"  by situation_level: {counts_by_level}")
    print(f"  alert (level 4-5): {n_alert}")
    print(f"\nSaved {len(stations)} stations → {OUTPUT}")


if __name__ == "__main__":
    main()
