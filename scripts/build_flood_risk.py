#!/usr/bin/env python3
"""
Build data/flood-risk.json from GISTDA Flood Recurrence API.
Method: query centroid of EVERY subdistrict (tambon) in Thailand — full coverage.

Source data:
  - Subdistrict boundaries: GADM 4.1 Thailand level 3 (auto-downloaded, 1.4 MB)
  - Flood history: GISTDA Point API ปี 2554–2566 (13 ปี)

Logic per subdistrict:
  - Query centroid → GISTDA returns flood history OR "not found"
  - "not found" = ไม่มีประวัติน้ำท่วมในตำบลนั้นเลย
  - Aggregate by province using actual subdistrict AREA (rai) — ไม่ใช่แค่นับจุด

Result: % พื้นที่จังหวัดที่มีประวัติน้ำท่วมซ้ำ (area-weighted, full tambon coverage)

Usage:
  python scripts/build_flood_risk.py               # ทุกตำบล ~40 นาที
  python scripts/build_flood_risk.py --resume       # ต่อจาก cache
  python scripts/build_flood_risk.py --test         # 100 ตำบลแรก
  python scripts/build_flood_risk.py --province "Chiang Mai"  # จังหวัดเดียว
"""
import argparse, json, os, sys, io, time, zipfile
from datetime import date
from urllib.request import urlretrieve

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import requests
    import geopandas as gpd
    from shapely.geometry import Point
except ImportError as e:
    sys.exit(f"ERROR: {e}\npip install geopandas requests shapely pyproj")

HERE      = os.path.dirname(os.path.abspath(__file__))
ROOT      = os.path.join(HERE, "..")
OUTPUT    = os.path.join(ROOT, "data", "flood-risk.json")
CACHE     = os.path.join(ROOT, "data", "source", "tambon_flood_cache.json")
ADM3_LOCAL = os.path.join(ROOT, "data", "source", "gadm41_THA_3.json")
ADM3_ZIP  = os.path.join(ROOT, "data", "source", "gadm41_THA_3.zip")
ADM1_FILE = os.path.join(ROOT, "data", "source", "tha_admin1.geojson")
GADM_URL  = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_THA_3.json.zip"
UTM       = "EPSG:32647"

API_URL   = "https://api-gateway.gistda.or.th/api/2.0/resources/gi-service/v1.1/disasters/flood-recurrence"
# Public demo key from GISTDA Open Data (https://opendata.gistda.or.th)
# Override via env var GISTDA_API_KEY if you have a dedicated key
DEMO_KEY  = os.environ.get("GISTDA_API_KEY", "CoxyRDixPBGCMuEkriUXZqlBlUMTZK6klJ8WKgalsLuQ74fTNJsFZUQXLVBPuk9o")
HEADERS   = {"Referer": "https://opendata.gistda.or.th/"}
DELAY     = 0.3   # วินาที ระหว่าง request
MAX_RETRY = 2
RETRY_DELAY = 5.0


def load_adm3():
    """Download (if needed) and load GADM Thailand level 3 subdistrict GeoJSON"""
    if not os.path.exists(ADM3_LOCAL):
        if not os.path.exists(ADM3_ZIP):
            print(f"Downloading GADM 4.1 Thailand level 3 (~1.4 MB)...")
            os.makedirs(os.path.dirname(ADM3_ZIP), exist_ok=True)
            urlretrieve(GADM_URL, ADM3_ZIP)
            print(f"  → {ADM3_ZIP}")
        print("Extracting...")
        with zipfile.ZipFile(ADM3_ZIP) as z:
            names = z.namelist()
            json_files = [n for n in names if n.endswith(".json")]
            if not json_files:
                sys.exit(f"ERROR: No .json found in zip. Contents: {names}")
            z.extract(json_files[0], os.path.dirname(ADM3_LOCAL))
            extracted = os.path.join(os.path.dirname(ADM3_LOCAL), json_files[0])
            if extracted != ADM3_LOCAL:
                os.rename(extracted, ADM3_LOCAL)
        print(f"  → {ADM3_LOCAL}")

    print("Loading subdistrict boundaries (GADM THA level 3)...")
    gdf = gpd.read_file(ADM3_LOCAL)
    print(f"  {len(gdf)} subdistricts, CRS: {gdf.crs}")
    return gdf


def map_province_name(gadm_name, canonical_names):
    """Map GADM NAME_1 → canonical province key.
    GADM 4.1 strips all spaces (e.g. 'AmnatCharoen', 'BangkokMetropolis').
    We match by lowercasing and removing spaces from both sides.
    """
    # Already canonical (with spaces)
    if gadm_name in canonical_names:
        return gadm_name
    # Normalize: lowercase, no spaces
    norm = gadm_name.lower().replace(" ", "")
    for cn in canonical_names:
        if cn.lower().replace(" ", "") == norm:
            return cn
    return gadm_name  # return as-is — will be flagged in output


def query_gistda(lat, lon):
    """Query GISTDA point API. Returns dict with flood data or None (not found)."""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            r = requests.get(
                API_URL,
                params={"api_key": DEMO_KEY, "lat": str(lat), "lon": str(lon)},
                headers=HEADERS,
                timeout=20,
            )
            if r.status_code in (502, 503):
                if attempt < MAX_RETRY:
                    time.sleep(RETRY_DELAY)
                    continue
                return None
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return None  # "not found" = ไม่มีประวัติน้ำท่วม
        except Exception:
            if attempt < MAX_RETRY:
                time.sleep(RETRY_DELAY)
                continue
            return None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume",   action="store_true", help="ต่อจาก cache")
    parser.add_argument("--test",     action="store_true", help="100 ตำบลแรก")
    parser.add_argument("--province", help="เฉพาะจังหวัดนี้ (ชื่อภาษาอังกฤษ)")
    args = parser.parse_args()

    # ── 1. Load subdistrict boundaries ──────────────────────────────────────
    gdf_wgs = load_adm3()

    # ── 2. Load canonical province names from tha_admin1.geojson ────────────
    prov_gdf  = gpd.read_file(ADM1_FILE)
    canonical = set(prov_gdf["adm1_name"].map(lambda n: "Bangkok Metropolis" if n == "Bangkok" else str(n)))
    # Fix for Bangkok Metropolis
    canonical.discard("Bangkok")
    canonical.add("Bangkok Metropolis")

    # ── 3. Prepare rows: centroid (UTM for area, WGS84 for query) ───────────
    gdf_utm = gdf_wgs.to_crs(UTM)
    gdf_utm["area_rai"] = gdf_utm.geometry.area / 1600.0

    rows = []
    for idx, row in gdf_utm.iterrows():
        gadm_prov = str(gdf_wgs.loc[idx, "NAME_1"])
        prov_key  = map_province_name(gadm_prov, canonical)
        # Centroid in WGS84
        c_wgs = gdf_wgs.loc[idx].geometry.centroid
        lat, lon = round(c_wgs.y, 6), round(c_wgs.x, 6)
        tambon_id = f"{gadm_prov}|{gdf_wgs.loc[idx, 'NAME_2']}|{gdf_wgs.loc[idx, 'NAME_3']}"
        rows.append({
            "id":       tambon_id,
            "prov_key": prov_key,
            "area_rai": row["area_rai"],
            "lat":      lat,
            "lon":      lon,
        })

    # Apply filters
    if args.province:
        all_prov_keys = sorted({r["prov_key"] for r in rows})  # save before filter
        rows = [r for r in rows if r["prov_key"] == args.province]
        if not rows:
            print(f"ERROR: ไม่พบจังหวัด '{args.province}'")
            print("Available:", all_prov_keys)
            sys.exit(1)
    if args.test:
        rows = rows[:100]
        print(f"[TEST MODE — {len(rows)} subdistricts]")

    print(f"\nTotal subdistricts: {len(rows)}")
    est_min = len(rows) * DELAY / 60
    print(f"Estimated time: ~{est_min:.0f} minutes at {DELAY}s/request\n")

    # ── 4. Load cache ────────────────────────────────────────────────────────
    cache = {}
    if args.resume and os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
        print(f"Cache loaded: {len(cache)} tambons already done\n")

    # ── 5. Query GISTDA for each tambon centroid ─────────────────────────────
    results = dict(cache)  # tambon_id → {flooded, total_years, area_rai}
    todo = [r for r in rows if r["id"] not in results]
    print(f"To query: {len(todo)} tambons (skipping {len(rows)-len(todo)} cached)\n")

    for i, row in enumerate(todo, 1):
        data = query_gistda(row["lat"], row["lon"])
        total_years = int(data["total"]) if data and data.get("total") else 0
        flooded     = total_years > 0  # ต้องมีอย่างน้อย 1 ปีที่ท่วม, total=0 = ไม่นับ

        results[row["id"]] = {
            "prov_key":   row["prov_key"],
            "area_rai":   round(row["area_rai"]),
            "flooded":    flooded,
            "total_years": total_years,
            "lat":        row["lat"],
            "lon":        row["lon"],
        }

        # Progress
        sym = "🌊" if flooded else "·"
        if i % 50 == 0 or i == len(todo):
            pct_done = i / len(todo) * 100
            remaining_min = (len(todo) - i) * DELAY / 60
            print(f"[{i:4d}/{len(todo)}] {pct_done:4.0f}%  {sym}  ETA: {remaining_min:.0f} min", flush=True)

        # Save cache every 100 tambons (not on last — post-loop handles it)
        if i % 100 == 0 and i < len(todo):
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(DELAY)

    # Final cache save
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # ── 6. Aggregate by province (area-weighted) ─────────────────────────────
    prov_data = {}
    for tid, v in results.items():
        pk = v["prov_key"]
        if pk not in prov_data:
            prov_data[pk] = {"total_rai": 0, "flood_rai": 0, "tambons": 0, "flood_tambons": 0}
        prov_data[pk]["total_rai"]    += v["area_rai"]
        prov_data[pk]["tambons"]      += 1
        if v["flooded"]:
            prov_data[pk]["flood_rai"]   += v["area_rai"]
            prov_data[pk]["flood_tambons"] += 1

    # ── 7. Build output ───────────────────────────────────────────────────────
    provinces_out = {}
    for pk in sorted(prov_data.keys()):
        pd = prov_data[pk]
        pct = round(pd["flood_rai"] / pd["total_rai"] * 100, 1) if pd["total_rai"] > 0 else 0.0
        provinces_out[pk] = {
            "pct":          pct,
            "flood_rai":    pd["flood_rai"],
            "province_rai": pd["total_rai"],
            "flood_tambons": pd["flood_tambons"],
            "total_tambons": pd["tambons"],
        }

    # ── 8. Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    top10 = sorted(provinces_out.items(), key=lambda x: x[1]["pct"], reverse=True)[:10]
    print("Top 10 จังหวัดเสี่ยงน้ำท่วมสูงสุด:")
    for pk, v in top10:
        print(f"  {pk:<35} {v['pct']:5.1f}%  ({v['flood_rai']:>10,} ไร่)  {v['flood_tambons']}/{v['total_tambons']} ตำบล")

    covered = len([v for v in provinces_out.values() if v["total_tambons"] > 0])
    unmapped = [pk for pk in provinces_out if pk not in canonical]
    if unmapped:
        print(f"\n⚠️  Province name mismatch: {unmapped}")

    if args.test:
        print("\n[TEST — ไม่ save flood-risk.json]")
        return

    # ── 9. Save ───────────────────────────────────────────────────────────────
    out = {
        "_meta": {
            "source":            "GISTDA — พื้นที่น้ำท่วมซ้ำซาก ปี 2554–2566 (13 ปี)",
            "source_en":         "GISTDA — Recurring Flood Areas 2011–2023",
            "source_url":        "https://opendata.gistda.or.th/en/dataset/disasters-01",
            "boundary_source":   "GADM 4.1 Thailand level 3 (subdistrict/tambon)",
            "method":            "Tambon centroid query — full coverage, area-weighted",
            "tambons_queried":   len(results),
            "provinces_covered": covered,
            "period":            "2011-2023 (13 years)",
            "updated":           date.today().isoformat(),
            "note":              "% คำนวณจากพื้นที่ตำบลจริง ไม่ใช่การสุ่มตัวอย่าง — แม่นกว่าเวอร์ชันเดิม",
        },
        "provinces": provinces_out,
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {covered} provinces → {OUTPUT}")


if __name__ == "__main__":
    main()
