#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build data/flood-risk.json using Global Flood Database (GFD) via Google Earth Engine.

Dataset: GLOBAL_FLOOD_DB/MODIS_EVENTS/V1 (Cloud to Street / Google)
- 100 flood events in Thailand, 2000–2018
- Band 'flooded': 1 = pixel was flooded in this event
- Band 'jrc_perm_water': 1 = permanent water (rivers/sea) → exclude
- Resolution: 250m MODIS
- Covers ALL flood types including flash floods in southern provinces

Method:
- Union all 100 events → "ever flooded" mask (excluding permanent water)
- Also compute flood frequency (how many events hit each province)
- reduceRegions per province → % area flooded + avg event count
- Much faster and more accurate than GISTDA point API (1 call vs 5,926 calls)

Output: data/flood-risk.json
Usage: python scripts/build_flood_risk.py
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import ee
import json
import os
from datetime import date

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

DATASET    = "GLOBAL_FLOOD_DB/MODIS_EVENTS/V1"
SCALE      = 250        # MODIS native resolution (meters)
M2_PER_RAI = 1600.0     # 1 rai = 1,600 m²


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


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_gee()
    provinces = build_provinces()
    print("✓ Provinces: GAUL 76 + Bueng Kan = 77 total")

    # ── Load GFD events for Thailand ─────────────────────────────────────────
    print(f"\n[GFD] {DATASET}")
    tha_bbox   = ee.Geometry.Rectangle([97.5, 5.5, 105.7, 20.5])
    gfd        = ee.ImageCollection(DATASET)
    tha_events = gfd.filterBounds(tha_bbox)
    n_events   = tha_events.size().getInfo()
    print(f"  Thailand flood events: {n_events}")

    # ── Build "ever flooded" mask (excluding permanent water) ─────────────────
    # flooded band  : 1 = pixel was flooded in this event
    # jrc_perm_water: 1 = permanent water body (rivers/sea) → exclude to avoid
    #                 counting permanent water as flood-prone land
    ever_flooded = tha_events.select("flooded").max()           # 1 = flooded ≥ 1 event
    perm_water   = tha_events.select("jrc_perm_water").max()    # 1 = permanent water
    flood_mask   = ever_flooded.updateMask(perm_water.Not())    # exclude rivers/sea

    # Count how many distinct events hit each pixel (flood frequency per pixel)
    event_freq = tha_events.select("flooded").sum().rename("n_events")

    # Combine into single image: 'flooded' (0/1 fraction after mean) + 'n_events' (count)
    flood_img = flood_mask.rename("flooded").addBands(event_freq)

    # ── Add area_m2 to each province feature (computed on-the-fly from GAUL polygon) ──
    provinces_with_area = provinces.map(lambda f: f.set("area_m2", f.geometry().area()))

    # ── reduceRegions at 250m (MODIS native resolution) ──────────────────────
    print("  Running reduceRegions (250m MODIS) ...")
    result   = flood_img.reduceRegions(
        collection=provinces_with_area,
        reducer=ee.Reducer.mean(),
        scale=SCALE,
    )
    features = result.getInfo()["features"]
    print(f"  Got {len(features)} provinces from GEE")

    # ── Parse results ─────────────────────────────────────────────────────────
    # reduceRegions with a multi-band image + mean() returns properties named
    # after each band: 'flooded' and 'n_events' (GEE uses band name directly).
    # Fallback keys cover edge-cases where GEE appends '_mean'.
    provinces_data = {}
    null_list      = []

    for f in features:
        props     = f["properties"]
        gaul_name = props.get("ADM1_NAME", "")
        mapped    = NAME_MAP.get(gaul_name, gaul_name)

        pct_raw      = (props.get("flooded")
                        or props.get("flooded_mean")
                        or props.get("mean"))
        n_events_raw = (props.get("n_events")
                        or props.get("n_events_mean"))
        area_m2      = props.get("area_m2")

        prov_rai = round(area_m2 / M2_PER_RAI) if area_m2 else None

        if pct_raw is None:
            # Province has zero overlap with any GFD flood event → pct = 0
            provinces_data[mapped] = {
                "pct":          0.0,
                "flood_rai":    0,
                "province_rai": prov_rai,
                "flood_events": 0.0,
            }
            null_list.append(gaul_name)
        else:
            pct       = round(float(pct_raw) * 100, 2)     # fraction → percent
            n_ev      = round(float(n_events_raw), 2) if n_events_raw is not None else 0.0
            flood_rai = round(pct * prov_rai / 100) if prov_rai else None
            provinces_data[mapped] = {
                "pct":          pct,
                "flood_rai":    flood_rai,
                "province_rai": prov_rai,
                "flood_events": n_ev,
            }

    # ── Summary ───────────────────────────────────────────────────────────────
    pct_vals = [v["pct"] for v in provinces_data.values()]
    if null_list:
        print(f"  Zero-flood provinces (set pct=0): {null_list}")
    else:
        print("  All provinces have flood history ✓")
    print(f"  Provinces total: {len(pct_vals)}/77")
    if pct_vals:
        print(f"  pct range: {min(pct_vals):.2f}% – {max(pct_vals):.2f}%"
              f"  Avg: {sum(pct_vals)/len(pct_vals):.2f}%")

    top10 = sorted(provinces_data.items(), key=lambda x: x[1]["pct"], reverse=True)[:10]
    print("\n  Top 10 flood-risk provinces (% area ever flooded 2000-2018):")
    for rank, (name, vals) in enumerate(top10, 1):
        print(f"    {rank:2d}. {name:<35s} {vals['pct']:6.2f}%"
              f"  ({vals['flood_events']:.1f} events avg)")

    # ── Save ──────────────────────────────────────────────────────────────────
    output = {
        "_meta": {
            "source":       "Global Flood Database (Cloud to Street / Google) via GEE",
            "dataset":      DATASET,
            "period":       "2000-2018 (19 years)",
            "method":       ("Pixel-based union of flood events (250m MODIS)"
                             " — ครอบคลุมทุกประเภทน้ำท่วม รวม flash flood ภาคใต้"),
            "total_events": n_events,
            "updated":      date.today().isoformat(),
            "note":         ("pct = % พื้นที่จังหวัดที่เคยถูกน้ำท่วม"
                             " · flood_events = จำนวนครั้งเฉลี่ยต่อพื้นที่ท่วม"),
        },
        "provinces": dict(sorted(provinces_data.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = "data/flood-risk.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {len(provinces_data)} provinces → {out_path}")


if __name__ == "__main__":
    main()
