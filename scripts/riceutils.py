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

# โปรเจกต์ Google Earth Engine
GEE_PROJECT = "agriculture-monitoring-497007"

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


# ── Province centroids from thailand-data.js ─────────────────────────────────
def load_centroids(js_path=None, method="bbox"):
    """อ่าน thailand-data.js → { name: {lat, lon} } ต่อจังหวัด

    method='bbox'   — จุดกึ่งกลาง bounding box (min+max)/2 — มาตรฐาน, ไม่เบี้ยวชายฝั่ง
    method='vertex' — ค่าเฉลี่ย vertex sum/len — ของเดิม (เผื่อ rollback)
    """
    if js_path is None:
        js_path = os.path.join(_ROOT, "thailand-data.js")
    with open(js_path, encoding="utf-8") as f:
        js = f.read()
    js = re.sub(r"^window\.THAILAND_GEO\s*=\s*", "", js.strip().rstrip(";"))
    geo = json.loads(js)

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
    return centroids
