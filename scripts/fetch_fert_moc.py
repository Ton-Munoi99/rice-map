#!/usr/bin/env python3
import requests
import json
import os
import sys
from datetime import datetime, timedelta

# บังคับการแสดงผลเป็น UTF-8 สำหรับ Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# IDs สำหรับปุ๋ยจาก MOC Data API
FERT_CONFIG = {
    "urea_46_0_0":   {"id": "D14001", "name": "ปุ๋ยยูเรีย 46-0-0"},
    "form_16_20_0":  {"id": "D14002", "name": "ปุ๋ยสูตร 16-20-0"},
    "form_15_15_15": {"id": "D14003", "name": "ปุ๋ยสูตร 15-15-15"}
}

OUTPUT_FILE = "data/fert-data.js"

def fetch_prices(product_id):
    today = datetime.now()
    # ดึงย้อนหลัง 15 วันเพื่อให้มั่นใจว่ามีข้อมูล (บางจังหวัดอัปเดตช้า)
    from_date = (today - timedelta(days=15)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")
    
    url = f"https://dataapi.moc.go.th/gis-product-prices?product_id={product_id}&from_date={from_date}&to_date={to_date}"
    
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Error fetching {product_id}: {e}")
        return []

def main():
    print("Fetching Fertilizer Prices from MOC API...")
    os.makedirs("data", exist_ok=True)
    
    provincial_data = {}

    for key, info in FERT_CONFIG.items():
        print(f"Fetching {info['name']} ({info['id']})...")
        data = fetch_prices(info["id"])
        
        # จัดกลุ่มข้อมูลรายจังหวัด
        temp_prov = {}
        if not isinstance(data, list):
            print(f"  Warning: Expected list from API, got {type(data)}")
            continue

        for entry in data:
            if not isinstance(entry, dict):
                continue
            prov = entry.get("province_name", "").replace("จังหวัด", "").strip()
            if not prov: continue
            
            # เก็บค่า avg price ล่าสุด (API มักจะเรียงวันที่มาให้แล้ว)
            price = entry.get("price_avg") or entry.get("price_max") or entry.get("price_min")
            if price:
                temp_prov[prov] = float(price)
        
        # ใส่ลงใน provincial_data
        for prov, price in temp_prov.items():
            if prov not in provincial_data:
                provincial_data[prov] = {}
            provincial_data[prov][key] = price
        
        print(f"  Found data for {len(temp_prov)} provinces")

    if not provincial_data:
        print("No data retrieved. Check API status or Product IDs.")
        return

    # เขียนไฟล์ JS
    js_content = f"window.FERT_DATA = {json.dumps(provincial_data, ensure_ascii=False, indent=2)};"
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(js_content)
    
    print(f"Updated -> {OUTPUT_FILE} ({len(provincial_data)} provinces)")


if __name__ == "__main__":
    main()
