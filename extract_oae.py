#!/usr/bin/env python3
"""
Extract Table 1.4 (นาปี 2566-2568) and Table 1.7 (นาปรัง 2567-2569)
from OAE PDF: สถิติการเกษตรของประเทศไทย ปี 2568.pdf

Outputs:
  - jasmine:  ข้าวเจ้าหอมมะลิในพื้นที่ + นอกพื้นที่ (combined, area/prod summed, yield recalculated)
  - white:    ข้าวเจ้าอื่น ๆ only (exclude เหนียว + ปทุมธานี 1)
"""
import pdfplumber, sys, io, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PDF_PATH = r'C:\Users\sponlapatp\Desktop\สถิติการเกษตรของประเทศไทย ปี 2568.pdf'

SKIP_EN = {
    'Whole Kingdom','Northern','Northeastern','Central','Southern','Eastern',
    'Hom mali rice in the area','Hom mali rice outside the area',
    'Pathum Thani 1','Other White Rice','Glutinous Rice',
    'Region/\nProvince', 'Region/', 'Province'
}
SKIP_REGION_TH = {
    'รวมทั้งประเทศ','เหนือ','ตะวันออกเฉียงเหนือ','กลาง','ใต้','ตะวันออก',
    'ภาค/จังหวัด'
}
JASMINE_TH = {'ข้าวเจ้าหอมมะลิในพื้นที่', 'ข้าวเจ้าหอมมะลินอกพื้นที่'}
WHITE_TH   = {'ข้าวเจ้าอื่น ๆ', 'ข้าวเจ้าอื่น\xa0ๆ', 'ข้าวเจ้าอื่นๆ'}
SKIP_TH    = {'ข้าวเจ้าปทุมธานี 1', 'ข้าวเหนียว'}


def to_num(s):
    if not s:
        return 0
    s = str(s).replace(',', '').replace('\xa0', '').strip()
    try:
        return float(s)
    except:
        return 0


def process_pages(pdf, page_range, years, season, data, state):
    for pi in page_range:
        page = pdf.pages[pi]
        tables = page.extract_tables()
        for tbl in tables:
            for row in tbl:
                if not row or all(c is None or str(c).strip() == '' for c in row):
                    continue
                col0 = str(row[0] or '').strip()
                col_last = str(row[-1] or '').strip() if len(row) > 1 else ''

                # Skip pure header rows
                if not col0 or col0 in {'', 'ภาค/จังหวัด'}:
                    continue
                if 'เนื้อที่เพาะปลูก' in col0 or 'Planted area' in col_last:
                    continue
                if any(y in col0 for y in ['2566', '2567', '2568', '2569']):
                    continue

                is_jasmine = col0 in JASMINE_TH
                is_white = col0 in WHITE_TH
                is_skip = col0 in SKIP_TH

                if is_skip:
                    continue

                if not is_jasmine and not is_white:
                    # Province or region row
                    is_region = col0 in SKIP_REGION_TH
                    if is_region:
                        continue
                    # Province: has non-variety English name
                    en = col_last.strip()
                    if en and en not in SKIP_EN and len(en) > 2:
                        state['prov'] = en
                        if en not in data:
                            data[en] = {}
                    continue

                # Variety row — need current province
                if not state['prov']:
                    continue

                rice_type = 'jasmine' if is_jasmine else 'white'
                prov = state['prov']

                # Columns: 0=name, 1-3=planted, 4-6=harvested, 7-9=production, 10-12=yield, 13=EN
                vals = row[1:]  # drop col0
                # remove trailing EN column if present
                if len(vals) >= 13:
                    vals = vals[:12]

                for idx, year in enumerate(years):
                    ap = to_num(vals[idx])     if len(vals) > idx     else 0
                    ah = to_num(vals[idx + 3]) if len(vals) > idx + 3 else 0
                    pr = to_num(vals[idx + 6]) if len(vals) > idx + 6 else 0
                    yd = to_num(vals[idx + 9]) if len(vals) > idx + 9 else 0

                    key = f'{season}_{year}'
                    if rice_type not in data[prov]:
                        data[prov][rice_type] = {}
                    if key not in data[prov][rice_type]:
                        data[prov][rice_type][key] = {
                            'area_plant': 0, 'area_harv': 0, 'prod': 0
                        }

                    d = data[prov][rice_type][key]
                    d['area_plant'] += ap
                    d['area_harv'] += ah
                    d['prod'] += pr
                    # Recalculate yield from summed harv + prod (more accurate for combined jasmine)


def main():
    data = {}
    state = {'prov': None}

    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"PDF pages: {len(pdf.pages)}")

        print("\n--- Extracting Table 1.4 (นาปี pages 34-42) ---")
        state['prov'] = None
        process_pages(pdf, range(33, 42), ['2566', '2567', '2568f'], 'napi', data, state)

        print("--- Extracting Table 1.7 (นาปรัง pages 47-52) ---")
        state['prov'] = None
        process_pages(pdf, range(46, 52), ['2567', '2568f', '2569f'], 'naprang', data, state)

    # Recalculate yield for all
    for prov, types in data.items():
        for rtype, seasons in types.items():
            for key, d in seasons.items():
                if d['area_harv'] > 0:
                    d['yield_kgrai'] = round(d['prod'] * 1000 / d['area_harv'], 0)
                else:
                    d['yield_kgrai'] = 0
                d['area_plant'] = round(d['area_plant'])
                d['area_harv']  = round(d['area_harv'])
                d['prod']       = round(d['prod'])

    print(f"\nProvinces extracted: {len(data)}")
    for prov in sorted(data.keys()):
        types = list(data[prov].keys())
        keys  = [k for t in types for k in data[prov][t].keys()]
        print(f"  {prov:35s}: {types}  seasons={set(keys)}")

    # Save JSON
    out_path = r'C:\Users\sponlapatp\Desktop\Rice Map\data\oae_extracted.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {out_path}")

    # Also print first 3 provinces in detail
    print("\n=== Sample data (first 3 provinces) ===")
    for prov in list(sorted(data.keys()))[:3]:
        print(f"\n{prov}:")
        for rtype, seasons in data[prov].items():
            print(f"  [{rtype}]")
            for sk, sv in seasons.items():
                print(f"    {sk}: harv={sv['area_harv']:,} rai | prod={sv['prod']:,} ton | yield={sv['yield_kgrai']} kg/rai")


if __name__ == '__main__':
    main()
