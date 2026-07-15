#!/usr/bin/env python3
"""
Extract OAE Table 1.4 (นาปี 2566-2568) and Table 1.7 (นาปรัง 2567-2569) from the
official PDF: สถิติการเกษตรของประเทศไทย ปี 2568.pdf → data/oae_extracted.json

This is the *refresh* step. The extracted JSON is committed, and
`update_rice_data.py` applies its napi figures onto rice-data.{csv,js}. Re-run
this only when a new OAE edition is published (drop the new PDF at repo root, or
pass its path as argv[1]).

  python scripts/extract_oae.py ["path/to/สถิติการเกษตร...2568.pdf"]

Outputs per province:
  - jasmine: ข้าวเจ้าหอมมะลิในพื้นที่ + นอกพื้นที่ (combined, area/prod summed, yield recalculated)
  - white:   ข้าวเจ้าอื่น ๆ only (exclude เหนียว + ปทุมธานี 1)

Note: page ranges and column layout below are calibrated to the Thai-language
2568 edition. A different edition/layout will need them re-checked.
"""
import io
import json
import sys
from pathlib import Path

import pdfplumber

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "สถิติการเกษตรของประเทศไทย ปี 2568.pdf"
OUT_PATH = ROOT / "data" / "oae_extracted.json"

SKIP_EN = {
    "Whole Kingdom", "Northern", "Northeastern", "Central", "Southern", "Eastern",
    "Hom mali rice in the area", "Hom mali rice outside the area",
    "Pathum Thani 1", "Other White Rice", "Glutinous Rice",
    "Region/\nProvince", "Region/", "Province",
}
SKIP_REGION_TH = {
    "รวมทั้งประเทศ", "เหนือ", "ตะวันออกเฉียงเหนือ", "กลาง", "ใต้", "ตะวันออก",
    "ภาค/จังหวัด",
}
JASMINE_TH = {"ข้าวเจ้าหอมมะลิในพื้นที่", "ข้าวเจ้าหอมมะลินอกพื้นที่"}
WHITE_TH = {"ข้าวเจ้าอื่น ๆ", "ข้าวเจ้าอื่น\xa0ๆ", "ข้าวเจ้าอื่นๆ"}
SKIP_TH = {"ข้าวเจ้าปทุมธานี 1", "ข้าวเหนียว"}


def to_num(s):
    if not s:
        return 0
    s = str(s).replace(",", "").replace("\xa0", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0


def process_pages(pdf, page_range, years, season, data, state):
    for pi in page_range:
        page = pdf.pages[pi]
        for tbl in page.extract_tables():
            for row in tbl:
                if not row or all(c is None or str(c).strip() == "" for c in row):
                    continue
                col0 = str(row[0] or "").strip()
                col_last = str(row[-1] or "").strip() if len(row) > 1 else ""

                if not col0 or col0 in {"", "ภาค/จังหวัด"}:
                    continue
                if "เนื้อที่เพาะปลูก" in col0 or "Planted area" in col_last:
                    continue
                if any(y in col0 for y in ["2566", "2567", "2568", "2569"]):
                    continue

                is_jasmine = col0 in JASMINE_TH
                is_white = col0 in WHITE_TH
                if col0 in SKIP_TH:
                    continue

                if not is_jasmine and not is_white:
                    # province or region row
                    if col0 in SKIP_REGION_TH:
                        continue
                    en = col_last.strip()
                    if en and en not in SKIP_EN and len(en) > 2:
                        state["prov"] = en
                        data.setdefault(en, {})
                    continue

                if not state["prov"]:
                    continue

                rice_type = "jasmine" if is_jasmine else "white"
                prov = state["prov"]

                # Columns: 0=name, 1-3=planted, 4-6=harvested, 7-9=production, 10-12=yield, 13=EN
                vals = row[1:]
                if len(vals) >= 13:
                    vals = vals[:12]

                for idx, year in enumerate(years):
                    ap = to_num(vals[idx]) if len(vals) > idx else 0
                    ah = to_num(vals[idx + 3]) if len(vals) > idx + 3 else 0
                    pr = to_num(vals[idx + 6]) if len(vals) > idx + 6 else 0
                    # yield column (vals[idx+9]) is recomputed below from summed harv+prod

                    key = f"{season}_{year}"
                    d = data[prov].setdefault(rice_type, {}).setdefault(
                        key, {"area_plant": 0, "area_harv": 0, "prod": 0}
                    )
                    d["area_plant"] += ap
                    d["area_harv"] += ah
                    d["prod"] += pr


def main():
    if not PDF_PATH.exists():
        sys.exit(f"Source PDF not found: {PDF_PATH}\nPass its path as argv[1] or drop it at repo root.")

    data = {}
    state = {"prov": None}
    with pdfplumber.open(str(PDF_PATH)) as pdf:
        print(f"PDF pages: {len(pdf.pages)}")
        print("--- Table 1.4 (นาปี pages 34-42) ---")
        state["prov"] = None
        process_pages(pdf, range(33, 42), ["2566", "2567", "2568f"], "napi", data, state)
        print("--- Table 1.7 (นาปรัง pages 47-52) ---")
        state["prov"] = None
        process_pages(pdf, range(46, 52), ["2567", "2568f", "2569f"], "naprang", data, state)

    for seasons in data.values():
        for by_key in seasons.values():
            for d in by_key.values():
                d["yield_kgrai"] = round(d["prod"] * 1000 / d["area_harv"], 0) if d["area_harv"] > 0 else 0
                d["area_plant"] = round(d["area_plant"])
                d["area_harv"] = round(d["area_harv"])
                d["prod"] = round(d["prod"])

    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Provinces extracted: {len(data)} → {OUT_PATH}")


if __name__ == "__main__":
    main()
