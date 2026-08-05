#!/usr/bin/env python3
"""
Build data/rice-mills.json from the DIT Excel export (primary source):

  Primary : thai_rice_mills_dit_2026-04-23.xlsx → sheet 'รายชื่อโรงสี'
            903 raw rows, 60 provinces, deduplicated to ~886 unique mills
            (DIT issues multiple license records per mill — same name+district)
  Supplements: MANUAL_ADDITIONS — provinces confirmed by provincial-office
            data but absent from the Excel export (DIT registration gap)

Deduplication key: name + district + province (keeps highest-capacity entry).
Output: data/rice-mills.json
"""
import json, os, sys
from datetime import date

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE   = os.path.dirname(__file__)
ROOT   = os.path.join(HERE, "..")
XLS_XL = os.path.join(ROOT, "thai_rice_mills_dit_2026-04-23.xlsx")
OUTPUT = os.path.join(ROOT, "data", "rice-mills.json")

# Provinces confirmed by provincial-office data but absent from DIT Excel.
# mills=[] means individual names unavailable; count/large/medium/small are known.
# Source: สำนักงานพาณิชย์จังหวัด via data.go.th / gdcatalog.go.th (2568/2025)
MANUAL_ADDITIONS: dict[str, dict] = {
    "สุพรรณบุรี": {
        "count": 85, "large": 28, "medium": 45, "small": 12,
        "mills": [],
        "source_note": "สำนักงานพาณิชย์จังหวัดสุพรรณบุรี (data.go.th) ปี 2568 — ไม่มีข้อมูลรายชื่อ",
    },
}

TYPE_MAP = {
    "โรงสีขนาดใหญ่": "ใหญ่",
    "โรงสีขนาดกลาง": "กลาง",
    "โรงสีขนาดเล็ก": "เล็ก",
}


def _province_record(mills: list) -> dict:
    """Deduplicate by name+district (same address = same mill), sort by capacity desc."""
    sorted_mills = sorted(mills, key=lambda m: m["capacity"], reverse=True)
    seen: set = set()
    unique: list = []
    for m in sorted_mills:
        key = (m["name"], m.get("district", ""))
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return {
        "count":  len(unique),
        "large":  sum(1 for m in unique if m["type"] == "ใหญ่"),
        "medium": sum(1 for m in unique if m["type"] == "กลาง"),
        "small":  sum(1 for m in unique if m["type"] == "เล็ก"),
        "mills":  unique,
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


def load_excel() -> dict[str, list]:
    """Read DIT Excel รายชื่อโรงสี → {province_th: [mill_dict, ...]}"""
    df = pd.read_excel(XLS_XL, sheet_name="รายชื่อโรงสี", engine="openpyxl")
    df.columns = [c.strip() for c in df.columns]
    df["จังหวัด"]      = df["จังหวัด"].fillna("").str.strip().str.removeprefix("จังหวัด")
    df["ประเภทโรงสี"]  = df["ประเภทโรงสี"].fillna("")
    df["กำลังการผลิต"] = pd.to_numeric(df["กำลังการผลิต"], errors="coerce").fillna(0)

    provinces: dict[str, list] = {}
    for _, row in df.iterrows():
        prov = row["จังหวัด"]
        if not prov:
            continue
        mill = _mill_dict(
            name       = str(row["ชื่อโรงสี/ผู้ประกอบการ"]).strip(),
            type_short = TYPE_MAP.get(str(row["ประเภทโรงสี"]).strip(), "เล็ก"),
            capacity   = int(row["กำลังการผลิต"]),
            district   = ("" if pd.isna(row.get("อำเภอ/เขต"))
                          else str(row.get("อำเภอ/เขต", "")).strip()),
            phone      = ("" if pd.isna(row.get("โทรศัพท์"))
                          else str(row.get("โทรศัพท์", "")).strip()),
        )
        provinces.setdefault(prov, []).append(mill)

    print(f"  Excel raw : {sum(len(v) for v in provinces.values())} rows / {len(provinces)} provinces")
    return provinces


def main() -> None:
    print("Loading Excel (DIT รายชื่อโรงสี)...")
    raw = load_excel()
    if not raw:
        sys.exit("ERROR: Excel returned 0 mills — aborting")

    # Build deduplicated province records; manual additions fill provinces not in Excel
    dit_provinces = {p: _province_record(v) for p, v in raw.items()}
    manual_new    = {p: v for p, v in MANUAL_ADDITIONS.items() if p not in dit_provinces}
    provinces     = {**manual_new, **dit_provinces}   # dit wins on collision
    total         = sum(p["count"] for p in provinces.values())

    raw_total = sum(len(v) for v in raw.values())
    print(f"  After dedup: {total - sum(v['count'] for v in manual_new.values())} DIT mills "
          f"({raw_total - (total - sum(v['count'] for v in manual_new.values()))} duplicates removed)")
    if manual_new:
        print(f"  Manual: {sum(v['count'] for v in manual_new.values())} mills / {len(manual_new)} provinces")

    output = {
        "_meta": {
            "source":            "กรมการค้าภายใน (DIT) — Excel export รายชื่อโรงสี",
            "updated":           date.today().isoformat(),
            "total_mills":       total,
            "provinces_covered": len(provinces),
            "raw_excel_rows":    raw_total,
            "manual_mills":      sum(v["count"] for v in manual_new.values()),
            "note":              "กำลังการผลิต หน่วย ตัน/วัน · dedup by name+district",
        },
        "provinces": provinces,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {total} mills / {len(provinces)} provinces  →  {OUTPUT}")


if __name__ == "__main__":
    main()
