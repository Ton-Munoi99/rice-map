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
STATIC_ROWS = [
    {"province": {"th": "อุทัยธานี", "en": "Uthai Thani"}, "date": {"th": "1 ก.ค. 2569", "en": "1 Jul 2026"},
     "formula": "46-0-0", "price": {"th": "1,245–1,250", "en": "1,245–1,250"},
     "source": {"th": "พาณิชย์จังหวัด (ตรากระต่าย)", "en": "Provincial Commerce Office"},
     "url": "https://uthaithani.moc.go.th/th/content/category/detail/id/3536/iid/172901", "live": False},
    {"province": {"th": "ตรัง", "en": "Trang"}, "date": {"th": "11 มิ.ย. 2569", "en": "11 Jun 2026"},
     "formula": "18-46-0", "price": {"th": "1,600", "en": "1,600"},
     "source": {"th": "พาณิชย์จังหวัด (46-0-0 หมดสต็อก)", "en": "Provincial Commerce Office"},
     "url": "https://trang.moc.go.th/th/content/category/detail/id/161/iid/169293", "live": False},
    {"province": {"th": "ขอนแก่น", "en": "Khon Kaen"}, "date": {"th": "10 มี.ค. 2569", "en": "10 Mar 2026"},
     "formula": "46-0-0", "price": {"th": "895–900", "en": "895–900"},
     "source": {"th": "พาณิชย์จังหวัด", "en": "Provincial Commerce Office"},
     "url": "https://khonkaen.moc.go.th/th/content/category/detail/id/161/iid/152362", "live": False},
    {"province": {"th": "เชียงราย", "en": "Chiang Rai"}, "date": {"th": "สัปดาห์ที่ 4 มี.ค. 2569", "en": "Wk4 Mar 2026"},
     "formula": "46-0-0", "price": {"th": "870–1,150", "en": "870–1,150"},
     "source": {"th": "พาณิชย์จังหวัด (อ.เมือง/อ.เทิง/อ.แม่จัน ตราหัววัวคันไถ)", "en": "Provincial Commerce Office (3 districts)"},
     "url": "https://chiangrai.moc.go.th/th/file/get/file/202606053f1ffaf61275e889e2cfad5af3cbbb99135539.pdf", "live": False},
]

# แหล่ง "ตารางราคาสด" URL คงที่ ที่รีเฟรชได้จริง — ดึงผ่าน Firecrawl
LIVE_SOURCES = [
    {
        "province": {"th": "หนองคาย (ท่าบ่อ)", "en": "Nong Khai (Tha Bo)"},
        "source": {"th": "สหกรณ์การเกษตรท่าบ่อ (หลายแบรนด์)", "en": "Tha Bo Agri Co-op (multi-brand)"},
        "url": "https://www.coopthabo.com/thabo-2",
        "formula": "46-0-0",
        # ราคา: จับ "สูตร 46 - 0 - 0 ราคา <n> บาท" ทุกแบรนด์ → ช่วง min–max
        "price_re": r"46\s*-\s*0\s*-\s*0\s*ราคา\s*([\d,]+)\s*บาท",
        "date_re": r"update\s*วันที่\s*(\d{1,2})\s*(" + "|".join(TH_MONTHS) + r")",
    },
    {
        "province": {"th": "ทั่วไป (แบรนด์ดัง)", "en": "General (major brands)"},
        "source": {"th": "svpolysack — ตรากระต่าย/หัววัว/ม้าบิน/มงกุฎ", "en": "svpolysack — major brands"},
        "url": "https://svpolysack.com/fertilizer-price/",
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


def parse_prices(md, price_re):
    nums = []
    for m in re.findall(price_re, md):
        for part in (m if isinstance(m, tuple) else (m,)):
            n = int(part.replace(",", ""))
            if 500 <= n <= 3000:  # กันเลขขยะ (ราคาปุ๋ยจริงอยู่ในช่วงนี้)
                nums.append(n)
    return nums


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
    nums = parse_prices(md, src["price_re"])
    if not nums:
        raise RuntimeError("no plausible price parsed")
    lo, hi = min(nums), max(nums)
    price_str = f"{lo:,}" if lo == hi else f"{lo:,}–{hi:,}"
    d = parse_date(md, src["date_re"]) or {"th": f"ดึงล่าสุด {date.today().isoformat()}", "en": f"as of {date.today().isoformat()}"}
    return {"province": src["province"], "date": d, "formula": src["formula"],
            "price": {"th": price_str, "en": price_str}, "source": src["source"], "url": src["url"], "live": True}


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
                print(f"✓ {src['url']} → {live_rows[-1]['price']['th']}")
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
