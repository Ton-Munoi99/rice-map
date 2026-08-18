#!/usr/bin/env python3
"""ชั่วคราว: ผ่อนด่าน phenology ระดับไหนทำให้พื้นที่นาใกล้ OAE ขึ้นโดยไม่นับพืชอื่นเพิ่ม

ออกแบบการวัด: ผ่อนเกณฑ์แล้วพื้นที่ต้องเพิ่มใน "จังหวัดข้าว" แต่ต้องไม่เพิ่มใน
"จังหวัดยาง/ปาล์ม" ที่แทบไม่มีนา — ถ้าเพิ่มทั้งคู่แปลว่าแค่นับมั่วขึ้น
ไม่เขียนไฟล์ข้อมูล ลบทิ้งได้หลังได้คำตอบ
"""
import csv, os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ee
import fetch_rice_evi as F
from riceutils import init_gee, GAUL_NAME_MAP as NM

init_gee()
RAI = 625.0

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
oae = {}
with open(os.path.join(root, "rice-data.csv"), encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
yr = max(r["year"] for r in rows)
for r in rows:
    if r["year"] == yr and r["area"]:
        oae[r["province_en"]] = oae.get(r["province_en"], 0) + float(r["area"])

RICE = [p for p, a in sorted(oae.items(), key=lambda x: -x[1])[:20]]          # จังหวัดข้าวใหญ่
CTRL = [p for p, a in oae.items() if a < 20000]                              # แทบไม่มีนา = ยาง/ปาล์ม

# ── สร้างชุด EVI/LSWI ย้อนหลังครั้งเดียว ใช้ซ้ำทุกสูตร ──────────────────────
hist = F.get_history_months(F.latest_q1_periods(n=1)[0][0], F.PHENOLOGY_MONTHS) \
       if hasattr(F, "latest_q1_periods") else None
from riceutils import latest_q1_periods
hist = F.get_history_months(latest_q1_periods(n=1)[0][0], F.PHENOLOGY_MONTHS)
evis, lswis = [], []
for a, b in hist:
    m = (ee.ImageCollection("MODIS/061/MOD13A3").filterDate(a, b)
         .select(["EVI", "sur_refl_b02", "sur_refl_b07"]).mosaic())
    e = m.select("EVI").multiply(0.0001)
    nir = m.select("sur_refl_b02").multiply(0.0001)
    sw = m.select("sur_refl_b07").multiply(0.0001)
    evis.append(e.rename("EVI"))
    lswis.append(nir.subtract(sw).divide(nir.add(sw)).rename("LSWI"))

evi_col = ee.ImageCollection(evis)
evi_max = evi_col.max()
evi_min = evi_col.min()
amp = evi_max.subtract(evi_min)

def gate(flood_evi_max, peak_min, amp_min, min_evi_max, need_flood=True):
    conds = evi_max.gte(peak_min).And(amp.gte(amp_min)).And(evi_min.lte(min_evi_max))
    if need_flood:
        fl = [l.gt(e).And(e.lt(flood_evi_max)).rename("f")
              for e, l in zip(evis, lswis)]
        conds = conds.And(ee.ImageCollection(fl).reduce(ee.Reducer.anyNonZero()))
    return conds.rename("g")

VARIANTS = [
    ("ปัจจุบัน (เคยโล่ง≤0.20)",  dict(flood_evi_max=.30, peak_min=.40, amp_min=.25, min_evi_max=.20)),
    ("เคยโล่ง≤0.22",            dict(flood_evi_max=.30, peak_min=.40, amp_min=.25, min_evi_max=.22)),
    ("เคยโล่ง≤0.24",            dict(flood_evi_max=.30, peak_min=.40, amp_min=.25, min_evi_max=.24)),
    ("เคยโล่ง≤0.26",            dict(flood_evi_max=.30, peak_min=.40, amp_min=.25, min_evi_max=.26)),
    ("เคยโล่ง≤0.28",            dict(flood_evi_max=.30, peak_min=.40, amp_min=.25, min_evi_max=.28)),
    ("เคยโล่ง≤0.30",            dict(flood_evi_max=.30, peak_min=.40, amp_min=.25, min_evi_max=.30)),
    ("เคยโล่ง≤0.26 + แกว่ง≥0.30", dict(flood_evi_max=.30, peak_min=.40, amp_min=.30, min_evi_max=.26)),
]

union, glad, _ = F.load_rice_mask()
excl, _d = F.load_exclusion_mask()
if excl is not None:
    union = union.And(excl.Not())

img = None
for i, (_n, kw) in enumerate(VARIANTS):
    b = gate(**kw).updateMask(union).rename(f"v{i}")
    img = b if img is None else img.addBands(b)

prov = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
res = img.reduceRegions(collection=prov, reducer=ee.Reducer.sum(), scale=1000).getInfo()

data = {}
for f in res["features"]:
    p = f["properties"]
    data[NM.get(p["ADM1_NAME"], p["ADM1_NAME"])] = p

# เว็บซ่อนจังหวัดที่ OAE < 15,000 ไร่อยู่แล้ว (RICE_EVI_MIN_OAE_RAI)
SHOWN = [p for p, a in oae.items() if a >= 15000]
print(f"จังหวัดที่เว็บแสดง {len(SHOWN)} จาก {len(oae)}
")
print(f"{'สูตร':30}{'ข้าวใหญ่÷OAE':>14}{'รวมประเทศ÷OAE':>16}{'ส่วนเกินในจว.ที่แสดง':>24}")
for i2, (name, _kw) in enumerate(VARIANTS):
    k = f"v{i2}"
    ratios = [(data[p].get(k, 0) or 0) * RAI / oae[p] for p in RICE if p in data]
    tot = sum((v.get(k, 0) or 0) * RAI for v in data.values())
    excess = sum(max(0.0, (data[p].get(k, 0) or 0) * RAI - oae[p]) for p in SHOWN if p in data)
    print(f"  {name:28}{st.median(ratios):>12.2f}x{tot/sum(oae.values()):>15.2f}x{excess:>21,.0f} ไร่")
