#!/usr/bin/env python3
"""
Build data/rice-mills.json from two local DIT snapshots + manual supplements:

  Primary  : data/rice-mills-api-snapshot.xlsx   — 1,364 mills, 45 provinces
             (downloaded from DIT SearchRiceTrade API, Apr 2026)
  Fallback : thai_rice_mills_dit_2026-04-23.xlsx — 903 mills, 60 provinces
             (DIT web export, Apr 2026; used only for the 15 provinces
              absent from the API snapshot)
  Supplements: MANUAL_ADDITIONS below — provinces confirmed present in
             provincial-office data but absent from DIT API (API gap)

To refresh API snapshot: re-run scripts/fetch_rice_mills_api.py, then this script.
Output: data/rice-mills.json
"""
import json, os, sys, io
from datetime import date

import pandas as pd

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE   = os.path.dirname(__file__)
ROOT   = os.path.join(HERE, "..")
API_XL = os.path.join(ROOT, "data", "rice-mills-api-snapshot.xlsx")
XLS_XL = os.path.join(ROOT, "thai_rice_mills_dit_2026-04-23.xlsx")
OUTPUT = os.path.join(ROOT, "data", "rice-mills.json")

# Provinces confirmed by provincial-office data but absent from DIT API/Excel.
# mills=[] means individual names unavailable; count/large/medium/small are known.
# Source: สำนักงานพาณิชย์จังหวัด via data.go.th / gdcatalog.go.th (2568/2025)
MANUAL_ADDITIONS: dict[str, dict] = {
    "สุพรรณบุรี": {
        "count": 85, "large": 28, "medium": 45, "small": 12,
        "mills": [],
        "source_note": "สำนักงานพาณิชย์จังหวัดสุพรรณบุรี (data.go.th) ปี 2568 — ไม่มีข้อมูลรายชื่อ",
    },
}

# Short labels used in JSON (match tooltip + detail-card display)
TYPE_MAP = {
    "โรงสีขนาดใหญ่": "ใหญ่",
    "โรงสีขนาดกลาง": "กลาง",
    "โรงสีขนาดเล็ก": "เล็ก",
}


def _province_record(mills: list) -> dict:
    """Deduplicate by name, sort by capacity desc, return province summary dict.

    DIT issues multiple license records per mill (same name/capacity/address).
    Keep the first occurrence after sorting — highest-capacity wins on ties.
    """
    sorted_mills = sorted(mills, key=lambda m: m["capacity"], reverse=True)
    seen: set = set()
    unique_mills = []
    for m in sorted_mills:
        if m["name"] not in seen:
            seen.add(m["name"])
            unique_mills.append(m)
    return {
        "count":  len(unique_mills),
        "large":  sum(1 for m in unique_mills if m["type"] == "ใหญ่"),
        "medium": sum(1 for m in unique_mills if m["type"] == "กลาง"),
        "small":  sum(1 for m in unique_mills if m["type"] == "เล็ก"),
        "mills":  unique_mills,
    }


def _mill_dict(name: str, type_short: str, capacity: int,
               district: str, phone: str) -> dict:
    """Return a compact mill dict, omitting empty optional fields."""
    m: dict = {"name": name, "type": type_short, "capacity": capacity}
    if district:
        m["district"] = district
    if phone:
        m["phone"] = phone
    return m


def load_api_snapshot() -> dict[str, list]:
    """Read API Excel snapshot → {province_th: [mill_dict, ...]}"""
    df = pd.read_excel(API_XL, engine="openpyxl")
    df["provinceName"]  = df["provinceName"].fillna("").str.strip()
    df["description"]   = df["description"].fillna("")
    df["millCapacity"]  = pd.to_numeric(df["millCapacity"], errors="coerce").fillna(0)
    df["disctrictName"] = df["disctrictName"].fillna("").str.strip()
    df["tel"]           = df["tel"].fillna("").str.strip()

    provinces: dict[str, list] = {}
    for _, row in df.iterrows():
        prov = row["provinceName"]
        if not prov:
            continue
        mill = _mill_dict(
            name     = str(row.get("tName", "")).strip(),
            type_short = TYPE_MAP.get(str(row["description"]).strip(), "เล็ก"),
            capacity = int(row["millCapacity"]),
            district = str(row["disctrictName"]),
            phone    = str(row["tel"]),
        )
        provinces.setdefault(prov, []).append(mill)

    print(f"  API snapshot : {sum(len(v) for v in provinces.values())} mills / {len(provinces)} provinces")
    return provinces


def load_excel_fallback(api_provinces: set) -> dict[str, list]:
    """Read DIT Excel export → provinces NOT already covered by API."""
    df = pd.read_excel(XLS_XL, engine="openpyxl")
    df.columns = [c.strip() for c in df.columns]
    df["จังหวัด"]     = df["จังหวัด"].fillna("").str.strip().str.removeprefix("จังหวัด")
    df["ประเภทโรงสี"] = df["ประเภทโรงสี"].fillna("")
    df["กำลังการผลิต"] = pd.to_numeric(df["กำลังการผลิต"], errors="coerce").fillna(0)

    provinces: dict[str, list] = {}
    for prov, grp in df.groupby("จังหวัด"):
        if not prov or prov in api_provinces:
            continue
        mills = [
            _mill_dict(
                name     = str(row["ชื่อโรงสี/ผู้ประกอบการ"]).strip(),
                type_short = TYPE_MAP.get(str(row["ประเภทโรงสี"]).strip(), "เล็ก"),
                capacity = int(row["กำลังการผลิต"]),
                district = ("" if pd.isna(row.get("อำเภอ/เขต"))
                            else str(row.get("อำเภอ/เขต","")).strip()),
                phone    = ("" if pd.isna(row.get("โทรศัพท์"))
                            else str(row.get("โทรศัพท์","")).strip()),
            )
            for _, row in grp.iterrows()
        ]
        if mills:
            provinces[prov] = mills

    print(f"  Excel fallback: {sum(len(v) for v in provinces.values())} mills / {len(provinces)} additional provinces")
    return provinces


def main() -> None:
    print("Loading API snapshot...")
    api = load_api_snapshot()
    if not api:
        sys.exit("ERROR: API snapshot has 0 mills — aborting to protect existing data")

    print("Loading Excel fallback...")
    xls = load_excel_fallback(set(api.keys()))

    # Merge order: manual < xls < api (api wins on any collision)
    dit_provinces = {p: _province_record(v) for p, v in {**xls, **api}.items()}
    manual_new    = {p: v for p, v in MANUAL_ADDITIONS.items() if p not in dit_provinces}
    provinces     = {**manual_new, **dit_provinces}
    total         = sum(p["count"] for p in provinces.values())

    if manual_new:
        print(f"  Manual supplements: {sum(v['count'] for v in manual_new.values())} mills / {len(manual_new)} provinces")

    output = {
        "_meta": {
            "source":            "กรมการค้าภายใน (DIT) — API snapshot + Excel export + manual supplements",
            "updated":           date.today().isoformat(),
            "total_mills":       total,
            "provinces_covered": len(provinces),
            "api_mills":         sum(len(v) for v in api.values()),
            "excel_mills":       sum(len(v) for v in xls.values()),
            "manual_mills":      sum(v["count"] for v in manual_new.values()),
            "note":              "กำลังการผลิต หน่วย ตัน/วัน",
        },
        "provinces": provinces,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {total} mills / {len(provinces)} provinces  →  {OUTPUT}")


if __name__ == "__main__":
    main()
