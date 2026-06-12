#!/usr/bin/env python3
"""
Fetch real-time flash flood / landslide early warning stations from DWR EWS.
กรมทรัพยากรน้ำ (DWR) — ews.dwr.go.th — ไม่ต้องใช้ API key

สถานะ: 0=ปกติ  1=เฝ้าระวัง  2=เตรียมพร้อม  3=วิกฤต  9=ไม่มีข้อมูล (ข้ามไป)
ประเภท: RF=สถานีวัดฝน  WL=สถานีวัดระดับน้ำ

Output: data/ews.json
"""
import json, sys, io, requests
from datetime import datetime, timezone
from collections import Counter

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API_URL = "https://ews.dwr.go.th/ews/web-service/stn"
OUTPUT  = "data/ews.json"


def _num(v):
    try:
        f = float(v)
        return round(f, 2)
    except (TypeError, ValueError):
        return None


def fetch_stations():
    for attempt in range(3):
        try:
            r = requests.post(
                API_URL,
                headers={"User-Agent": "Mozilla/5.0"},
                data={"action": "LoadStation"},
                timeout=60,
            )
            r.raise_for_status()
            return json.loads(r.content.decode("utf-8"))
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  attempt {attempt+1} failed ({e}) — retrying...", file=sys.stderr)


def main():
    print(f"Fetching EWS DWR stations from {API_URL} ...")
    raw = fetch_stations()
    print(f"  total raw rows: {len(raw)}")

    stations = []
    for s in raw:
        status = int(s.get("status") or 0)
        if status == 9:
            continue   # ไม่มีข้อมูล/ออฟไลน์ — ข้ามไป

        lat = _num(s.get("latitude"))
        lon = _num(s.get("longitude"))
        if lat is None or lon is None:
            continue

        stations.append({
            "stn":      s.get("stn") or "",
            "name":     s.get("name") or "",
            "stn_type": s.get("stn_type") or "",
            "province": s.get("province") or "",
            "amphoe":   s.get("amphoe") or "",
            "tambon":   s.get("tambon") or "",
            "basin":    s.get("main_basin") or "",
            "lat":      lat,
            "lon":      lon,
            "status":   status,
            "warn":     s.get("warn"),
            "rain":     _num(s.get("rain")),
            "rain12h":  _num(s.get("rain12h")),
            "rain07h":  _num(s.get("rain07h")),
            "wl":       s.get("wl") if s.get("wl") not in (None, "N/A") else None,
            "soil":     _num(s.get("soil")),
            "date":     s.get("date") or "",
        })

    counts = Counter(s["status"] for s in stations)
    n_alert = sum(1 for s in stations if s["status"] >= 1)

    output = {
        "_meta": {
            "updated_at":  datetime.now(timezone.utc).isoformat(),
            "source":      "กรมทรัพยากรน้ำ (DWR) — ews.dwr.go.th",
            "source_en":   "Department of Water Resources — Early Warning System",
            "total":       len(stations),
            "n_alert":     n_alert,
            "counts_by_status": {str(k): counts[k] for k in sorted(counts)},
            "note":        "สถานีเตือนภัยน้ำป่า/ดินถล่ม realtime · 1=เฝ้าระวัง 2=เตรียมพร้อม 3=วิกฤต",
        },
        "stations": stations,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  by status: {dict(sorted(counts.items()))}")
    print(f"  active alerts (status 1-3): {n_alert}")
    print(f"\nSaved {len(stations)} stations → {OUTPUT}")


if __name__ == "__main__":
    main()
