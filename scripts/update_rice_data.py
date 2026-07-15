#!/usr/bin/env python3
"""
Apply official OAE 2568-edition นาปี figures (Table 1.4) onto the rice dataset.

Reads the committed extraction `data/oae_extracted.json` (produced by
`extract_oae.py`) and overwrites the 2566/2567/2568 production/yield/area rows
for white + jasmine with the official numbers, tagging source =
`oae_stats_2568_table_1_4`. Prices and the 2565/2569 rows are left untouched.

This replaces the earlier one-off manual data commit: the 2568 official numbers
now live in a committed artifact + this script, so rice-data.{csv,js} is
reproducible. Reads rice-data.csv (the authoritative primary the app loads first;
estimated_trend prices are already cleared there — see clear_estimated_trend_prices.py)
and writes BOTH rice-data.csv and rice-data.js so they stay in sync.

Run from repo root:  python scripts/update_rice_data.py
"""
import csv
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
RICE_JS = ROOT / "rice-data.js"
RICE_CSV = ROOT / "rice-data.csv"
OAE_JSON = ROOT / "data" / "oae_extracted.json"

SOURCE = "oae_stats_2568_table_1_4"
SOURCE_TITLE = "สถิติการเกษตรของประเทศไทย ปี 2568 · ตารางที่ 1.4 ข้าวนาปีแยกพันธุ์"
SOURCE_URL = "https://www.oae.go.th"
SOURCE_NOTE_W = "Official OAE data Table 1.4, ข้าวเจ้าอื่นๆ (other white rice, excl. glutinous & Pathum Thani 1)"
SOURCE_NOTE_J = "Official OAE data Table 1.4, ข้าวเจ้าหอมมะลิ (in-area + outside-area combined)"

# PDF province name → app province name
PROV_MAP = {
    "Bangkok": "Bangkok Metropolis",
    "ChiangMai": "Chiang Mai",
    "Ayutthaya": "Phra Nakhon Si Ayutthaya",
    "Others1/": None,  # drop
}
# PDF year key → app year (2568f forecast shows as 2568, replacing the trend estimate)
YEAR_MAP = {"2566": "2566", "2567": "2567", "2568f": "2568"}

CSV_FIELDS = [
    "province_th", "province_en", "region", "rice_type", "year",
    "production", "yield", "area", "area_planted", "yield_planted",
    "price", "price_low", "price_high", "price_low_alt", "price_high_alt",
    "price_basis", "source", "source_title", "source_url", "source_note", "source_date",
]
INT_FIELDS = ("production", "yield", "area", "area_planted", "yield_planted", "price")
# int when present, "" when absent (matches rice-data.js typing)
INT_OR_BLANK = ("price_low", "price_high", "price_low_alt", "price_high_alt")


def load_rows():
    """Read the authoritative CSV, coercing cell strings back to rice-data.js typing."""
    rows = []
    with RICE_CSV.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            for f in INT_FIELDS:
                v = (r.get(f) or "").strip()
                r[f] = int(v) if v else 0
            for f in INT_OR_BLANK:
                v = (r.get(f) or "").strip()
                r[f] = int(v) if v else ""
            rows.append(r)
    return rows


def load_oae():
    oae = json.loads(OAE_JSON.read_text(encoding="utf-8"))
    fixed = {}
    for prov, types in oae.items():
        mapped = PROV_MAP.get(prov, prov)
        if mapped is None:
            continue
        # merge (e.g. a duplicate "ChiangMai" spelling into "Chiang Mai")
        dest = fixed.setdefault(mapped, {})
        for rtype, seasons in types.items():
            dest.setdefault(rtype, {}).update({k: v for k, v in seasons.items() if k not in dest.get(rtype, {})})
    return fixed


def main():
    rows = load_rows()
    oae = load_oae()
    lookup = {(r["province_en"], r["rice_type"], r["year"]): r for r in rows}

    updated = 0
    unmatched = []
    for prov, types in oae.items():
        for rice_type in ("white", "jasmine"):
            for pdf_year, app_year in YEAR_MAP.items():
                d = types.get(rice_type, {}).get(f"napi_{pdf_year}")
                if not d:
                    continue
                row = lookup.get((prov, rice_type, app_year))
                if row is None:
                    unmatched.append(f"{prov}/{rice_type}/{app_year}")
                    continue
                row["production"] = int(d["prod"])
                row["yield"] = int(d["yield_kgrai"])
                row["area"] = int(d["area_harv"])
                row["area_planted"] = int(d["area_plant"])
                row["yield_planted"] = int(round(d["prod"] * 1000 / d["area_plant"])) if d["area_plant"] > 0 else 0
                row["source"] = SOURCE
                row["source_title"] = SOURCE_TITLE
                row["source_url"] = SOURCE_URL
                row["source_note"] = SOURCE_NOTE_J if rice_type == "jasmine" else SOURCE_NOTE_W
                updated += 1

    # write both outputs in sync
    RICE_JS.write_text(
        "window.RICE_DATA_ROWS=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";",
        encoding="utf-8",
    )
    with RICE_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {updated} napi rows (source={SOURCE}) → rice-data.js + rice-data.csv")
    if unmatched:
        print(f"⚠️  {len(unmatched)} OAE rows had no matching app row: {unmatched[:8]}")


if __name__ == "__main__":
    main()
