#!/usr/bin/env python3
"""
จำแนกระยะข้าวจาก EVI — ที่เดียวสำหรับทั้ง pipeline

เดิมโค้ดชุดนี้ซ้ำอยู่ทั้ง fetch_rice_evi.py และ fetch_rice_evi_district.py
ย้ายมารวมกันเพื่อไม่ให้แก้ที่เดียวแล้วอีกที่ค้าง

เคยลองเพิ่มกฎ "ห้ามออกระยะปลายฤดูนอกหน้าต่างเก็บเกี่ยวของภาค" แล้วถอดออก —
ดูเหตุผลใน CHANGELOG (ปฏิทินนาปีใช้ตัดสินไม่ได้ เพราะหลายจังหวัดมีนาปรัง
ชลประทานพอๆ กับนาปี เชียงราย 127% ของพื้นที่นาปี จึงปลูกเหลื่อมกันได้)

Run self-test: python scripts/rice_stage.py
"""
TREND_EPS = 0.02  # |Δ EVI| ต่ำกว่านี้ถือว่าทรงตัว (กัน noise MODIS รายเดือน)


def classify_evi(evi_val, evi_prev=None):
    """ระยะข้าวจาก EVI + ทิศทาง (เทียบเดือนก่อนหน้า)

    ค่าสูง = ออกรวง (ยอด canopy) ไม่ใช่สุกแก่ — สุกแก่ EVI ลดลง
    """
    if evi_val is None:
        return None
    if evi_val < 0.15:
        return "fallow"
    rising = True if evi_prev is None else (evi_val - evi_prev) >= -TREND_EPS
    if evi_val < 0.25:
        return "seedling" if rising else "harvest"
    if evi_val < 0.40:
        return "tillering" if rising else "ripening"
    if evi_val < 0.55:
        return "heading" if rising else "ripening"
    return "heading"


def _selftest():
    assert classify_evi(None) is None
    assert classify_evi(0.10, 0.30) == "fallow"
    assert classify_evi(0.20, 0.19) == "seedling"
    assert classify_evi(0.20, 0.30) == "harvest"
    assert classify_evi(0.306, 0.332) == "ripening"
    assert classify_evi(0.306, 0.280) == "tillering"
    assert classify_evi(0.50, 0.30) == "heading"
    assert classify_evi(0.50, 0.60) == "ripening"
    assert classify_evi(0.70, 0.90) == "heading"   # >=0.55 ค่าสูงสุดเสมอ
    # dead-band: ลดลงน้อยกว่า TREND_EPS ยังนับเป็นขาขึ้น
    assert classify_evi(0.306, 0.320) == "tillering"
    assert classify_evi(0.306, 0.327) == "ripening"
    print("ok")


if __name__ == "__main__":
    _selftest()
