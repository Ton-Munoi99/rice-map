#!/usr/bin/env python3
"""ชั่วคราว: วัดว่า reduceRegions ที่ scale 250 ม. GEE รับไหวไหม

ตอบคำถามเดียว — เปลี่ยนจาก grid 1 กม. เป็น 250 ม. (พิกเซลเพิ่ม 16 เท่า)
แล้วชนลิมิตหน่วยความจำ/เวลาของ GEE หรือไม่ ไม่เขียนไฟล์ข้อมูลใดๆ
ลบทิ้งได้หลังได้คำตอบ
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ee
from riceutils import init_gee, latest_q1_periods, q1_evi_image

init_gee()
periods = latest_q1_periods(n=2)
evi = q1_evi_image(periods[1][0], periods[0][1])

th = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", "Thailand"))
d1 = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq("ADM0_NAME", "Thailand"))

for label, fc, n in [("จังหวัด (77)", th, 77), ("อำเภอ (813)", d1, 813)]:
    for scale in (1000, 250):
        t0 = time.time()
        try:
            res = evi.reduceRegions(
                collection=fc,
                reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
                scale=scale,
            ).select(["mean", "count"], None, False).getInfo()
            got = len(res["features"])
            px = sum((f["properties"].get("count") or 0) for f in res["features"])
            print(f"  {label:14} scale {scale:>4} ม. → {time.time()-t0:6.1f} วิ · {got} พื้นที่ · {px:,.0f} พิกเซล  ✅")
        except Exception as e:
            print(f"  {label:14} scale {scale:>4} ม. → {time.time()-t0:6.1f} วิ  ❌ {type(e).__name__}: {str(e)[:160]}")
