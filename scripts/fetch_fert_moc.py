#!/usr/bin/env python3
import requests
import json
import os
import sys
from datetime import datetime, timedelta

# Force UTF-8 for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Fertilizer IDs from MOC Data API
FERT_CONFIG = {
    "urea_46_0_0":   {"id": "D14001", "name": "ปุ๋ยยูเรีย 46-0-0"},
    "form_16_20_0":  {"id": "D14002", "name": "ปุ๋ยสูตร 16-20-0"},
    "form_15_15_15": {"id": "D14003", "name": "ปุ๋ยสูตร 15-15-15"}
}

OUTPUT_FILE = "data/fert-data.js"

def fetch_national_data(product_id):
    today = datetime.now()
    # ดึงย้อนหลัง 15 วัน
    from_date = (today - timedelta(days=15)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")
    
    url = f"https://dataapi.moc.go.th/gis-product-prices?product_id={product_id}&from_date={from_date}&to_date={to_date}"
    
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        # สำหรับ GIS API ค่าเฉลี่ยรวมระดับประเทศจะอยู่ที่ root keys
        if isinstance(data, dict):
            p_min = data.get("price_min_avg")
            p_max = data.get("price_max_avg")
            
            # ถ้ามีค่าเฉลี่ยรายวันใน price_list ให้เอามาถัวเฉลี่ยถ่วงน้ำหนักหรือเอาค่าล่าสุด
            # ในที่นี้ใช้ price_min_avg และ price_max_avg ที่ API คำนวณมาให้เลย
            if p_min and p_max:
                avg = (float(p_min) + float(p_max)) / 2
                return {
                    "price_min": float(p_min),
                    "price_max": float(p_max),
                    "price_avg": round(avg, 2)
                }
            
            # Fallback: ถ้าไม่มี _avg ให้ดูใน price_list อันล่าสุด
            pl = data.get("price_list", [])
            if pl and isinstance(pl, list) and len(pl) > 0:
                latest = pl[-1]
                if isinstance(latest, dict):
                    l_min = latest.get("price_min")
                    l_max = latest.get("price_max")
                    if l_min and l_max:
                        return {
                            "price_min": float(l_min),
                            "price_max": float(l_max),
                            "price_avg": round((float(l_min) + float(l_max)) / 2, 2)
                        }
        return None
    except Exception as e:
        print(f"  Error fetching {product_id}: {e}")
        return None

def main():
    print("Fetching National Fertilizer Prices from MOC API...")
    os.makedirs("data", exist_ok=True)
    
    national_data = {}

    for key, info in FERT_CONFIG.items():
        print(f"Fetching {info['name']} ({info['id']})...")
        res = fetch_national_data(info["id"])
        if res:
            national_data[key] = res
            print(f"  ✅ Avg: {res['price_avg']} THB")
        else:
            print(f"  ⚠️ No data for {key}")

    if not national_data:
        print("❌ No data retrieved. Using historical reference as fallback.")
        # Fallback values if API fails
        national_data = {
            "urea_46_0_0": {"price_avg": 850, "note": "Historical Avg"},
            "form_16_20_0": {"price_avg": 820, "note": "Historical Avg"},
            "form_15_15_15": {"price_avg": 1050, "note": "Historical Avg"}
        }

    # Save to JS file
    # We empty out FERT_DATA to remove provincial mock data as requested
    output_js = (
        f"window.FERT_DATA = {{}}; // Removed provincial mock data\n"
        f"window.FERT_NATIONAL = {json.dumps(national_data, ensure_ascii=False, indent=2)};\n"
        f"window.FERT_UPDATED = '{datetime.now().strftime('%Y-%m-%d %H:%M')}';"
    )
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output_js)
    
    print(f"Updated -> {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
