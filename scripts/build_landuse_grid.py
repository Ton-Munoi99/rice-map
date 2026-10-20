#!/usr/bin/env python3
"""
build_landuse_grid.py
---------------------
แผนที่สภาพการใช้ที่ดิน กรมพัฒนาที่ดิน (1:25,000 · ปี 2563–2568 แล้วแต่จังหวัด) 77 จังหวัด
→ ตารางพิกัด 0.00125° (~138 ม., 3×3 ช่อง ≈ 1 pixel VIIRS 375 ม.) → data/source/landuse_grid.npz

ใช้โดย fetch_firms_hotspots.py เพื่อบอกว่าจุดความร้อนตกในนาข้าว อ้อย มัน หรือข้าวโพด

⚠️ สัญญาอนุญาตของ กพด. คือ CC BY-NC-ND (ห้ามเชิงพาณิชย์ · ห้ามเผยแพร่ฉบับดัดแปลง)
   ตารางนี้คือฉบับดัดแปลง → **ห้าม commit** (data/source/ อยู่ใน .gitignore) · เก็บใน
   GitHub Actions cache ของ repo เท่านั้น · สิ่งที่เผยแพร่คือ "จำนวนจุดต่อชนิดพืช" ซึ่งเป็นผลวิเคราะห์
   เจ้าของยืนยันเงื่อนไขนี้ 20 ต.ค. 69

ดาวน์โหลด ~3 GB ทีละจังหวัด แล้วลบทิ้งทันที (ใช้ดิสก์ทีละไม่กี่ร้อย MB) · รันเฉพาะตอน cache หาย
ไม่ครบ 77 จังหวัด = exit 1 และไม่เขียนไฟล์ (ตารางมีรูจะทำให้จุดในจังหวัดที่ขาดกลายเป็น "ไม่มีข้อมูล" เงียบๆ)

Run: python scripts/build_landuse_grid.py [--selftest] [รหัสจังหวัด เช่น lri cri — ใช้ทดสอบ]
"""
import os
import re
import sys
import tempfile
import zipfile

import numpy as np
import requests

from fetch_firms_hotspots import BBOX

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INDEX = "https://tswc.ldd.go.th/DownloadGIS/Index_Lu.html"
BASE = "https://tswc.ldd.go.th/DownloadGIS/"
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "data", "source", "landuse_grid.npz")
RES = 0.00125
N_PROVINCES = 77
# 0 = นอกแผนที่ · ลำดับนี้ถูกเก็บลงไฟล์ด้วย ฝั่งอ่านไม่ต้อง hardcode
CLASSES = ["unmapped", "rice", "sugarcane", "cassava", "corn", "other_crop", "forest", "industry", "other"]


def lu_class(code):
    """LU_CODE ของ กพด. → index ใน CLASSES · รหัสผสม (A101+A202, A204/A302) ใช้พืชหลักตัวแรก"""
    c = re.split(r"[+/]", str(code or "").strip())[0].upper()
    if c.startswith("A1"):                       # นาข้าว / นาร้าง
        return 1
    if c in ("A203", "A202", "A204"):
        return {"A203": 2, "A204": 3, "A202": 4}[c]
    if c.startswith("A"):
        return 5
    if c.startswith("F"):
        return 6
    if c.startswith("U5"):                       # โรงงาน / ลานตากพืชผล
        return 7
    return 8 if c else 0


def zip_urls():
    html = requests.get(INDEX, timeout=60).content.decode("tis-620", "replace")
    urls = sorted({BASE + u for u in re.findall(r"href=[\"'](web_LU/DataLu/[^\"']*Landuse_\w+\.zip)", html)})
    if len(urls) < N_PROVINCES:
        raise SystemExit(f"หน้าดาวน์โหลดมีแค่ {len(urls)} ไฟล์ (ต้อง {N_PROVINCES}) — หน้าเว็บอาจเปลี่ยน")
    return urls


def burn(url, grid, year, transform_for):
    import geopandas as gpd
    from rasterio.features import rasterize

    with tempfile.TemporaryDirectory() as tmp:
        zpath = os.path.join(tmp, "lu.zip")
        with requests.get(url, stream=True, timeout=300) as r, open(zpath, "wb") as f:
            r.raise_for_status()
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        # บางจังหวัดเป็น zip ซ้อน zip (สมุทรสาคร: Landuse_skn/สมุทรสาคร2567.zip) — แตกจนไม่เหลือ zip
        while True:
            zips = [os.path.join(d, f) for d, _, fs in os.walk(tmp) for f in fs if f.lower().endswith(".zip")]
            if not zips:
                break
            for zp in zips:
                with zipfile.ZipFile(zp) as z:
                    z.extractall(zp[:-4] + "_x")
                os.remove(zp)
        shps = [os.path.join(d, f) for d, _, fs in os.walk(tmp) for f in fs
                if re.search(r"LU_[A-Z]+_25\d\d\.shp$", f, re.I)]   # Linux แยกตัวพิมพ์ — .SHP ก็ต้องเจอ
        if len(shps) != 1:
            raise ValueError(f"{url}: เจอ shapefile การใช้ที่ดิน {len(shps)} ไฟล์ (ต้อง 1)")
        y = int(re.search(r"_(25\d\d)\.shp$", shps[0], re.I).group(1))
        gdf = gpd.read_file(shps[0], columns=["LU_CODE"]).to_crs(4326)
    cls = gdf["LU_CODE"].map(lu_class)
    x0, y0, x1, y1 = gdf.total_bounds
    (r0, c0), (h, w), tf = transform_for(x0, y0, x1, y1)
    win = rasterize(((g, int(v)) for g, v in zip(gdf.geometry, cls) if g is not None and v),
                    out_shape=(h, w), transform=tf, fill=0, dtype="uint8")
    hit = win > 0
    grid[r0:r0 + h, c0:c0 + w][hit] = win[hit]
    year[r0:r0 + h, c0:c0 + w][hit] = y - 2500
    return y, len(gdf), int(hit.sum())


def main(only):
    from rasterio.transform import from_origin

    lon0, lat0, lon1, lat1 = BBOX
    H, W = round((lat1 - lat0) / RES), round((lon1 - lon0) / RES)
    grid = np.zeros((H, W), np.uint8)
    year = np.zeros((H, W), np.uint8)

    def transform_for(x0, y0, x1, y1):
        c0 = max(0, int((x0 - lon0) / RES))
        r0 = max(0, int((lat1 - y1) / RES))
        c1 = min(W, int((x1 - lon0) / RES) + 1)
        r1 = min(H, int((lat1 - y0) / RES) + 1)
        return (r0, c0), (r1 - r0, c1 - c0), from_origin(lon0 + c0 * RES, lat1 - r0 * RES, RES, RES)

    urls = zip_urls()
    if only:
        urls = [u for u in urls if re.search(r"Landuse_(\w+)\.zip", u).group(1).lower() in only]
    years = {}
    for i, url in enumerate(urls, 1):
        code = re.search(r"Landuse_(\w+)\.zip", url).group(1).lower()
        y, n, cells = burn(url, grid, year, transform_for)
        years[code] = y
        print(f"[{i}/{len(urls)}] {code} ปี {y} · {n:,} แปลง · {cells:,} ช่อง", flush=True)
    if not only and len(years) != N_PROVINCES:
        raise SystemExit(f"ได้ {len(years)} จังหวัด ไม่ครบ {N_PROVINCES} — ไม่เขียนไฟล์")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    tmp = OUTPUT + ".tmp.npz"
    np.savez_compressed(tmp, grid=grid, year=year, bbox=np.array(BBOX), res=RES,
                        classes=np.array(CLASSES), years=np.array(sorted(set(years.values()))))
    os.replace(tmp, OUTPUT)   # เขียนเสร็จทั้งไฟล์ก่อนค่อยแทน — cache ไม่มีวันได้ไฟล์ครึ่งๆ
    print(f"✅ {OUTPUT} · {os.path.getsize(OUTPUT) / 1e6:.1f} MB · ปีข้อมูล {sorted(set(years.values()))}")


def _selftest():
    assert CLASSES[lu_class("A101")] == "rice" and CLASSES[lu_class("A100")] == "rice"
    assert CLASSES[lu_class("A101+A202")] == "rice"          # นา + ข้าวโพดหลังนา → นา
    assert CLASSES[lu_class("A202+A213")] == "corn"
    assert CLASSES[lu_class("A203")] == "sugarcane" and CLASSES[lu_class("A204/A302")] == "cassava"
    assert CLASSES[lu_class("A302")] == "other_crop" and CLASSES[lu_class("F201")] == "forest"
    assert CLASSES[lu_class("U502")] == "industry" and CLASSES[lu_class("U201")] == "other"
    assert CLASSES[lu_class("M201+A101")] == "other" and lu_class("") == 0 and lu_class(None) == 0
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main({a.lower() for a in sys.argv[1:]})
