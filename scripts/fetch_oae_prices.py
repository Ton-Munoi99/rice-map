#!/usr/bin/env python3
"""
fetch_oae_prices.py
--------------------
ดึงราคาข้าวเปลือกระดับประเทศจาก OAE CKAN API
แล้วเขียนลง data/prices-live.json เพื่อให้ index.html โหลดได้ตอนเปิดเว็บ

API Source: https://catalog.oae.go.th
Resource IDs:
  - ข้าวเปลือกเจ้า : c72f9a58-6969-48d6-9203-7859362adaf7
  - ข้าวเปลือกหอมมะลิ : (ต้องหา resource_id เพิ่ม)
"""

import requests
import json
import os
from datetime import datetime, timezone

# ───────────────────────────────────────────
# Config
# ───────────────────────────────────────────
CKAN_BASE = "https://catalog.oae.go.th/api/3/action/datastore_search"

RESOURCES = {
    "white_rice": {
        "resource_id": "c72f9a58-6969-48d6-9203-7859362adaf7",
        "label_th": "ข้าวเปลือกเจ้า (ความชื้น 15%)",
        "label_en": "White Rice Paddy (15% moisture)",
        "key": "white"
    }
    # เพิ่ม jasmine ถ้าพบ resource_id
}

OUTPUT_FILE = "data/prices-live.json"


def fetch_all_records(resource_id: str) -> list:
    """ดึงข้อมูลทั้งหมดจาก CKAN API (pagination)"""
    records = []
    offset = 0
    limit = 100

    while True:
        url = (
            f"{CKAN_BASE}"
            f"?resource_id={resource_id}"
            f"&limit={limit}&offset={offset}"
        )
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            batch = data["result"]["records"]
            records.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        except Exception as e:
            print(f"  ⚠️  Error fetching offset={offset}: {e}")
            break

    return records


def latest_records(records: list) -> dict:
    """
    คืนค่าข้อมูลล่าสุด:
    - latest_month: ราคาเดือนล่าสุดที่มีข้อมูล
    - last_12_months: ย้อนหลัง 12 เดือน สำหรับ mini chart
    """
    sorted_r = sorted(records, key=lambda x: (x["year"], x["month"]))
    latest = sorted_r[-1] if sorted_r else {}
    last_12 = sorted_r[-12:] if len(sorted_r) >= 12 else sorted_r
    return {
        "latest": {
            "year": latest.get("year"),
            "month": latest.get("month"),
            "value_thb_per_ton": latest.get("Value"),     # บาท/ตัน — ราคาที่ไร่นา
        },
        "trend_12m": [
            {
                "year": r["year"],
                "month": r["month"],
                "value": r["Value"]
            }
            for r in last_12
        ]
    }


def main():
    os.makedirs("data", exist_ok=True)

    # โหลดไฟล์เดิมถ้ามี (เพื่อ merge ไม่ flush ทิ้ง)
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    result = {
        **existing,
        "oae_national": {},
        "meta": {
            "source": "OAE CKAN API — catalog.oae.go.th",
            "source_en": "Office of Agricultural Economics (OAE)",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "note_th": "ราคาเฉลี่ยรายเดือน ณ ราคาที่เกษตรกรขายได้ที่ไร่นา (ระดับประเทศ)",
            "note_en": "Monthly average farm-gate price at national level"
        }
    }

    for key, cfg in RESOURCES.items():
        print(f"🔄  Fetching {cfg['label_en']} ...")
        records = fetch_all_records(cfg["resource_id"])
        print(f"    ✅  {len(records)} records retrieved")

        if records:
            summary = latest_records(records)
            result["oae_national"][key] = {
                "label_th": cfg["label_th"],
                "label_en": cfg["label_en"],
                **summary
            }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅  Saved → {OUTPUT_FILE}")
    latest = result["oae_national"].get("white", {}).get("latest", {})
    if latest:
        print(f"    ล่าสุด: ปี {latest['year']} เดือน {latest['month']} "
              f"= {latest['value_thb_per_ton']:,} บาท/ตัน")


if __name__ == "__main__":
    main()
