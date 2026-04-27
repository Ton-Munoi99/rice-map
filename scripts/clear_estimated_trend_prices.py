"""
Option A: clear price_low / price_high from rice-data.csv rows where
source = estimated_trend.  All other fields are left untouched.
CSV = historical OAE data only; prices-live.json overlay provides current prices.
"""
import csv, io, pathlib

CSV_PATH = pathlib.Path(__file__).parent.parent / "rice-data.csv"

raw = CSV_PATH.read_bytes()
# Preserve BOM if present
bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
text = raw.decode("utf-8-sig")

reader = csv.DictReader(io.StringIO(text))
fieldnames = reader.fieldnames

rows = []
cleared = 0
for row in reader:
    if row.get("source") == "estimated_trend":
        row["price_low"] = ""
        row["price_high"] = ""
        cleared += 1
    rows.append(row)

out = io.StringIO()
writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
writer.writeheader()
writer.writerows(rows)

CSV_PATH.write_bytes(bom + out.getvalue().encode("utf-8"))
print(f"Cleared price_low/price_high for {cleared} estimated_trend rows.")
