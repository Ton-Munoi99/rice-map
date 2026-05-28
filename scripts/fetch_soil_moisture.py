#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_soil_moisture.py
ดึงข้อมูลความชื้นในดิน (soil moisture) รายจังหวัด ประเทศไทย จาก NASA SMAP via Google Earth Engine
→ บันทึกที่ data/soil-moisture.json

Strategy (hybrid):
  Primary:  SMAP L3 SPL3SMP_E/006 — direct satellite retrieval, 9km, AM+PM quality-masked
  Fallback: SMAP L4 SPL4SMGP/008 — model-assimilated gap-fill, 11km, global coverage
            ใช้เฉพาะจังหวัดที่ L3 return null (เมือง/ชายฝั่ง/ป่าหนา)

Source:
  L3 NASA/SMAP/SPL3SMP_E/006 — soil_moisture_am/pm (cm³/cm³) × 200 → 0–100%
  L4 NASA/SMAP/SPL4SMGP/008 — sm_surface_wetness (0–1) × 100 → 0–100%
Auth:   GEE Service Account (GEE_SERVICE_ACCOUNT_KEY env var)
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ee
import json
import os
from datetime import date, datetime, timedelta, timezone

# ── Province name mapping: GAUL → rice-map ─────────────────────────────────
NAME_MAP = {
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

# ── Dataset config ────────────────────────────────────────────────────────────
L3_COLLECTION = "NASA/SMAP/SPL3SMP_E/006"
L3_BAND_AM    = "soil_moisture_am"
L3_BAND_PM    = "soil_moisture_pm"
L3_QUAL_AM    = "retrieval_qual_flag_am"
L3_QUAL_PM    = "retrieval_qual_flag_pm"
L3_SCALE      = 9000   # 9 km
L3_SM_SCALE   = 200    # cm³/cm³ × 200 → 0–100% (0.5 saturated = 100%)

L4_COLLECTION = "NASA/SMAP/SPL4SMGP/008"
L4_BAND       = "sm_surface_wetness"   # 0–1 fraction, already normalized
L4_SCALE      = 11000  # 11 km
L4_SM_SCALE   = 100    # × 100 → 0–100%


# ── GEE Auth ─────────────────────────────────────────────────────────────────
def init_gee():
    key_data = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    if key_data:
        key_dict = json.loads(key_data)
        credentials = ee.ServiceAccountCredentials(
            email=key_dict["client_email"],
            key_data=key_dict["private_key"],
        )
        ee.Initialize(credentials, project="agriculture-monitoring-497007")
        print("✓ Authenticated via Service Account")
    else:
        ee.Initialize(project="agriculture-monitoring-497007")
        print("✓ Authenticated via default credentials")


# ── Province polygons (GAUL 76 + Bueng Kan) ──────────────────────────────────
def build_provinces():
    gaul_provinces = (
        ee.FeatureCollection("FAO/GAUL/2015/level1")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
    )
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
        "ADM1_NAME": "Bung Kan", "ADM0_NAME": "Thailand",
    })
    return gaul_provinces.merge(ee.FeatureCollection([bueng_kan_feat]))


# ── Find latest available date ────────────────────────────────────────────────
def get_smap_window(col, window_days=7, label=""):
    latest_ts = (
        col.sort("system:time_start", False)
        .first()
        .get("system:time_start")
        .getInfo()
    )
    latest_dt     = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
    end_day       = latest_dt.date()
    start_day     = end_day - timedelta(days=window_days - 1)
    end_exclusive = end_day + timedelta(days=1)
    print(f"  {label} window ({window_days}d): {start_day} → {end_day} "
          f"(latest: {latest_dt.strftime('%Y-%m-%d')})")
    return start_day.isoformat(), end_day.isoformat(), end_exclusive.isoformat()


# ── L3: combine AM+PM with quality masking ───────────────────────────────────
def add_l3_combined(image):
    am = image.select(L3_BAND_AM).updateMask(image.select(L3_QUAL_AM).eq(0))
    pm = image.select(L3_BAND_PM).updateMask(image.select(L3_QUAL_PM).eq(0))
    combined = (
        am.rename("sm").addBands(pm.rename("sm_pm"))
        .reduce(ee.Reducer.mean())
        .rename("sm")
    )
    return combined


# ── Run reduceRegions and parse results ──────────────────────────────────────
def reduce_provinces(img, provinces, scale, sm_scale, source_label):
    result   = img.multiply(sm_scale).clamp(0, 100).reduceRegions(
        collection=provinces,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )
    features = result.getInfo()["features"]
    out = {}
    for f in features:
        props     = f["properties"]
        gaul_name = props.get("ADM1_NAME", "")
        mapped    = NAME_MAP.get(gaul_name, gaul_name)
        val = props.get("mean")
        if val is None:
            val = props.get("sm_mean")
        out[mapped] = {
            "smp":    round(float(val), 1) if val is not None else None,
            "source": source_label,
        }
    return out


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_gee()
    provinces = build_provinces()
    print("✓ Provinces: GAUL 76 + Bueng Kan = 77 total")

    # ── Step 1: SMAP L3 (primary) ─────────────────────────────────────────────
    print("\n[L3] NASA/SMAP/SPL3SMP_E/006 — direct satellite retrieval")
    l3_full = ee.ImageCollection(L3_COLLECTION).select(
        [L3_BAND_AM, L3_BAND_PM, L3_QUAL_AM, L3_QUAL_PM]
    )
    start_l3, end_l3, end_l3_exc = get_smap_window(l3_full, 7, "L3")
    l3_window = l3_full.filterDate(start_l3, end_l3_exc)
    l3_count  = l3_window.size().getInfo()
    print(f"  Images in 7-day window: {l3_count}")
    if l3_count == 0:
        start_l3, end_l3, end_l3_exc = get_smap_window(l3_full, 14, "L3 fallback")
        l3_window = l3_full.filterDate(start_l3, end_l3_exc)

    l3_img  = l3_window.map(add_l3_combined).mean()
    l3_data = reduce_provinces(l3_img, provinces, L3_SCALE, L3_SM_SCALE, "SMAP L3")

    l3_null = [k for k, v in l3_data.items() if v["smp"] is None]
    l3_ok   = len(l3_data) - len(l3_null)
    print(f"  L3 result: {l3_ok} provinces with data, {len(l3_null)} null")
    if l3_null:
        print(f"  L3 null: {l3_null}")

    # ── Step 2: SMAP L4 fallback (gap-fill null provinces) ───────────────────
    provinces_data = dict(l3_data)
    start_l4 = end_l3  # use same approximate date

    if l3_null:
        print(f"\n[L4] NASA/SMAP/SPL4SMGP/008 — gap-fill for {len(l3_null)} null provinces")
        l4_full = ee.ImageCollection(L4_COLLECTION).select([L4_BAND])
        start_l4, end_l4, end_l4_exc = get_smap_window(l4_full, 7, "L4")
        l4_window = l4_full.filterDate(start_l4, end_l4_exc)
        l4_count  = l4_window.size().getInfo()
        print(f"  Images in 7-day window: {l4_count}")

        l4_img  = l4_window.mean()
        l4_data = reduce_provinces(l4_img, provinces, L4_SCALE, L4_SM_SCALE, "SMAP L4")

        filled = []
        for prov in l3_null:
            l4_val = l4_data.get(prov, {}).get("smp")
            if l4_val is not None:
                provinces_data[prov] = {"smp": l4_val, "source": "SMAP L4"}
                filled.append(f"{prov}={l4_val:.1f}%")
        print(f"  L4 filled: {filled}")

    # ── Summary ───────────────────────────────────────────────────────────────
    final_null = [k for k, v in provinces_data.items() if v["smp"] is None]
    smp_vals   = [v["smp"] for v in provinces_data.values() if v["smp"] is not None]
    l4_count_used = sum(1 for v in provinces_data.values() if v.get("source") == "SMAP L4")

    print(f"\n  Final: {len(smp_vals)} provinces with data, {len(final_null)} null")
    if smp_vals:
        print(f"  smp range: {min(smp_vals):.1f}% – {max(smp_vals):.1f}%")
        print(f"  smp avg:   {sum(smp_vals)/len(smp_vals):.1f}%")
        print(f"  L3 direct: {len(smp_vals)-l4_count_used} · L4 gap-fill: {l4_count_used}")
    if final_null:
        print(f"  Still null: {final_null}")

    # ── Save ──────────────────────────────────────────────────────────────────
    # Strip internal source field for output (keep only smp)
    clean_provinces = {k: {"smp": v["smp"]} for k, v in provinces_data.items()}

    output = {
        "_meta": {
            "source":       "NASA SMAP via Google Earth Engine (L3 primary + L4 gap-fill)",
            "dataset_l3":   L3_COLLECTION,
            "dataset_l4":   L4_COLLECTION,
            "band_l3":      f"{L3_BAND_AM} + {L3_BAND_PM} (quality-masked, mean)",
            "band_l4":      f"{L4_BAND} (gap-fill for null provinces)",
            "unit":         "% ความชุ่มชื้น (0% = แห้ง, 100% = อิ่มตัว)",
            "resolution":   "L3: 9km · L4: 11km — spatial average per province",
            "period_start": start_l3,
            "period_end":   end_l3,
            "updated":      date.today().isoformat(),
            "l3_provinces": len(smp_vals) - l4_count_used,
            "l4_provinces": l4_count_used,
            "note":         "ความชื้นในดินระดับผิว — 0% = แห้งสนิท, 100% = อิ่มตัว",
        },
        "provinces": dict(sorted(clean_provinces.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = "data/soil-moisture.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {len(clean_provinces)} provinces → {out_path}")


if __name__ == "__main__":
    main()
