#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_districts_geo.py
Export simplified district boundaries จาก FAO GAUL 2015 level2 via GEE

Output: data/districts-geo.json
Format:
  {
    "_meta": { ... },
    "provinces": {
      "Chiang Mai": {
        "bbox": [lng_min, lat_min, lng_max, lat_max],
        "districts": {
          "Mueang Chiang Mai": [ [[lng,lat],...] ],   ← Polygon rings
          "Mae Rim":           [ [[lng,lat],...] ],
          ...
        }
      }
    }
  }

Simplification: maxError=3000m (3km) — พอสำหรับ mini map แสดงบนหน้าจอ
File size target: ~500KB–1MB
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ee
import json
import os
from datetime import date
from riceutils import init_gee, GAUL_NAME_MAP as PROV_MAP


# Simplification error in meters — 3km = ดีพอสำหรับ mini map
SIMPLIFY_ERROR_M = 1500
# Coordinate decimal places — 4 digits ≈ 11m accuracy (เพียงพอ)
COORD_PRECISION  = 4


def round_coords(coords, precision=COORD_PRECISION):
    """Round coordinate arrays recursively to reduce JSON size"""
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], precision), round(coords[1], precision)]
    return [round_coords(c, precision) for c in coords]


def extract_rings(geometry):
    """
    คืน list of rings จาก Polygon หรือ MultiPolygon geometry
    แต่ละ ring = [[lng,lat], ...]
    """
    geo_type = geometry.get("type", "")
    coords   = geometry.get("coordinates", [])

    if geo_type == "Polygon":
        # coords = [outer_ring, hole1, hole2, ...]  เอาแค่ outer ring
        return [round_coords(coords[0])] if coords else []

    elif geo_type == "MultiPolygon":
        # coords = [ [[outer_ring], [hole]], ... ]  เอา outer ring แต่ละ polygon
        rings = []
        for poly in coords:
            if poly:
                rings.append(round_coords(poly[0]))
        return rings

    return []


def main():
    init_gee()
    print(f"Exporting district geometry (simplify={SIMPLIFY_ERROR_M}m)...")

    # ── Load + simplify districts ─────────────────────────────────────────────
    districts = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
        .select(["ADM1_NAME", "ADM2_NAME"])  # ไม่เอา field อื่น ลด payload
        .map(lambda f: f.simplify(maxError=SIMPLIFY_ERROR_M))
    )
    print(f"✓ Loaded + simplified FAO GAUL level2 (813 districts)")

    # ── Download ──────────────────────────────────────────────────────────────
    print("  Downloading geometry (this may take ~30–60s)...")
    features = districts.getInfo()["features"]
    print(f"  Got {len(features)} features")

    # ── Group by province ─────────────────────────────────────────────────────
    provinces_data = {}

    for f in features:
        props      = f["properties"]
        prov_gaul  = props.get("ADM1_NAME", "")
        dist_name  = props.get("ADM2_NAME", "")
        geometry   = f.get("geometry", {})

        prov_mapped = PROV_MAP.get(prov_gaul, prov_gaul)

        if prov_mapped not in provinces_data:
            provinces_data[prov_mapped] = {"bbox": None, "districts": {}}

        rings = extract_rings(geometry)
        if rings:
            provinces_data[prov_mapped]["districts"][dist_name] = rings

    # ── Compute bbox per province ─────────────────────────────────────────────
    for prov, data in provinces_data.items():
        all_lngs = []
        all_lats = []
        for rings in data["districts"].values():
            for ring in rings:
                for pt in ring:
                    all_lngs.append(pt[0])
                    all_lats.append(pt[1])
        if all_lngs:
            data["bbox"] = [
                round(min(all_lngs), COORD_PRECISION),
                round(min(all_lats), COORD_PRECISION),
                round(max(all_lngs), COORD_PRECISION),
                round(max(all_lats), COORD_PRECISION),
            ]

    # ── Stats ─────────────────────────────────────────────────────────────────
    total_d   = sum(len(p["districts"]) for p in provinces_data.values())
    total_pts = sum(
        sum(len(r) for rings in p["districts"].values() for r in rings)
        for p in provinces_data.values()
    )
    print(f"  Provinces: {len(provinces_data)}")
    print(f"  Districts: {total_d}")
    print(f"  Total coordinate points: {total_pts:,}")

    # ── Write output ──────────────────────────────────────────────────────────
    output = {
        "_meta": {
            "source":          "FAO GAUL 2015 level2 via Google Earth Engine",
            "simplify_error":  f"{SIMPLIFY_ERROR_M}m",
            "coord_precision": COORD_PRECISION,
            "updated":         date.today().isoformat(),
            "provinces":       len(provinces_data),
            "districts":       total_d,
            "note":            (
                "Simplified district boundaries for mini map rendering. "
                "3km simplification — adequate for province-level drill-down display."
            ),
        },
        "provinces": dict(sorted(provinces_data.items())),
    }

    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "districts-geo.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))  # compact JSON

    size_kb = os.path.getsize(out_path) / 1024
    print(f"✅ Saved → {out_path}  ({size_kb:.0f} KB)")

    # Sample output
    sample_prov = "Chiang Mai"
    if sample_prov in provinces_data:
        sample = provinces_data[sample_prov]
        print(f"\nSample — {sample_prov}:")
        print(f"  bbox: {sample['bbox']}")
        print(f"  districts: {len(sample['districts'])}")
        first_d = next(iter(sample["districts"]))
        first_r = sample["districts"][first_d][0]
        print(f"  {first_d}: {len(first_r)} points, first: {first_r[0]}")


if __name__ == "__main__":
    main()
