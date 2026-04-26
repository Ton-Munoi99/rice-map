import json
import re
import sys
from pathlib import Path

import pandas as pd


sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
CSV_FILE = ROOT / "data" / "farmer_households.csv"
JS_FILE = ROOT / "rice-data.js"

# Read CSV with the source encoding used by the OAE export.
df = pd.read_csv(CSV_FILE, encoding="cp874")

# Filter for the latest year available.
latest_year = df["year"].max()
df_latest = df[df["year"] == latest_year]

households = {}
for _, row in df_latest.iterrows():
    province_name = str(row["province_name"]).strip()
    households[province_name] = int(row["amount"])

js_assignment = (
    "\nwindow.PROVINCE_HOUSEHOLDS = "
    f"{json.dumps(households, ensure_ascii=False, separators=(',', ':'))};\n"
)

content = JS_FILE.read_text(encoding="utf-8")
pattern = re.compile(r"\n(?:const|window\.)PROVINCE_HOUSEHOLDS\s*=\s*\{[\s\S]*?\};\n?")

if pattern.search(content):
    content = pattern.sub(js_assignment, content, count=1)
    action = "Updated"
else:
    content = content.rstrip() + js_assignment
    action = "Appended"

JS_FILE.write_text(content, encoding="utf-8")
print(f"{action} window.PROVINCE_HOUSEHOLDS in {JS_FILE.name}")
