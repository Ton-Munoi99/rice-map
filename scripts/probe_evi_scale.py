#!/usr/bin/env python3
"""ชั่วคราว: 250 ม. ทำให้พื้นที่นาใกล้ความจริง (OAE) ขึ้นจริงไหม

วัดพื้นที่นาที่ดาวเทียมจับได้ที่ scale 1000 กับ 250 แล้วเทียบกับ OAE รายจังหวัด
ไม่เขียนไฟล์ข้อมูล ลบทิ้งได้หลังได้คำตอบ
"""
import csv, os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ee
import fetch_rice_evi as F
from riceutils import init_gee, latest_q1_periods, q1_evi_image, GAUL_NAME_MAP as NM

init_gee()
p = latest_q1_periods(n=4)
evi = q1_evi_image(p[1][0], p[0][1])
union, glad, _ = F.load_rice_mask()
excl, _d = F.load_exclusion_mask()
if excl is not None:
    union = union.And(excl.Not())
flood, _w = F.build_rice_phenology_mask(p[0][0], F.PHENOLOGY_MONTHS)

confirmed = evi.updateMask(union.And(flood))
prov = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", "Thailand"))

# OAE: พื้นที่นาปี+นาปรังปีล่าสุด (ความจริงอ้างอิง)
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
oae = {}
with open(os.path.join(root, "rice-data.csv"), encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
yr = max(r["year"] for r in rows)
for r in rows:
    if r["year"] == yr and r["area"]:
        oae[r["province_en"]] = oae.get(r["province_en"], 0) + float(r["area"])

res = {}
for scale, rai_per_px in ((1000, 625.0), (250, 39.0625)):
    out = confirmed.reduceRegions(
        collection=prov, reducer=ee.Reducer.count(), scale=scale
    ).select(["ADM1_NAME", "count"], None, False).getInfo()
    res[scale] = {NM.get(f["properties"]["ADM1_NAME"], f["properties"]["ADM1_NAME"]):
                  (f["properties"].get("count") or 0) * rai_per_px
                  for f in out["features"]}

common = [k for k in res[1000] if k in oae and oae[k] > 0]
print(f"เทียบ {len(common)} จังหวัดที่มีทั้งดาวเทียมและ OAE (ปี {yr})\n")
print(f"{'':12}{'รวมทั้งประเทศ':>18}{'เทียบ OAE':>12}{'ค่ากลางอัตราส่วน':>18}{'ค่าเฉลี่ยคลาดเคลื่อน':>20}")
tot_oae = sum(oae[k] for k in common)
for scale in (1000, 250):
    tot = sum(res[scale][k] for k in common)
    ratios = [res[scale][k] / oae[k] for k in common]
    ape = [abs(res[scale][k] - oae[k]) / oae[k] for k in common]
    print(f"  {scale:>4} ม.  {tot:>16,.0f} ไร่{tot/tot_oae:>11.2f}x{st.median(ratios):>17.2f}x{st.mean(ape)*100:>18.0f}%")
print(f"  {'OAE':>4}     {tot_oae:>16,.0f} ไร่")
better = sum(1 for k in common
             if abs(res[250][k] - oae[k]) / oae[k] < abs(res[1000][k] - oae[k]) / oae[k])
print(f"\n250 ม. ใกล้ OAE กว่า: {better}/{len(common)} จังหวัด")
