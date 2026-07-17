#!/usr/bin/env python3
"""
Fetch recent Thai rice-related news from Google News RSS (free, no API key).
Runs via GitHub Actions (see update-rice-news.yml).

Google News RSS aggregates many Thai outlets and supports Thai keyword search
plus a `when:Nd` recency operator. We query rice-economy / rice-farming terms,
then post-filter to drop off-topic hits (wheat/corn/foreign-market/food-dish),
dedupe by normalized title, and keep the newest N.

Output: data/rice-news.json
  { _meta: {source, updated, query, count}, items: [{title, source, date, url}] }
Headlines only (facts) + source attribution + link — no article text scraped.
"""
import sys, io, os, re, json, html, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUTPUT   = "data/rice-news.json"
ARCHIVE  = "data/rice-news-archive.json"   # คลังข่าวสะสม ดูย้อนหลังได้ ไม่ลบของเก่า
MAX_ITEMS = 8            # เก็บข่าวใหม่สุดกี่ข่าว (ไฟล์แสดงผล)
WITHIN    = "14d"        # ช่วงเวลาข่าว (Google News when: operator)
TIMEOUT   = 30

# คำค้น (ต้องมีคำใดคำหนึ่ง) — เน้นเศรษฐกิจ/การเกษตรข้าวของไทย
QUERY = (
    'ราคาข้าว OR ส่งออกข้าว OR ข้าวเปลือก OR ข้าวนาปรัง OR ข้าวนาปี '
    'OR ข้าวหอมมะลิ OR ชาวนา OR "นโยบายข้าว" OR "ประกันราคาข้าว"'
)

# ต้องมีคำใดคำหนึ่งใน title จึงถือว่าเกี่ยวข้าวไทยจริง
MUST_INCLUDE = ["ข้าว", "ชาวนา", "นาปรัง", "นาปี"]

# ตัดทิ้งถ้า title มีคำเหล่านี้ — "ชาวนา/ข้าว" กว้างไป เจอในหวย/เพลง/นิทาน/ชาวนาเกลือ-กุ้ง
EXCLUDE = [
    "ข้าวสาลี", "ข้าวโพด", "ข้าวบาร์เลย์", "ข้าวฟ่าง",   # พืชอื่น
    "ข้าวมันไก่", "ข้าวผัด", "ข้าวหมู", "ข้าวแกง", "ข้าวกล่อง", "ข้าวเหนียวมะม่วง",  # อาหารจานเดียว
    "ข้าวหมาก", "ข้าวต้มมัด", "ข้าวยำ", "ก๋วยเตี๋ยว", "เฝอ",
    "เลขท้าย", "เลขเด็ด", "หวย", "ลอตเตอรี่", "เลขดัง", "ถูกรางวัล",   # หวย/ลอตเตอรี่
    "เพลง", "คอนเสิร์ต", "ไวรัล", "True AF", "TrueAF", "Super Band",  # บันเทิง/ไวรัล
    "ซูเปอร์แบนด์", "ละคร", "นิทาน", "อินฟลู", "งูเหลือม",
    "ชาวนาเกลือ", "นาเกลือ", "ชาวนากุ้ง", "นากุ้ง", "ราคากุ้ง",       # ชาวนาที่ไม่ใช่ข้าว
]

# ตัดทิ้งทั้งแหล่ง — สำนักต่างชาติที่แปลไทยอัตโนมัติ (ข่าวข้าวเวียดนาม/ต่างประเทศล้วน ไม่ใช่ข่าวข้าวไทย)
SOURCE_EXCLUDE = ["Vietnam.vn", "vietnam.vn", "Investing.com", "nhk.or.jp"]


def strip_source_suffix(title, source):
    """Google News ต่อ ' - <source>' ท้าย title — ตัดออกให้สะอาด"""
    title = html.unescape(title).strip()
    if source and title.endswith(f"- {source}"):
        title = title[: -len(f"- {source}")].strip()
    return title


def norm(title):
    """normalize สำหรับ dedupe — ตัดช่องว่าง/เครื่องหมาย เทียบ 40 ตัวแรก"""
    return re.sub(r"[\s\W]+", "", title)[:40]


def archive_news(relevant):
    """สะสมข่าวที่ผ่าน filter ลง ARCHIVE (ไม่ลบของเก่า) — dedupe ด้วย title ที่ normalize แล้ว
    เขียนไฟล์เฉพาะเมื่อมีข่าวใหม่จริง (กัน commit เปล่า)"""
    prev = []
    if os.path.exists(ARCHIVE):
        try:
            prev = json.load(open(ARCHIVE, encoding="utf-8")).get("items", [])
        except (ValueError, OSError):
            prev = []

    seen = {norm(x["title"]) for x in prev}
    added = 0
    for it in relevant:
        k = norm(it["title"])
        if k in seen:
            continue
        seen.add(k)
        prev.append({**it, "archived": date.today().isoformat()})
        added += 1

    if not added:
        print(f"Archive: no new items ({len(prev)} total)")
        return

    prev.sort(key=lambda x: (x.get("date", ""), x.get("archived", "")), reverse=True)
    with open(ARCHIVE, "w", encoding="utf-8") as f:
        json.dump(
            {"_meta": {"source": "Google News RSS", "updated": date.today().isoformat(),
                       "count": len(prev), "note": "คลังข่าวข้าวไทยสะสม (ดูย้อนหลัง) · หัวข้อ + ลิงก์ต้นฉบับ"},
             "items": prev},
            f, ensure_ascii=False, indent=2)
    print(f"Archive: +{added} new → {len(prev)} total in {ARCHIVE}")


def fetch_items():
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{QUERY} when:{WITHIN}", "hl": "th", "gl": "TH", "ceid": "TH:th"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RiceMap news bot)"})
    raw = urllib.request.urlopen(req, timeout=TIMEOUT).read()
    root = ET.fromstring(raw)
    return root.findall(".//item")


def main():
    try:
        items = fetch_items()
    except Exception as e:
        print(f"[ERROR] Google News RSS fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(items)} raw items")
    seen, out = set(), []
    for it in items:
        raw_title = it.findtext("title", "") or ""
        src_el = it.find("{*}source")
        source = (src_el.text if src_el is not None else "") or ""
        title = strip_source_suffix(raw_title, source)
        link = it.findtext("link", "") or ""
        pub = it.findtext("pubDate", "") or ""

        if not title or not link:
            continue
        # relevance filter
        if source in SOURCE_EXCLUDE:
            continue
        if not any(k in title for k in MUST_INCLUDE):
            continue
        if any(bad in title for bad in EXCLUDE):
            continue
        key = norm(title)
        if key in seen:
            continue
        seen.add(key)

        # parse date → ISO (YYYY-MM-DD)
        iso = ""
        try:
            iso = parsedate_to_datetime(pub).astimezone(timezone.utc).date().isoformat()
        except Exception:
            iso = date.today().isoformat()

        out.append({
            "title": title,
            "source": source,
            "date": iso,
            "url": link,
        })

    # newest first
    out.sort(key=lambda x: x["date"], reverse=True)

    if not out:
        print("[WARN] no relevant items after filtering — keeping previous file if present", file=sys.stderr)
        if os.path.exists(OUTPUT):
            sys.exit(0)   # อย่าเขียนทับด้วยไฟล์ว่าง
        sys.exit(1)

    archive_news(out)          # สะสมข่าวทั้งหมดที่ผ่าน filter (ก่อนตัดเหลือ N)
    out = out[:MAX_ITEMS]      # ไฟล์แสดงผลเก็บแค่ N ข่าวล่าสุด

    result = {
        "_meta": {
            "source":  "Google News RSS",
            "updated": date.today().isoformat(),
            "query":   QUERY,
            "within":  WITHIN,
            "count":   len(out),
            "note":    "ข่าวข้าวไทยล่าสุด รวบรวมจาก Google News RSS · หัวข้อข่าว + ลิงก์ไปต้นฉบับ",
        },
        "items": out,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved {len(out)} news items → {OUTPUT}")
    for x in out:
        print(f"  [{x['date']}] ({x['source']}) {x['title'][:60]}")


if __name__ == "__main__":
    main()
