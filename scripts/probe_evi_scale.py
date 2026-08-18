#!/usr/bin/env python3
"""ชั่วคราว: วัดว่าท่อจริง (5 band + mask + phenology) ที่ scale 250 ม. GEE รับไหวไหม"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ee
import fetch_rice_evi as F
from riceutils import init_gee, latest_q1_periods, q1_evi_image

init_gee()
periods = latest_q1_periods(n=4)
evi = q1_evi_image(periods[1][0], periods[0][1])
prev = q1_evi_image(periods[3][0], periods[2][1])

union_mask, glad_mask, _ = F.load_rice_mask()
excl, _d = F.load_exclusion_mask()
if excl is not None:
    union_mask = union_mask.And(excl.Not())

t0 = time.time()
flood_conf, _w = F.build_rice_phenology_mask(periods[0][0], F.PHENOLOGY_MONTHS)
print(f"  สร้าง phenology mask: {time.time()-t0:.1f} วิ")

scan_evi = evi.updateMask(union_mask)
flood_in_scan = flood_conf.updateMask(union_mask)
rice_evi = evi.updateMask(union_mask.And(flood_conf))
prev_rice = prev.updateMask(union_mask.And(flood_conf))
glad_ind = glad_mask.updateMask(union_mask)

img = (scan_evi.rename("EVIscan")
       .addBands(rice_evi.rename("EVIrice"))
       .addBands(prev_rice.rename("EVIprev"))
       .addBands(flood_in_scan.float().rename("flooded"))
       .addBands(glad_ind.float().rename("glad")))

prov = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
dist = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
red = (ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True)
       .combine(ee.Reducer.sum(), sharedInputs=True))

for label, fc in [("จังหวัด (77)", prov), ("อำเภอ (813)", dist)]:
    for scale in (1000, 250):
        t = time.time()
        try:
            r = img.reduceRegions(collection=fc, reducer=red, scale=scale).getInfo()
            n = len(r["features"])
            px = sum((f["properties"].get("EVIscan_count") or 0) for f in r["features"])
            print(f"  {label:13} 5 band · scale {scale:>4} ม. → {time.time()-t:6.1f} วิ · {n} พื้นที่ · scan {px:,.0f} พิกเซล ✅")
        except Exception as e:
            print(f"  {label:13} 5 band · scale {scale:>4} ม. → {time.time()-t:6.1f} วิ ❌ {type(e).__name__}: {str(e)[:180]}")
