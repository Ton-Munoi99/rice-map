#!/usr/bin/env python3
"""
Fetch active tropical cyclone alerts near Thailand from GDACS (free RSS, no API key).
Output: data/storm-alerts.json
"""
import os, sys, math, json, requests
import xml.etree.ElementTree as ET
from riceutils import bkk_today, haversine_km

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUTPUT = os.path.join(DATA, "storm-alerts.json")

TH_CENTER = (13.0, 101.0)   # lat, lon — ศูนย์กลางประเทศไทย
NEAR_THRESHOLD_KM = 2500    # แสดงพายุที่อยู่ในรัศมีนี้
GDACS_URL = "https://www.gdacs.org/xml/rss.xml"

# ชนิดพายุ (ภาษาอังกฤษใน GDACS → ไทย/อังกฤษที่แสดง)
STORM_TYPE_MAP = {
    "Tropical Depression":   ("ดีเปรสชั่น",      "Tropical Depression"),
    "Tropical Storm":        ("พายุโซนร้อน",     "Tropical Storm"),
    "Typhoon":               ("ไต้ฝุ่น",         "Typhoon"),
    "Super Typhoon":         ("ซูเปอร์ไต้ฝุ่น",  "Super Typhoon"),
    "Cyclone":               ("ไซโคลน",          "Cyclone"),
    "Hurricane":             ("เฮอริเคน",        "Hurricane"),
    "Severe Cyclonic Storm": ("พายุหมุน",        "Severe Cyclonic Storm"),
}

# ระดับเตือนภัย GDACS → ไอคอน + คำ
ALERT_MAP = {
    "Red":    {"level": "high",   "icon": "🔴", "th": "อันตราย",  "en": "Dangerous"},
    "Orange": {"level": "medium", "icon": "🟠", "th": "เฝ้าระวัง", "en": "Watch"},
    "Green":  {"level": "low",    "icon": "🟡", "th": "ติดตาม",   "en": "Monitor"},
}

# ทิศ (ไทย, อังกฤษ) — เรียงตามเข็มทิศ เริ่มที่เหนือ
DIRECTIONS = [
    ("เหนือ", "N"), ("ตะวันออกเฉียงเหนือ", "NE"), ("ตะวันออก", "E"),
    ("ตะวันออกเฉียงใต้", "SE"), ("ใต้", "S"), ("ตะวันตกเฉียงใต้", "SW"),
    ("ตะวันตก", "W"), ("ตะวันตกเฉียงเหนือ", "NW"),
]

NS = {
    "gdacs":  "http://www.gdacs.org",
    "georss": "http://www.georss.org/georss",
}


def fetch_gdacs_storms():
    try:
        r = requests.get(GDACS_URL, timeout=20, headers={"User-Agent": "RiceMap/1.0"})
        r.raise_for_status()
        items = ET.fromstring(r.content).findall(".//item")
        print(f"GDACS RSS: {len(items)} total events")
    except Exception as e:
        print(f"GDACS error: {e}")
        return []

    storms = []
    for item in items:
        etype = item.find("gdacs:eventtype", NS)
        if etype is None or etype.text != "TC":
            continue
        is_current = item.find("gdacs:iscurrent", NS)
        if is_current is not None and is_current.text.lower() == "false":
            continue

        point = item.find("georss:point", NS)
        if point is None or not point.text:
            continue
        parts = point.text.strip().split()
        if len(parts) < 2:
            continue
        lat, lon = float(parts[0]), float(parts[1])

        dist_km = haversine_km(TH_CENTER[0], TH_CENTER[1], lat, lon)
        if dist_km > NEAR_THRESHOLD_KM:
            continue

        name_el = item.find("gdacs:eventname", NS)
        name = (name_el.text if name_el is not None else "Unknown").upper()

        alert_el = item.find("gdacs:alertlevel", NS)
        alert = ALERT_MAP.get(alert_el.text if alert_el is not None else "Green", ALERT_MAP["Green"])

        severity_el = item.find("gdacs:severity", NS)
        raw_type = (severity_el.text if severity_el is not None else "") or \
                   (item.findtext("description") or "")
        type_th, type_en = "พายุหมุนเขตร้อน", "Tropical Cyclone"
        for en_key, (th_val, en_val) in STORM_TYPE_MAP.items():
            if en_key.lower() in raw_type.lower():
                type_th, type_en = th_val, en_val
                break

        # ทิศของพายุเทียบกับไทย (ทิศที่พายุอยู่ ไม่ใช่ทิศที่กำลังเคลื่อน — GDACS ไม่ให้ track vector)
        bearing = math.degrees(math.atan2(TH_CENTER[1] - lon, TH_CENTER[0] - lat)) % 360
        dir_th, dir_en = DIRECTIONS[round(bearing / 45) % 8]

        storms.append({
            "name":         name,
            "type_th":      type_th,
            "type_en":      type_en,
            "alert_icon":   alert["icon"],
            "alert_th":     alert["th"],
            "alert_en":     alert["en"],
            "distance_km":  round(dist_km),
            "direction_th": dir_th,
            "direction_en": dir_en,
        })
        print(f"  Storm: {name} ({type_th}) | {dist_km:.0f}km | {alert['th']}")

    storms.sort(key=lambda s: s["distance_km"])
    return storms


def main():
    print("Fetching GDACS storm data...")
    storms = fetch_gdacs_storms()

    output = {
        "_meta": {
            "source":  "GDACS — Global Disaster Alert and Coordination System",
            "updated": bkk_today(),
            "storms_near_thailand": len(storms),
        },
        "storms": storms,
    }

    os.makedirs(DATA, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved → {OUTPUT}  ({len(storms)} storms near Thailand)")


if __name__ == "__main__":
    main()
