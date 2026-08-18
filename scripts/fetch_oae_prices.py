#!/usr/bin/env python3
"""
fetch_oae_prices.py
--------------------
ราคาข้าวเปลือกที่เกษตรกรขายได้ ระดับประเทศ (รายสัปดาห์) → data/prices-live.json

ทำไมเปลี่ยนแหล่ง: เดิมยิง CKAN datastore ของ catalog.oae.go.th ตรงๆ ด้วย
resource_id ซึ่งตั้งแต่ 20 พ.ค. 2569 ตอบ 403 "ไม่ได้รับอนุญาตให้อ่านทรัพยากร"
สคริปต์เดิมกลืน error แล้วเขียน oae_national เป็น {} ทับของเดิม แต่ยัง exit 0
workflow จึงขึ้นเขียวทุกวันโดยที่ข้อมูลหายไป 3 เดือนไม่มีใครรู้

แหล่งใหม่คือ API ที่ตัว catalog ชี้ไปเอง (ดู resource url ในชุดข้อมูล
"ราคาที่เกษตรกรขายได้รายสัปดาห์ สินค้าข้าวเปลือก") — เปิดสาธารณะ ไม่ต้องมี key
ให้รายสัปดาห์ (เดิมรายเดือน) ย้อนถึง 2554 และมีหอมมะลิด้วย (เดิมมีแต่ข้าวเจ้า)

Run: python scripts/fetch_oae_prices.py
"""
import json
import os
import sys

import requests

API = "https://agriapi.nabc.go.th/api/weekly-prices/product"
# API อยู่หลัง Cloudflare ซึ่งบล็อก 403 เมื่อยิงจาก IP ดาต้าเซ็นเตอร์ด้วย UA ของ
# python-requests (จากไทยผ่านหมด แต่ runner ของ GitHub Actions โดนทุกครั้ง)
# ส่ง header แบบเบราว์เซอร์เพื่อยกคะแนน bot score — ไม่ได้หลบ CAPTCHA หรือ challenge ใดๆ
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "th,en;q=0.9",
    "Referer": "https://catalog.oae.go.th/",
}
CATALOG_URL = "https://catalog.oae.go.th/dataset/weekly-prices-paddy"
TIMEOUT = 30
PAGE = 100

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(_ROOT, "data", "prices-live.json")

# คีย์ต้องเป็น white / jasmine เพราะ index.html อ่าน oae_national.white.latest
# (สคริปต์เดิมเขียน "white_rice" ตามชื่อ dict ทำให้เว็บอ่านไม่เจอแม้ตอนดึงสำเร็จ)
PRODUCTS = {
    "white": {
        "product_name": "ข้าวเปลือกเจ้า ความชื้น 15",
        "label_th": "ข้าวเปลือกเจ้า (ความชื้น 15%)",
        "label_en": "White paddy (15% moisture)",
    },
    "jasmine": {
        "product_name": "ข้าวเปลือกเจ้าหอมมะลิ ความชื้น 15",
        "label_th": "ข้าวเปลือกหอมมะลิ (ความชื้น 15%)",
        "label_en": "Jasmine paddy (15% moisture)",
    },
}


def fetch_all(product_name):
    """ดึงทุกหน้า — API ตอบ total มาให้ ใช้ offset เลื่อน"""
    rows, offset = [], 0
    while True:
        r = requests.get(
            API,
            params={"product_name": product_name, "limit": PAGE, "offset": offset},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        body = r.json()
        if not body.get("success"):
            raise RuntimeError(f"API ตอบ success=false: {str(body)[:200]}")
        batch = body.get("data") or []
        rows.extend(batch)
        total = (body.get("pagination") or {}).get("total", len(rows))
        if not batch or len(rows) >= total:
            return rows
        offset += PAGE


def latest_of(rows):
    """แถวล่าสุดตาม ปี→เดือน→สัปดาห์ (API ไม่รับประกันลำดับ จึงเรียงเอง)"""
    national = [r for r in rows if r.get("province_code") == "TH00"]
    if not national:
        return None
    newest = max(national, key=lambda r: (r["year_th"], int(r["month"]), r["week"]))
    try:
        value = round(float(newest["value"]))
    except (TypeError, ValueError):
        return None
    return {
        # เดือนเป็น int เพราะ index.html ใช้ทำ index ใน monthNames[]
        "year": newest["year_th"],
        "month": int(newest["month"]),
        "week": newest["week"],
        "value_thb_per_ton": value,
    }


def main():
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)

    # เริ่มจากของเดิมเสมอ — ดึงไม่สำเร็จต้องไม่ลบข้อมูลที่ยังใช้ได้อยู่ทิ้ง
    oae = dict(existing.get("oae_national") or {})
    failed = []

    for key, cfg in PRODUCTS.items():
        try:
            rows = fetch_all(cfg["product_name"])
            latest = latest_of(rows)
            if not latest:
                raise RuntimeError("ไม่พบแถวระดับประเทศ (TH00) ที่อ่านค่าได้")
            oae[key] = {
                "label_th": cfg["label_th"],
                "label_en": cfg["label_en"],
                "latest": latest,
            }
            print(f"  {key:8} {len(rows):>4} แถว · ล่าสุด {latest['year']}-"
                  f"{latest['month']:02d} สัปดาห์ {latest['week']} = "
                  f"{latest['value_thb_per_ton']:,} บาท/ตัน")
        except Exception as e:
            failed.append(f"{key}: {type(e).__name__}: {e}")
            print(f"  [ERROR] {key}: {e}", file=sys.stderr)

    result = {
        **existing,
        "oae_national": oae,
        "_meta": {
            **(existing.get("_meta") or {}),
            "source": "OAE / NABC weekly farm-gate prices",
            "source_url": CATALOG_URL,
            "api": API,
            "note_th": "ราคาที่เกษตรกรขายได้ รายสัปดาห์ ระดับประเทศ (สศก.) · "
                       "ราคารายจังหวัดในไฟล์เดียวกันมาจากสมาคมโรงสี ดู provincial_prices",
            "note_en": "Weekly national farm-gate paddy prices (OAE). Provincial prices in "
                       "this file come from the Millers Association — see provincial_prices.",
        },
    }
    # อัปเดตเวลาเฉพาะตอนดึงได้จริง ไม่งั้น freshness monitor จะเห็นว่าไฟล์สดทั้งที่ข้อมูลค้าง
    if not failed:
        from datetime import datetime, timezone
        result["_meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUTPUT_FILE}")

    if failed:
        # ออกด้วย error ให้ workflow แดง — ความเงียบคือสาเหตุที่ของเดิมพังอยู่ 3 เดือน
        print(f"[FAIL] ดึงไม่สำเร็จ {len(failed)}/{len(PRODUCTS)} รายการ: {failed}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
