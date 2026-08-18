#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
riceutils.py — โค้ดที่ใช้ร่วมกันระหว่าง fetch_*.py ของ Rice Map

import ได้ทันทีเมื่อรัน `python scripts/fetch_X.py` เพราะ Python ใส่ scripts/
เป็น sys.path[0] อัตโนมัติ

หมายเหตุ: import ของหนัก (ee) ทำแบบ lazy ในฟังก์ชัน เพื่อให้ workflow ที่ไม่ได้
ติดตั้ง earthengine-api (ฝน/อากาศ) import โมดูลนี้ได้โดยไม่พัง
"""
import os
import re
import json
import math

# โปรเจกต์ Google Earth Engine
GEE_PROJECT = "agriculture-monitoring-497007"


def haversine_km(lat1, lon1, lat2, lon2):
    """ระยะทางวงกลมใหญ่ระหว่างสองพิกัด (กม.)"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))

# ── Province name mapping: GAUL → rice-map ─────────────────────────────────
# superset 19 entries (รวม Bueng Kan) ใช้ได้ทั้ง GEE province + district scripts
GAUL_NAME_MAP = {
    "Bangkok":                  "Bangkok Metropolis",
    "Buriram":                  "Buri Ram",
    "Chainat":                  "Chai Nat",
    "Chonburi":                 "Chon Buri",
    "Kampaeng Phet":            "Kamphaeng Phet",
    "Lopburi":                  "Lop Buri",
    "Nong Bua Lamphu":          "Nong Bua Lam Phu",
    "Phachinburi":              "Prachin Buri",
    "Phra Nakhon Si Ayudhya":   "Phra Nakhon Si Ayutthaya",
    "Prachuap Khilikhan":       "Prachuap Khiri Khan",
    "Samut Prakarn":            "Samut Prakan",
    "Samut Songkham":           "Samut Songkhram",
    "Si Saket":                 "Si Sa Ket",
    "Sisaket":                  "Si Sa Ket",
    "Singburi":                 "Sing Buri",
    "Suphanburi":               "Suphan Buri",
    "Trad":                     "Trat",
    "Bung Kan":                 "Bueng Kan",
    "Changwat Bueng Kan":       "Bueng Kan",
}

# Bueng Kan polygon — FAO GAUL 2015 ไม่มีบึงกาฬ (แยกจากหนองคายปี 2011)
_BUENG_KAN_POLY = [[
    [103.378, 17.979], [103.380, 18.121], [103.416, 18.215],
    [103.453, 18.319], [103.498, 18.416], [103.558, 18.502],
    [103.594, 18.582], [103.640, 18.643], [103.723, 18.693],
    [103.810, 18.681], [103.875, 18.640], [103.952, 18.620],
    [104.030, 18.598], [104.113, 18.562], [104.193, 18.507],
    [104.230, 18.438], [104.218, 18.350], [104.170, 18.263],
    [104.082, 18.210], [103.990, 18.174], [103.900, 18.110],
    [103.840, 18.035], [103.760, 17.970], [103.680, 17.952],
    [103.590, 17.960], [103.500, 17.960], [103.420, 17.970],
    [103.378, 17.979],
]]

# repo root = โฟลเดอร์แม่ของ scripts/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# จังหวัดที่ polygon ใน thailand-data.js เพี้ยน (จุดกระจายผิด) → ใช้พิกัดจริงแทน
# Satun: geometry corrupt ทำให้ centroid ตกกลางอ่าวไทย (~330km จากจริง)
CENTROID_OVERRIDE = {
    "Satun": {"lat": 6.75, "lon": 100.02},   # จ.สตูล (เขตในแผ่นดิน)
}


# ── GEE Auth ─────────────────────────────────────────────────────────────────
def init_gee():
    """Authenticate GEE ด้วย Service Account (CI) หรือ default credentials (local)"""
    import ee  # lazy — workflow ฝน/อากาศ ไม่มี ee
    key_data = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    if key_data:
        key_dict = json.loads(key_data)
        credentials = ee.ServiceAccountCredentials(
            email=key_dict["client_email"],
            key_data=key_dict["private_key"],
        )
        ee.Initialize(credentials, project=GEE_PROJECT)
        print("✓ Authenticated via Service Account")
    else:
        ee.Initialize(project=GEE_PROJECT)
        print("✓ Authenticated via default credentials")


# ── Province polygons (GAUL 76 + Bueng Kan) ──────────────────────────────────
def build_provinces():
    """FeatureCollection จังหวัดไทย 77 จังหวัด (GAUL 76 + บึงกาฬ)"""
    import ee  # lazy
    gaul = (
        ee.FeatureCollection("FAO/GAUL/2015/level1")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )
    bueng_kan = ee.Feature(
        ee.Geometry.Polygon(_BUENG_KAN_POLY),
        {"ADM1_NAME": "Bung Kan", "ADM0_NAME": "Thailand"},
    )
    return gaul.merge(ee.FeatureCollection([bueng_kan]))


# ── Province geometry from thailand-data.js ──────────────────────────────────
def _load_geo(js_path=None):
    """อ่าน thailand-data.js → GeoJSON dict (features รายจังหวัด, พิกัด lon/lat)"""
    if js_path is None:
        js_path = os.path.join(_ROOT, "thailand-data.js")
    with open(js_path, encoding="utf-8") as f:
        js = f.read()
    js = re.sub(r"^window\.THAILAND_GEO\s*=\s*", "", js.strip().rstrip(";"))
    return json.loads(js)


# ── Province centroids from thailand-data.js ─────────────────────────────────
def load_centroids(js_path=None, method="bbox"):
    """อ่าน thailand-data.js → { name: {lat, lon} } ต่อจังหวัด

    method='bbox'   — จุดกึ่งกลาง bounding box (min+max)/2 — มาตรฐาน, ไม่เบี้ยวชายฝั่ง
    method='vertex' — ค่าเฉลี่ย vertex sum/len — ของเดิม (เผื่อ rollback)
    """
    geo = _load_geo(js_path)

    centroids = {}
    for feat in geo["features"]:
        name = feat["properties"]["name"]
        geom = feat["geometry"]
        all_pts = []
        if geom["type"] == "Polygon":
            for ring in geom["coordinates"]:
                all_pts.extend(ring)
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    all_pts.extend(ring)
        if not all_pts:
            continue
        lons = [p[0] for p in all_pts]
        lats = [p[1] for p in all_pts]
        if method == "vertex":
            lat = sum(lats) / len(lats)
            lon = sum(lons) / len(lons)
        else:  # bbox center (default)
            lat = (min(lats) + max(lats)) / 2
            lon = (min(lons) + max(lons)) / 2
        centroids[name] = {"lat": round(lat, 4), "lon": round(lon, 4)}
    # แทนที่จังหวัดที่ polygon เพี้ยนด้วยพิกัดจริง
    for name, pt in CENTROID_OVERRIDE.items():
        if name in centroids:
            centroids[name] = dict(pt)
    return centroids


# ── Multi-point sampling inside province polygons ────────────────────────────
def _point_in_ring(lon, lat, ring):
    """Ray casting — จุดอยู่ใน ring ไหม"""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _point_in_geom(lon, lat, geom):
    """จุดอยู่ในจังหวัดไหม — นับ parity ทุก ring (รองรับรูใน polygon) ทุกชิ้นของ MultiPolygon"""
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poly in polys:
        if sum(1 for ring in poly if _point_in_ring(lon, lat, ring)) % 2 == 1:
            return True
    return False


def load_sample_points(js_path=None, max_pts=6):
    """จุดตัวอย่างหลายจุดกระจายในเขตจังหวัด → { name: [{lat, lon}, ...] }

    Deterministic (ตาราง grid ตายตัว ไม่มี random) เพื่อให้ผลรันซ้ำได้เหมือนเดิม
    ใช้จับฝนกระจุกเฉพาะจุด (เช่น orographic แถบเทือกเขา) ที่ centroid จุดเดียวพลาด
    จังหวัดใน CENTROID_OVERRIDE (geometry เพี้ยน) ใช้จุด override จุดเดียว
    """
    grid = 5  # 5×5 candidate grid ต่อจังหวัด
    geo = _load_geo(js_path)
    centroids = load_centroids(js_path)
    out = {}
    for feat in geo["features"]:
        name = feat["properties"]["name"]
        c = centroids.get(name)
        if name in CENTROID_OVERRIDE:
            out[name] = [dict(CENTROID_OVERRIDE[name])]
            continue
        geom = feat["geometry"]
        all_pts = []
        if geom["type"] == "Polygon":
            for ring in geom["coordinates"]:
                all_pts.extend(ring)
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    all_pts.extend(ring)
        if not all_pts:
            if c:
                out[name] = [dict(c)]
            continue
        lons = [p[0] for p in all_pts]
        lats = [p[1] for p in all_pts]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        pts = []
        if c and _point_in_geom(c["lon"], c["lat"], geom):
            pts.append((c["lon"], c["lat"]))
        candidates = []
        for gi in range(grid):
            for gj in range(grid):
                lon = min_lon + (max_lon - min_lon) * (gi + 0.5) / grid
                lat = min_lat + (max_lat - min_lat) * (gj + 0.5) / grid
                if _point_in_geom(lon, lat, geom):
                    candidates.append((lon, lat))
        # เลือกกระจายเท่าๆ กันไม่เกิน max_pts (นับรวม centroid ที่ใส่ไปแล้ว)
        need = max(0, max_pts - len(pts))
        if candidates and need:
            if len(candidates) <= need:
                pts.extend(candidates)
            else:
                step = len(candidates) / need
                pts.extend(candidates[int(k * step)] for k in range(need))
        if not pts and c:
            pts = [(c["lon"], c["lat"])]
        # dedupe (centroid อาจตรงกับจุด grid พอดี) — รักษาลำดับเดิม
        seen, uniq = set(), []
        for lo, la in pts:
            key = (round(lo, 4), round(la, 4))
            if key not in seen:
                seen.add(key)
                uniq.append({"lat": key[1], "lon": key[0]})
        out[name] = uniq
    return out


# ── MOD13Q1: ภาพ EVI ล่าสุดแบบราย 16 วัน ────────────────────────────────────
# ทำไมไม่ใช้ MOD13A3 (รายเดือน) กับค่าปัจจุบัน: composite รายเดือนออกช้า —
# 8 ส.ค. 2569 ยังไม่มีของเดือน ก.ค. ทำให้เว็บแสดงข้อมูลเก่า 2 เดือน
# MOD13Q1 เป็น composite ราย 16 วัน ออกเร็วกว่ามาก (ตรวจกับ NASA CMR: ช่วง
# 28 ก.ค.–12 ส.ค. มีให้ใช้แล้วตั้งแต่ 18 ส.ค.) และละเอียด 250 ม.
#
# ใช้เฉพาะ "ค่า EVI ปัจจุบัน + ก่อนหน้า" เท่านั้น ส่วน mask/phenology ยังใช้
# MOD13A3 รายเดือนย้อน 12 เดือนเหมือนเดิม เพราะเป็นค่าสะสมทั้งปี ความสดไม่สำคัญ
MOD13Q1 = "MODIS/061/MOD13Q1"
_Q1_LOOKBACK_DAYS = 80  # ครอบ composite ราย 16 วัน ได้อย่างน้อย 4 ช่วง


def latest_q1_periods(n=2, today=None):
    """คืน [(start_iso, end_iso), ...] ของ composite MOD13Q1 ล่าสุด n ช่วง (ใหม่→เก่า)

    อ่านวันที่จริงจาก system:time_start ไม่คำนวณ DOY เอง เพราะรอบ composite
    ของ MODIS ไม่ตรงกับปฏิทินและอาจข้ามช่วงถ้าภาพเสีย
    """
    import ee
    from datetime import date as _date, timedelta as _td

    end = today or _date.today()
    start = end - _td(days=_Q1_LOOKBACK_DAYS)
    col = (
        ee.ImageCollection(MOD13Q1)
        .filterDate(start.isoformat(), (end + _td(days=1)).isoformat())
        .select("EVI")
        .sort("system:time_start", False)
    )
    millis = col.aggregate_array("system:time_start").getInfo() or []
    out = []
    for ms in millis[:n]:
        s = _date.fromtimestamp(ms / 1000)
        out.append((s.isoformat(), (s + _td(days=15)).isoformat()))
    return out


def q1_evi_image(start_iso, end_iso):
    """ภาพ EVI (scaled) ของช่วงนั้น — กรองพิกเซลที่เมฆบังออกก่อน แล้วเฉลี่ยทุกภาพ

    ต้องกรอง QA เพราะ composite ราย 16 วันมีภาพให้เลือกน้อยกว่ารายเดือน
    หน้าฝนไทยจึงเหลือพิกเซลที่เมฆบังเยอะ ทำให้ EVI ต่ำผิดจริง
    (ทดลองไม่กรอง: ค่าเฉลี่ยประเทศร่วงจาก 0.43 เหลือ 0.33 และ 40 จังหวัด
     ถูกจัดเป็น "ทรงพุ่มโรย" กลางเดือน ส.ค. ซึ่งเป็นไปไม่ได้ตอนข้าวกำลังโต)

    แต่กรองอย่างเดียวทำให้ครอบคลุมเหลือ 51/77 จังหวัด จึงรับช่วงกว้างกว่า
    1 composite ได้ แล้ว mean() ข้ามภาพเพื่ออุดรูที่เมฆบัง

    SummaryQA: 0 = ดี, 1 = พอใช้, 2 = หิมะ/น้ำแข็ง, 3 = เมฆ → เก็บ 0-1
    """
    import ee
    from datetime import date as _date, timedelta as _td

    hi = (_date.fromisoformat(end_iso) + _td(days=1)).isoformat()

    def _clean(img):
        return img.select("EVI").updateMask(img.select("SummaryQA").lte(1))

    return (
        ee.ImageCollection(MOD13Q1)
        .filterDate(start_iso, hi)
        .map(_clean)
        .mean()
        .multiply(0.0001)
    )
