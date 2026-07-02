#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_rice_evi_s2_poc.py
PoC: Rice EVI จาก Sentinel-2 10m (แทน MODIS 1km) — เฉพาะไม่กี่จังหวัดทดสอบ

เป้าหมาย: พิสูจน์ว่า S2 10m แก้ปัญหา mixed-pixel (MODIS 625 ไร่/พิกเซล) ได้จริง
ก่อนตัดสินใจเปลี่ยนทั้งประเทศ — ไม่แตะ pipeline MODIS ที่ใช้งานจริง

- Sensor:  COPERNICUS/S2_SR_HARMONIZED (10–20m) · cloud-masked (SCL) · median รายเดือน
- EVI:     2.5·(NIR−Red)/(NIR + 6·Red − 7.5·Blue + 1)   [B8, B4, B2]
- LSWI:    (NIR−SWIR)/(NIR+SWIR)                          [B8, B11]
- Mask + phenology + GLAD-preferred: reuse จาก fetch_rice_evi.py (single source)
- Output:  data/rice-evi-s2-poc.json  (ไม่ทับ rice-evi.json)
- Compute: scale=20, tileScale=8, เฉพาะ TEST_PROVINCES → คุมโควตา GEE

รันแบบ manual (workflow_dispatch) เท่านั้น — ดู log เทียบ S2 vs MODIS vs OAE
"""
import sys, io, os, re, json
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ee
from riceutils import init_gee, build_provinces, GAUL_NAME_MAP as NAME_MAP
# reuse ตรรกะเดียวกับ MODIS pipeline (คงความสอดคล้อง)
from fetch_rice_evi import (
    get_last_month_dates, get_history_months, classify_evi,
    load_rice_mask, load_exclusion_mask,
    FLOOD_EVI_MAX, PEAK_MIN, AMP_MIN, MIN_EVI_MAX,
    GLAD_MIN_PIXELS, GLAD_BONUS_RATIO,
)

# จังหวัดทดสอบ (ชื่อ GAUL) — ครอบคลุมกรณีต่างกัน
#   Nakhon Si Thammarat = palm/rubber เยอะ (เคย overcount 13×)
#   Suphanburi          = นาแท้ภาคกลาง (naprang เยอะ)
#   Chiang Rai          = นาเหนือแปลงใหญ่
#   Phuket              = แทบไม่มีนา (ควรได้ ~0)
TEST_GAUL = ["Nakhon Si Thammarat", "Suphanburi", "Chiang Rai", "Phuket"]

REDUCE_SCALE   = 20    # m — ละเอียดกว่า MODIS 50× แต่คุมโควตาได้
TILE_SCALE     = 8     # กัน out-of-memory ตอน reduceRegions ที่ scale ละเอียด
PIXEL_AREA_RAI = (REDUCE_SCALE * REDUCE_SCALE) / 1600.0   # 1 ไร่ = 1600 m² → 20m px = 0.25 ไร่
S2 = "COPERNICUS/S2_SR_HARMONIZED"


def s2_indices(img):
    """cloud-mask (SCL) + คำนวณ EVI, LSWI จาก reflectance ที่ scale แล้ว"""
    scl = img.select("SCL")
    # ตัด: 3=cloud shadow, 8=cloud med, 9=cloud high, 10=cirrus, 11=snow
    good = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    sr   = img.select(["B2", "B4", "B8", "B11"]).multiply(0.0001)
    blue, red, nir, swir = sr.select("B2"), sr.select("B4"), sr.select("B8"), sr.select("B11")
    evi = (nir.subtract(red).multiply(2.5)
           .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1))
           .rename("EVI"))
    lswi = nir.subtract(swir).divide(nir.add(swir)).rename("LSWI")
    return evi.addBands(lswi).updateMask(good)


def s2_month(start, end, region):
    """median composite รายเดือน (cloud-masked) ในขอบเขต region"""
    col = (ee.ImageCollection(S2)
           .filterDate(start, end)
           .filterBounds(region)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
           .map(s2_indices))
    return col.median()   # ถ้าไม่มีภาพ → bands masked (safe)


def s2_phenology(history, region):
    """rice-confirmation จาก S2 (mirror เงื่อนไข MODIS: flood+peak+amp+minEVI)"""
    evi_imgs, flood_imgs = [], []
    for s, e in history:
        comp = s2_month(s, e, region)
        evi  = comp.select("EVI")
        lswi = comp.select("LSWI")
        flood_imgs.append(lswi.gt(evi).And(evi.lt(FLOOD_EVI_MAX)).rename("flooded"))
        evi_imgs.append(evi.rename("EVI"))
    flood_any = ee.ImageCollection(flood_imgs).reduce(ee.Reducer.anyNonZero()).rename("flooded")
    evi_col   = ee.ImageCollection(evi_imgs)
    evi_max, evi_min = evi_col.max(), evi_col.min()
    rice_confirm = (flood_any
                    .And(evi_max.gte(PEAK_MIN))
                    .And(evi_max.subtract(evi_min).gte(AMP_MIN))
                    .And(evi_min.lte(MIN_EVI_MAX))
                    .rename("flooded"))
    return rice_confirm


def load_oae_area():
    """OAE rice area (napi+naprang, max year) ต่อจังหวัด — เทียบความแม่น"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    def rows(path, var):
        txt = open(os.path.join(root, path), encoding="utf-8").read()
        m = re.search(re.escape(var) + r"\s*=\s*(\[.*?\])\s*;?\s*$", txt, re.S) or re.search(r"(\[.*\])", txt, re.S)
        return json.loads(m.group(1))
    def maxrai(rs):
        by = {}
        for r in rs:
            by[(r.get("province_en"), str(r.get("year")))] = by.get((r.get("province_en"), str(r.get("year"))), 0) + (r.get("area", 0) or 0)
        best = {}
        for (p, _), a in by.items():
            best[p] = max(best.get(p, 0), a)
        return best
    napi = maxrai(rows("rice-data.js", "window.RICE_DATA_ROWS"))
    napr = maxrai(rows("naprang-data.js", "window.NAPRANG_DATA_ROWS"))
    return {p: napi.get(p, 0) + napr.get(p, 0) for p in set(list(napi) + list(napr))}


def main():
    init_gee()
    start, end = get_last_month_dates()
    month_label = start[:7]
    history = get_history_months(start, 12)
    prev_end = start  # exclusive; prev month = เดือนก่อน start
    # prev month range
    from datetime import date, timedelta
    pe = date.fromisoformat(start) - timedelta(days=1)
    ps = pe.replace(day=1)
    print(f"S2 PoC — month {month_label} · provinces {TEST_GAUL} · scale {REDUCE_SCALE}m")

    provinces = build_provinces().filter(ee.Filter.inList("ADM1_NAME", TEST_GAUL))
    region = provinces.geometry()

    union_mask, glad_mask, mask_source = load_rice_mask()
    excl, excl_desc = load_exclusion_mask()
    if excl is not None:
        union_mask = union_mask.And(excl.Not())
        print(f"✓ Excluded: {excl_desc}")

    cur  = s2_month(start, end, region).select("EVI")
    prev = s2_month(ps.isoformat(), pe.isoformat(), region).select("EVI")
    rice_confirm = s2_phenology(history, region)
    flood_in_scan = rice_confirm.updateMask(union_mask)

    scan_evi  = cur.updateMask(union_mask)
    rice_evi  = cur.updateMask(flood_in_scan)
    prev_rice = prev.updateMask(flood_in_scan)
    glad_ind  = (glad_mask if glad_mask is not None else ee.Image(0)).updateMask(union_mask)

    combined = (scan_evi.rename("EVIscan")
                .addBands(rice_evi.rename("EVIrice"))
                .addBands(prev_rice.rename("EVIprev"))
                .addBands(flood_in_scan.float().rename("flooded"))
                .addBands(glad_ind.float().rename("glad")))
    result = combined.reduceRegions(
        collection=provinces,
        reducer=(ee.Reducer.mean()
                 .combine(ee.Reducer.count(), sharedInputs=True)
                 .combine(ee.Reducer.sum(),   sharedInputs=True)),
        scale=REDUCE_SCALE, tileScale=TILE_SCALE,
    )
    feats = result.select(
        ["ADM1_NAME", "EVIscan_mean", "EVIrice_mean", "EVIprev_mean",
         "EVIscan_count", "flooded_sum", "glad_sum"]).getInfo()["features"]

    oae = load_oae_area()
    modis = {}
    try:
        mj = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "data", "rice-evi.json"), encoding="utf-8"))
        modis = mj.get("provinces", {})
    except Exception:
        pass

    out = {}
    print(f"\n{'province':<22}{'S2 EVI':>8}{'S2 rai':>10}{'MODIS rai':>11}{'OAE rai':>10}  stage")
    for f in feats:
        p = f["properties"]
        name = NAME_MAP.get(p.get("ADM1_NAME", ""), p.get("ADM1_NAME", ""))
        evi = p.get("EVIrice_mean")
        prevv = p.get("EVIprev_mean")
        scan = int(p.get("EVIscan_count", 0) or 0)
        conf = int(p.get("flooded_sum", 0) or 0)
        gl   = int(p.get("glad_sum", 0) or 0)
        if evi is None or scan == 0 or conf == 0:
            out[name] = {"evi": None, "stage": None, "rice_rai": 0}
            print(f"{name:<22}{'—':>8}{0:>10,}{(modis.get(name,{}).get('rice_rai') or 0):>11,}{oae.get(name,0):>10,}  —")
            continue
        evi_r = round(float(evi), 4)
        prev_r = round(float(prevv), 4) if prevv is not None else None
        trend = round(evi_r - prev_r, 4) if prev_r is not None else None
        bonus = max(0, conf - gl)
        if gl >= GLAD_MIN_PIXELS and bonus > GLAD_BONUS_RATIO * gl:
            rice_px, basis = gl, "glad"
        else:
            rice_px, basis = conf, "union"
        rice_rai = int(round(rice_px * PIXEL_AREA_RAI))
        stage = classify_evi(evi_r, prev_r)
        out[name] = {"evi": evi_r, "evi_prev": prev_r, "trend": trend, "stage": stage,
                     "rice_rai": rice_rai, "rice_basis": basis,
                     "confidence": round(min(conf / scan, 1.0), 3),
                     "scan_rai": int(round(scan * PIXEL_AREA_RAI)),
                     "glad_rai": int(round(gl * PIXEL_AREA_RAI))}
        m_rai = modis.get(name, {}).get("rice_rai") or 0
        print(f"{name:<22}{evi_r:>8.3f}{rice_rai:>10,}{m_rai:>11,}{oae.get(name,0):>10,}  {stage}")

    output = {
        "_meta": {
            "poc": True,
            "sensor": "Sentinel-2 SR Harmonized (10-20m)",
            "note": "PoC เทียบ S2 vs MODIS vs OAE — ไม่ใช่ layer จริง",
            "reduce_scale_m": REDUCE_SCALE,
            "month": month_label,
            "provinces": TEST_GAUL,
            "mask": mask_source + (f" − exclusion({excl_desc})" if excl is not None else ""),
        },
        "month": month_label,
        "provinces": out,
    }
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    path = os.path.join(root, "data", "rice-evi-s2-poc.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {path}")


if __name__ == "__main__":
    main()
