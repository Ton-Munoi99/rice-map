#!/usr/bin/env python3
"""
Refresh real (retail) fertilizer prices weekly → data/fertilizer-prices.json

The government provincial-commerce announcements are one-off dated news posts
(no stable feed), so they can't be auto-refreshed — they stay as static dated
reference rows below. The only reliably-refreshing sources are maintained
retail/co-op price lists at stable URLs; their price numbers are buried in
page-builder markup, so we fetch them through Firecrawl (clean markdown) rather
than raw HTML. Requires env FIRECRAWL_API_KEY (GitHub Actions secret). No-ops
cleanly if the key is unset, keeping the last committed JSON.

Run: python scripts/fetch_fertilizer_prices.py
"""
import io
import json
import os
import re
import sys
import urllib.request
from datetime import date

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = "data/fertilizer-prices.json"
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
TIMEOUT = 90

TH_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
             "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# แถวอ้างอิงจากประกาศพาณิชย์จังหวัด (ราชการ) — คงที่ ไม่รีเฟรชอัตโนมัติ (โพสต์ครั้งเดียว)
# แต่ละแถวโชว์ได้หลายสูตร (prices) จากแหล่งเดียวกัน — ไม่ใช่แค่ยูเรีย
STATIC_ROWS = [
    {"province": {"th": "อุทัยธานี", "en": "Uthai Thani"}, "date": {"th": "1 ก.ค. 2569", "en": "1 Jul 2026"},
     "prices": [
         {"formula": "46-0-0", "price": {"th": "1,245–1,250", "en": "1,245–1,250"}},
         {"formula": "30-0-0", "price": {"th": "940", "en": "940"}},
     ],
     "source": {"th": "พาณิชย์จังหวัด (ตรากระต่าย)", "en": "Provincial Commerce Office"},
     "url": "https://uthaithani.moc.go.th/th/content/category/detail/id/3536/iid/172901", "live": False},
    {"province": {"th": "ตรัง", "en": "Trang"}, "date": {"th": "11 มิ.ย. 2569", "en": "11 Jun 2026"},
     "prices": [
         {"formula": "18-46-0", "price": {"th": "1,600", "en": "1,600"}},
         {"formula": "0-0-60", "price": {"th": "880–940", "en": "880–940"}},
         {"formula": "21-0-0", "price": {"th": "700–780", "en": "700–780"}},
         {"formula": "15-15-15", "price": {"th": "1,050–1,320", "en": "1,050–1,320"}},
     ],
     "source": {"th": "พาณิชย์จังหวัด (46-0-0 หมดสต็อก)", "en": "Provincial Commerce Office (46-0-0 out of stock)"},
     "url": "https://trang.moc.go.th/th/content/category/detail/id/161/iid/169293", "live": False},
    {"province": {"th": "ขอนแก่น", "en": "Khon Kaen"}, "date": {"th": "10 มี.ค. 2569", "en": "10 Mar 2026"},
     "prices": [
         {"formula": "46-0-0", "price": {"th": "895–900", "en": "895–900"}},
         {"formula": "18-46-0", "price": {"th": "1,450", "en": "1,450"}},
         {"formula": "0-0-60", "price": {"th": "760–830", "en": "760–830"}},
         {"formula": "21-0-0", "price": {"th": "515–540", "en": "515–540"}},
         {"formula": "15-15-15", "price": {"th": "1,015–1,050", "en": "1,015–1,050"}},
         {"formula": "16-20-0", "price": {"th": "895–920", "en": "895–920"}},
     ],
     "source": {"th": "พาณิชย์จังหวัด", "en": "Provincial Commerce Office"},
     "url": "https://khonkaen.moc.go.th/th/content/category/detail/id/161/iid/152362", "live": False},
    {"province": {"th": "เชียงราย", "en": "Chiang Rai"}, "date": {"th": "สัปดาห์ที่ 4 มี.ค. 2569", "en": "Wk4 Mar 2026"},
     "prices": [
         {"formula": "46-0-0", "price": {"th": "870–1,150", "en": "870–1,150"}},
         {"formula": "16-20-0", "price": {"th": "900–1,070", "en": "900–1,070"}},
         {"formula": "15-15-15", "price": {"th": "990–1,200", "en": "990–1,200"}},
     ],
     "source": {"th": "พาณิชย์จังหวัด (อ.เมือง/อ.เทิง/อ.แม่จัน ตราหัววัวคันไถ)", "en": "Provincial Commerce Office (3 districts)"},
     "url": "https://chiangrai.moc.go.th/th/file/get/file/202606053f1ffaf61275e889e2cfad5af3cbbb99135539.pdf", "live": False},
    {"province": {"th": "สกลนคร", "en": "Sakon Nakhon"}, "date": {"th": "19 มี.ค. 2569", "en": "19 Mar 2026"},
     "prices": [
         {"formula": "46-0-0", "price": {"th": "850–1,150", "en": "850–1,150"}},
         {"formula": "0-0-60", "price": {"th": "850–900", "en": "850–900"}},
         {"formula": "21-0-0", "price": {"th": "590–630", "en": "590–630"}},
         {"formula": "15-15-15", "price": {"th": "1,020–1,070", "en": "1,020–1,070"}},
         {"formula": "16-8-8", "price": {"th": "795–850", "en": "795–850"}},
         {"formula": "29-5-18", "price": {"th": "1,120–1,250", "en": "1,120–1,250"}},
     ],
     "source": {"th": "พาณิชย์จังหวัด (lot ใหม่ขึ้นจาก 1,000)", "en": "Provincial Commerce Office (new lot up from 1,000)"},
     "url": "https://sakonnakhon.moc.go.th/th/content/category/detail/id/161/iid/154425", "live": False},
    {"province": {"th": "สิงห์บุรี", "en": "Sing Buri"}, "date": {"th": "30 เม.ย. 2569", "en": "30 Apr 2026"},
     "prices": [
         {"formula": "46-0-0", "price": {"th": "900", "en": "900"}},
         {"formula": "16-20-0", "price": {"th": "935–1,040", "en": "935–1,040"}},
         {"formula": "15-15-15", "price": {"th": "920–1,100", "en": "920–1,100"}},
     ],
     "source": {"th": "พาณิชย์จังหวัด (46-0-0 แบรนด์รอง/ตราสิงห์โต)", "en": "Provincial Commerce Office (46-0-0 secondary brand)"},
     "url": "https://singburi.moc.go.th/th/content/category/detail/id/3536/iid/157398", "live": False},
]

# แหล่ง "ตารางราคาสด" URL คงที่ ที่รีเฟรชได้จริง — ดึงผ่าน Firecrawl
# type "block": ตัดเฉพาะบล็อกแบรนด์แรก (block_start→block_end) แล้วจับทุกคู่ "สูตร X ราคา Y บาท" ในนั้น (หลายสูตร)
# type "single": จับสูตรเดียวด้วย regex ตรงๆ (ไม่มีบล็อกแบรนด์ให้ตัด)
LIVE_SOURCES = [
    {
        "province": {"th": "หนองคาย (ท่าบ่อ)", "en": "Nong Khai (Tha Bo)"},
        "source": {"th": "สหกรณ์การเกษตรท่าบ่อ (ตรากระต่าย)", "en": "Tha Bo Agri Co-op (Rabbit brand)"},
        "url": "https://www.coopthabo.com/thabo-2",
        "type": "block",
        "block_start": "ปุ๋ยตรากระต่าย",
        "block_end": r"!\[|ปุ๋ยตรา",  # ตัดที่รูปถัดไป หรือหัวข้อแบรนด์ถัดไป
        # ต้นทางบางบรรทัดมี ** (markdown bold) แทรกกลาง เช่น "สูตร****16 - 20 -0" — ยอมรับ * คั่นได้
        "formula_re": r"สูตร[\s*]*([\d\s\-]+?)\s*ราคา\s*([\d,]+|\*[^*]*\*)\s*บาท",
        "date_re": r"update\s*วันที่\s*(\d{1,2})\s*(" + "|".join(TH_MONTHS) + r")",
    },
    {
        "province": {"th": "ทั่วไป (แบรนด์ดัง)", "en": "General (major brands)"},
        "source": {"th": "svpolysack — ตรากระต่าย/หัววัว/ม้าบิน/มงกุฎ", "en": "svpolysack — major brands"},
        "url": "https://svpolysack.com/fertilizer-price/",
        "type": "single",
        "formula": "46-0-0",
        "price_re": r"46\s*0\s*0[^\n]*?([\d,]{4,5})\s*[-–]\s*([\d,]{4,5})\s*บาท",
        "date_re": None,  # บทความไม่มีวันที่ชัด → ใช้วันดึงข้อมูล
    },
]


def firecrawl_markdown(url):
    body = json.dumps({"url": url, "formats": ["markdown"], "onlyMainContent": True}).encode()
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape", data=body,
        headers={"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.load(r)
    if not data.get("success"):
        raise RuntimeError(f"firecrawl failed: {str(data)[:200]}")
    return data["data"]["markdown"]


def norm_formula(raw):
    """'46 - 0 - 0' / '46  0  0' → '46-0-0'"""
    parts = [p for p in re.split(r"[\s\-]+", raw.strip()) if p]
    return "-".join(parts)


def parse_prices_single(md, price_re):
    nums = []
    for m in re.findall(price_re, md):
        for part in (m if isinstance(m, tuple) else (m,)):
            n = int(part.replace(",", ""))
            if 500 <= n <= 3000:  # กันเลขขยะ (ราคาปุ๋ยจริงอยู่ในช่วงนี้)
                nums.append(n)
    return nums


def parse_prices_block(md, block_start, block_end, formula_re):
    """ตัดข้อความเฉพาะบล็อกแบรนด์แรก แล้วจับทุกคู่ (สูตร, ราคา) ในนั้น"""
    i = md.find(block_start)
    if i < 0:
        raise RuntimeError(f"block_start not found: {block_start!r}")
    rest = md[i + len(block_start):]
    m_end = re.search(block_end, rest)
    block = rest[: m_end.start()] if m_end else rest[:800]

    out = []
    for formula_raw, price_raw in re.findall(formula_re, block):
        formula = norm_formula(formula_raw)
        digits = re.sub(r"[^\d]", "", price_raw)
        if not digits:
            continue  # เช่น "*สินค้าหมด*" — ข้าม
        n = int(digits)
        if 500 <= n <= 3000:
            out.append((formula, n))
    return out


def parse_date(md, date_re):
    if not date_re:
        return None
    m = re.search(date_re, md)
    if not m:
        return None
    day, mon = m.group(1), m.group(2)
    en_mon = EN_MONTHS[TH_MONTHS.index(mon)]
    return {"th": f"{int(day)} {mon} 2569", "en": f"{int(day)} {en_mon} 2026"}


def fetch_live_row(src):
    md = firecrawl_markdown(src["url"])
    d = parse_date(md, src["date_re"]) or {"th": f"ดึงล่าสุด {date.today().isoformat()}", "en": f"as of {date.today().isoformat()}"}

    if src["type"] == "block":
        pairs = parse_prices_block(md, src["block_start"], src["block_end"], src["formula_re"])
        if not pairs:
            raise RuntimeError("no plausible price parsed")
        prices = [{"formula": f, "price": {"th": f"{n:,}", "en": f"{n:,}"}} for f, n in pairs]
    else:  # single
        nums = parse_prices_single(md, src["price_re"])
        if not nums:
            raise RuntimeError("no plausible price parsed")
        lo, hi = min(nums), max(nums)
        price_str = f"{lo:,}" if lo == hi else f"{lo:,}–{hi:,}"
        prices = [{"formula": src["formula"], "price": {"th": price_str, "en": price_str}}]

    return {"province": src["province"], "date": d, "prices": prices,
            "source": src["source"], "url": src["url"], "live": True}


def load_prev():
    if os.path.exists(OUT):
        try:
            return json.load(open(OUT, encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"rows": []}


def main():
    prev = load_prev()
    prev_live = {r["url"]: r for r in prev.get("rows", []) if r.get("live")}

    if not FIRECRAWL_KEY:
        print("[INFO] FIRECRAWL_API_KEY not set — keeping existing JSON (no refresh)", file=sys.stderr)
        if os.path.exists(OUT):
            sys.exit(0)
        # ไม่มีไฟล์เดิม → เขียน seed จาก static rows เท่านั้น เพื่อให้เว็บมีข้อมูล
        live_rows = []
    else:
        live_rows = []
        for src in LIVE_SOURCES:
            try:
                live_rows.append(fetch_live_row(src))
                got = ", ".join(f"{p['formula']}={p['price']['th']}" for p in live_rows[-1]["prices"])
                print(f"✓ {src['url']} → {got}")
            except Exception as e:
                print(f"[WARN] {src['url']}: {e} — keeping previous if any", file=sys.stderr)
                if src["url"] in prev_live:
                    live_rows.append(prev_live[src["url"]])

    rows = live_rows + STATIC_ROWS
    result = {
        "_meta": {
            "updated": date.today().isoformat(),
            "note": ("ราคาซื้อขายจริง — แถว live รีเฟรชทุกสัปดาห์จากตารางราคาสหกรณ์/ร้านค้า "
                     "ส่วนแถวราชการเป็นประกาศพาณิชย์จังหวัด (คงที่ ตามวันที่ระบุ) · "
                     "ตัวอย่างบางแหล่ง ไม่ใช่ค่าเฉลี่ยทั้งประเทศ"),
        },
        "rows": rows,
    }
    os.makedirs("data", exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Wrote {len(rows)} rows ({len(live_rows)} live) → {OUT}")


if __name__ == "__main__":
    main()
