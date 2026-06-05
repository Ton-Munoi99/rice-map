#!/usr/bin/env python3
"""
Fetch active storm/cyclone alerts near Thailand from GDACS (free API)
+ derive weather summary from existing data files.
Output: data/storm-alerts.json
"""
import json, os, sys, io, math, requests
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUTPUT = os.path.join(DATA, "storm-alerts.json")

# Thailand bounding box + center
TH_CENTER = (13.0, 101.0)  # lat, lon
TH_BBOX = {"lat_min": 4, "lat_max": 21, "lon_min": 95, "lon_max": 110}
NEAR_THRESHOLD_KM = 2500  # show storms within 2500km

GDACS_URL = "https://www.gdacs.org/xml/rss.xml"

# Storm type Thai names
STORM_TYPE_MAP = {
    "Tropical Depression":   "ดีเปรสชั่น",
    "Tropical Storm":        "พายุโซนร้อน",
    "Typhoon":               "ไต้ฝุ่น",
    "Super Typhoon":         "ซูเปอร์ไต้ฝุ่น",
    "Cyclone":               "ไซโคลน",
    "Hurricane":             "เฮอริเคน",
    "Severe Cyclonic Storm": "พายุหมุน",
}

ALERT_COLOR_MAP = {
    "Red":    {"level": "high",   "icon": "🔴", "th": "อันตราย",   "en": "Dangerous"},
    "Orange": {"level": "medium", "icon": "🟠", "th": "เฝ้าระวัง",  "en": "Watch"},
    "Green":  {"level": "low",    "icon": "🟡", "th": "ติดตาม",    "en": "Monitor"},
}

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def bearing_to_direction(deg):
    dirs = ["เหนือ","ตะวันออกเฉียงเหนือ","ตะวันออก","ตะวันออกเฉียงใต้","ใต้","ตะวันตกเฉียงใต้","ตะวันตก","ตะวันตกเฉียงเหนือ"]
    return dirs[round(deg / 45) % 8]

def fetch_gdacs_storms():
    # XML namespaces used in GDACS RSS feed
    NS = {
        "gdacs":   "http://www.gdacs.org",
        "georss":  "http://www.georss.org/georss",
        "geo":     "http://www.w3.org/2003/01/geo/wgs84_pos#",
    }
    try:
        r = requests.get(GDACS_URL, timeout=20, headers={"User-Agent": "RiceMap/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        print(f"GDACS RSS: {len(items)} total events")
    except Exception as e:
        print(f"GDACS error: {e}")
        return []

    storms = []
    for item in items:
        # Only tropical cyclone events
        etype = item.find("gdacs:eventtype", NS)
        if etype is None or etype.text != "TC":
            continue

        # Skip non-current events
        is_current = item.find("gdacs:iscurrent", NS)
        if is_current is not None and is_current.text.lower() == "false":
            continue

        # Position from georss:point (lat lon)
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
        alert_color = alert_el.text if alert_el is not None else "Green"
        alert_info  = ALERT_COLOR_MAP.get(alert_color, ALERT_COLOR_MAP["Green"])

        # Storm type from severity or description
        severity_el = item.find("gdacs:severity", NS)
        raw_type = severity_el.text if severity_el is not None else ""
        if not raw_type:
            desc_el = item.find("description")
            raw_type = desc_el.text if desc_el is not None else ""

        storm_type_en = "Tropical Cyclone"
        storm_type_th = "พายุหมุนเขตร้อน"
        for en_key, th_val in STORM_TYPE_MAP.items():
            if en_key.lower() in raw_type.lower():
                storm_type_en = en_key
                storm_type_th = th_val
                break

        # Bearing from storm to Thailand center
        d_lat = TH_CENTER[0] - lat
        d_lon = TH_CENTER[1] - lon
        bearing = math.degrees(math.atan2(d_lon, d_lat)) % 360
        direction_th = bearing_to_direction(bearing)

        # Approximate ETA (very rough: assume 20km/h average storm speed)
        eta_hours = round(dist_km / 20)
        approaching = d_lat > 0 or abs(d_lon) < 5  # rough heuristic

        storms.append({
            "name":         name,
            "type_th":      storm_type_th,
            "type_en":      storm_type_en,
            "alert_level":  alert_info["level"],
            "alert_icon":   alert_info["icon"],
            "alert_th":     alert_info["th"],
            "alert_en":     alert_info["en"],
            "distance_km":  round(dist_km),
            "direction_th": direction_th,
            "approaching":  approaching,
            "eta_hours":    eta_hours,
            "lat":          round(lat, 2),
            "lon":          round(lon, 2),
        })
        print(f"  Storm: {name} ({storm_type_th}) | {dist_km:.0f}km | {alert_color}")

    storms.sort(key=lambda s: s["distance_km"])
    return storms

def derive_weather_summary():
    """Derive national weather summary from existing JSON files."""
    summary = {}

    # Alert summary from agri-warnings.json
    try:
        aw = json.load(open(os.path.join(DATA, "agri-warnings.json"), encoding="utf-8"))
        s = aw.get("summary", {})
        summary["flood_high"]   = s.get("high", 0)
        summary["flood_medium"] = s.get("medium", 0)
        summary["flood_low"]    = s.get("low", 0)
        summary["normal"]       = s.get("normal", s.get("none", 0))
        summary["alerts_updated"] = aw.get("_meta", {}).get("updated", "")
    except Exception as e:
        print(f"agri-warnings: {e}")

    # Top rain forecast province
    try:
        fc = json.load(open(os.path.join(DATA, "rain-forecast.json"), encoding="utf-8"))
        provs = fc.get("provinces", {})
        if provs:
            top = max(provs.items(), key=lambda x: x[1].get("rain_7d", 0))
            summary["top_rain_province"] = top[0]
            summary["top_rain_mm"]       = round(top[1].get("rain_7d", 0))
    except Exception as e:
        print(f"rain-forecast: {e}")

    # Average soil moisture
    try:
        sm = json.load(open(os.path.join(DATA, "soil-moisture.json"), encoding="utf-8"))
        vals = [v["smp"] for v in sm.get("provinces", {}).values() if v.get("smp") is not None]
        if vals:
            summary["soil_moisture_avg"] = round(sum(vals) / len(vals), 1)
            summary["soil_updated"] = sm.get("_meta", {}).get("period_end", "")
    except Exception as e:
        print(f"soil-moisture: {e}")

    return summary

def main():
    print("Fetching GDACS storm data...")
    storms = fetch_gdacs_storms()
    print(f"\nDeriving weather summary from existing data...")
    weather_summary = derive_weather_summary()

    output = {
        "_meta": {
            "source_storms":  "GDACS — Global Disaster Alert and Coordination System",
            "source_weather": "Derived from agri-warnings.json + rain-forecast.json + soil-moisture.json",
            "updated":        date.today().isoformat(),
            "storms_near_thailand": len(storms),
        },
        "storms": storms,
        "has_active_storm": len(storms) > 0,
        "weather_summary": weather_summary,
    }

    os.makedirs(DATA, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved → {OUTPUT}")
    print(f"  Storms near Thailand: {len(storms)}")
    if storms:
        for s in storms:
            print(f"    {s['alert_icon']} {s['name']} ({s['type_th']}) — {s['distance_km']}km")

if __name__ == "__main__":
    main()
