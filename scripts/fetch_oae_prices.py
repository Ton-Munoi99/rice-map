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
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import requests

API = "https://agriapi.nabc.go.th/api/weekly-prices/product"
# API อยู่หลัง Cloudflare ซึ่งตอบ 403 ให้ IP ดาต้าเซ็นเตอร์ — ยิงจากไทยผ่านทุก UA
# แต่ runner ของ GitHub Actions โดนทุกครั้ง (ลองส่ง header แบบเบราว์เซอร์แล้วไม่ช่วย
# เพราะบล็อกที่ชื่อเสียง IP ไม่ใช่ UA) จึงมีทางสำรองผ่าน Firecrawl ซึ่งใช้เบราว์เซอร์จริง
# และรีโปนี้ตั้ง FIRECRAWL_API_KEY ไว้อยู่แล้วสำหรับราคาปุ๋ย
HEADERS = {"User-Agent": "RiceMap/1.0 (+https://github.com/Ton-Munoi99/rice-map)"}
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
# ยอมให้ข้อมูลล่าช้าได้เท่านี้ — เกินนี้ถือว่าต้นทางหยุดอัปเดต ให้ workflow แดง
MAX_LAG_MONTHS = 3
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


def _url(product_name):
    q = urllib.parse.urlencode({"product_name": product_name, "limit": 1, "offset": 0})
    return f"{API}?{q}"


def _via_firecrawl(url):
    """ทางสำรองเมื่อ Cloudflare บล็อก — Firecrawl ใช้เบราว์เซอร์จริงจึงผ่าน
    ตอบกลับเป็น markdown ที่ห่อ JSON ไว้ในโค้ดบล็อก จึงต้องแกะออกมาก่อน"""
    if not FIRECRAWL_KEY:
        raise RuntimeError("โดนบล็อก และไม่มี FIRECRAWL_API_KEY ให้ใช้ทางสำรอง")
    body = json.dumps({"url": url, "formats": ["markdown"], "onlyMainContent": False}).encode()
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape", data=body,
        headers={"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.load(r)
    if not data.get("success"):
        raise RuntimeError(f"firecrawl ไม่สำเร็จ: {str(data)[:200]}")
    md = data["data"]["markdown"]
    m = re.search(r"\{.*\}", md, re.S)
    if not m:
        raise RuntimeError(f"firecrawl ไม่ได้ JSON กลับมา: {md[:200]}")
    return json.loads(m.group(0))


def fetch_latest(product_name):
    """แถวล่าสุดของสินค้านั้น — API เรียงใหม่ไปเก่า จึงขอแค่แถวเดียว"""
    url = _url(product_name)
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        body = r.json()
        via = "direct"
    except requests.HTTPError as e:
        if e.response is None or e.response.status_code != 403:
            raise
        body = _via_firecrawl(url)
        via = "firecrawl"

    if not body.get("success"):
        raise RuntimeError(f"API ตอบ success=false: {str(body)[:200]}")
    rows = [x for x in (body.get("data") or []) if x.get("province_code") == "TH00"]
    if not rows:
        raise RuntimeError("ไม่พบแถวระดับประเทศ (TH00)")
    newest = max(rows, key=lambda x: (x["year_th"], int(x["month"]), x["week"]))

    # กันกรณีต้นทางหยุดอัปเดตแล้วเรายังดึง "สำเร็จ" อยู่ทุกวัน
    bkk = datetime.now(timezone.utc) + timedelta(hours=7)
    lag = (bkk.year + 543 - newest["year_th"]) * 12 + (bkk.month - int(newest["month"]))
    if lag > MAX_LAG_MONTHS:
        raise RuntimeError(f"ข้อมูลล่าสุด {newest['year_th']}-{newest['month']} เก่ากว่า {MAX_LAG_MONTHS} เดือน")

    return {
        # เดือนเป็น int เพราะ index.html ใช้ทำ index ใน monthNames[]
        "year": newest["year_th"],
        "month": int(newest["month"]),
        "week": newest["week"],
        "value_thb_per_ton": round(float(newest["value"])),
    }, via


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
            latest, via = fetch_latest(cfg["product_name"])
            oae[key] = {
                "label_th": cfg["label_th"],
                "label_en": cfg["label_en"],
                "latest": latest,
            }
            print(f"  {key:8} [{via}] ล่าสุด {latest['year']}-{latest['month']:02d} "
                  f"สัปดาห์ {latest['week']} = {latest['value_thb_per_ton']:,} บาท/ตัน")
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
