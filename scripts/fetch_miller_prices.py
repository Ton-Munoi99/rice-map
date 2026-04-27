#!/usr/bin/env python3
"""
fetch_miller_prices.py
----------------------
ดาวน์โหลด PDF ราคาข้าวล่าสุดจากเว็บสมาคมโรงสีข้าวไทย
แล้วดึงราคาและบันทึกลง data/prices-live.json

URL Pattern:
  http://www.thairicemillers.org/images/introc_1429264173/PricericeDDMMYYYY.pdf
  (YYYY = ปี พ.ศ.)

PDF Structure (3 หน้า):
  Page 1: ราคาข้าวสาร กรุงเทพ (ไม่ใช้)
  Page 2: ข้าวเปลือกเจ้า รายจังหวัด  → white  (มี 2 คอลัมน์: 25% และ 15%)
  Page 3: ข้าวเปลือกหอมมะลิ รายจังหวัด → jasmine (ความชื้น 15%)

รัน: python scripts/fetch_miller_prices.py
"""

import os
import re
import json
import tempfile
from datetime import datetime, timedelta, timezone

import requests

try:
    import pdfplumber
except ImportError:
    print("pdfplumber ไม่ได้ติดตั้ง  ->  pip install pdfplumber")
    raise

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
BASE_URL       = "http://www.thairicemillers.org/images/introc_1429264173"
OUTPUT_FILE    = "data/prices-live.json"
LOOK_BACK_DAYS = 7

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "http://www.thairicemillers.org/",
}

# Map ชื่อจังหวัดภาษาไทย → ชื่อภาษาอังกฤษที่ใช้ใน rice-data.js
PROVINCE_MAP = {
    "กรุงเทพมหานคร": "Bangkok Metropolis",
    "กระบี่": "Krabi", "กาญจนบุรี": "Kanchanaburi",
    "กาฬสินธุ์": "Kalasin", "กำแพงเพชร": "Kamphaeng Phet",
    "ขอนแก่น": "Khon Kaen", "จันทบุรี": "Chanthaburi",
    "ฉะเชิงเทรา": "Chachoengsao", "ชลบุรี": "Chon Buri",
    "ชัยนาท": "Chai Nat", "ชัยภูมิ": "Chaiyaphum",
    "ชุมพร": "Chumphon", "เชียงราย": "Chiang Rai",
    "เชียงใหม่": "Chiang Mai", "ตรัง": "Trang",
    "ตราด": "Trat", "ตาก": "Tak",
    "นครนายก": "Nakhon Nayok", "นครปฐม": "Nakhon Pathom",
    "นครพนม": "Nakhon Phanom", "นครราชสีมา": "Nakhon Ratchasima",
    "นครศรีธรรมราช": "Nakhon Si Thammarat",
    "นครสวรรค์": "Nakhon Sawan", "นนทบุรี": "Nonthaburi",
    "นราธิวาส": "Narathiwat", "น่าน": "Nan",
    "บึงกาฬ": "Bueng Kan", "บุรีรัมย์": "Buri Ram",
    "ปทุมธานี": "Pathum Thani",
    "ประจวบคีรีขันธ์": "Prachuap Khiri Khan",
    "ปราจีนบุรี": "Prachin Buri", "ปัตตานี": "Pattani",
    "พระนครศรีอยุธยา": "Phra Nakhon Si Ayutthaya",
    "พะเยา": "Phayao", "พังงา": "Phangnga",
    "พัทลุง": "Phatthalung", "พิจิตร": "Phichit",
    "พิษณุโลก": "Phitsanulok", "เพชรบุรี": "Phetchaburi",
    "เพชรบูรณ์": "Phetchabun", "แพร่": "Phrae",
    "ภูเก็ต": "Phuket", "มหาสารคาม": "Maha Sarakham",
    "มุกดาหาร": "Mukdahan", "แม่ฮ่องสอน": "Mae Hong Son",
    "ยโสธร": "Yasothon", "ยะลา": "Yala",
    "ร้อยเอ็ด": "Roi Et", "ระนอง": "Ranong",
    "ระยอง": "Rayong", "ราชบุรี": "Ratchaburi",
    "ลพบุรี": "Lop Buri", "ลำปาง": "Lampang",
    "ลำพูน": "Lamphun", "เลย": "Loei",
    "ศรีสะเกษ": "Si Sa Ket", "สกลนคร": "Sakon Nakhon",
    "สงขลา": "Songkhla", "สตูล": "Satun",
    "สมุทรปราการ": "Samut Prakan",
    "สมุทรสงคราม": "Samut Songkhram",
    "สมุทรสาคร": "Samut Sakhon",
    "สระแก้ว": "Sa Kaeo", "สระบุรี": "Saraburi",
    "สิงห์บุรี": "Sing Buri", "สุโขทัย": "Sukhothai",
    "สุพรรณบุรี": "Suphan Buri", "สุราษฎร์ธานี": "Surat Thani",
    "สุรินทร์": "Surin", "หนองคาย": "Nong Khai",
    "หนองบัวลำภู": "Nong Bua Lam Phu",
    "อ่างทอง": "Ang Thong", "อำนาจเจริญ": "Amnat Charoen",
    "อุดรธานี": "Udon Thani", "อุตรดิตถ์": "Uttaradit",
    "อุทัยธานี": "Uthai Thani", "อุบลราชธานี": "Ubon Ratchathani",
}

# ชื่อย่อที่ PDF ใช้ → ชื่อเต็ม
ABBREV_MAP = {
    "กรุงเทพ": "กรุงเทพมหานคร",
    "อยุธยา":  "พระนครศรีอยุธยา",
}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def parse_price(text: str):
    """แปลงข้อความราคาเป็น float"""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(text))
    try:
        val = float(cleaned)
        return round(val * 1000 if val < 100 else val, 2)
    except ValueError:
        return None


def consonant_skeleton(text: str) -> str:
    """ดึงเฉพาะพยัญชนะไทย (U+0E01–U+0E2E) ทิ้งสระ/วรรณยุกต์/ช่องว่างทั้งหมด

    ใช้เพื่อจับชื่อจังหวัดเมื่อ PDF เพี้ยนลำดับสระ — เช่น
    "ฉะเชงิ เทรา" → "ฉชงทร" ตรงกับ skeleton ของ "ฉะเชิงเทรา" → "ฉชงทร"
    """
    return ''.join(c for c in str(text) if 'ก' <= c <= 'ฮ')


# Build skeleton lookup once: full names + abbreviations
PROVINCE_BY_SKELETON = {}
for _full in PROVINCE_MAP:
    _skel = consonant_skeleton(_full)
    if _skel:
        PROVINCE_BY_SKELETON[_skel] = _full
for _abbr, _full in ABBREV_MAP.items():
    _skel = consonant_skeleton(_abbr)
    if _skel:
        PROVINCE_BY_SKELETON[_skel] = _full


def find_province_th(text: str):
    """ค้นหาชื่อจังหวัดจากข้อความ — รองรับ:
    1. ชื่อเต็ม (substring match)
    2. ชื่อย่อใน PDF (ผ่าน ABBREV_MAP)
    3. PDF ที่สระเพี้ยน (consonant skeleton match)
    """
    text = str(text)
    for abbr, full in ABBREV_MAP.items():
        if abbr in text and full not in text:
            text = text.replace(abbr, full)
    for th_name in PROVINCE_MAP:
        if th_name in text:
            return th_name
    # Fallback: skeleton match for vowel-reorder PDF artifacts.
    # Prefer the LONGEST matching skeleton to avoid short-name false positives
    # (e.g. "แพร่"→"พร" matches inside "สุพรรณบุรี"→"สพรรณบร").
    line_skel = consonant_skeleton(text)
    if line_skel:
        best = None
        for prov_skel, full in PROVINCE_BY_SKELETON.items():
            if prov_skel and prov_skel in line_skel:
                if best is None or len(prov_skel) > len(best[0]):
                    best = (prov_skel, full)
        if best:
            return best[1]
    return None


def generate_candidate_urls(days_back: int = 7):
    """สร้าง URL ที่เป็นไปได้ย้อนหลัง days_back วัน"""
    candidates = []
    today = datetime.now(timezone.utc)
    for delta in range(days_back + 1):
        d = today - timedelta(days=delta)
        day      = d.strftime("%d")
        month    = d.strftime("%m")
        year_be  = str(d.year + 543)
        for prefix in ["Pricerice", "pricerice"]:
            fname = f"{prefix}{day}{month}{year_be}.pdf"
            candidates.append((d.strftime("%Y-%m-%d"), f"{BASE_URL}/{fname}"))
    return candidates


# ─────────────────────────────────────────────
# Download PDF
# ─────────────────────────────────────────────
def find_and_download_pdf():
    """ค้นหาและดาวน์โหลด PDF 3-หน้าล่าสุด (มีข้อมูลรายจังหวัด)

    สมาคมโรงสีออก PDF 2 แบบ:
      - 3 หน้า (จ/พ/ศ): ราคา กทม + ข้าวเปลือกเจ้า + หอมมะลิ รายจังหวัด
      - 1 หน้า (อ/พฤ): ราคา กทม. เท่านั้น — ใช้ไม่ได้

    → ข้าม PDF ที่เล็กกว่า ~1MB (แบบ 1-หน้า) แล้วย้อนหาวันก่อนหน้า
    """
    candidates = generate_candidate_urls(LOOK_BACK_DAYS)
    print(f"[search] {len(candidates)} URL candidates...")

    MIN_FULL_REPORT_BYTES = 1_000_000  # 3-page PDFs ~1.9MB, 1-page ~650KB

    for date_str, url in candidates:
        try:
            r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
            if r.status_code != 200:
                print(f"[miss]  {date_str}: HTTP {r.status_code}")
                continue
            r2 = requests.get(url, headers=HEADERS, timeout=30)
            r2.raise_for_status()
            size = len(r2.content)
            if size < MIN_FULL_REPORT_BYTES:
                print(f"[skip]  {date_str}: {size:,}b (1-page, no provincial data)")
                continue
            print(f"[found] {url}  [{date_str}] {size:,}b")
            return r2.content, date_str, url
        except requests.RequestException as e:
            print(f"[err]   {date_str}: {e}")

    print("[warn] ไม่พบ PDF 3-หน้าใน 7 วันที่ผ่านมา")
    return None, None, None


# ─────────────────────────────────────────────
# Extract prices from PDF
# ─────────────────────────────────────────────
# Page 3 section markers — stop processing jasmine when reaching these
JASMINE_STOP_MARKERS_SKEL = [
    consonant_skeleton("ข้าวเปลือกหอมปทุม"),     # Pathum
    consonant_skeleton("ข้าวเปลือกเหนียว"),      # Sticky / kor 6
    consonant_skeleton("ข้าวเปลือกเหนยี ว"),     # Sticky (vowel-reordered variant)
    consonant_skeleton("ข้าว กข"),                # GorKor varieties
    consonant_skeleton("ข้าวเปลอื กเหนียว"),     # variant
]


def _ensure_prov(prices: dict, th_name: str, date_str: str) -> dict:
    if th_name not in prices:
        prices[th_name] = {
            "white": None, "white_low": None, "white_high": None,
            "jasmine": None, "jasmine_low": None, "jasmine_high": None,
            "date": date_str,
        }
    return prices[th_name]


def _parse_range(lo_str: str, hi_str: str):
    """Parse a price range. Returns (low, high, avg) or (None, None, None) if out of range."""
    lo_v = parse_price(lo_str)
    hi_v = parse_price(hi_str)
    if lo_v and hi_v and 3000 <= lo_v <= 30000:
        return int(lo_v), int(hi_v), round((lo_v + hi_v) / 2)
    return None, None, None


def extract_prices_from_bytes(pdf_bytes: bytes, date_str: str) -> dict:
    """อ่าน PDF bytes แล้วดึงราคาข้าวรายจังหวัด (ความชื้น 15%)

    PDF format (3 หน้า):
      Page 1: ราคา กทม — ข้าม
      Page 2: ข้าวเปลือกเจ้า รายจังหวัด (white)  — มี 2 คอลัมน์: 25% และ 15%
      Page 3: ข้าวเปลือกหอมมะลิ + ปทุม + เหนียว + กข79 (เอาเฉพาะหอมมะลิ)

    Layout ของแต่ละแถว: บรรทัด 1 = ราคา, บรรทัด 2 = ชื่อจังหวัด
    (PDF รุ่นใหม่กลับด้านจาก format เดิม)
    """
    prices = {}
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    PAGE_TYPE = {2: "white", 3: "jasmine"}
    PRICE_RE = re.compile(r"([\d,]+)\s*-\s*([\d,]+)")

    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                rice_type = PAGE_TYPE.get(page_num)
                if rice_type is None:
                    continue

                text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                lines = [L.strip() for L in text.splitlines() if L.strip()]
                print(f"  Page {page_num} ({rice_type}): {len(lines)} lines")

                pending_ranges = None  # price line awaiting its province
                page_prov_count = 0

                for line in lines:
                    # On jasmine page, stop at next-section markers
                    if rice_type == "jasmine":
                        line_skel = consonant_skeleton(line)
                        if any(m and m in line_skel for m in JASMINE_STOP_MARKERS_SKEL):
                            break

                    th_name = find_province_th(line)
                    price_ranges = PRICE_RE.findall(line)

                    # Case A: line has BOTH price and province (legacy format)
                    if th_name and price_ranges:
                        prov_data = _ensure_prov(prices, th_name, date_str)
                        idx = 1 if len(price_ranges) >= 2 else 0
                        lo, hi, avg = _parse_range(*price_ranges[idx])
                        if avg is not None and prov_data[rice_type] is None:
                            prov_data[rice_type] = avg
                            prov_data[f"{rice_type}_low"] = lo
                            prov_data[f"{rice_type}_high"] = hi
                            page_prov_count += 1
                        pending_ranges = None
                        continue

                    # Case B: price-only line → save for next province line
                    if price_ranges:
                        pending_ranges = price_ranges
                        continue

                    # Case C: province-only line → pair with pending price
                    if th_name and pending_ranges:
                        prov_data = _ensure_prov(prices, th_name, date_str)
                        idx = 1 if len(pending_ranges) >= 2 else 0
                        lo, hi, avg = _parse_range(*pending_ranges[idx])
                        if avg is not None and prov_data[rice_type] is None:
                            prov_data[rice_type] = avg
                            prov_data[f"{rice_type}_low"] = lo
                            prov_data[f"{rice_type}_high"] = hi
                            page_prov_count += 1
                        pending_ranges = None
                        continue

                    # Province seen but no pending price (e.g. duplicate row from 2-col layout)
                    # OR neither — just skip

                print(f"    -> +{page_prov_count} provinces from page {page_num}")
    finally:
        os.unlink(tmp_path)

    print(f"  [done] {len(prices)} provinces found")
    return prices


# ─────────────────────────────────────────────
# Load existing JSON + duplicate check
# ─────────────────────────────────────────────
def load_existing():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def already_up_to_date(existing: dict, new_date: str) -> bool:
    prov = existing.get("provincial_prices", {})
    data = prov.get("data", {})
    if not data:
        return False
    sample = next(iter(data.values()), {})
    return sample.get("date", "") >= new_date


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    os.makedirs("data", exist_ok=True)

    pdf_bytes, date_str, source_url = find_and_download_pdf()
    if not pdf_bytes:
        print("[warn] ไม่พบข้อมูลใหม่ — ออกจาก script")
        return

    existing = load_existing()
    if already_up_to_date(existing, date_str):
        print(f"[info] ข้อมูลวันที่ {date_str} มีแล้ว — ไม่ต้อง update")
        return

    print(f"\n[extract] PDF วันที่ {date_str}...")
    prices = extract_prices_from_bytes(pdf_bytes, date_str)

    if not prices:
        print("[warn] ดึงราคาไม่ได้ — PDF format อาจเปลี่ยน")
        return

    result = {
        **existing,
        "provincial_prices": {
            "source_th":  "สมาคมโรงสีข้าวไทย",
            "source_en":  "Thai Rice Millers Association",
            "source_url": source_url,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "note_th":    "ราคาข้าวเปลือกรายจังหวัด ความชื้น 15% (บาท/ตัน)",
            "note_en":    "Provincial paddy rice prices at 15% moisture (THB/ton)",
            "moisture":   "15%",
            "data":       prices,
        }
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n[saved] {OUTPUT_FILE}")
    print(f"  {len(prices)} provinces | date: {date_str}")
    for prov, vals in list(prices.items())[:5]:
        print(f"  {prov}: white={vals.get('white')} jasmine={vals.get('jasmine')}")


if __name__ == "__main__":
    main()
