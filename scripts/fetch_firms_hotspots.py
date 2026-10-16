#!/usr/bin/env python3
"""
fetch_firms_hotspots.py
-----------------------
จุดความร้อน (active fire) จากดาวเทียม NASA/NOAA VIIRS ย้อนหลัง 7 วัน → data/firms-hotspots.json
นับรายจังหวัด ทุกจุดที่ตกในจังหวัด (ไม่กรองพื้นที่นาข้าว — เจ้าของเลือกแบบนี้ 16 ต.ค. 69)

แหล่งข้อมูล: NASA FIRMS ไฟล์สาธารณะ ไม่ต้องใช้ MAP_KEY
  https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/
  SUOMI_VIIRS_C2_SouthEast_Asia_7d.csv  (VIIRS 375 ม. · Suomi-NPP ดวงเดียว · NRT)

ตัวเลขนี้คือ "ต่ำสุด" ไม่ใช่จำนวนไฟทั้งหมด: ดาวเทียมผ่านวันละ ~2 ครั้ง มองไม่เห็นไฟเล็ก
ไฟใต้เมฆ หรือไฟที่ดับก่อนดาวเทียมผ่าน และบอกไม่ได้ว่าเป็นไฟนา ไร่อ้อย หรือป่า

Run: python scripts/fetch_firms_hotspots.py [--selftest]
"""
import csv
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

from riceutils import _load_geo, _point_in_geom, bkk_today

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = ("https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/"
       "SUOMI_VIIRS_C2_SouthEast_Asia_7d.csv")
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "data", "firms-hotspots.json")
REQUIRED_COLS = {"latitude", "longitude", "acq_date", "acq_time", "frp", "confidence"}

# กรอบหยาบของประเทศไทย ไว้ตัดจุดของประเทศอื่นก่อนทำ point-in-polygon (ไฟล์ทั้งภูมิภาคมี ~87,000 จุด)
BBOX = (97.3, 5.5, 105.7, 20.5)   # lon_min, lat_min, lon_max, lat_max

# ไฟล์ทั้งภูมิภาคต้องมีจุดหลักหมื่น ถ้าน้อยกว่านี้คือไฟล์ขาด ไม่ใช่ "ไม่มีไฟ"
MIN_REGION_ROWS = 10_000
MIN_DISTINCT_DATES = 5     # ต้องครอบคลุมเกือบทั้ง 7 วัน
MAX_STALE_DAYS = 2         # วันล่าสุดในไฟล์ห่างจากวันนี้ (UTC) ได้ไม่เกินนี้


def parse_rows(text):
    """CSV → list[dict] เฉพาะแถวที่พิกัดอ่านได้ · ขาดคอลัมน์สำคัญ = ValueError"""
    reader = csv.DictReader(io.StringIO(text))
    cols = set(reader.fieldnames or [])
    if not REQUIRED_COLS <= cols:
        raise ValueError(f"CSV ขาดคอลัมน์ {sorted(REQUIRED_COLS - cols)} — รูปแบบไฟล์อาจเปลี่ยน")
    rows = []
    for r in reader:
        try:
            r["_lon"], r["_lat"] = float(r["longitude"]), float(r["latitude"])
            r["_frp"] = float(r["frp"] or 0)
        except ValueError:
            continue
        rows.append(r)
    return rows


def check_region(rows, today_utc):
    """ไฟล์ทั้งภูมิภาคต้องเต็ม — ไม่งั้นเลขรายจังหวัดจะต่ำลงเงียบๆ แล้วเขียนทับของดี"""
    if len(rows) < MIN_REGION_ROWS:
        raise ValueError(f"ไฟล์มีแค่ {len(rows)} จุด (ปกติหลักหมื่น) — ไม่ครบ")
    dates = sorted({r["acq_date"] for r in rows})
    if len(dates) < MIN_DISTINCT_DATES:
        raise ValueError(f"ครอบคลุมแค่ {len(dates)} วัน ({dates[0]}..{dates[-1]})")
    newest = datetime.strptime(dates[-1], "%Y-%m-%d").date()
    if (today_utc - newest).days > MAX_STALE_DAYS:
        raise ValueError(f"จุดล่าสุดคือ {dates[-1]} เก่าเกิน {MAX_STALE_DAYS} วัน")
    return dates


def province_shapes():
    out = {}
    for feat in _load_geo()["features"]:
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        pts = [p for poly in polys for ring in poly for p in ring]
        lons, lats = [p[0] for p in pts], [p[1] for p in pts]
        out[feat["properties"]["name"]] = (min(lons), min(lats), max(lons), max(lats), geom)
    return out


def assign(rows, shapes):
    """จุดแต่ละจุด → จังหวัด · คืน (counts, outside) outside = จุดในกรอบไทยที่ไม่ตกจังหวัดไหน (ทะเล/ชายแดน)"""
    prov = {n: {"count_7d": 0, "count_latest": 0, "last_date": None, "frp_mw": 0.0} for n in shapes}
    newest = max((r["acq_date"] for r in rows), default=None)
    outside = 0
    for r in rows:
        lon, lat = r["_lon"], r["_lat"]
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        hit = None
        for name, (x0, y0, x1, y1, geom) in shapes.items():
            if x0 <= lon <= x1 and y0 <= lat <= y1 and _point_in_geom(lon, lat, geom):
                hit = name
                break
        if hit is None:
            outside += 1
            continue
        p = prov[hit]
        p["count_7d"] += 1
        p["frp_mw"] += r["_frp"]
        if r["acq_date"] == newest:
            p["count_latest"] += 1
        if p["last_date"] is None or r["acq_date"] > p["last_date"]:
            p["last_date"] = r["acq_date"]
    for p in prov.values():
        p["frp_mw"] = round(p["frp_mw"], 1)
    return prov, outside


def main():
    today_utc = datetime.now(timezone.utc).date()
    r = requests.get(URL, timeout=120, headers={"User-Agent": "RiceMap/1.0 (+https://github.com/Ton-Munoi99/rice-map)"})
    r.raise_for_status()
    rows = parse_rows(r.text)
    dates = check_region(rows, today_utc)   # ล้ม = exit 1 ก่อนเขียน ข้อมูลเดิมอยู่ครบ

    prov, outside = assign(rows, province_shapes())
    total = sum(p["count_7d"] for p in prov.values())
    result = {
        "_meta": {
            "updated": bkk_today(),
            "source": "NASA FIRMS · VIIRS 375 m (Suomi-NPP) · NRT",
            "source_url": "https://firms.modaps.eosdis.nasa.gov/",
            "window": {"from": dates[0], "to": dates[-1], "tz": "UTC (acq_date ของดาวเทียม)"},
            "provinces_with_hotspots": sum(1 for p in prov.values() if p["count_7d"]),
            "total_in_provinces": total,
            "in_thailand_bbox_outside_provinces": outside,
            "region_rows": len(rows),
            "note_th": "จุดความร้อนที่ดาวเทียมจับได้ — เป็นตัวเลขต่ำสุด ไม่ใช่ไฟทั้งหมด (ไฟเล็ก ไฟใต้เมฆ "
                       "หรือไฟที่ดับก่อนดาวเทียมผ่านจะไม่เห็น) · นับทุกจุดในจังหวัด ไม่แยกว่าเป็นนา ไร่ หรือป่า",
            "note_en": "Satellite-detected hotspots — a lower bound, not all fires (small, under-cloud or "
                       "short-lived fires are missed). Every point in the province is counted; crops, "
                       "cane fields and forest are not distinguished.",
        },
        "provinces": prov,
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    top = sorted(prov.items(), key=lambda kv: -kv[1]["count_7d"])[:5]
    print(f"✅ {total} จุดใน {result['_meta']['provinces_with_hotspots']} จังหวัด · {dates[0]}..{dates[-1]} · "
          f"นอกจังหวัด {outside} · สูงสุด " + ", ".join(f"{n} {p['count_7d']}" for n, p in top))


def _selftest():
    sq = {"type": "Polygon", "coordinates": [[[100, 14], [101, 14], [101, 15], [100, 15], [100, 14]]]}
    shapes = {"A": (100, 14, 101, 15, sq)}
    mk = lambda lon, lat, d, frp="2.0": {"_lon": lon, "_lat": lat, "acq_date": d, "_frp": float(frp)}
    prov, outside = assign([mk(100.5, 14.5, "2026-10-01"), mk(100.6, 14.6, "2026-10-02", "3.5"),
                            mk(110, 14.5, "2026-10-02"),   # นอกกรอบไทย: ไม่นับเลย
                            mk(102, 14.5, "2026-10-02")],  # ในกรอบไทยแต่ไม่อยู่จังหวัดไหน (ชายแดน/ทะเล)
                           shapes)
    assert prov["A"]["count_7d"] == 2 and prov["A"]["count_latest"] == 1, prov
    assert prov["A"]["frp_mw"] == 5.5 and prov["A"]["last_date"] == "2026-10-02", prov
    assert outside == 1, outside

    # ไฟล์ขาด ต้องไม่ผ่าน — ไม่งั้นทุกจังหวัดกลายเป็น 0 แล้วเขียนทับ
    today = datetime(2026, 10, 16).date()
    full = [mk(100, 14, f"2026-10-{d:02d}") for d in range(10, 17) for _ in range(2000)]
    assert len(check_region(full, today)) == 7
    for bad, why in ((full[:50], "น้อยเกิน"),
                     ([mk(100, 14, "2026-10-16")] * 20000, "วันเดียว"),
                     ([mk(100, 14, f"2026-10-{d:02d}") for d in range(1, 8) for _ in range(3000)], "เก่า")):
        try:
            check_region(bad, today)
        except ValueError:
            continue
        raise AssertionError(f"ควรปฏิเสธ: {why}")
    try:
        parse_rows("lat,lon\n1,2\n")
    except ValueError:
        pass
    else:
        raise AssertionError("ขาดคอลัมน์ต้อง error")
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
