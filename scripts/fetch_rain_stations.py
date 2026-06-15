#!/usr/bin/env python3
"""
Fetch real-time 24-hour rainfall stations from ThaiWater (HII/สสน.).
Free, no API key. ~4,400 telemetry stations updated continuously.

rain_level (เกณฑ์ TMD กรมอุตุนิยมวิทยา):
  0 = ไม่มีฝน (0mm)
  1 = เล็กน้อย (0.1–10mm)
  2 = ปานกลาง (10.1–35mm)
  3 = หนัก (35.1–90mm)
  4 = หนักมาก (90.1–150mm)
  5 = หนักมากสุดขีด (>150mm)

Output: data/rain-stations.json
"""
import json, sys, io, requests
from datetime import datetime, timezone
from collections import Counter

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/rain_24h"
OUTPUT  = "data/rain-stations.json"


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _loc(d, lang):
    return (d or {}).get(lang, "") if isinstance(d, dict) else ""


def rain_level(mm):
    if mm is None or mm <= 0:
        return 0
    if mm <= 10:
        return 1
    if mm <= 35:
        return 2
    if mm <= 90:
        return 3
    if mm <= 150:
        return 4
    return 5


def fetch_rows():
    for attempt in range(3):
        try:
            r = requests.get(API_URL, timeout=60)
            r.raise_for_status()
            return r.json()["data"]
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  attempt {attempt+1} failed ({e}) — retrying...", file=sys.stderr)


def main():
    print(f"Fetching ThaiWater rain_24h from {API_URL} ...")
    rows = fetch_rows()
    print(f"  total rows: {len(rows)}")

    stations = []
    for r in rows:
        st = r.get("station") or {}
        lat = _num(st.get("tele_station_lat"))
        lon = _num(st.get("tele_station_long"))
        if lat is None or lon is None:
            continue
        rain_mm = _num(r.get("rain_24h"))
        geo = r.get("geocode") or {}
        name = st.get("tele_station_name") or {}
        stations.append({
            "id":          r.get("id"),
            "name_th":     _loc(name, "th"),
            "name_en":     _loc(name, "en"),
            "lat":         lat,
            "lon":         lon,
            "rain_24h":    rain_mm,
            "rain_level":  rain_level(rain_mm),
            "province_th": _loc(geo.get("province_name"), "th"),
            "province_en": _loc(geo.get("province_name"), "en"),
            "amphoe_th":   _loc(geo.get("amphoe_name"), "th"),
            "agency":      _loc((r.get("agency") or {}).get("agency_shortname"), "th"),
            "dt":          r.get("rainfall_datetime") or "",
        })

    counts = Counter(s["rain_level"] for s in stations)
    counts_by_level = {str(k): counts[k] for k in sorted(counts)}
    n_heavy = sum(1 for s in stations if s["rain_level"] >= 3)

    output = {
        "_meta": {
            "updated_at":  datetime.now(timezone.utc).isoformat(),
            "source":      "ThaiWater (สสน./HII) — api-v3.thaiwater.net",
            "source_en":   "Hydro-Informatics Institute (HII) — ThaiWater open data",
            "total":       len(stations),
            "n_heavy":     n_heavy,
            "counts_by_level": counts_by_level,
            "note": "ปริมาณฝนสะสม 24 ชม. รายสถานี · 0=ไม่มีฝน 1=เล็กน้อย 2=ปานกลาง 3=หนัก 4=หนักมาก 5=หนักมากสุดขีด (เกณฑ์ TMD)",
        },
        "stations": stations,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  by rain_level: {counts_by_level}")
    print(f"  heavy rain (level 3+): {n_heavy}")
    print(f"\nSaved {len(stations)} stations → {OUTPUT}")


if __name__ == "__main__":
    main()
