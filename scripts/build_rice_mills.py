#!/usr/bin/env python3
"""
Build data/rice-mills.json by combining two DIT sources:
  1. DIT live API (SearchRiceTrade) — 1,364 mills, 45 provinces (more complete per province)
  2. DIT Excel export (thai_rice_mills_dit_2026-04-23.xlsx) — 903 mills, 60 provinces
     → used only for the 15 provinces absent from the API

Final output: ~1,450+ mills across ~60 provinces.
กำลังการผลิต หน่วย ตัน/วัน
"""
import json, os, sys, io, time, requests, pandas as pd
from datetime import date

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EXCEL  = os.path.join(os.path.dirname(__file__), "..", "thai_rice_mills_dit_2026-04-23.xlsx")
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "rice-mills.json")
API_URL = "https://www.dit.go.th/api/RiceTradeApi/SearchRiceTrade"

TYPE_MAP_FULL = {
    "โรงสีขนาดใหญ่": "ใหญ่",
    "โรงสีขนาดกลาง": "กลาง",
    "โรงสีขนาดเล็ก": "เล็ก",
}


# ── 1. Fetch from DIT API ──────────────────────────────────────────────────────
def fetch_api_mills():
    all_items = []
    for page in range(1, 5):
        r = requests.get(API_URL, params={"pageIndex": page, "pageSize": 1000}, timeout=30)
        r.raise_for_status()
        all_items.extend(r.json().get("items", []))
        print(f"  API page {page}: {len(r.json().get('items', []))} records")
        time.sleep(0.4)

    mills = [x for x in all_items if "โรงสี" in str(x.get("description", ""))]
    print(f"  API mills only: {len(mills)} records")

    provinces = {}
    for m in mills:
        prov = (m.get("provinceName") or "").strip()
        if not prov:
            continue
        t_raw = str(m.get("description", "")).strip()
        t_short = TYPE_MAP_FULL.get(t_raw, "เล็ก")
        name = str(m.get("tName") or "").strip()
        cap  = int(float(m.get("millCapacity") or 0))
        dist = str(m.get("disctrictName") or "").strip()
        phone = str(m.get("tel") or "").strip()
        mill = {"name": name, "type": t_short, "capacity": cap}
        if dist:
            mill["district"] = dist
        if phone:
            mill["phone"] = phone
        provinces.setdefault(prov, []).append(mill)

    return provinces  # { Thai province name → [mill dicts] }


# ── 2. Load from Excel (fallback for provinces missing from API) ───────────────
def load_excel_mills(api_provinces: set):
    df = pd.read_excel(EXCEL, engine="openpyxl")
    df.columns = [c.strip() for c in df.columns]
    df["จังหวัด"]     = df["จังหวัด"].fillna("").str.strip().str.removeprefix("จังหวัด")
    df["ประเภทโรงสี"] = df["ประเภทโรงสี"].fillna("")
    df["กำลังการผลิต"] = pd.to_numeric(df["กำลังการผลิต"], errors="coerce").fillna(0)

    provinces = {}
    for prov_th, grp in df.groupby("จังหวัด"):
        if not prov_th or prov_th in api_provinces:
            continue  # skip provinces already covered by API
        mills = []
        for _, row in grp.iterrows():
            t_raw  = str(row["ประเภทโรงสี"]).strip()
            t_short = TYPE_MAP_FULL.get(t_raw, "เล็ก")
            name   = str(row["ชื่อโรงสี/ผู้ประกอบการ"]).strip()
            cap    = int(row["กำลังการผลิต"])
            dist   = str(row.get("อำเภอ/เขต", "")).strip()
            phone  = str(row.get("โทรศัพท์", "")).strip()
            mill   = {"name": name, "type": t_short, "capacity": cap}
            if dist and dist != "nan":
                mill["district"] = dist
            if phone and phone != "nan":
                mill["phone"] = phone
            mills.append(mill)
        if mills:
            provinces[prov_th] = mills

    print(f"  Excel fallback: {sum(len(v) for v in provinces.values())} mills in {len(provinces)} additional provinces")
    return provinces


# ── 3. Assemble province records ───────────────────────────────────────────────
def build_province_record(mills: list) -> dict:
    mills_sorted = sorted(mills, key=lambda m: m["capacity"], reverse=True)
    return {
        "count":  len(mills_sorted),
        "large":  sum(1 for m in mills_sorted if m["type"] == "ใหญ่"),
        "medium": sum(1 for m in mills_sorted if m["type"] == "กลาง"),
        "small":  sum(1 for m in mills_sorted if m["type"] == "เล็ก"),
        "mills":  mills_sorted,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today = date.today().isoformat()

    print("Fetching from DIT API...")
    api_mills = fetch_api_mills()

    print("Loading Excel fallback...")
    xls_mills = load_excel_mills(set(api_mills.keys()))

    combined = {**{p: build_province_record(v) for p, v in api_mills.items()},
                **{p: build_province_record(v) for p, v in xls_mills.items()}}

    total = sum(p["count"] for p in combined.values())
    api_total = sum(len(v) for v in api_mills.values())
    xls_total = sum(len(v) for v in xls_mills.values())

    output = {
        "_meta": {
            "source":            "กรมการค้าภายใน (DIT) — API + Excel export",
            "updated":           today,
            "total_mills":       total,
            "provinces_covered": len(combined),
            "api_mills":         api_total,
            "excel_mills":       xls_total,
            "note":              "กำลังการผลิต หน่วย ตัน/วัน · API ครอบคลุม 45 จว. · Excel เพิ่มอีก 15 จว.",
        },
        "provinces": combined,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {total} mills across {len(combined)} provinces → {OUTPUT}")
    print(f"  API: {api_total} mills / {len(api_mills)} provinces")
    print(f"  Excel (additional): {xls_total} mills / {len(xls_mills)} provinces")


if __name__ == "__main__":
    main()
