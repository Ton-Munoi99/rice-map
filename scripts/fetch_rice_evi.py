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
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import calendar
import ee
import json
import os
from riceutils import bkk_today, init_gee, GAUL_NAME_MAP as NAME_MAP
from riceutils import PHENOLOGY_MONTHS, FLOOD_EVI_MAX, PEAK_MIN, AMP_MIN, MIN_EVI_MAX, RUBBER_ASSET, load_rice_mask, load_exclusion_mask, get_history_months, build_rice_phenology_mask, latest_q1_periods, q1_evi_image
from rice_stage import TREND_EPS, classify_evi


# ── EVI stage classification (trend-aware) ────────────────────────────────────

# classify_evi ย้ายไป rice_stage.py แล้ว (ใช้ร่วมกับสคริปต์ระดับอำเภอ + ตัวคำนวณซ้ำ)
def main():
    init_gee()

    # ── MOD13Q1 composite ราย 16 วัน ล่าสุด (ค่าที่แสดงบนแผนที่) ───────────
    # เดิมใช้ MOD13A3 รายเดือนซึ่งออกช้าจนเว็บแสดงข้อมูลเก่า 2 เดือน
    periods = latest_q1_periods(n=4)
    if not periods:
        raise RuntimeError("ไม่พบ composite MOD13Q1 ในช่วง 80 วันล่าสุด")
    # รวม 2 composite (~32 วัน) เพื่ออุดรูที่เมฆบัง — ครอบคลุมกลับมาใกล้รายเดือน
    start, end = periods[1][0], periods[0][1]
    month_label = start[:7]
    print(f"Fetching Rice EVI (MOD13Q1 16-day): {start} → {end}")
    evi_img = q1_evi_image(start, end)

    # ── Hybrid Union Mask (GLAD ∪ MCD12Q1 Cropland) ─────────────────────────
    union_mask, glad_mask, mask_source = load_rice_mask()

    # ── ลบพืชยืนต้น (ปาล์ม/ยาง) ออกจาก scan area ───────────────────────────
    exclusion_mask, excl_desc = load_exclusion_mask()
    if exclusion_mask is not None:
        union_mask = union_mask.And(exclusion_mask.Not())
        mask_source += f" − exclusion({excl_desc})"
        print(f"✓ Excluded perennial crops: {excl_desc}")
    else:
        print("  → No perennial-crop exclusion layer (relying on phenology gate)")

    # ── EVI ของ composite ก่อนหน้า (ดูทิศทางขึ้น/ลงของทรงพุ่ม) ─────────────
    # ทิศทางวัดข้าม 16 วันแทน 1 เดือน จึงแกว่งน้อยกว่าเดิมโดยธรรมชาติ
    # TREND_EPS เท่าเดิม = การตัดสิน "ขาลง" เข้มขึ้นเล็กน้อย ซึ่งเป็นทางที่ปลอดภัยกว่า
    if len(periods) > 3:
        prev_start_iso, prev_end_iso = periods[3][0], periods[2][1]
        prev_evi_img = q1_evi_image(prev_start_iso, prev_end_iso)
    else:
        prev_start_iso = prev_end_iso = None
        prev_evi_img = evi_img.updateMask(ee.Image(0))  # all-masked → trend = None
    print(f"  Previous window for trend: {prev_start_iso or '—'} → {prev_end_iso or '—'}")

    # ── Phenology rice-confirmation mask (flood + peak + amplitude) ─────────
    print(f"Building rice phenology mask (flood+peak+amplitude, {PHENOLOGY_MONTHS} months)...")
    flood_confirmation, pheno_window = build_rice_phenology_mask(
        start, PHENOLOGY_MONTHS
    )

    # ── Apply masks ────────────────────────────────────────────────────────
    # scan_evi       = EVI masked by UNION area (GLAD ∪ cropland) — ใช้นับ scan pixels
    # flood_in_scan  = rice confirmation within UNION area (binary)
    # rice_evi       = EVI เฉพาะพิกเซลนาที่ยืนยันแล้ว → mean = ความเขียวของ "นา" จริง
    #                  (เดิมเฉลี่ยทั้ง union scan ทำให้ยาง/ปาล์มปนค่าความเขียว)
    # prev_rice      = EVI เดือนก่อน เฉพาะพิกเซลนาที่ยืนยัน (สำหรับ trend ที่สะอาด)
    # glad_indicator = binary 1/0 per pixel: was this pixel in GLAD?
    scan_evi      = evi_img.updateMask(union_mask)
    flood_in_scan = flood_confirmation.updateMask(union_mask)
    rice_evi      = evi_img.updateMask(flood_in_scan)
    prev_rice     = prev_evi_img.updateMask(flood_in_scan)
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

    # ── Combined reduceRegions: 5-band image ──────────────────────────────
    # Band "EVIscan" = EVI ทั้ง union scan (ใช้ count = scan pixels + mean diagnostic)
    # Band "EVIrice" = EVI เฉพาะพิกเซลนายืนยัน (mean = ความเขียวของนาจริง — ใช้ทำ stage)
    # Band "EVIprev" = EVI เดือนก่อน เฉพาะพิกเซลนายืนยัน (สำหรับ trend)
    # Band "flooded" = phenology confirmation (binary 0/1)
    # Band "glad"    = GLAD indicator (1 = GLAD rice pixel, 0 = MCD12Q1 only)
    #
    # Reducer เอา:
    #   mean  → EVIscan_mean, EVIrice_mean, EVIprev_mean, flooded_mean, glad_mean
    #   count → EVIscan_count (= total scan pixels per province)
    #   sum   → flooded_sum (= confirmed pixels), glad_sum (= GLAD-only pixels)
    combined_img = (
        scan_evi.rename("EVIscan")
        .addBands(rice_evi.rename("EVIrice"))
        .addBands(prev_rice.rename("EVIprev"))
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
        ["ADM1_NAME", "EVIscan_mean", "EVIrice_mean", "EVIprev_mean",
         "EVIscan_count", "flooded_sum", "glad_sum"]
    ).getInfo()["features"]
    print(f"  Got {len(features)} provinces from GEE")

    # ── Build output ─────────────────────────────────────────────────────────
    provinces_data = {}
    null_provinces  = []

    for f in features:
        props           = f["properties"]
        gaul_name       = props.get("ADM1_NAME", "")
        evi_val         = props.get("EVIrice_mean")     # ความเขียวเฉพาะนายืนยัน
        evi_scan_val    = props.get("EVIscan_mean")     # ความเขียวทั้ง scan (diagnostic)
        evi_prev_val    = props.get("EVIprev_mean")
        scan_count      = int(props.get("EVIscan_count", 0) or 0)
        confirmed_count = int(props.get("flooded_sum",  0) or 0)
        glad_count      = int(props.get("glad_sum",     0) or 0)

        mapped = NAME_MAP.get(gaul_name, gaul_name)

        # ต้องมีทั้งพื้นที่ scan และพิกเซลนายืนยัน (evi_val = rice-only mean)
        if evi_val is not None and scan_count > 0 and confirmed_count > 0:
            evi_rounded   = round(float(evi_val), 4)
            evi_scan_r    = round(float(evi_scan_val), 4) if evi_scan_val is not None else None
            evi_prev_r    = round(float(evi_prev_val), 4) if evi_prev_val is not None else None
            trend         = round(evi_rounded - evi_prev_r, 4) if evi_prev_r is not None else None
            # confidence = confirmed (phenology-verified rice) / total scan area
            confidence    = round(min(confirmed_count / scan_count, 1.0), 3)
            stage         = classify_evi(evi_rounded, evi_prev_r)
            # bonus = pixels found by MCD12Q1 that GLAD missed
            bonus_count   = max(0, confirmed_count - glad_count)
            # เดิมมีกฎ "GLAD-preferred": ถ้า cropland-bonus เกิน 3 เท่าของ GLAD ให้เชื่อ
            # GLAD อย่างเดียว ตั้งใจกันยาง/ปาล์มที่หลุดมาใน cropland — แต่วัดจริงแล้ว
            # กฎนี้ทำงานเฉพาะ 10 จังหวัดข้าวใหญ่ (นครสวรรค์ อยุธยา ร้อยเอ็ด พิจิตร สุรินทร์…)
            # ซึ่งไม่มียาง/ปาล์ม และตัดพื้นที่นาจริงทิ้งรวม 9.2 ล้านไร่
            # อยุธยาเหลือ 6,875 ไร่ ทั้งที่ OAE มี 811,742 ไร่ — GLAD จับนาไม่ครบเอง
            # ส่วนจังหวัดยาง/ปาล์มที่กฎตั้งใจกัน ไม่เคยเข้าเงื่อนไขเลยสักจังหวัด
            # ถอดกฎแล้ว: ดีขึ้น 10 จังหวัด แย่ลง 0 · คลาดกลาง 53%→43% เฉลี่ย 60%→51%
            rice_count, rice_basis = confirmed_count, "union"
            rice_area_rai = int(rice_count    * 625)   # ไร่ นาข้าว (GLAD-preferred)
            scan_rai      = int(scan_count    * 625)
            glad_rai      = int(glad_count    * 625)
            confirmed_rai = int(confirmed_count * 625) # union ∩ phenology (diagnostic)

            provinces_data[mapped] = {
                "evi":          evi_rounded,         # ความเขียวเฉพาะพิกเซลนายืนยัน
                "evi_scan":     evi_scan_r,          # ความเขียวทั้ง scan area (diagnostic)
                "evi_prev":     evi_prev_r,          # EVI เดือนก่อนหน้า เฉพาะนายืนยัน (None ถ้าไม่มี)
                "trend":        trend,               # Δ EVI = เดือนนี้ − เดือนก่อน (+ ขึ้น / − ลง)
                "stage":        stage,
                "rice_pixels":  rice_count,          # GLAD-preferred rice pixels
                "rice_rai":     rice_area_rai,       # ไร่ นาข้าว (GLAD-preferred)
                "rice_basis":   rice_basis,          # "glad" = เชื่อแกน GLAD / "union" = รวม bonus
                "confidence":   confidence,          # confirmed/scan (phenology pass rate)
                "confirmed_pixels": confirmed_count, # union ∩ phenology (ก่อน GLAD-preferred)
                "confirmed_rai":    confirmed_rai,
                "scan_pixels":  scan_count,          # total union scan area
                "scan_rai":     scan_rai,
                "glad_pixels":  glad_count,          # GLAD rice pixels (subset; 0 if GLAD unavailable)
                "glad_rai":     glad_rai,
                "bonus_pixels": bonus_count,         # extra rice found by MCD12Q1 (0 if GLAD unavailable)
            }
        else:
            provinces_data[mapped] = {
                "evi":          None,
                "evi_scan":     None,
                "evi_prev":     None,
                "trend":        None,
                "stage":        None,
                "rice_pixels":  0,
                "rice_rai":     0,
                "rice_basis":   None,
                "confidence":   None,
                "confirmed_pixels": 0,
                "confirmed_rai":    0,
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
        total_glad   = sum(v["glad_pixels"]      for v in valid)
        total_scan   = sum(v["scan_pixels"]      for v in valid)
        total_conf   = sum(v["confirmed_pixels"] for v in valid)
        total_rice   = sum(v["rice_pixels"]      for v in valid)   # GLAD-preferred
        total_bonus  = sum(v["bonus_pixels"]     for v in valid)
        print(f"  GLAD rice pixels:      {total_glad:,}")
        print(f"  Union scan pixels:     {total_scan:,}")
        print(f"  Confirmed (union∩phen):{total_conf:,}  ({total_conf*625:,.0f} rai)")
        print(f"  Rice (GLAD-preferred): {total_rice:,}  ({total_rice*625:,.0f} rai)")
        print(f"  Bonus from MCD12Q1:    +{total_bonus:,} pixels ({total_bonus*625:,.0f} rai)")

        # จังหวัดที่ GLAD-preferred ตัด bonus ออก (bonus มากผิดปกติ → น่าจะพืชอื่น)
        trimmed = [(k, v) for k, v in provinces_data.items()
                   if v.get("rice_basis") == "glad"]
        if trimmed:
            trimmed.sort(key=lambda x: x[1]["confirmed_pixels"] - x[1]["rice_pixels"], reverse=True)
            print(f"  ✂️  GLAD-preferred trimmed {len(trimmed)} provinces (bonus likely non-rice):")
            for name, v in trimmed[:10]:
                cut = (v["confirmed_pixels"] - v["rice_pixels"]) * 625
                print(f"     {name}: {v['confirmed_rai']:,} → {v['rice_rai']:,} rai  (−{cut:,} rai trimmed)")

    stage_counts = {}
    for v in provinces_data.values():
        s = v.get("stage")
        if s:
            stage_counts[s] = stage_counts.get(s, 0) + 1
    print(f"  Stage distribution: {stage_counts}")

    # ── Write output ─────────────────────────────────────────────────────────
    output = {
        "_meta": {
            "source":     "NASA MODIS MOD13Q1 16-day EVI (250m) + MOD13A3 LSWI mask via Google Earth Engine",
            "source_url": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1",
            "dataset":    "MODIS/061/MOD13Q1 (EVI, 16-day 250m) · mask/phenology: MODIS/061/MOD13A3 monthly 1km",
            "period_start": start,
            "period_end":   end,
            "composite_days": 16,
            "rice_mask":  mask_source,
            "method":     (
                "Hybrid Union Mask (GLAD rice ∪ MCD12Q1 cropland) + "
                "Rice phenology gate: flood ตอน canopy โปร่ง (LSWI>EVI & EVI<%.2f) "
                "AND peak EVI≥%.2f AND amplitude≥%.2f AND min EVI≤%.2f จาก %d เดือน "
                "(Xiao et al. 2005 + amplitude/min-EVI gate ตัดยาง/ปาล์ม/ป่า). "
                "ค่า EVI/stage เฉลี่ยเฉพาะพิกเซลนายืนยัน (ไม่ปนพืชยืนต้น). "
                "rice_rai แบบ GLAD-preferred (ตัด cropland-bonus ที่มากผิดปกติ). "
                "Stage แยกด้วยทิศทาง EVI (heading ขาขึ้น / ripening ขาลง)"
                % (FLOOD_EVI_MAX, PEAK_MIN, AMP_MIN, MIN_EVI_MAX, PHENOLOGY_MONTHS)
            ),
            "phenology_window":     pheno_window,
            "phenology_months":     PHENOLOGY_MONTHS,
            "thresholds": {
                "flood_evi_max": FLOOD_EVI_MAX,
                "peak_min":      PEAK_MIN,
                "amp_min":       AMP_MIN,
                "min_evi_max":   MIN_EVI_MAX,
                "trend_eps":     TREND_EPS,
            },
            "resolution":           "1 km / monthly composite",
            "period":               f"{start} to {end}",
            "month":                month_label,
            "updated":              bkk_today(),
            "provinces_covered":    len(valid),
            "note": (
                f"Rice phenology gate ({PHENOLOGY_MONTHS} เดือน): flood ตอน canopy โปร่ง + "
                f"peak EVI≥{PEAK_MIN} + amplitude≥{AMP_MIN} → ตัดพืชยืนต้น (ยาง/ปาล์ม/ป่า) "
                f"และพื้นที่น้ำ (บ่อกุ้ง/ป่าชายเลน/นาเกลือ) ออกจากนาข้าว. "
                f"stage ใช้ทิศทาง EVI: ค่าสูง=ออกรวง(ยอดเขียว) ไม่ใช่สุกแก่ — สุกแก่ EVI ลดลง"
            ),
            "fields": {
                "evi":          "ค่าเฉลี่ย EVI เฉพาะพิกเซลนายืนยัน (ไม่ปนพืชยืนต้น)",
                "evi_scan":     "ค่าเฉลี่ย EVI ทั้ง union scan (diagnostic — รวมพืชอื่น)",
                "evi_prev":     "ค่าเฉลี่ย EVI เดือนก่อนหน้า เฉพาะนายืนยัน (null ถ้าไม่มีข้อมูล)",
                "trend":        "Δ EVI = เดือนนี้ − เดือนก่อน (+ ขาขึ้น / − ขาลง)",
                "stage":        "ระยะข้าวจาก EVI + ทิศทาง (heading ขาขึ้น / ripening ขาลง)",
                "rice_pixels":  "pixel นาข้าว GLAD-preferred (ใช้แสดงผล)",
                "rice_rai":     "พื้นที่นาข้าว GLAD-preferred (ไร่)",
                "rice_basis":   "glad = เชื่อแกน GLAD (ตัด bonus) / union = รวม cropland bonus",
                "confirmed_pixels": "pixel union∩phenology ก่อน GLAD-preferred (diagnostic)",
                "confirmed_rai":    "พื้นที่ union∩phenology (ไร่, diagnostic)",
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
