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
import calendar
from datetime import date, timedelta

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


# ── Rice mask + phenology (ใช้ร่วมทั้งระดับจังหวัดและอำเภอ) ─────────────
# เดิมโค้ดชุดนี้ซ้ำอยู่ทั้ง fetch_rice_evi.py และ fetch_rice_evi_district.py
# รวมถึงค่าคงที่จูนเกณฑ์ ซึ่งต้องแก้ให้ตรงกันทั้งสองไฟล์ทุกครั้ง —
# 18 ส.ค. 2569 ต้องแก้ MIN_EVI_MAX สองที่พร้อมกัน ถ้าหลุดที่เดียวแผนที่จังหวัด
# กับรายอำเภอจะใช้เกณฑ์คนละชุดโดยไม่มีใครรู้ จึงยกมารวมไว้ที่เดียว

PHENOLOGY_MONTHS = 12   # จำนวนเดือนย้อนหลังที่ตรวจ flooding phase
FLOOD_EVI_MAX = 0.30   # น้ำท่วมขังต้องเกิดตอน canopy ยังโปร่ง (เตรียมดิน/ปักดำ) ไม่ใช่ป่าเขียวทึบ
PEAK_MIN      = 0.40   # ต้องมีเดือนที่ต้นข้าวขึ้น canopy เขียวจริง → ตัดน้ำเปิด/บ่อกุ้ง/นาเกลือ
AMP_MIN       = 0.25   # EVI แกว่งตามฤดูสูง → ตัดพืชยืนต้นเขียวคงที่ทั้งปี (ยาง ปาล์ม ป่า)
MIN_EVI_MAX   = 0.22   # ต้องเคย "โล่ง/น้ำขัง" อย่างน้อย 1 เดือน (min EVI ต่ำ) → ตัวตัดยาง/ปาล์ม/ป่า
RUBBER_ASSET = ""       # เช่น "projects/xxx/assets/thailand_rubber_2023" (ปล่อยว่าง = ข้าม)


def load_rice_mask():
    """
    โหลด rice scan mask แบบ Hybrid Union:
    1. GLAD LCLUC 2020 Rice Paddy (Class 24) — rice-specific
    2. MODIS MCD12Q1 Cropland (Class 12, 14) — ครอบคลุมกว้างกว่า
    3. Union = GLAD ∪ MCD12Q1 — scan area กว้าง, Phenology กรอง rice-only

    เหตุผลที่ใช้ union:
    - GLAD underrepresent จังหวัดเล็กภาคกลาง (อ่างทอง 4px, สิงห์บุรี 6px, ปทุมธานี 2px)
    - MCD12Q1 ครอบคลุมกว้างกว่า (1km native) แต่รวม cropland ทุกชนิด
    - Phenology gate (LSWI > EVI) จะกรองเอาเฉพาะนาข้าวที่มี flooding signature
    - อ้อย/มัน/ข้าวโพด ปลูกบนดินแห้ง → ไม่ผ่าน phenology → ถูกกรองออก

    Returns:
        union_mask  — ee.Image binary (1 = GLAD rice OR MCD12Q1 cropland)
        glad_mask   — ee.Image binary (1 = GLAD rice only, สำหรับ per-province stats)
        mask_source — str description
    """
    import ee  # lazy — workflow ฝน/อากาศ ไม่ได้ติดตั้ง earthengine-api
    glad_mask = None
    cropland_mask = None

    # ── GLAD LCLUC 2020 Rice Paddy ──
    try:
        glad_mask = ee.Image("projects/glad/GLCLU2020/v2/LCLUC_2020").eq(24)
        print("✓ Loaded GLAD LCLUC 2020 (rice paddy class 24)")
    except Exception as e:
        print(f"  ⚠️ GLAD not available: {e}")

    # ── MODIS MCD12Q1 Cropland ──
    try:
        lc = ee.Image("MODIS/061/MCD12Q1/2022_01_01").select("LC_Type1")
        cropland_mask = lc.eq(12).Or(lc.eq(14))
        print("✓ Loaded MCD12Q1 Cropland (classes 12, 14)")
    except Exception as e:
        print(f"  ⚠️ MCD12Q1 not available: {e}")

    # ── Build union ──
    if glad_mask is not None and cropland_mask is not None:
        union_mask = glad_mask.Or(cropland_mask)
        mask_source = "GLAD LCLUC 2020 Rice ∪ MODIS MCD12Q1 Cropland (Phenology-gated)"
        print("✓ Union mask: GLAD rice ∪ MCD12Q1 cropland")
    elif glad_mask is not None:
        union_mask = glad_mask
        mask_source = "GLAD LCLUC 2020 — Rice Paddy (Class 24)"
        print("  → Using GLAD only (MCD12Q1 unavailable)")
    elif cropland_mask is not None:
        union_mask = cropland_mask
        glad_mask = None   # GLAD unavailable — bonus_pixels will be 0 (N/A)
        mask_source = "MODIS MCD12Q1 Cropland (fallback, GLAD unavailable)"
        print("  → Using MCD12Q1 only (GLAD unavailable)")
    else:
        raise RuntimeError("No rice/cropland mask available!")

    return union_mask, glad_mask, mask_source

def load_exclusion_mask():
    """
    โหลด mask พืชยืนต้นที่ไม่ใช่ข้าว (ปาล์ม/ยาง) สำหรับลบออกจาก scan area
    เป็น defense-in-depth เสริม phenology gate

    Returns:
        excl_mask — ee.Image binary (1 = ปาล์ม/ยาง, 0 = อื่นๆ, unmasked ทั้งภาพ) | None
        desc      — str อธิบายชั้นที่โหลดได้
    """
    import ee  # lazy — workflow ฝน/อากาศ ไม่ได้ติดตั้ง earthengine-api
    parts, names = [], []

    # ── Oil palm: Descals et al. (BIOPAMA/GlobalOilPalm/v1) ──
    try:
        palm = (
            ee.ImageCollection("BIOPAMA/GlobalOilPalm/v1")
            .select("classification")
            .mosaic()
            .lt(3)            # 1,2 = palm ; 3 = non-palm
            .unmask(0)        # นอกพื้นที่ dataset → 0 (ไม่ลบพิกเซลนา)
        )
        parts.append(palm)
        names.append("oil palm (Descals BIOPAMA v1)")
        print("✓ Loaded oil-palm exclusion (BIOPAMA/GlobalOilPalm/v1)")
    except Exception as e:
        print(f"  ⚠️ oil-palm layer unavailable: {e}")

    # ── Rubber (optional asset) ──
    if RUBBER_ASSET:
        try:
            rubber = ee.Image(RUBBER_ASSET).gt(0).unmask(0)
            parts.append(rubber)
            names.append(f"rubber ({RUBBER_ASSET})")
            print("✓ Loaded rubber exclusion")
        except Exception as e:
            print(f"  ⚠️ rubber layer unavailable: {e}")

    if not parts:
        return None, "none"

    excl = parts[0]
    for p in parts[1:]:
        excl = excl.Or(p)
    return excl.unmask(0), " ∪ ".join(names)

def get_history_months(current_start_iso, n=12):
    """
    คืน list ของ (start_iso, end_iso) สำหรับ n เดือนก่อนหน้า current_start
    เรียงจากเก่า → ใหม่  ไม่รวมเดือน current_start เอง
    ตัวอย่าง: current='2026-05-01', n=3 → [(2026-02), (2026-03), (2026-04)]
    """
    d = date.fromisoformat(current_start_iso)
    ranges = []
    for i in range(n, 0, -1):
        month = d.month - i
        year  = d.year
        while month <= 0:
            month += 12
            year  -= 1
        last_day = calendar.monthrange(year, month)[1]
        ranges.append((
            date(year, month, 1).isoformat(),
            date(year, month, last_day).isoformat(),
        ))
    return ranges

def build_rice_phenology_mask(current_start_iso, n_months=12):
    """
    สร้าง rice-confirmation mask จาก phenology ของนาข้าวใน n เดือนย้อนหลัง

    เดิมใช้แค่ "LSWI > EVI ≥1 เดือน" ซึ่งหลวมเกินไป — พืชยืนต้น (ยาง/ปาล์ม/ป่า)
    และพื้นที่น้ำ (บ่อเลี้ยงสัตว์น้ำ/ป่าชายเลน/นาเกลือ) หลุดเข้ามาเป็น rice ได้
    เพราะค่า LSWI สูงกว่า EVI ในบางเดือนโดยไม่ต้องเป็นนาข้าว

    เงื่อนไขนาข้าวจริง (pixel ต้องผ่านทั้ง 3):
      1. flood_any  — เคยมีเดือน "น้ำท่วมขังตอน canopy โปร่ง": LSWI > EVI และ EVI < FLOOD_EVI_MAX
                       = ระยะเตรียมดิน/ปักดำจริง (ไม่ใช่ LSWI>EVI จากป่าที่ EVI แกว่ง)
      2. evi_max ≥ PEAK_MIN     — มีเดือนที่ต้นข้าวขึ้น canopy เขียวจริง → ตัดน้ำเปิด/บ่อกุ้ง/นาเกลือ
      3. amplitude ≥ AMP_MIN    — EVI แกว่งตามฤดูสูง (max−min) → ตัดพืชยืนต้นเขียวคงที่ทั้งปี
      4. evi_min ≤ MIN_EVI_MAX  — ต้องเคยโล่ง/น้ำขัง (min EVI ต่ำ) → ตัดยาง/ปาล์ม/ป่าที่เขียวตลอดปี

    แหล่งข้อมูล: MOD13A3 (EVI + LSWI จาก b02 NIR, b07 SWIR2), cloud-composited แล้ว
    - LSWI = (NIR − SWIR2) / (NIR + SWIR2)
    - window 12 เดือน ครอบคลุมนาปี (flooding Jun-Aug) + นาปรัง (Dec-Jan)

    Return:
        rice_confirm — ee.Image binary (1 = ผ่าน phenology ครบ 3 เงื่อนไข) band "flooded"
        window_str   — "YYYY-MM to YYYY-MM"
    """
    import ee  # lazy — workflow ฝน/อากาศ ไม่ได้ติดตั้ง earthengine-api
    history = get_history_months(current_start_iso, n_months)
    print(f"  Phenology window: {history[0][0][:7]} → {history[-1][0][:7]} ({n_months} months)")

    evi_imgs, flood_imgs = [], []
    for m_start, m_end in history:
        # ดึง EVI + NIR + SWIR2 จาก MOD13A3 ในคราวเดียว
        mod13 = (
            ee.ImageCollection("MODIS/061/MOD13A3")
            .filterDate(m_start, m_end)
            .select(["EVI", "sur_refl_b02", "sur_refl_b07"])
            .mosaic()              # all-masked ถ้าไม่มีข้อมูล → safe (ถูกข้ามใน max/min/any)
        )

        evi  = mod13.select("EVI").multiply(0.0001)
        nir  = mod13.select("sur_refl_b02").multiply(0.0001)
        swir = mod13.select("sur_refl_b07").multiply(0.0001)

        # LSWI = (NIR - SWIR2) / (NIR + SWIR2)
        lswi = nir.subtract(swir).divide(nir.add(swir))

        # Flooding: น้ำมากกว่าพืช (LSWI>EVI) และ canopy ยังโปร่ง (EVI ต่ำ)
        flooded = lswi.gt(evi).And(evi.lt(FLOOD_EVI_MAX)).rename("flooded")
        evi_imgs.append(evi.rename("EVI"))
        flood_imgs.append(flooded)

    if not flood_imgs:
        print("  ⚠️ No phenology data — returning zero mask")
        return ee.Image(0).rename("flooded"), "no data"

    # เคย flood (แบบ canopy โปร่ง) ≥1 เดือน
    flood_any = (
        ee.ImageCollection(flood_imgs)
        .reduce(ee.Reducer.anyNonZero())
        .rename("flooded")
    )
    # สถิติฤดูกาลของ EVI ต่อ pixel
    evi_col   = ee.ImageCollection(evi_imgs)
    evi_max   = evi_col.max()
    evi_min   = evi_col.min()
    amplitude = evi_max.subtract(evi_min)

    rice_confirm = (
        flood_any
        .And(evi_max.gte(PEAK_MIN))
        .And(amplitude.gte(AMP_MIN))
        .And(evi_min.lte(MIN_EVI_MAX))
        .rename("flooded")
    )
    window_str = f"{history[0][0][:7]} to {history[-1][0][:7]}"
    return rice_confirm, window_str


def km_outside(lat, lon, bbox):
    """ระยะจากจุดถึงกรอบจังหวัด (กม.) — 0 = อยู่ในกรอบ

    สถานีวัดน้ำมักตั้งริมน้ำซึ่งเป็นเส้นเขตแดน จึงหลุดกรอบเล็กน้อยได้เป็นปกติ
    แต่ถ้าหลุดมากแปลว่าต้นทางติดชื่อจังหวัดไม่ตรงกับพิกัดจริง
    """
    x0, y0, x1, y1 = bbox
    dx = max(x0 - lon, 0, lon - x1)
    dy = max(y0 - lat, 0, lat - y1)
    return math.hypot(dx * 111 * math.cos(math.radians(lat)), dy * 111)
