#!/usr/bin/env python3
"""
fetch_trea_fob.py
-----------------
ดึงราคา FOB ข้าวส่งออกจาก TREA (สมาคมผู้ส่งออกข้าวไทย)
URL: https://www.thairiceexporters.or.th/price.htm

ตารางมี 5 คอลัมน์วันที่ คอลัมน์สุดท้าย (texts[-1]) = ราคาล่าสุดเสมอ
Header row: texts[0] == 'Item' (exact match)

Jasmine: ใช้แถว "Thai Hom Mali Rice - Premium" ที่มีปีพืชผลใหม่ที่สุด
         (ตรวจจาก (YYYY/YY) หรือ (YY/YY) ในชื่อแถว — ไม่ hardcode ปี)
White:   ใช้แถว "White Rice 5%"
"""

import json
import os
import re
import ssl
import sys
import io
import urllib.request

from bs4 import BeautifulSoup

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _normalize(s: str) -> str:
    """ลด whitespace ซ้ำให้เหลือ 1 ช่อง"""
    return re.sub(r'\s+', ' ', s).strip()


def _crop_year(row_text: str) -> int:
    """
    ดึงปีพืชผลจากชื่อแถว เช่น
      "Thai Hom Mali ... (2025/26)" → 2025
      "Thai Hom Mali ... (68/69)"   → 68   (ปี พ.ศ. สั้น)
    คืนค่า 0 ถ้าหาไม่เจอ
    """
    m = re.search(r'\((\d{2,4})/\d{2}\)', row_text)
    return int(m.group(1)) if m else 0


def fetch_trea_fob():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = 'https://www.thairiceexporters.or.th/price.htm'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, context=ctx, timeout=20).read()

    try:
        html_str = html.decode('cp874', errors='ignore')
    except Exception:
        html_str = html.decode('utf-8', errors='ignore')

    soup = BeautifulSoup(html_str, 'html.parser')
    rows = soup.find_all('tr')

    dates = []
    prices = {}
    best_jasmine_year = -1   # ติดตามปีพืชผลล่าสุดของ jasmine

    for row in rows:
        tds = row.find_all('td')
        if not tds:
            continue
        texts = [t.get_text(strip=True) for t in tds if t.get_text(strip=True)]
        if not texts:
            continue

        # ─── Header row: texts[0] เท่ากับ 'Item' พอดี (ไม่ใช่ substring ของ cell ใหญ่)
        if texts[0] == 'Item' and not dates:
            for t in texts[1:]:   # ข้าม 'Item' เอง
                clean = _normalize(t)
                if re.match(r'\d{1,2}\s[A-Za-z]{3}\s\d{4}$', clean) and clean not in dates:
                    dates.append(clean)
            continue

        # ─── Jasmine: Thai Hom Mali Rice - Premium (ปีพืชผลใหม่สุด)
        if 'Thai Hom Mali Rice - Premium' in texts[0]:
            crop_yr = _crop_year(texts[0])
            if crop_yr > best_jasmine_year and len(texts) > 1 and texts[-1].isdigit():
                best_jasmine_year = crop_yr
                prices['jasmine_fob'] = int(texts[-1])
            continue

        # ─── White Rice 5%
        if 'White Rice 5%' in texts[0]:
            if len(texts) > 1 and texts[-1].isdigit():
                prices['white_fob'] = int(texts[-1])
            continue

    if not dates:
        print("[ERROR] ไม่พบ header row 'Item' — HTML structure อาจเปลี่ยน")
        return

    latest_date = dates[-1]   # คอลัมน์สุดท้าย = วันที่ล่าสุดเสมอ

    if not prices:
        print("[ERROR] ไม่พบราคา — ตรวจสอบชื่อแถวในตาราง TREA")
        return

    output = {
        "date":   latest_date,
        "unit":   "USD/MT",
        "prices": prices,
        "source": "Thai Rice Exporters Association (TREA)",
    }

    print("Extracted FOB Prices:")
    print(json.dumps(output, indent=2, ensure_ascii=False))

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'trea-fob.json')

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved → {out_path}")


if __name__ == '__main__':
    fetch_trea_fob()
