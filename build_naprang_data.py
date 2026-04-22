#!/usr/bin/env python3
"""
Build data/naprang-data.js from oae_extracted.json (Table 1.7 นาปรัง)
Years: 2567 / 2568f→2568 / 2569f→2569
Rice types: white (ข้าวเจ้าอื่นๆ), jasmine (หอมมะลิ in+out)
"""
import json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

OAE_JSON = r'C:\Users\sponlapatp\Desktop\Rice Map\data\oae_extracted.json'
OUT_JS   = r'C:\Users\sponlapatp\Desktop\Rice Map\data\naprang-data.js'

YEAR_MAP = {'naprang_2567': '2567', 'naprang_2568f': '2568', 'naprang_2569f': '2569'}

with open(OAE_JSON, encoding='utf-8') as f:
    oae = json.load(f)

# Province name fixes (same as update_rice_data.py)
PROV_MAP = {
    'Bangkok':   'Bangkok Metropolis',
    'ChiangMai': 'Chiang Mai',
    'Ayutthaya': 'Phra Nakhon Si Ayutthaya',
    'Others1/':  None,
}

out = {}
for raw_prov, types in oae.items():
    prov = PROV_MAP.get(raw_prov, raw_prov)
    if prov is None:
        continue
    for rice_type in ('white', 'jasmine'):
        if rice_type not in types:
            continue
        for season_key, app_year in YEAR_MAP.items():
            d = types[rice_type].get(season_key)
            if not d or d['prod'] == 0:
                continue
            if prov not in out:
                out[prov] = {}
            if rice_type not in out[prov]:
                out[prov][rice_type] = {}
            out[prov][rice_type][app_year] = {
                'production': int(d['prod']),
                'yield':      int(d['yield_kgrai']),
                'area':       int(d['area_harv']),
                'area_planted': int(d['area_plant']),
            }

# Stats
total_entries = sum(
    len(seasons)
    for types in out.values()
    for seasons in types.values()
)
provs_with_white   = sum(1 for v in out.values() if 'white'   in v)
provs_with_jasmine = sum(1 for v in out.values() if 'jasmine' in v)
print(f'Provinces with naprang white:   {provs_with_white}')
print(f'Provinces with naprang jasmine: {provs_with_jasmine}')
print(f'Total data entries: {total_entries}')

# Sample
for prov in list(sorted(out.keys()))[:3]:
    print(f'\n{prov}:')
    for rt, yrs in out[prov].items():
        for yr, d in yrs.items():
            print(f'  [{rt}] {yr}: prod={d["production"]:>10,} | yield={d["yield"]:>4} | area={d["area"]:>10,}')

# Write JS
js = (
    '// นาปรัง (Second Rice) province data — OAE สถิติการเกษตรฯ ปี 2568 Table 1.7\n'
    '// white = ข้าวเจ้าอื่นๆ | jasmine = หอมมะลิ (in-area + outside-area)\n'
    '// years: 2567 (official) | 2568 (forecast) | 2569 (forecast)\n'
    f'window.NAPRANG_DATA={json.dumps(out, ensure_ascii=False, separators=(",", ":"))};'
)
with open(OUT_JS, 'w', encoding='utf-8') as f:
    f.write(js)
print(f'\nSaved → {OUT_JS}  ({len(js):,} bytes)')
