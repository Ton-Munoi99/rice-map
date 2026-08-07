#!/usr/bin/env python3
"""
Rebuild data/biomass-plants.json from DEDE's public GeoServer WFS.

The DEDE data catalog only publishes biomass plants as a raster PDF map (no text
layer), but the same layer is served as GeoJSON from their GeoServer — plant name,
lat/lon, tambon/amphoe/province, installed capacity and fuel type. That is strictly
richer than the 2565 questionnaire this file used to hold (79 respondent plants),
which under-counted the country roughly threefold.

The 2565 survey did carry one thing the WFS does not: a "buys rice straw/husk" flag.
Those flags are preserved by matching survey plants onto WFS plants by
normalized-name WITHIN THE SAME PROVINCE — fuzzy name matching alone pairs
"มิตรผล ด่านช้าง" (Suphan Buri) with "มิตรผล ภูเวียง" (Khon Kaen), so the province
constraint is load-bearing, not decoration.

Each plant records where its rice-fuel evidence came from:
  fuel_src "dede2569" — DEDE's own fuel field says แกลบ/ฟาง (authoritative)
  fuel_src "survey2565" — carried over from the older questionnaire only

Run: python scripts/fetch_biomass_plants.py
"""
import csv
import difflib
import json
import os
import re
import sys
import unicodedata
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LAYER = "gisdede:9000_2569_biomassdec68"   # ข้อมูล ณ ธ.ค. 2568 (เผยแพร่ 2569)
WFS = ("https://gis.dede.go.th/geoserver/wfs?service=WFS&version=2.0.0"
       f"&request=GetFeature&typeName={LAYER}&outputFormat=application/json")
TIMEOUT = 120

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "biomass-plants.json")
CSV = os.path.join(ROOT, "rice-data.csv")

# คำที่บอกว่าเชื้อเพลิงมาจากข้าว — ตรวจในฟิลด์ type ของ DEDE
HUSK_WORDS = ("แกลบ",)
STRAW_WORDS = ("ฟาง",)


def load_th2en():
    """province_th -> province_en (rice-data.csv มี BOM ต้องใช้ utf-8-sig)"""
    with open(CSV, encoding="utf-8-sig") as f:
        return {r["province_th"]: r["province_en"]
                for r in csv.DictReader(f) if r.get("province_th")}


def norm(s):
    """ชื่อโรงให้เทียบกันได้ — ตัดคำนำหน้านิติบุคคล วงเล็บ ช่องว่าง"""
    s = unicodedata.normalize("NFC", str(s))
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"บริษัท|จำกัด|มหาชน|บจก\.|บมจ\.|หจก\.|จก\.|โรงไฟฟ้า", "", s)
    return re.sub(r"[\s​.,\-]+", "", s)


def fetch_wfs():
    req = urllib.request.Request(WFS, headers={"User-Agent": "RiceMap/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def load_survey_flags():
    """อ่าน rice_straw/rice_husks จากไฟล์เดิม (สำรวจ 2565) -> {(prov_en, normname): (straw, husk)}"""
    if not os.path.exists(OUT):
        return {}
    try:
        prev = json.load(open(OUT, encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    # ไฟล์ที่ถูกเขียนโดยสคริปต์นี้แล้วจะมี _meta.source_layer — อย่าอ่านทับตัวเอง
    if prev.get("_meta", {}).get("source_layer"):
        return prev.get("_survey2565_flags", {})
    out = {}
    for prov_en, v in prev.get("provinces", {}).items():
        for p in v.get("plants", []):
            if p.get("rice_straw") or p.get("rice_husks"):
                out[f"{prov_en}|{norm(p['name'])}"] = [bool(p.get("rice_straw")),
                                                       bool(p.get("rice_husks"))]
    return out


def match_flag(prov_en, name, flags, by_prov):
    """หา flag ของโรงนี้ — ตรงเป๊ะก่อน แล้วค่อย fuzzy *ภายในจังหวัดเดียวกัน*"""
    k = f"{prov_en}|{norm(name)}"
    if k in flags:
        return flags[k]
    cands = by_prov.get(prov_en, [])
    m = difflib.get_close_matches(norm(name), cands, n=1, cutoff=0.82)
    return flags[f"{prov_en}|{m[0]}"] if m else None


def main():
    th2en = load_th2en()
    flags = load_survey_flags()
    by_prov = {}
    for key in flags:
        prov, nm = key.split("|", 1)
        by_prov.setdefault(prov, []).append(nm)

    try:
        gj = fetch_wfs()
    except Exception as e:
        print(f"[ERROR] WFS fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    feats = gj.get("features", [])
    print(f"WFS {LAYER}: {len(feats)} features")

    provinces, unmapped, carried = {}, set(), 0
    for f in feats:
        p = f["properties"]
        prov_en = th2en.get(p["prov_th"])
        if not prov_en:
            unmapped.add(p["prov_th"])
            continue

        fuel = (p.get("type") or "").strip()
        husk = any(w in fuel for w in HUSK_WORDS)
        straw = any(w in fuel for w in STRAW_WORDS)
        from_dede = husk or straw

        # เก็บ flag จากสำรวจ 2565 เสมอ แม้ DEDE จะระบุเชื้อเพลิงหลักเป็นอย่างอื่น —
        # โรงที่เผากากอ้อยเป็นหลักก็รับซื้อแกลบเสริมได้ ทิ้งไปคือทำข้อมูลหาย
        hit = match_flag(prov_en, p["name_th"], flags, by_prov)
        if hit:
            straw = straw or hit[0]
            husk = husk or hit[1]
            carried += 1

        fuel_src = ("both" if (from_dede and hit) else
                    "dede2569" if from_dede else
                    "survey2565" if hit else None)

        coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
        plant = {
            "name": p["name_th"],
            "mw": round(float(p.get("instcap_al") or 0), 2),
            "rice_straw": straw,
            "rice_husks": husk,
            "fuel": fuel,
            "amphoe": p.get("amphoe_th"),
            "tambon": p.get("tambon_th"),
            "lat": coords[1],
            "lon": coords[0],
        }
        if fuel_src:
            plant["fuel_src"] = fuel_src
        provinces.setdefault(prov_en, {"count": 0, "plants": []})["plants"].append(plant)

    for v in provinces.values():
        v["plants"].sort(key=lambda x: -x["mw"])
        v["count"] = len(v["plants"])

    total = sum(v["count"] for v in provinces.values())
    mw = sum(x["mw"] for v in provinces.values() for x in v["plants"])
    rice = sum(1 for v in provinces.values() for x in v["plants"]
               if x["rice_straw"] or x["rice_husks"])
    nofuel = sum(1 for v in provinces.values() for x in v["plants"]
                 if x["fuel"] in ("", "Renewable", "Biomass"))
    seen, dups = set(), 0
    for prov_en, v in provinces.items():
        for x in v["plants"]:
            key = (prov_en, x["name"])
            dups += key in seen
            seen.add(key)

    result = {
        "_meta": {
            "source": "กรมพัฒนาพลังงานทดแทนและอนุรักษ์พลังงาน (พพ./DEDE)",
            "source_en": "Dept. of Alternative Energy Development and Efficiency (DEDE)",
            "source_layer": LAYER,
            "source_url": "https://gis.dede.go.th/geoserver/wfs",
            "year": "2569",
            "as_of": "ธันวาคม 2568",
            "as_of_en": "Dec 2025",
            "total": total,
            "total_mw": round(mw, 2),
            "provinces_covered": len(provinces),
            "rice_fuel_plants": rice,
            "unspecified_fuel": nofuel,
            # ต้นทาง DEDE มีชื่อโรงซ้ำในจังหวัดเดียวกันอยู่เท่านี้ (คนละหน่วยผลิต/คนละพิกัด)
            # ไม่ตัดออก เพราะยอดรวมต้องตรงกับที่ พพ. ประกาศ
            "duplicate_names": dups,
            "note": (f"ทะเบียนโรงไฟฟ้าชีวมวลที่ขายไฟเข้าระบบ {total} โรง {len(provinces)} จังหวัด · "
                     f"ระบุเชื้อเพลิงจากข้าว (แกลบ/ฟาง) {rice} โรง · "
                     f"อีก {nofuel} โรงไม่ระบุชนิดเชื้อเพลิงในต้นทาง"),
            "note_en": (f"On-grid biomass power plants: {total} plants across {len(provinces)} provinces · "
                        f"{rice} report rice fuel (husk/straw) · {nofuel} have no fuel type stated at source"),
        },
        "provinces": dict(sorted(provinces.items())),
        # เก็บ flag จากสำรวจ 2565 ไว้ให้รอบถัดไปยัง carry ต่อได้ หลังไฟล์เดิมถูกเขียนทับแล้ว
        "_survey2565_flags": flags,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  {total} plants · {mw:,.2f} MW · {len(provinces)} provinces")
    print(f"  rice fuel: {rice} ({rice - carried} from DEDE fuel field, {carried} carried from 2565 survey)")
    print(f"  fuel not stated at source: {nofuel}")
    if unmapped:
        print(f"[WARN] province names not mapped: {sorted(unmapped)}", file=sys.stderr)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
