#!/usr/bin/env python3
"""
Update rice-data.js with official OAE data from:
  สถิติการเกษตรของประเทศไทย ปี 2568 (Table 1.4 นาปี, years 2566/2567/2568f)

Rules:
  - Replace 2566, 2567, 2568 production/yield/area with official PDF figures
  - Keep 2565, 2569 rows as-is (not in new PDF)
  - Keep ALL price data untouched
  - Keep source metadata updated
  - Province mapping: Bangkok→Bangkok Metropolis, ChiangMai→Chiang Mai

Run: python update_rice_data.py
"""
import json, re, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

RICE_JS   = r'C:\Users\sponlapatp\Desktop\Rice Map\rice-data.js'
OAE_JSON  = r'C:\Users\sponlapatp\Desktop\Rice Map\data\oae_extracted.json'
OUT_JS    = r'C:\Users\sponlapatp\Desktop\Rice Map\rice-data.js'

SOURCE_TITLE = 'สถิติการเกษตรของประเทศไทย ปี 2568 · ตารางที่ 1.4 ข้าวนาปีแยกพันธุ์'
SOURCE_URL   = 'https://www.oae.go.th'
SOURCE_NOTE_W = 'Official OAE data Table 1.4, ข้าวเจ้าอื่นๆ (other white rice, excl. glutinous & Pathum Thani 1)'
SOURCE_NOTE_J = 'Official OAE data Table 1.4, ข้าวเจ้าหอมมะลิ (in-area + outside-area combined)'

# Province name fixes from PDF → app name
PROV_MAP = {
    'Bangkok':    'Bangkok Metropolis',
    'ChiangMai':  'Chiang Mai',
    'Ayutthaya':  'Phra Nakhon Si Ayutthaya',
    'Others1/':   None,   # drop
}

# Year mapping: PDF year string → app year string
YEAR_MAP = {
    '2566':  '2566',
    '2567':  '2567',
    '2568f': '2568',   # forecast → shows as 2568 in app (replaces trend estimate)
}

# ── Load existing rice-data.js ───────────────────────────────────────────────
print('Loading rice-data.js...')
with open(RICE_JS, encoding='utf-8') as f:
    js_content = f.read().strip().lstrip('\ufeff')
start = js_content.index('[')
end   = js_content.rindex(']') + 1
rows  = json.loads(js_content[start:end])
print(f'  Loaded {len(rows)} existing rows')

# Build lookup: (province_en, rice_type, year) → row index
lookup = {}
for i, r in enumerate(rows):
    key = (r['province_en'], r['rice_type'], r['year'])
    lookup[key] = i

# ── Load OAE extracted JSON ──────────────────────────────────────────────────
print('Loading oae_extracted.json...')
with open(OAE_JSON, encoding='utf-8') as f:
    oae = json.load(f)

# Fix province names
fixed_oae = {}
for prov, types in oae.items():
    mapped = PROV_MAP.get(prov, prov)
    if mapped is None:
        print(f'  Dropping: {prov}')
        continue
    if mapped != prov:
        print(f'  Rename: {prov} → {mapped}')
    # Merge ChiangMai white naprang data into Chiang Mai if needed
    if mapped in fixed_oae:
        for rtype, seasons in types.items():
            if rtype not in fixed_oae[mapped]:
                fixed_oae[mapped][rtype] = {}
            for sk, sv in seasons.items():
                if sk not in fixed_oae[mapped][rtype]:
                    fixed_oae[mapped][rtype][sk] = sv
    else:
        fixed_oae[mapped] = types

oae = fixed_oae
print(f'  OAE provinces after fix: {len(oae)}')

# ── Apply updates ────────────────────────────────────────────────────────────
updated = 0
skipped_no_match = []

for pdf_prov, types in sorted(oae.items()):
    for rice_type in ('white', 'jasmine'):
        if rice_type not in types:
            continue
        for pdf_year, app_year in YEAR_MAP.items():
            season_key = f'napi_{pdf_year}'
            if season_key not in types[rice_type]:
                continue

            d = types[rice_type][season_key]
            key = (pdf_prov, rice_type, app_year)

            if key not in lookup:
                skipped_no_match.append(f'{pdf_prov} / {rice_type} / {app_year}')
                continue

            idx = lookup[key]
            row = rows[idx]

            # Only update production/yield/area fields — keep price data intact
            old_prod = row['production']
            row['production']    = int(d['prod'])
            row['yield']         = int(d['yield_kgrai'])
            row['area']          = int(d['area_harv'])
            row['area_planted']  = int(d['area_plant'])
            row['yield_planted'] = int(round(d['prod'] * 1000 / d['area_plant'])) if d['area_plant'] > 0 else 0
            row['source']        = 'oae_stats_2568_table_1_4'
            row['source_title']  = SOURCE_TITLE
            row['source_url']    = SOURCE_URL
            row['source_note']   = SOURCE_NOTE_J if rice_type == 'jasmine' else SOURCE_NOTE_W

            delta = int(d['prod']) - old_prod
            updated += 1

print(f'\nUpdated: {updated} rows')
if skipped_no_match:
    print(f'No match in app ({len(skipped_no_match)}):')
    for s in skipped_no_match[:10]:
        print(f'  {s}')

# ── Verify totals ────────────────────────────────────────────────────────────
print('\n=== Verification: Napi 2567 Production (tons) ===')
print(f'{"Province":35s} {"White (new)":>15} {"Jasmine (new)":>15}')
for prov in ['Surin','Nakhon Ratchasima','Nakhon Sawan','Ayutthaya','Chiang Mai']:
    wi = lookup.get((prov,'white','2567'))
    ji = lookup.get((prov,'jasmine','2567'))
    wv = rows[wi]['production'] if wi is not None else 0
    jv = rows[ji]['production'] if ji is not None else 0
    print(f'{prov:35s} {wv:>15,} {jv:>15,}')

# ── Write output ─────────────────────────────────────────────────────────────
print(f'\nWriting {OUT_JS}...')
json_str = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
with open(OUT_JS, 'w', encoding='utf-8') as f:
    f.write(f'window.RICE_DATA_ROWS={json_str};')
print(f'Done. File size: {len(json_str):,} bytes')
print('rice-data.js updated successfully.')
