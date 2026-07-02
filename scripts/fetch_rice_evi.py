#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_rice_evi.py
ดึงข้อมูล EVI เฉพาะพื้นที่นาข้าว รายจังหวัด ประเทศไทย
จาก NASA MODIS via Google Earth Engine + Rice Mask (GLAD) + Phenology Confirmation

Source:  MODIS/061/MOD13A3 — Monthly EVI Composite (1km)
LSWI:    MODIS/061/MOD13A3 — sur_refl_b02 (NIR) + sur_refl_b07 (SWIR2)
         ใช้ MOD13A3 แทน MOD09A1 เพราะ cloud-composited แล้ว ไม่มีปัญหาเมฆฤดูฝน
Mask:    GLAD LCLUC 2020 Rice Paddy (Class 24) ∪ MODIS MCD12Q1 Cropland
         Union mask = ขยาย scan area → Phenology gate กรอง rice-only
Method:  Hybrid Union Mask + Phenology flooding confirmation
         LSWI > EVI ใน ≥1 เดือน จาก 12 เดือนย้อนหลัง (Xiao et al. 2005)
         ครอบคลุม: นาปี (flooding Jun-Aug) + นาปรัง (flooding Dec-Jan)
         เฉพาะ pixel ที่ผ่าน Phenology จึงนับเป็น rice (confirmed)
→ บันทึกที่ data/rice-evi.json
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import calendar
import ee
import json
import os
from datetime import date, timedelta
from riceutils import init_gee, GAUL_NAME_MAP as NAME_MAP


# ── Phenology window ────────────────────────────────────────────────────────
# 12 เดือน = ครอบคลุมทั้งนาปี (flooding Jun-Aug) + นาปรัง (flooding Dec-Jan)
PHENOLOGY_MONTHS = 12   # จำนวนเดือนย้อนหลังที่ตรวจ flooding phase

# ── Rice-refinement thresholds (แก้ปัญหา mask หลุดพืชยืนต้น/พื้นที่น้ำ) ─────────
# เดิมใช้แค่ "LSWI > EVI ≥1 เดือน" → ยาง/ปาล์ม/ป่า/บ่อเลี้ยงสัตว์น้ำ/ป่าชายเลน
# หลุดเข้ามาเป็น false positive (ภูเก็ต/จันทบุรี/สุราษฎร์ฯ ขึ้นเขียวทั้งที่แทบไม่มีนา)
# เพิ่มเงื่อนไข phenology ของนาข้าวจริง (ต้องผ่านทั้ง 3):
FLOOD_EVI_MAX = 0.30   # น้ำท่วมขังต้องเกิดตอน canopy ยังโปร่ง (เตรียมดิน/ปักดำ) ไม่ใช่ป่าเขียวทึบ
PEAK_MIN      = 0.40   # ต้องมีเดือนที่ต้นข้าวขึ้น canopy เขียวจริง → ตัดน้ำเปิด/บ่อกุ้ง/นาเกลือ
AMP_MIN       = 0.20   # EVI แกว่งตามฤดูสูง → ตัดพืชยืนต้นเขียวคงที่ทั้งปี (ยาง ปาล์ม ป่า)

# ── Stage trend threshold ────────────────────────────────────────────────────
# EVI ขึ้นสูงสุดที่ "ออกรวง" แล้วลดลงตอนสร้างเมล็ด–สุกแก่ (senescence) จนเหลือ ~0.4
# ตอนเก็บเกี่ยว (Xiao et al.; Sentinel-2 rice phenology). ค่าเดือนเดียวจึงกำกวม —
# ต้องดู "ทิศทาง" เทียบเดือนก่อนหน้า: ขาขึ้น = กำลังเข้าออกรวง, ขาลง = สร้างเมล็ด/สุกแก่
TREND_EPS = 0.02       # |Δ EVI| ต่ำกว่านี้ถือว่าทรงตัว (กัน noise MODIS รายเดือน)


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_last_month_dates():
    """คืน (start, end) ของเดือนที่แล้ว"""
    today = date.today()
    first_this = today.replace(day=1)
    last_prev  = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


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


# ── Rice Mask ────────────────────────────────────────────────────────────────

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


# ── Phenology: Flooding confirmation via MOD13A3 LSWI ───────────────────────

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

    แหล่งข้อมูล: MOD13A3 (EVI + LSWI จาก b02 NIR, b07 SWIR2), cloud-composited แล้ว
    - LSWI = (NIR − SWIR2) / (NIR + SWIR2)
    - window 12 เดือน ครอบคลุมนาปี (flooding Jun-Aug) + นาปรัง (Dec-Jan)

    Return:
        rice_confirm — ee.Image binary (1 = ผ่าน phenology ครบ 3 เงื่อนไข) band "flooded"
        window_str   — "YYYY-MM to YYYY-MM"
    """
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
        .rename("flooded")
    )
    window_str = f"{history[0][0][:7]} to {history[-1][0][:7]}"
    return rice_confirm, window_str


# ── EVI stage classification (trend-aware) ────────────────────────────────────

def classify_evi(evi_val, evi_prev=None):
    """
    จำแนกระยะข้าวจาก EVI + ทิศทาง (เทียบเดือนก่อนหน้า)

    หลักการ: ความเขียว (EVI) ขึ้นสูงสุดที่ "ออกรวง/ออกดอก" แล้วลดลงตอนสร้างเมล็ด–สุกแก่
    ดังนั้นค่าสูงคือ canopy เขียวสุด (heading) ไม่ใช่ "ใกล้เก็บเกี่ยว" — นาใกล้เก็บเกี่ยว
    EVI จะ "ลดลง" ต่างหาก. เมื่อรู้ทิศทางจึงแยก heading (ขาขึ้น) กับ ripening (ขาลง) ได้

    evi_prev = None → ไม่รู้ทิศทาง → เดาเป็นขาขึ้น (label ตามระดับความเขียว)
    """
    if evi_val is None:
        return None
    if evi_val < 0.15:
        return "fallow"        # นาว่าง / เตรียมดิน / น้ำขัง
    rising = True if evi_prev is None else (evi_val - evi_prev) >= -TREND_EPS
    if evi_val < 0.25:
        return "seedling" if rising else "harvest"    # ต้นกล้า(ขึ้น) / เก็บเกี่ยว-ตอซัง(ลง)
    if evi_val < 0.40:
        return "tillering" if rising else "ripening"  # แตกกอ(ขึ้น) / สุกแก่(ลง)
    # EVI ≥ 0.40 = canopy หนาแน่น
    if evi_val < 0.55:
        return "heading" if rising else "ripening"    # ออกรวง(ขึ้น) / สร้างเมล็ด-สุกแก่(ลง)
    return "heading"           # ≥0.55 = ยอด canopy เขียวสุด = ออกรวง/ออกดอก (ไม่ใช่สุกแก่)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_gee()

    start, end = get_last_month_dates()
    month_label = start[:7]
    print(f"Fetching Rice EVI: {start} → {end}")

    # ── MODIS MOD13A3 Monthly EVI (เดือนเป้าหมาย) ──────────────────────────
    collection = (
        ee.ImageCollection("MODIS/061/MOD13A3")
        .filterDate(start, end)
        .select("EVI")
    )
    count = collection.size().getInfo()
    if count == 0:
        prev_start = (
            date.fromisoformat(start).replace(day=1) - timedelta(days=1)
        ).replace(day=1).isoformat()
        prev_end = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        print(f"  No data for {start}–{end}, fallback to {prev_start}–{prev_end}")
        collection = (
            ee.ImageCollection("MODIS/061/MOD13A3")
            .filterDate(prev_start, prev_end)
            .select("EVI")
        )
        month_label = prev_start[:7]
        start, end  = prev_start, prev_end

    evi_img = collection.first().multiply(0.0001)

    # ── Hybrid Union Mask (GLAD ∪ MCD12Q1 Cropland) ─────────────────────────
    union_mask, glad_mask, mask_source = load_rice_mask()

    # ── Previous-month EVI (สำหรับดูทิศทาง ขึ้น/ลง → แยก heading vs ripening) ──
    prev_end_d   = date.fromisoformat(start) - timedelta(days=1)
    prev_start_d = prev_end_d.replace(day=1)
    prev_evi_img = (
        ee.ImageCollection("MODIS/061/MOD13A3")
        .filterDate(prev_start_d.isoformat(), prev_end_d.isoformat())
        .select("EVI")
        .mosaic()               # all-masked ถ้าไม่มีข้อมูล → EVIprev_mean = null → trend None
        .multiply(0.0001)
    )
    print(f"  Previous month for trend: {prev_start_d.isoformat()[:7]}")

    # ── Phenology rice-confirmation mask (flood + peak + amplitude) ─────────
    print(f"Building rice phenology mask (flood+peak+amplitude, {PHENOLOGY_MONTHS} months)...")
    flood_confirmation, pheno_window = build_rice_phenology_mask(
        start, PHENOLOGY_MONTHS
    )

    # ── Apply masks ────────────────────────────────────────────────────────
    # scan_evi       = EVI masked by UNION area (GLAD ∪ cropland)
    # prev_in_scan   = previous-month EVI within UNION area (for trend)
    # flood_in_scan  = rice confirmation within UNION area
    # glad_indicator = binary 1/0 per pixel: was this pixel in GLAD?
    scan_evi      = evi_img.updateMask(union_mask)
    prev_in_scan  = prev_evi_img.updateMask(union_mask)
    flood_in_scan = flood_confirmation.updateMask(union_mask)
    # glad_indicator: 1 = GLAD rice pixel, masked elsewhere
    # ถ้า GLAD ไม่มี → zero image (glad_sum = 0, bonus_pixels จะเป็น N/A)
    _glad_src      = glad_mask if glad_mask is not None else ee.Image(0)
    glad_indicator = _glad_src.updateMask(union_mask)
    print("✓ Applied union mask (GLAD ∪ MCD12Q1) + rice phenology mask")

    # ── Thailand provinces (FAO GAUL 2015 + Bueng Kan supplement) ──────────
    # FAO GAUL 2015 มีแค่ 76 จังหวัด — ไม่มีบึงกาฬ (แยกจากหนองคายปี 2554)
    # แก้ไขโดย append custom feature สำหรับบึงกาฬ
    gaul_provinces = (
        ee.FeatureCollection("FAO/GAUL/2015/level1")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )

    # บึงกาฬ — approximate boundary (ใช้ได้กับ MODIS 1km resolution)
    # พิกัดจาก GADM 4.1 / OpenStreetMap boundary (ตัดทอนให้กระชับ)
    # พื้นที่จริง ~4,305 km² | centroid ~18.39°N 103.65°E
    bueng_kan_poly = ee.Geometry.Polygon([[
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
    ]])
    bueng_kan_feat = ee.Feature(bueng_kan_poly, {
        "ADM1_NAME": "Bung Kan",   # ชื่อที่ NAME_MAP map → "Bueng Kan"
        "ADM0_NAME": "Thailand",
    })
    bueng_kan_fc = ee.FeatureCollection([bueng_kan_feat])

    provinces = gaul_provinces.merge(bueng_kan_fc)
    print(f"✓ Provinces: GAUL 76 + Bueng Kan = 77 total")

    # ── Combined reduceRegions: 4-band image ──────────────────────────────
    # Band "EVI"     = EVI within union scan area (เดือนนี้)
    # Band "EVIprev" = EVI เดือนก่อนหน้า (สำหรับ trend)
    # Band "flooded" = phenology confirmation (binary 0/1)
    # Band "glad"    = GLAD indicator (1 = GLAD rice pixel, 0 = MCD12Q1 only)
    #
    # Reducer เอา:
    #   mean  → EVI_mean, EVIprev_mean, flooded_mean, glad_mean
    #   count → EVI_count (= total scan pixels per province)
    #   sum   → flooded_sum (= confirmed pixels), glad_sum (= GLAD-only pixels)
    combined_img = (
        scan_evi.rename("EVI")
        .addBands(prev_in_scan.rename("EVIprev"))
        .addBands(flood_in_scan.float().rename("flooded"))
        .addBands(glad_indicator.float().rename("glad"))
    )

    result = combined_img.reduceRegions(
        collection=provinces,
        reducer=(
            ee.Reducer.mean()
            .combine(reducer2=ee.Reducer.count(), sharedInputs=True)
            .combine(reducer2=ee.Reducer.sum(),   sharedInputs=True)
        ),
        scale=1000,
    )

    features = result.select(
        ["ADM1_NAME", "EVI_mean", "EVIprev_mean", "EVI_count", "flooded_sum", "glad_sum"]
    ).getInfo()["features"]
    print(f"  Got {len(features)} provinces from GEE")

    # ── Build output ─────────────────────────────────────────────────────────
    provinces_data = {}
    null_provinces  = []

    for f in features:
        props           = f["properties"]
        gaul_name       = props.get("ADM1_NAME", "")
        evi_val         = props.get("EVI_mean")
        evi_prev_val    = props.get("EVIprev_mean")
        scan_count      = int(props.get("EVI_count",    0) or 0)
        confirmed_count = int(props.get("flooded_sum",  0) or 0)
        glad_count      = int(props.get("glad_sum",     0) or 0)

        mapped = NAME_MAP.get(gaul_name, gaul_name)

        if evi_val is not None and scan_count > 0:
            evi_rounded   = round(float(evi_val), 4)
            evi_prev_r    = round(float(evi_prev_val), 4) if evi_prev_val is not None else None
            trend         = round(evi_rounded - evi_prev_r, 4) if evi_prev_r is not None else None
            # confidence = confirmed (phenology-verified rice) / total scan area
            confidence    = round(min(confirmed_count / scan_count, 1.0), 3)
            stage         = classify_evi(evi_rounded, evi_prev_r)
            # rice_pixels/rice_rai = confirmed pixels (actual rice with flooding)
            rice_area_rai = int(confirmed_count * 625)
            scan_rai      = int(scan_count      * 625)
            glad_rai      = int(glad_count      * 625)
            # bonus = pixels found by MCD12Q1 that GLAD missed
            bonus_count   = max(0, confirmed_count - glad_count)

            provinces_data[mapped] = {
                "evi":          evi_rounded,
                "evi_prev":     evi_prev_r,          # EVI เดือนก่อนหน้า (None ถ้าไม่มีข้อมูล)
                "trend":        trend,               # Δ EVI = เดือนนี้ − เดือนก่อน (+ ขึ้น / − ลง)
                "stage":        stage,
                "rice_pixels":  confirmed_count,    # confirmed rice (phenology-gated)
                "rice_rai":     rice_area_rai,       # ไร่ นาข้าวที่ยืนยันแล้ว
                "confidence":   confidence,
                "scan_pixels":  scan_count,          # total union scan area
                "scan_rai":     scan_rai,
                "glad_pixels":  glad_count,          # GLAD rice pixels (subset; 0 if GLAD unavailable)
                "glad_rai":     glad_rai,
                "bonus_pixels": bonus_count,         # extra rice found by MCD12Q1 (0 if GLAD unavailable)
            }
        else:
            provinces_data[mapped] = {
                "evi":          None,
                "evi_prev":     None,
                "trend":        None,
                "stage":        None,
                "rice_pixels":  0,
                "rice_rai":     0,
                "confidence":   None,
                "scan_pixels":  0,
                "scan_rai":     0,
                "glad_pixels":  0,
                "glad_rai":     0,
                "bonus_pixels": 0,
            }
            null_provinces.append(gaul_name)

    if null_provinces:
        print(f"  ⚠️ provinces with no rice pixels: {null_provinces}")

    # ── Summary stats ────────────────────────────────────────────────────────
    valid = [v for v in provinces_data.values() if v["evi"] is not None]
    if valid:
        evi_vals  = [v["evi"]        for v in valid]
        conf_vals = [v["confidence"] for v in valid]
        print(f"  EVI range:        {min(evi_vals):.3f} – {max(evi_vals):.3f}")
        print(f"  EVI average:      {sum(evi_vals)/len(evi_vals):.3f}")
        print(f"  Confidence range: {min(conf_vals):.1%} – {max(conf_vals):.1%}")
        print(f"  Confidence avg:   {sum(conf_vals)/len(conf_vals):.1%}")

        # ── Hybrid mask effectiveness ──
        total_glad   = sum(v["glad_pixels"]  for v in valid)
        total_scan   = sum(v["scan_pixels"]  for v in valid)
        total_conf   = sum(v["rice_pixels"] for v in valid)
        total_bonus  = sum(v["bonus_pixels"] for v in valid)
        print(f"  GLAD rice pixels:   {total_glad:,}")
        print(f"  Union scan pixels:  {total_scan:,}")
        print(f"  Confirmed rice:     {total_conf:,}  ({total_conf*625:,.0f} rai)")
        print(f"  Bonus from MCD12Q1: +{total_bonus:,} pixels ({total_bonus*625:,.0f} rai)")

        # จังหวัดที่ได้ประโยชน์จาก hybrid mask มากที่สุด
        boosted = [(k, v) for k, v in provinces_data.items()
                   if v.get("bonus_pixels", 0) > 0]
        if boosted:
            boosted.sort(key=lambda x: x[1]["bonus_pixels"], reverse=True)
            print("  📈 Provinces boosted by MCD12Q1:")
            for name, v in boosted[:10]:
                old_px = v["glad_pixels"]
                new_px = v["rice_pixels"]
                bonus  = v["bonus_pixels"]
                print(f"     {name}: GLAD {old_px} → confirmed {new_px}  (+{bonus} bonus, +{bonus*625:,} rai)")

    stage_counts = {}
    for v in provinces_data.values():
        s = v.get("stage")
        if s:
            stage_counts[s] = stage_counts.get(s, 0) + 1
    print(f"  Stage distribution: {stage_counts}")

    # ── Write output ─────────────────────────────────────────────────────────
    output = {
        "_meta": {
            "source":     "NASA MODIS MOD13A3 (EVI + LSWI) via Google Earth Engine",
            "source_url": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3",
            "dataset":    "MODIS/061/MOD13A3 (EVI + LSWI: b02 NIR, b07 SWIR2)",
            "rice_mask":  mask_source,
            "method":     (
                "Hybrid Union Mask (GLAD rice ∪ MCD12Q1 cropland) + "
                "Rice phenology gate: flood ตอน canopy โปร่ง (LSWI>EVI & EVI<%.2f) "
                "AND peak EVI≥%.2f AND seasonal amplitude≥%.2f จาก %d เดือน "
                "(Xiao et al. 2005 + amplitude gate ตัดพืชยืนต้น). "
                "Stage แยกด้วยทิศทาง EVI (heading ขาขึ้น / ripening ขาลง)"
                % (FLOOD_EVI_MAX, PEAK_MIN, AMP_MIN, PHENOLOGY_MONTHS)
            ),
            "phenology_window":     pheno_window,
            "phenology_months":     PHENOLOGY_MONTHS,
            "thresholds": {
                "flood_evi_max": FLOOD_EVI_MAX,
                "peak_min":      PEAK_MIN,
                "amp_min":       AMP_MIN,
                "trend_eps":     TREND_EPS,
            },
            "resolution":           "1 km / monthly composite",
            "period":               f"{start} to {end}",
            "month":                month_label,
            "updated":              date.today().isoformat(),
            "provinces_covered":    len(valid),
            "note": (
                f"Rice phenology gate ({PHENOLOGY_MONTHS} เดือน): flood ตอน canopy โปร่ง + "
                f"peak EVI≥{PEAK_MIN} + amplitude≥{AMP_MIN} → ตัดพืชยืนต้น (ยาง/ปาล์ม/ป่า) "
                f"และพื้นที่น้ำ (บ่อกุ้ง/ป่าชายเลน/นาเกลือ) ออกจากนาข้าว. "
                f"stage ใช้ทิศทาง EVI: ค่าสูง=ออกรวง(ยอดเขียว) ไม่ใช่สุกแก่ — สุกแก่ EVI ลดลง"
            ),
            "fields": {
                "evi":          "ค่าเฉลี่ย EVI เดือนนี้ (union scan area)",
                "evi_prev":     "ค่าเฉลี่ย EVI เดือนก่อนหน้า (null ถ้าไม่มีข้อมูล)",
                "trend":        "Δ EVI = เดือนนี้ − เดือนก่อน (+ ขาขึ้น / − ขาลง)",
                "stage":        "ระยะข้าวจาก EVI + ทิศทาง (heading ขาขึ้น / ripening ขาลง)",
                "rice_pixels":  "pixel นาข้าวที่ผ่าน Phenology (confirmed)",
                "rice_rai":     "พื้นที่นาข้าวยืนยัน (ไร่)",
                "confidence":   "สัดส่วน confirmed/scan (0-1)",
                "scan_pixels":  "total union scan area (GLAD ∪ MCD12Q1)",
                "scan_rai":     "พื้นที่ scan ทั้งหมด (ไร่)",
                "glad_pixels":  "pixel จาก GLAD rice (0 ถ้า GLAD unavailable)",
                "glad_rai":     "พื้นที่ GLAD rice (ไร่)",
                "bonus_pixels": "pixel เพิ่มจาก MCD12Q1 ที่ผ่าน Phenology (0 ถ้า GLAD unavailable)",
            },
            "stages": {
                "fallow":    "นาว่าง / เตรียมดิน (EVI < 0.15)",
                "seedling":  "ต้นกล้า / ปักดำ (EVI 0.15–0.25 · ขาขึ้น)",
                "tillering": "แตกกอ / เจริญเติบโต (EVI 0.25–0.40 · ขาขึ้น)",
                "heading":   "ออกรวง / ออกดอก · ยอด canopy เขียวสุด (EVI ≥ 0.40 ขาขึ้น หรือ ≥ 0.55)",
                "ripening":  "สร้างเมล็ด / สุกแก่ · ใกล้เก็บเกี่ยว (EVI ขาลงจากยอด)",
                "harvest":   "เก็บเกี่ยว / ตอซัง (EVI 0.15–0.25 · ขาลง)",
            },
        },
        "month": month_label,
        "provinces": dict(sorted(provinces_data.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "rice-evi.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(provinces_data)} provinces → {out_path}")
    print(f"   Method: GLAD + Phenology (window: {pheno_window})")


if __name__ == "__main__":
    main()
