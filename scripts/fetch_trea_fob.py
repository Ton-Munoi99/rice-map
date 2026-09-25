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
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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


DATE_RE = re.compile(r'\d{1,2}\s[A-Za-z]{3}\s\d{4}$')
REQUIRED_PRICES = ('jasmine_fob', 'white_fob')


def _latest_cell(tds, header_len, latest_idx):
    """ราคาในคอลัมน์วันที่ล่าสุด — None ถ้าช่องนั้นว่าง

    เดิมกรองช่องว่างทิ้งก่อนแล้วหยิบตัวสุดท้าย ถ้าสัปดาห์ล่าสุดยังว่าง จะได้ราคาสัปดาห์ก่อน
    มาติดวันที่ล่าสุด · ถ้าจำนวนช่องไม่ตรงกับ header (colspan ฯลฯ) จับคู่ตามตำแหน่งไม่ได้
    จึงถอยไปใช้วิธีเดิม
    """
    raw = [t.get_text(strip=True) for t in tds]
    if header_len and latest_idx is not None and len(raw) == header_len:
        cell = raw[latest_idx]
        return int(cell) if cell.isdigit() else None
    texts = [x for x in raw if x]
    print(f"[warn] แถว '{texts[0][:40] if texts else '?'}' มี {len(raw)} ช่อง ≠ header {header_len} — ใช้ค่าตัวท้ายสุด")
    return int(texts[-1]) if len(texts) > 1 and texts[-1].isdigit() else None


def parse_trea_table(html_str):
    """คืน (latest_date, prices) หรือ None ถ้าตารางไม่ครบ — ไม่ครบแล้วห้ามเขียนทับ"""
    soup = BeautifulSoup(html_str, 'html.parser')
    dates, prices = [], {}
    header_len, latest_idx = 0, None
    best_jasmine_year = -1   # ติดตามปีพืชผลล่าสุดของ jasmine

    for row in soup.find_all('tr'):
        tds = row.find_all('td')
        if not tds:
            continue
        texts = [t.get_text(strip=True) for t in tds if t.get_text(strip=True)]
        if not texts:
            continue

        # ─── Header row: texts[0] เท่ากับ 'Item' พอดี (ไม่ใช่ substring ของ cell ใหญ่)
        if texts[0] == 'Item' and not dates:
            header_len = len(tds)
            for i, t in enumerate(tds):
                clean = _normalize(t.get_text(strip=True))
                if DATE_RE.match(clean) and clean not in dates:
                    dates.append(clean)
                    latest_idx = i   # คอลัมน์วันที่ตัวท้ายสุด (ไม่ใช่ช่องท้ายสุดของแถว)
            continue

        # ─── Jasmine: Thai Hom Mali Rice - Premium (ปีพืชผลใหม่สุดที่มีราคาสัปดาห์ล่าสุด)
        if 'Thai Hom Mali Rice - Premium' in texts[0]:
            crop_yr = _crop_year(texts[0])
            price = _latest_cell(tds, header_len, latest_idx)
            if crop_yr > best_jasmine_year and price is not None:
                best_jasmine_year = crop_yr
                prices['jasmine_fob'] = price
            continue

        # ─── White Rice 5%
        if 'White Rice 5%' in texts[0]:
            price = _latest_cell(tds, header_len, latest_idx)
            if price is not None:
                prices['white_fob'] = price
            continue

    if not dates:
        print("[ERROR] ไม่พบ header row 'Item' — HTML structure อาจเปลี่ยน")
        return None

    missing = [k for k in REQUIRED_PRICES if k not in prices]
    if missing:
        # เขียนไปครึ่งเดียว = ราคาอีกตัวหายจากหน้าเว็บ · เก็บไฟล์เดิมที่วันที่กับราคาตรงกันไว้ดีกว่า
        print(f"[ERROR] ไม่พบราคา {missing} ในคอลัมน์ {dates[-1]} — ไม่เขียนทับ trea-fob.json")
        return None

    return dates[-1], prices   # คอลัมน์วันที่ท้ายสุด = วันที่ล่าสุดเสมอ


def _selftest():
    def table(header, *rows):
        tr = lambda cells: "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
        return "<table>" + tr(header) + "".join(tr(r) for r in rows) + "</table>"
    H = ["Item", "26 Aug 2026", "2 Sep 2026", "9 Sep 2026", "16 Sep 2026", "23 Sep 2026"]
    J = ["Thai Hom Mali Rice - Premium (2025/26)", 1180, 1180, 1185, 1190, 1190]
    W = ["White Rice 5%", 470, 472, 475, 478, 479]
    # ปกติ
    assert parse_trea_table(table(H, J, W)) == ("23 Sep 2026", {"jasmine_fob": 1190, "white_fob": 479})
    # สัปดาห์ล่าสุดของข้าวขาวยังว่าง → เดิมได้ 478 ติดวันที่ 23 ก.ย. · ตอนนี้ไม่เขียนทับ
    assert parse_trea_table(table(H, J, W[:-1] + [""])) is None
    # แถวปีพืชผลใหม่เพิ่งเริ่ม (สัปดาห์ต้นๆ ว่าง) แต่มีราคาล่าสุด → ใช้ปีใหม่
    J_new = ["Thai Hom Mali Rice - Premium (2026/27)", "", "", "", 1250, 1260]
    assert parse_trea_table(table(H, J, J_new, W))[1]["jasmine_fob"] == 1260
    # ปีใหม่ยังไม่มีราคาสัปดาห์ล่าสุด → ใช้ปีเก่าที่มีราคาสัปดาห์นี้
    J_new_blank = ["Thai Hom Mali Rice - Premium (2026/27)", "", "", "", 1250, ""]
    assert parse_trea_table(table(H, J, J_new_blank, W))[1]["jasmine_fob"] == 1190
    # header และแถวมีช่องเว้นท้าย → ยังต้องอ่านคอลัมน์วันที่ ไม่ใช่ช่องว่างท้ายแถว
    assert parse_trea_table(table(H + [""], J + [""], W + [""])) == ("23 Sep 2026", {"jasmine_fob": 1190, "white_fob": 479})
    # จำนวนช่องไม่ตรง header → ถอยไปวิธีเดิม (ตัวท้ายสุดที่ไม่ว่าง)
    assert parse_trea_table(table(H, J, ["White Rice 5%", 475, 479]))[1]["white_fob"] == 479
    # ไม่มี header
    assert parse_trea_table(table(["x"], J, W)) is None
    print("selftest ok")


def fetch_trea_fob():
    url = 'https://www.thairiceexporters.or.th/price.htm'
    # verify=False เพราะใบรับรองของเว็บ TREA ใช้ไม่ได้ — เดิมทำแบบเดียวกันผ่าน ssl context
    html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'},
                        timeout=20, verify=False).content

    try:
        html_str = html.decode('cp874', errors='ignore')
    except Exception:
        html_str = html.decode('utf-8', errors='ignore')

    parsed = parse_trea_table(html_str)
    if parsed is None:
        return
    latest_date, prices = parsed

    # ── อัตราแลกเปลี่ยน USD/THB จาก open.er-api.com (ฟรี ไม่ต้อง key)
    usd_thb = None
    try:
        fx = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        fx.raise_for_status()
        usd_thb = round(fx.json()["rates"]["THB"], 2)
        print(f"USD/THB: {usd_thb}")
    except Exception as e:
        print(f"[warn] ดึงอัตราแลกเปลี่ยนไม่ได้: {e}")

    output = {
        "date":    latest_date,
        "unit":    "USD/MT",
        "prices":  prices,
        "usd_thb": usd_thb,
        "source":  "Thai Rice Exporters Association (TREA)",
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
    if '--selftest' in sys.argv:
        _selftest()
    else:
        fetch_trea_fob()
