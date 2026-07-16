"""
Final sync stage of the rice-data pipeline (run after estimate_2568_2569.js).

Clears price_low/price_high from estimated_trend rows (CSV = historical OAE
data only; prices-live.json overlay provides current prices), then writes BOTH
rice-data.csv and rice-data.js from the same row set — this is what keeps the
two files consistent, since estimate_2568_2569.js only writes the .js file.

Reads rice-data.js (the file the estimate stage just updated) as input.
Run from repo root:  python scripts/clear_estimated_trend_prices.py
"""
import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RICE_JS = ROOT / "rice-data.js"
RICE_CSV = ROOT / "rice-data.csv"

CSV_FIELDS = [
    "province_th", "province_en", "region", "rice_type", "year",
    "production", "yield", "area", "area_planted", "yield_planted",
    "price", "price_low", "price_high", "price_low_alt", "price_high_alt",
    "price_basis", "source", "source_title", "source_url", "source_note", "source_date",
]

text = RICE_JS.read_text(encoding="utf-8")
rows = json.loads(text[text.index("[") : text.rindex("]") + 1])

cleared = 0
for row in rows:
    if row.get("source") == "estimated_trend" and (row.get("price_low") or row.get("price_high")):
        row["price_low"] = ""
        row["price_high"] = ""
        cleared += 1

RICE_JS.write_text(
    "window.RICE_DATA_ROWS=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";",
    encoding="utf-8",
)
with RICE_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

print(f"Cleared estimated prices on {cleared} rows; wrote rice-data.js + rice-data.csv in sync ({len(rows)} rows).")
