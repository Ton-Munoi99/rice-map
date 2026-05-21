#!/usr/bin/env python3
"""
Build data/flood-risk.json from GISTDA Flood Recurrence API (Point-based).

Source: GISTDA — พื้นที่น้ำท่วมซ้ำซาก ปี 2554–2566 (13 ปี)
API:    Point-based: lat/lon → flood recurrence data per subdistrict
Auth:   Demo key + Referer header

Approach: Monte Carlo grid sampling — ~40 random points per province,
query point API, estimate % area that's flood-prone.

Usage:
  python scripts/build_flood_risk.py               # ทั้ง 77 จังหวัด (~10 นาที)
  python scripts/build_flood_risk.py --test         # 5 จังหวัดแรก
  python scripts/build_flood_risk.py --resume       # ต่อจาก cache

Output: data/flood-risk.json
"""
import argparse, json, os, sys, io, time, random
from datetime import date

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import requests
    import geopandas as gpd
    from shapely.geometry import Point
except ImportError as e:
    sys.exit(f"ERROR: {e}\npip install geopandas requests shapely pyproj")

HERE   = os.path.dirname(__file__)
ROOT   = os.path.join(HERE, "..")
OUTPUT = os.path.join(ROOT, "data", "flood-risk.json")
CACHE  = os.path.join(ROOT, "data", "source", "gistda_point_cache.json")
UTM    = "EPSG:32647"

# ── GISTDA API ────────────────────────────────────────────────────────────────
API_URL  = "https://api-gateway.gistda.or.th/api/2.0/resources/gi-service/v1.1/disasters/flood-recurrence"
DEMO_KEY = "CoxyRDixPBGCMuEkriUXZqlBlUMTZK6klJ8WKgalsLuQ74fTNJsFZUQXLVBPuk9o"
HEADERS  = {"Referer": "https://opendata.gistda.or.th/"}

POINTS_PER_PROVINCE = 40   # จุด sampling ต่อจังหวัด
POINT_DELAY         = 0.3  # วินาที ระหว่าง request
PROVINCE_DELAY      = 2.0  # วินาที ระหว่างจังหวัด
MAX_RETRIES         = 2
RETRY_DELAY         = 5.0

NAME_FIX = {"Bangkok": "Bangkok Metropolis"}


def load_provinces():
    """Load province boundaries (WGS84) from cached GeoJSON"""
    cached = os.path.join(ROOT, "data", "source", "tha_admin1.geojson")
    zip_paths = [
        os.path.join(ROOT, "data", "source", "tha_admin_boundaries.geojson.zip"),
        os.path.join(os.path.expanduser("~"), "Downloads", "tha_admin_boundaries.geojson.zip"),
    ]
    if os.path.exists(cached):
        print(f"Loading provinces (cached): {cached}")
        gdf = gpd.read_file(cached)
    else:
        for zp in zip_paths:
            if os.path.exists(zp):
                import zipfile
                with zipfile.ZipFile(zp) as z:
                    with z.open("tha_admin1.geojson") as f:
                        gdf = gpd.read_file(f)
                gdf.to_file(cached, driver="GeoJSON")
                break
        else:
            sys.exit("ERROR: ไม่พบ tha_admin1.geojson — โหลดจาก HDX ก่อน")

    gdf = gdf.rename(columns={"adm1_name": "prov_en"})
    gdf["prov_en"] = gdf["prov_en"].map(lambda n: NAME_FIX.get(str(n), str(n)))
    print(f"  {len(gdf)} provinces, CRS: {gdf.crs}")
    return gdf[["prov_en", "geometry"]]


def random_points_in_polygon(polygon, n):
    """Generate n random points inside a polygon"""
    points = []
    minx, miny, maxx, maxy = polygon.bounds
    attempts = 0
    max_attempts = n * 20  # safety limit
    while len(points) < n and attempts < max_attempts:
        x = random.uniform(minx, maxx)
        y = random.uniform(miny, maxy)
        p = Point(x, y)
        if polygon.contains(p):
            points.append((y, x))  # (lat, lon)
        attempts += 1
    return points


def query_point(lat, lon):
    """Query GISTDA point API, returns dict or None"""
    params = {"api_key": DEMO_KEY, "lat": str(lat), "lon": str(lon)}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 503 or r.status_code == 502:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return None
            r.raise_for_status()
            data = r.json()
            # Point API returns list with 1 item or {"result":"not found"}
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return None  # not found = no flood at this point
        except Exception:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            return None
    return None


def process_province(geom, prov_en, n_points=POINTS_PER_PROVINCE):
    """Sample n random points in province, query each via point API"""
    points = random_points_in_polygon(geom, n_points)
    if not points:
        return {"flood_pct": 0.0, "sampled": 0, "flooded": 0, "avg_total": 0, "subdistricts": set()}

    flooded_count = 0
    total_years_sum = 0
    subdistricts = set()
    errors = 0

    for i, (lat, lon) in enumerate(points):
        result = query_point(lat, lon)
        if result is None and errors < 3:
            # Could be "not found" or error — we treat both as not flooded
            pass
        elif result is not None:
            total = result.get("total", 0)
            if total and int(total) > 0:
                flooded_count += 1
                total_years_sum += int(total)
                sub = result.get("subdistrict_name", "")
                dist = result.get("district_name", "")
                if sub:
                    subdistricts.add((sub, dist))

        # Progress dot
        if (i + 1) % 10 == 0:
            print(".", end="", flush=True)
        time.sleep(POINT_DELAY)

    flood_pct = round(flooded_count / len(points) * 100, 1) if points else 0.0
    avg_total = round(total_years_sum / flooded_count, 1) if flooded_count > 0 else 0

    return {
        "flood_pct": flood_pct,
        "sampled": len(points),
        "flooded": flooded_count,
        "avg_total": avg_total,
        "subdist_count": len(subdistricts),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="5 จังหวัดแรก")
    parser.add_argument("--resume", action="store_true", help="ต่อจาก cache")
    parser.add_argument("--points", type=int, default=POINTS_PER_PROVINCE, help="จุด sample ต่อจังหวัด")
    args = parser.parse_args()

    random.seed(42)  # reproducible sampling

    # 1. Load provinces
    prov_wgs = load_provinces()
    prov_utm = prov_wgs.to_crs(UTM)
    prov_utm["province_rai"] = prov_utm.geometry.area / 1600.0

    rows = list(zip(prov_wgs["prov_en"], prov_wgs.geometry, prov_utm["province_rai"]))
    if args.test:
        rows = rows[:5]
        print(f"  [TEST MODE — {len(rows)} จังหวัด]\n")

    # 2. Load cache
    cache = {}
    if args.resume and os.path.exists(CACHE):
        with open(CACHE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"  Cache loaded: {len(cache)} provinces\n")

    # 3. Process
    n_points = args.points
    total_requests = len(rows) * n_points
    est_minutes = total_requests * POINT_DELAY / 60
    print(f"Processing {len(rows)} provinces × {n_points} points = {total_requests} requests")
    print(f"Estimated time: ~{est_minutes:.0f} minutes")
    print(f"API: {API_URL} (point-based)\n")

    results = {}
    for i, (prov_en, geom, province_rai) in enumerate(rows, 1):
        # Skip if cached
        if args.resume and prov_en in cache:
            results[prov_en] = cache[prov_en]
            c = cache[prov_en]
            print(f"[{i:2d}/{len(rows)}] {prov_en:<35} (cached) {c['pct']}%")
            continue

        print(f"[{i:2d}/{len(rows)}] {prov_en:<35} ", end="", flush=True)
        res = process_province(geom, prov_en, n_points)

        pct = res["flood_pct"]
        flood_rai = round(province_rai * pct / 100)

        results[prov_en] = {
            "flood_rai": flood_rai,
            "province_rai": round(province_rai),
            "pct": pct,
            "avg_years_flooded": res["avg_total"],
            "subdist_count": res["subdist_count"],
            "_sampled": res["sampled"],
            "_flooded_points": res["flooded"],
        }

        bar = "█" * max(1, int(pct / 2)) if pct > 0 else ""
        print(f" {pct:5.1f}%  ({res['flooded']}/{res['sampled']} pts)  avg_yrs={res['avg_total']}  {bar}")

        # Save cache after each province
        cache[prov_en] = results[prov_en]
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        # Delay between provinces
        if i < len(rows):
            time.sleep(PROVINCE_DELAY)

    # 4. Summary
    print(f"\n{'='*65}")
    top10 = sorted(results.items(), key=lambda x: x[1]["pct"], reverse=True)[:10]
    print("Top 10 เสี่ยงสูงสุด (GISTDA 2554–2566):")
    for en, v in top10:
        print(f"  {en:<35} {v['pct']:5.1f}%  ({v['flood_rai']:>10,} ไร่)  avg {v.get('avg_years_flooded',0)} yrs")

    zero_count = sum(1 for v in results.values() if v["pct"] == 0)
    nonzero = [v["pct"] for v in results.values() if v["pct"] > 0]
    avg_pct = sum(nonzero) / len(nonzero) if nonzero else 0
    print(f"\nProvinces with flood: {len(nonzero)}/{len(results)}")
    print(f"Provinces without flood: {zero_count}")
    print(f"Average flood % (non-zero): {avg_pct:.1f}%")

    if args.test:
        print("\n[TEST — ไม่ save flood-risk.json]")
        return

    # 5. Save — clean internal fields
    clean_results = {}
    for en, v in results.items():
        clean_results[en] = {
            "flood_rai": v["flood_rai"],
            "province_rai": v["province_rai"],
            "pct": v["pct"],
        }

    output = {
        "_meta": {
            "source":            "GISTDA — พื้นที่น้ำท่วมซ้ำซาก ปี 2554–2566",
            "source_en":         "GISTDA — Recurring Flood Areas 2011–2023",
            "source_url":        "https://opendata.gistda.or.th/en/dataset/disasters-01",
            "api_url":           API_URL,
            "updated":           date.today().isoformat(),
            "period":            "2011-2023 (13 years)",
            "method":            f"Monte Carlo point sampling ({n_points} points/province) via GISTDA point API",
            "provinces_covered": len(clean_results),
            "note":              "% พื้นที่จังหวัดที่อยู่ในเขตน้ำท่วมซ้ำซาก · ประมาณจากการสุ่มจุด (point-based API) · GISTDA ข้อมูลดาวเทียม 13 ปี",
            "boundary_source":   "OCHA HDX — Thailand Admin Boundaries (tha_admin1)",
        },
        "provinces": dict(sorted(clean_results.items())),
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {len(clean_results)} provinces → {OUTPUT}")


if __name__ == "__main__":
    main()
