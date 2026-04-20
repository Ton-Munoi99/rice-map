#!/usr/bin/env python3
"""
extract_pdf_prices.py
----------------------
ดึงราคาข้าวรายจังหวัดจาก PDF ของสมาคมโรงสีข้าวไทย
แล้วเขียนลง data/prices-live.json

วิธีใช้:
  1) วาง PDF ใน data/prices/ เช่น data/prices/price_17042569.pdf
  2) push ขึ้น GitHub → Actions รัน script นี้อัตโนมัติ

รูปแบบชื่อไฟล์:  price_DDMMYYYY.pdf  (ปี ค.ศ. หรือ พ.ศ. ก็ได้)
"""

import os
import re
import json
import glob
from datetime import datetime, timezone

try:
    import pdfplumber
except ImportError:
    print("❌  pdfplumber ไม่ได้ติดตั้ง  →  pip install pdfplumber")
    raise

# ───────────────────────────────────────────
# Config
# ───────────────────────────────────────────
PDF_DIR    = "data/prices"
OUTPUT_FILE = "data/prices-live.json"

# Map ชื่อสินค้าใน PDF → key ใน JSON
RICE_TYPE_MAP = {
    "ข้าวเปลือกหอมมะลิ 105":   "jasmine",
    "ข้าวหอมมะลิ":              "jasmine",
    "หอมมะลิ":                  "jasmine",
    "ข้าวเปลือกเจ้า":           "white",
    "ข้าวเปลือกเจ้า ความชื้น": "white",
    "ข้าวเจ้า":                 "white",
}

# Map ชื่อจังหวัดย่อ/เต็ม → province_id ที่ใช้ใน rice-data.js
# (เพิ่มได้ตามจังหวัดที่ปรากฏใน PDF จริง)
PROVINCE_MAP = {
    "กรุงเทพมหานคร": "10", "กระบี่": "81", "กาญจนบุรี": "71",
    "กาฬสินธุ์": "46", "กำแพงเพชร": "62", "ขอนแก่น": "40",
    "จันทบุรี": "22", "ฉะเชิงเทรา": "24", "ชลบุรี": "20",
    "ชัยนาท": "18", "ชัยภูมิ": "36", "ชุมพร": "86",
    "เชียงราย": "57", "เชียงใหม่": "50", "ตรัง": "92",
    "ตราด": "23", "ตาก": "63", "นครนายก": "26",
    "นครปฐม": "73", "นครพนม": "48", "นครราชสีมา": "30",
    "นครศรีธรรมราช": "80", "นครสวรรค์": "60", "นนทบุรี": "12",
    "นราธิวาส": "96", "น่าน": "55", "บึงกาฬ": "38",
    "บุรีรัมย์": "31", "ปทุมธานี": "13", "ประจวบคีรีขันธ์": "77",
    "ปราจีนบุรี": "25", "ปัตตานี": "94", "พระนครศรีอยุธยา": "14",
    "พะเยา": "56", "พังงา": "82", "พัทลุง": "93",
    "พิจิตร": "66", "พิษณุโลก": "65", "เพชรบุรี": "76",
    "เพชรบูรณ์": "67", "แพร่": "54", "ภูเก็ต": "83",
    "มหาสารคาม": "44", "มุกดาหาร": "49", "แม่ฮ่องสอน": "58",
    "ยโสธร": "35", "ยะลา": "95", "ร้อยเอ็ด": "45",
    "ระนอง": "85", "ระยอง": "21", "ราชบุรี": "70",
    "ลพบุรี": "16", "ลำปาง": "52", "ลำพูน": "51",
    "เลย": "42", "ศรีสะเกษ": "33", "สกลนคร": "47",
    "สงขลา": "90", "สตูล": "91", "สมุทรปราการ": "11",
    "สมุทรสงคราม": "75", "สมุทรสาคร": "74", "สระแก้ว": "27",
    "สระบุรี": "19", "สิงห์บุรี": "17", "สุโขทัย": "64",
    "สุพรรณบุรี": "72", "สุราษฎร์ธานี": "84", "สุรินทร์": "32",
    "หนองคาย": "43", "หนองบัวลำภู": "39", "อ่างทอง": "15",
    "อำนาจเจริญ": "37", "อุดรธานี": "41", "อุตรดิตถ์": "53",
    "อุทัยธานี": "61", "อุบลราชธานี": "34",
}


# ───────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────
def parse_price(text: str):
    """แปลงข้อความราคาเป็น float (บาท/ตัน หรือ บาท/กก.)"""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(text))
    try:
        val = float(cleaned)
        # ถ้าราคา < 100 คาดว่าเป็น บาท/กก. → convert เป็น บาท/ตัน
        return round(val * 1000 if val < 100 else val, 2)
    except ValueError:
        return None


def find_province(text: str):
    """ค้นหาชื่อจังหวัดจากข้อความ"""
    for name, pid in PROVINCE_MAP.items():
        if name in str(text):
            return name, pid
    return None, None


def classify_rice(text: str):
    """จำแนกประเภทข้าวจากข้อความ"""
    for pattern, key in RICE_TYPE_MAP.items():
        if pattern in str(text):
            return key
    return "unknown"


def extract_date_from_filename(filename: str):
    """ดึงวันที่จากชื่อไฟล์ เช่น price_17042569.pdf"""
    m = re.search(r"(\d{2})(\d{2})(\d{4})", os.path.basename(filename))
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # ถ้าปี > 2500 = พ.ศ. → convert
        if year > 2500:
            year -= 543
        return f"{year:04d}-{month:02d}-{day:02d}"
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def extract_prices_from_pdf(pdf_path: str) -> dict:
    """
    อ่าน PDF แล้วดึงราคาข้าวรายจังหวัด
    คืน dict: { province_name: { "white": float, "jasmine": float } }
    """
    prices = {}
    date_str = extract_date_from_filename(pdf_path)

    print(f"\n📄  Processing: {os.path.basename(pdf_path)}  [{date_str}]")

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue

                # ระบุ header row
                header = [str(c).strip() if c else "" for c in table[0]]
                print(f"  Page {page_num} | cols: {header[:6]}")

                # หาตำแหน่งคอลัมน์
                province_col = next(
                    (i for i, h in enumerate(header)
                     if any(k in h for k in ["จังหวัด", "Province"])), None
                )
                price_cols = {
                    "white": next(
                        (i for i, h in enumerate(header)
                         if any(k in h for k in ["เจ้า", "ขาว", "White"])), None
                    ),
                    "jasmine": next(
                        (i for i, h in enumerate(header)
                         if any(k in h for k in ["หอมมะลิ", "Jasmine", "KDML"])), None
                    ),
                }

                for row in table[1:]:  # skip header
                    if not row or not any(row):
                        continue

                    # ดึงชื่อจังหวัด
                    if province_col is not None and province_col < len(row):
                        prov_text = str(row[province_col] or "")
                    else:
                        prov_text = " ".join(str(c or "") for c in row[:3])

                    prov_name, _ = find_province(prov_text)
                    if not prov_name:
                        continue

                    if prov_name not in prices:
                        prices[prov_name] = {"white": None, "jasmine": None, "date": date_str}

                    for rice_key, col_idx in price_cols.items():
                        if col_idx is not None and col_idx < len(row):
                            val = parse_price(row[col_idx])
                            if val:
                                prices[prov_name][rice_key] = val

    print(f"  → {len(prices)} จังหวัดที่พบราคา")
    return prices


# ───────────────────────────────────────────
# Main
# ───────────────────────────────────────────
def main():
    os.makedirs("data", exist_ok=True)

    # โหลด prices-live.json เดิม
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    # หา PDF ล่าสุดใน data/prices/
    pdf_files = sorted(glob.glob(f"{PDF_DIR}/*.pdf"))
    if not pdf_files:
        print(f"⚠️  ไม่พบ PDF ใน {PDF_DIR}/")
        return

    latest_pdf = pdf_files[-1]   # ใช้ไฟล์ล่าสุด (เรียงตามชื่อ)
    print(f"📂  ใช้ไฟล์: {latest_pdf}")

    # รวมราคาจากทุก PDF (ถ้ามีหลายไฟล์ ใช้ไฟล์ล่าสุดทับ)
    all_prices = {}
    for pdf_path in pdf_files:
        prices = extract_prices_from_pdf(pdf_path)
        all_prices.update(prices)

    # เขียนลง prices-live.json
    result = {
        **existing,
        "provincial_prices": {
            "source_th": "สมาคมโรงสีข้าวไทย",
            "source_en": "Thai Rice Millers Association",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "note_th": "ราคาข้าวเปลือกรายจังหวัด (บาท/ตัน)",
            "note_en": "Provincial paddy rice prices (THB/ton)",
            "data": all_prices
        }
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅  Saved → {OUTPUT_FILE}")
    print(f"    {len(all_prices)} จังหวัด")

    # สรุปตัวอย่าง
    for prov, vals in list(all_prices.items())[:5]:
        print(f"    {prov}: เจ้า={vals.get('white')} หอมมะลิ={vals.get('jasmine')}")


if __name__ == "__main__":
    main()
