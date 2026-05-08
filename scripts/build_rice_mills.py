#!/usr/bin/env python3
"""
Convert thai_rice_mills_dit_2026-04-23.xlsx → data/rice-mills.json
Group by province, sort mills by capacity descending.
"""
import json, os, sys, io, pandas as pd
from datetime import date

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EXCEL = os.path.join(os.path.dirname(__file__), "..", "..", "thai_rice_mills_dit_2026-04-23.xlsx")
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "rice-mills.json")

TYPE_MAP = {
    "โรงสีขนาดใหญ่": "ใหญ่",
    "โรงสีขนาดกลาง": "กลาง",
    "โรงสีขนาดเล็ก": "เล็ก",
}

def main():
    df = pd.read_excel(EXCEL, engine="openpyxl")

    # Normalise column names
    df.columns = [c.strip() for c in df.columns]
    df["จังหวัด"]   = df["จังหวัด"].fillna("").str.strip().str.removeprefix("จังหวัด")
    df["ประเภทโรงสี"] = df["ประเภทโรงสี"].fillna("")
    df["กำลังการผลิต"] = pd.to_numeric(df["กำลังการผลิต"], errors="coerce").fillna(0)

    provinces = {}
    for prov_th, grp in df.groupby("จังหวัด"):
        if not prov_th:
            continue
        mills = []
        for _, row in grp.iterrows():
            t_raw = str(row["ประเภทโรงสี"]).strip()
            t_short = TYPE_MAP.get(t_raw, "เล็ก")
            name = str(row["ชื่อโรงสี/ผู้ประกอบการ"]).strip()
            cap  = int(row["กำลังการผลิต"])
            dist = str(row.get("อำเภอ/เขต", "")).strip()
            phone = str(row.get("โทรศัพท์", "")).strip()
            mill = {"name": name, "type": t_short, "capacity": cap}
            if dist and dist != "nan":
                mill["district"] = dist
            if phone and phone != "nan":
                mill["phone"] = phone
            mills.append(mill)

        mills.sort(key=lambda m: m["capacity"], reverse=True)
        large  = sum(1 for m in mills if m["type"] == "ใหญ่")
        medium = sum(1 for m in mills if m["type"] == "กลาง")
        small  = sum(1 for m in mills if m["type"] == "เล็ก")
        provinces[prov_th] = {
            "count": len(mills),
            "large": large, "medium": medium, "small": small,
            "mills": mills,
        }

    total = sum(p["count"] for p in provinces.values())
    output = {
        "_meta": {
            "source":      "กรมการค้าภายใน (DIT)",
            "updated":     "2026-04-23",
            "total_mills": total,
            "provinces_covered": len(provinces),
            "note":        "กำลังการผลิต หน่วย ตัน/วัน",
        },
        "provinces": provinces,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved {total} mills across {len(provinces)} provinces → {OUTPUT}")

if __name__ == "__main__":
    main()
