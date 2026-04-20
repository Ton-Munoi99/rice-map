import pandas as pd
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Read CSV with right encoding
df = pd.read_csv('C:\\Users\\sponlapatp\\Desktop\\Rice Map\\data\\farmer_households.csv', encoding='cp874')

# Filter for the latest year available
latest_year = df['year'].max()
df_latest = df[df['year'] == latest_year]

# Create Dictionary mapping Thai Province Name to amount
households = {}
for _, row in df_latest.iterrows():
    # Fix some province naming quirks if needed, e.g., 'กรุงเทพมหานคร'
    p_name = str(row['province_name']).strip()
    # Normalize naming to match RICE_DATA
    if p_name == 'พระนครศรีอยุธยา': p_name = 'พระนครศรีอยุธยา' 
    households[p_name] = int(row['amount'])

js_content = f"\nconst PROVINCE_HOUSEHOLDS = {json.dumps(households, ensure_ascii=False)};\n"

# Append to rice-data.js
js_file = 'C:\\Users\\sponlapatp\\Desktop\\Rice Map\\rice-data.js'
with open(js_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure we don't append it multiple times
if 'const PROVINCE_HOUSEHOLDS' not in content:
    with open(js_file, 'a', encoding='utf-8') as f:
        f.write(js_content)
    print("Successfully appended PROVINCE_HOUSEHOLDS to rice-data.js")
else:
    print("PROVINCE_HOUSEHOLDS already exists in rice-data.js")
