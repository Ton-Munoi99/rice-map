#!/usr/bin/env python3
"""
fetch_firms_hotspots.py
-----------------------
จุดความร้อน (active fire) จากดาวเทียม NASA/NOAA VIIRS 7 วันล่าสุด → data/firms-hotspots.json
นับรายจังหวัด ทุกจุดที่ตกในจังหวัด (ไม่กรองพื้นที่นาข้าว — เจ้าของเลือกแบบนี้ 16 ต.ค. 69)

แหล่งข้อมูล: NASA FIRMS ไฟล์สาธารณะ ไม่ต้องใช้ MAP_KEY
  https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/
  SUOMI_VIIRS_C2_SouthEast_Asia_7d.csv  (VIIRS 375 ม. · Suomi-NPP ดวงเดียว · NRT)

ตัดออกก่อนนับ (แก้จาก /code-review 19 ต.ค. 69):
  · ความมั่นใจต่ำ (confidence = low) — เช่นแสงสะท้อน/พื้นผิวร้อน ไม่ใช่ไฟ
  · แหล่งความร้อนประจำ — ช่อง ~1 กม. ที่ติดซ้ำ ≥3 วันใน 7 วัน คือปล่องโรงปูน/โรงกลั่น/โรงไฟฟ้า
    ไม่ใช่การเผา ไฟล์ NRT ไม่ได้ติดป้ายพวกนี้มา (สระบุรี อ.แก่งคอย ติดซ้ำ 3 วันในรอบทดสอบ)
  · วันเก่าเกิน 7 วันปฏิทิน — ไฟล์ "7d" ของ FIRMS เป็นช่วง 7×24 ชม. แบบเลื่อน จึงคร่อม 8 วันที่ UTC

ตัวเลขนี้คือ "ต่ำสุด" ไม่ใช่จำนวนไฟทั้งหมด: ดาวเทียมผ่านวันละ ~2 ครั้ง มองไม่เห็นไฟเล็ก
ไฟใต้เมฆ หรือไฟที่ดับก่อนดาวเทียมผ่าน และบอกไม่ได้ว่าเป็นไฟนา ไร่อ้อย หรือป่า

Run: python scripts/fetch_firms_hotspots.py [--selftest]
"""
import csv
import io
import json
import math
import os
import sys
from collections import defaultdict
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

WINDOW_DAYS = 7            # ป้ายบนเว็บเขียนว่า "7 วัน" — ตัดให้เหลือ 7 วันที่จริง แล้ว assert
MIN_REGION_ROWS = 10_000   # ไฟล์ทั้งภูมิภาคต้องมีจุดหลักหมื่น น้อยกว่านี้คือไฟล์ขาด ไม่ใช่ "ไม่มีไฟ"
MIN_DISTINCT_DATES = 5
MAX_STALE_DAYS = 2         # วันล่าสุดในไฟล์ห่างจากวันนี้ (UTC) ได้ไม่เกินนี้

PERSIST_CELL_DEG = 0.01    # ~1 กม. — ใหญ่กว่าความคลาดตำแหน่ง VIIRS 375 ม. แต่เล็กกว่านาแปลงข้างเคียง
PERSIST_MIN_DAYS = 3       # ช่องที่ติดซ้ำวันที่ต่างกันเท่านี้ใน 7 วัน = แหล่งความร้อนประจำ ไม่ใช่การเผา
NEAR_BORDER_DEG = 0.05     # ~5 กม. — จุดนอก polygon ที่ใกล้ขอบไทยขนาดนี้ แยกไม่ออกว่าอยู่ฝั่งไหน


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


def in_bbox(r):
    return BBOX[0] <= r["_lon"] <= BBOX[2] and BBOX[1] <= r["_lat"] <= BBOX[3]


def check_region(rows, today_utc):
    """ไฟล์ทั้งภูมิภาคต้องเต็ม และต้องมีจุดเหนือไทยทุกวัน — ไม่งั้นเลขรายจังหวัดจะต่ำลงเงียบๆ แล้วเขียนทับของดี"""
    if len(rows) < MIN_REGION_ROWS:
        raise ValueError(f"ไฟล์มีแค่ {len(rows)} จุด (ปกติหลักหมื่น) — ไม่ครบ")
    dates = sorted({r["acq_date"] for r in rows})
    if len(dates) < MIN_DISTINCT_DATES:
        raise ValueError(f"ครอบคลุมแค่ {len(dates)} วัน ({dates[0]}..{dates[-1]})")
    # หน้าต่างยึด "วันล่าสุดที่มีจุดเหนือไทย" ไม่ใช่วันล่าสุดของไฟล์ — วัน UTC ล่าสุดมักยังไม่ครบ
    # (ดาวเทียมยังไม่ผ่านไทย แต่ผ่านอินโดฯ แล้ว) ถ้ายึดวันนั้นจะตัดวันเต็มทิ้ง 1 วัน
    seen = {r["acq_date"] for r in rows if in_bbox(r)}
    if not seen:
        raise ValueError("ไม่มีจุดในกรอบประเทศไทยเลย")
    newest = datetime.strptime(max(seen), "%Y-%m-%d").date()
    if (today_utc - newest).days > MAX_STALE_DAYS:
        raise ValueError(f"จุดล่าสุดเหนือไทยคือ {newest} เก่าเกิน {MAX_STALE_DAYS} วัน")
    first = newest - timedelta(days=WINDOW_DAYS - 1)
    window = [(first + timedelta(days=i)).isoformat() for i in range(WINDOW_DAYS)]
    # ไฟล์ภูมิภาคครบแต่ขาดรอบที่ผ่านไทย (granule หาย) จะผ่านเช็กข้างบน — กรอบไทยรวมเพื่อนบ้านไว้ด้วย
    # จึงมีจุดทุกวันแม้นอกฤดูเผา ถ้าวันไหนในกรอบเป็นศูนย์ ถือว่ารอบที่ผ่านไทยหาย
    missing = [d for d in window if d not in seen]
    if missing:
        raise ValueError(f"ไม่มีจุดในกรอบประเทศไทยวันที่ {missing} — รอบที่ดาวเทียมผ่านไทยน่าจะหาย")
    return window


def select(rows, window):
    """ตัดสิ่งที่ไม่ใช่ไฟออก · คืน (kept, dropped_counts)"""
    first = window[0]
    rows = [r for r in rows if in_bbox(r) and r["acq_date"] >= first]
    n = len(rows)
    rows = [r for r in rows if r["confidence"].strip().lower() not in ("l", "low")]
    low = n - len(rows)
    cell = lambda r: (round(r["_lat"] / PERSIST_CELL_DEG), round(r["_lon"] / PERSIST_CELL_DEG))
    days = defaultdict(set)
    for r in rows:
        days[cell(r)].add(r["acq_date"])
    # รวมช่องข้างเคียง 3×3 — ปล่องเดียวกันตกคร่อมเส้นแบ่งช่องได้ (สระบุรี 101.074 กับ 101.076
    # ปัดไปคนละช่อง) ทำให้รัศมีจริง ~1–1.5 กม. · ราคา: นาติดกันที่เผาคนละวัน 3 วันจะถูกตัดด้วย
    near = lambda c: set().union(*(days.get((c[0] + i, c[1] + j), ()) for i in (-1, 0, 1) for j in (-1, 0, 1)))
    persistent = {c for c in days if len(near(c)) >= PERSIST_MIN_DAYS}
    kept = [r for r in rows if cell(r) not in persistent]
    return kept, {"low_confidence": low, "persistent_heat_source": len(rows) - len(kept),
                  "persistent_cells": len(persistent)}


def province_shapes():
    out = {}
    for feat in _load_geo()["features"]:
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        rings = [ring for poly in polys for ring in poly]
        lons = [p[0] for ring in rings for p in ring]
        lats = [p[1] for ring in rings for p in ring]
        out[feat["properties"]["name"]] = (min(lons), min(lats), max(lons), max(lats), geom, rings)
    return out


def edge_dist(lon, lat, rings):
    """ระยะ (องศา) จากจุดถึงขอบ polygon ที่ใกล้สุด — วัดถึงเส้นขอบ ไม่ใช่แค่จุดยอด"""
    best = math.inf
    for ring in rings:
        for (ax, ay), (bx, by) in zip(ring, ring[1:]):
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((lon - ax) * dx + (lat - ay) * dy) / (dx * dx + dy * dy or 1)))
            best = min(best, math.hypot(lon - ax - t * dx, lat - ay - t * dy))
    return best


def assign(rows, shapes):
    """จุด → จังหวัด · จุดที่ไม่ตก polygon ไหน แยกเป็น 2 กอง:
       near_border  ห่างขอบไทย < ~5 กม. (polygon แบบย่ออาจตัดจุดฝั่งไทยออก หรืออาจเป็นฝั่งเพื่อนบ้าน
                    แยกไม่ได้) — บันทึกไว้ที่จังหวัดที่ใกล้สุด แต่ไม่นับรวม count_7d
       outside      ไกลกว่านั้น = ประเทศเพื่อนบ้าน/ทะเล"""
    prov = {n: {"count_7d": 0, "last_date": None, "frp_mw": 0.0, "near_border_unassigned": 0}
            for n in shapes}
    outside = near = 0
    for r in rows:
        lon, lat = r["_lon"], r["_lat"]
        hit = None
        for name, (x0, y0, x1, y1, geom, _) in shapes.items():
            if x0 <= lon <= x1 and y0 <= lat <= y1 and _point_in_geom(lon, lat, geom):
                hit = name
                break
        if hit is None:
            d, nearest = min(((edge_dist(lon, lat, rings), n)
                              for n, (x0, y0, x1, y1, _, rings) in shapes.items()
                              if x0 - NEAR_BORDER_DEG <= lon <= x1 + NEAR_BORDER_DEG
                              and y0 - NEAR_BORDER_DEG <= lat <= y1 + NEAR_BORDER_DEG),
                             default=(math.inf, None))
            if d < NEAR_BORDER_DEG:
                prov[nearest]["near_border_unassigned"] += 1
                near += 1
            else:
                outside += 1
            continue
        p = prov[hit]
        p["count_7d"] += 1
        p["frp_mw"] += r["_frp"]
        if p["last_date"] is None or r["acq_date"] > p["last_date"]:
            p["last_date"] = r["acq_date"]
    for p in prov.values():
        p["frp_mw"] = round(p["frp_mw"], 1)
    return prov, {"near_border_unassigned": near, "outside_thailand": outside}


def main():
    today_utc = datetime.now(timezone.utc).date()
    r = requests.get(URL, timeout=120, headers={"User-Agent": "RiceMap/1.0 (+https://github.com/Ton-Munoi99/rice-map)"})
    r.raise_for_status()
    rows = parse_rows(r.text)
    window = check_region(rows, today_utc)   # ล้ม = exit 1 ก่อนเขียน ข้อมูลเดิมอยู่ครบ
    kept, dropped = select(rows, window)
    prov, placed = assign(kept, province_shapes())

    # พูดในข้อมูลแล้ว assert: ป้ายเขียนว่า 7 วัน
    days_spanned = (datetime.strptime(window[-1], "%Y-%m-%d") - datetime.strptime(window[0], "%Y-%m-%d")).days + 1
    assert days_spanned <= WINDOW_DAYS, (window[0], window[-1])

    total = sum(p["count_7d"] for p in prov.values())
    result = {
        "_meta": {
            "updated": bkk_today(),
            "source": "NASA FIRMS · VIIRS 375 m (Suomi-NPP) · NRT",
            "source_url": "https://firms.modaps.eosdis.nasa.gov/",
            "window": {"from": window[0], "to": window[-1], "days": days_spanned, "tz": "UTC (acq_date ของดาวเทียม)"},
            "provinces_with_hotspots": sum(1 for p in prov.values() if p["count_7d"]),
            "total_in_provinces": total,
            "excluded": dropped,
            "unplaced": placed,
            "region_rows": len(rows),
            "note_th": "จุดความร้อนที่ดาวเทียมจับได้ — เป็นตัวเลขต่ำสุด ไม่ใช่ไฟทั้งหมด (ไฟเล็ก ไฟใต้เมฆ "
                       "หรือไฟที่ดับก่อนดาวเทียมผ่านจะไม่เห็น) · นับทุกจุดในจังหวัด ไม่แยกว่าเป็นนา ไร่ หรือป่า · "
                       "ตัดจุดความมั่นใจต่ำ และจุดที่ติดซ้ำที่เดิม ≥3 วัน (ปล่องโรงงาน/โรงปูน) ออกแล้ว",
            "note_en": "Satellite-detected hotspots — a lower bound, not all fires (small, under-cloud or "
                       "short-lived fires are missed). Every point in the province is counted; crops, "
                       "cane fields and forest are not distinguished. Low-confidence detections and "
                       "spots firing on 3+ days in the same place (industrial stacks, cement kilns) are removed.",
        },
        "provinces": prov,
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    top = sorted(prov.items(), key=lambda kv: -kv[1]["count_7d"])[:5]
    print(f"✅ {total} จุดใน {result['_meta']['provinces_with_hotspots']} จังหวัด · {window[0]}..{window[-1]} "
          f"({days_spanned} วัน) · ตัดความมั่นใจต่ำ {dropped['low_confidence']} · ตัดแหล่งความร้อนประจำ "
          f"{dropped['persistent_heat_source']} ({dropped['persistent_cells']} ช่อง) · ใกล้ชายแดนไม่นับ "
          f"{placed['near_border_unassigned']} · นอกไทย {placed['outside_thailand']} · สูงสุด "
          + ", ".join(f"{n} {p['count_7d']}" for n, p in top))


def _selftest():
    mk = lambda lon, lat, d, frp="2.0", conf="nominal": {
        "_lon": lon, "_lat": lat, "acq_date": d, "_frp": float(frp), "confidence": conf}
    sq = {"type": "Polygon", "coordinates": [[[100, 14], [101, 14], [101, 15], [100, 15], [100, 14]]]}
    shapes = {"A": (100, 14, 101, 15, sq, sq["coordinates"])}

    # จังหวัด / ชายแดน / นอกไทย
    prov, placed = assign([mk(100.5, 14.5, "2026-10-01"), mk(100.6, 14.6, "2026-10-02", "3.5"),
                           mk(101.03, 14.5, "2026-10-02"),     # นอก polygon 3 กม. → ใกล้ชายแดน ไม่นับ
                           mk(102, 14.5, "2026-10-02")],       # ไกล → นอกไทย
                          shapes)
    assert prov["A"]["count_7d"] == 2 and prov["A"]["frp_mw"] == 5.5, prov
    assert prov["A"]["last_date"] == "2026-10-02" and prov["A"]["near_border_unassigned"] == 1, prov
    assert placed == {"near_border_unassigned": 1, "outside_thailand": 1}, placed

    # ตัดความมั่นใจต่ำ + แหล่งความร้อนประจำ (ติดที่เดิม 3 วัน) แต่ไม่ตัดไฟที่ติด 2 วัน
    window = [f"2026-10-{d:02d}" for d in range(10, 17)]
    rows = ([mk(100.5, 14.5, "2026-10-12", conf="low")]
            + [mk(101.04, 14.65, f"2026-10-{d}") for d in (12, 15, 16)]       # โรงปูน 3 วัน
            + [mk(101.0785, 14.633, "2026-10-13"), mk(101.076, 14.6307, "2026-10-15"),
               mk(101.0742, 14.6313, "2026-10-16")]                          # ปล่องคร่อมเส้นแบ่งช่อง
            + [mk(100.2, 14.2, "2026-10-13"), mk(100.2, 14.2, "2026-10-14")]  # ไฟจริง 2 วัน — เก็บ
            + [mk(100.3, 14.3, "2026-10-09")])                                # เก่ากว่าหน้าต่าง — ตัด
    kept, dropped = select(rows, window)
    assert len(kept) == 2 and dropped["low_confidence"] == 1, (kept, dropped)
    assert dropped["persistent_heat_source"] == 6 and dropped["persistent_cells"] == 3, dropped

    # ไฟล์ขาด / เก่า / ขาดรอบที่ผ่านไทย ต้องไม่ผ่าน — ไม่งั้นทุกจังหวัดกลายเป็น 0 แล้วเขียนทับ
    today = datetime(2026, 10, 16).date()
    full = [mk(100, 14, f"2026-10-{d:02d}") for d in range(9, 17) for _ in range(2000)]
    win = check_region(full, today)
    assert len(win) == 7 and win[0] == "2026-10-10", win          # 8 วันที่ในไฟล์ → ตัดเหลือ 7
    # วัน UTC ล่าสุดที่ดาวเทียมยังไม่ผ่านไทย (มีแต่จุดนอกกรอบ) ต้องไม่ถูกนับเป็นวันขาด
    win = check_region(full + [mk(120, 0, "2026-10-17")] * 50, today)
    assert win[-1] == "2026-10-16", win
    gap = [r for r in full if r["acq_date"] != "2026-10-14"] + [mk(120, 14, "2026-10-14")] * 2000
    for bad, why in ((full[:50], "น้อยเกิน"),
                     ([mk(100, 14, "2026-10-16")] * 20000, "วันเดียว"),
                     ([mk(100, 14, f"2026-10-{d:02d}") for d in range(1, 8) for _ in range(3000)], "เก่า"),
                     (gap, "ไม่มีจุดเหนือไทยวันหนึ่ง")):
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
