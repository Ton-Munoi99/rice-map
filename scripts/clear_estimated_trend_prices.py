"""
Final sync stage of the rice-data pipeline (run after estimate_2568_2569.js).

Clears price/price_low/price_high from estimated_trend rows (CSV = historical OAE
data only; prices-live.json overlay provides current prices), then writes BOTH
rice-data.csv and rice-data.js from the same row set — this is what keeps the
two files consistent, since estimate_2568_2569.js only writes the .js file.

Reads rice-data.js (the file the estimate stage just updated) as input.
Run from repo root:  python scripts/clear_estimated_trend_prices.py
"""
import json
import pathlib

from riceutils import write_rice_data

ROOT = pathlib.Path(__file__).resolve().parents[1]
RICE_JS = ROOT / "rice-data.js"


text = RICE_JS.read_text(encoding="utf-8")
rows = json.loads(text[text.index("[") : text.rindex("]") + 1])

cleared = 0
for row in rows:
    # price ต้องล้างด้วย — เดิมล้างแค่ low/high ราคาคาดการณ์ใน price จึงยังเป็นค่าที่แผนที่/กำไรใช้
    if row.get("source") == "estimated_trend" and (row.get("price_low") or row.get("price_high") or row.get("price")):
        row["price_low"] = ""
        row["price_high"] = ""
        row["price"] = 0
        cleared += 1

write_rice_data(rows)

print(f"Cleared estimated prices on {cleared} rows; wrote rice-data.js + rice-data.csv in sync ({len(rows)} rows).")
