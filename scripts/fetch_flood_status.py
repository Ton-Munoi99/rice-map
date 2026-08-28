#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_flood_status.py
สถานะน้ำท่วมรายจังหวัด → data/flood-status.json

**สีบนแผนที่มาจากสถานีวัดจริง ไม่ใช่จากข่าว** — ข่าวใช้เป็นบทสรุปประกอบเท่านั้น
เหตุผล: พาดหัวข่าวหลอกได้ เช่น 27 ส.ค. 69 ข่าว "ชัยภูมิ วิกฤตแล้ง" มีคำว่า
"น้ำท่วม" อยู่ในเนื้อหา (พูดถึงที่ลุ่มท่วมซ้ำซาก) ถ้าจับคำตรงๆ จะขึ้นสีว่า
ชัยภูมิท่วม ทั้งที่วิกฤตจริงคือแล้งและนาข้าวตายเพราะขาดน้ำนับแสนไร่

แทนที่ layer GISTDA เดิมที่ถอดออกไป — ภาพดาวเทียม GISTDA ไม่ระบุวันถ่ายภาพ
และค้างเป็นสัปดาห์ได้ ตรวจเมื่อ 28 ส.ค. 69 พบภาพเดิมค้างมา 3 วัน แสดง
13 จังหวัดที่ทับกับสถานีวัดจริงแค่ 2 และไม่มีน่านซึ่งเป็นข่าวใหญ่สุดของช่วงนั้น

แหล่งข้อมูล
  สี   : data/water-level.json (ThaiWater/สสน. 813 สถานี อัปเดตทุก 3 ชม.)
  ข่าว : Google News RSS (ฟรี ไม่ต้องมี key) — ใช้เล่าว่าเกิดอะไร ไม่ใช้ตัดสินสี

เกณฑ์ (วัดกับข้อมูลจริง 28 ส.ค. 69 ได้ 14/77 จังหวัด — ระดับ 1 ออกมาตรงกับ
รายชื่อที่ ปภ. เตือนเรื่องเจ้าพระยาวันก่อนหน้าพอดี: อยุธยา ลพบุรี สุพรรณบุรี
สมุทรปราการ กทม.)
  2 = ท่วม        — มีสถานีระดับ 5 (ล้นตลิ่ง) อย่างน้อย 1 จุด
  1 = ใกล้ล้นตลิ่ง — สถานีระดับ 4 (น้ำมาก) ≥3 จุด และ ≥30% ของสถานีในจังหวัด
  ไม่เข้าเกณฑ์     — ไม่ขึ้นสีเลย (ไม่ใช่ "ยืนยันว่าไม่ท่วม" ดู note ในไฟล์)

Run: python scripts/fetch_flood_status.py
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

from riceutils import PROVINCE_TH_EN, bkk_today

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WATER_LEVEL = "data/water-level.json"
OUTPUT = "data/flood-status.json"

# ── เกณฑ์ตัดสินสี (จากสถานีวัดจริงเท่านั้น) ────────────────────────────────
OVERBANK_LEVEL = 5      # ล้นตลิ่ง
HIGH_LEVEL = 4          # น้ำมาก (ยังไม่ล้น)
HIGH_MIN_COUNT = 3      # ต้องมีหลายจุด ไม่ใช่สถานีเดียวโดดๆ
HIGH_MIN_SHARE = 0.30   # และต้องเป็นสัดส่วนมีนัยของสถานีในจังหวัดนั้น

# ── ข่าว (บทสรุปเท่านั้น ไม่มีผลกับสี) ─────────────────────────────────────
# ถามแยกรายจังหวัด ไม่ใช่ query รวม: query รวม "น้ำท่วม" ดึงข่าวต่างประเทศ
# ท่วมกระแสมาเต็ม (28 ส.ค. 69 ได้ 93 ข่าว เป็นเนปาล/ทิเบตเกือบทั้งหมด
# มีจังหวัดไทยโผล่ในพาดหัวแค่จังหวัดเดียว) แล้วจับคู่จังหวัดไม่ได้เลย
NEWS_WITHIN = "3d"
NEWS_PER_PROVINCE = 3
TIMEOUT = 30
# Google แมตช์คำค้นกับ "เนื้อข่าว" ไม่ใช่พาดหัว — ข่าวกลิ่นเคมี/ยาเสพติด/
# อุบัติเหตุ ที่บังเอิญมีชื่อจังหวัดจึงหลุดเข้ามาได้ พาดหัวต้องมีคำเรื่องน้ำด้วย
NEWS_REQUIRE = [
    "น้ำท่วม", "อุทกภัย", "ล้นตลิ่ง", "น้ำป่า", "น้ำหลาก", "น้ำล้น",
    "ระดับน้ำ", "มวลน้ำ", "ระบายน้ำ", "น้ำเอ่อ", "จมน้ำ", "น้ำโขง",
]
# พาดหัวที่พูดถึงน้ำท่วมแต่ไม่ได้แปลว่าจังหวัดนั้นท่วมอยู่ตอนนี้
NEWS_EXCLUDE = [
    "รับมือ", "เตรียมพร้อม", "ซ้อมแผน", "ป้องกันน้ำท่วม",
    "หลังน้ำลด", "ฟื้นฟู", "เยียวยา", "ชดเชย", "ปีที่แล้ว", "เมื่อปี",
    "รำลึก", "ย้อนรอย", "บทเรียน",
    # ข่าวบริจาค/ช่วยเหลือ มักเป็นจังหวัดผู้ให้ ไม่ใช่จังหวัดที่ท่วม
    "บริจาค", "ธารน้ำใจ", "มอบถุงยังชีพ", "ตั้งศูนย์รับ",
]


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def strip_source_suffix(title, source):
    """Google News ต่อท้ายพาดหัวด้วย ' - ชื่อสำนักข่าว'"""
    if source and title.endswith(f" - {source}"):
        return title[: -len(source) - 3].strip()
    return title.strip()


def station_severity(o, h, n):
    """คืน (ระดับ, เหตุผล) — ตัดสินจากสถานีวัดจริงล้วน"""
    if o >= 1:
        return 2, f"มีสถานีล้นตลิ่ง {o} จุด"
    if h >= HIGH_MIN_COUNT and n and h / n >= HIGH_MIN_SHARE:
        return 1, f"สถานีน้ำมาก {h} จุด จาก {n} สถานี ({100 * h / n:.0f}%)"
    return 0, ""


def fetch_news(province_th):
    """ข่าวน้ำท่วมของจังหวัดหนึ่ง 3 วันล่าสุด — ล้มเหลวได้ ไม่ทำให้สีพัง"""
    q = f'"{province_th}" (น้ำท่วม OR อุทกภัย OR น้ำล้นตลิ่ง OR น้ำป่า) when:{NEWS_WITHIN}'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "th", "gl": "TH", "ceid": "TH:th"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RiceMap flood bot)"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=TIMEOUT).read())
    out, seen = [], set()
    for it in root.findall(".//item"):
        src_el = it.find("{*}source")
        source = (src_el.text if src_el is not None else "") or ""
        title = strip_source_suffix(it.findtext("title", "") or "", source)
        link = it.findtext("link", "") or ""
        if not title or not link:
            continue
        if any(bad in title for bad in NEWS_EXCLUDE):
            continue
        key = norm(title)
        if key in seen:
            continue
        # เอาเฉพาะพาดหัวที่เอ่ยชื่อจังหวัดจริง และเป็นเรื่องน้ำจริง
        if province_th not in title:
            continue
        if not any(w in title for w in NEWS_REQUIRE):
            continue
        seen.add(key)
        out.append({"title": title, "source": source, "url": link,
                    "date": (it.findtext("pubDate", "") or "")[:16]})
        if len(out) >= NEWS_PER_PROVINCE:
            break
    return out


def main():
    if not os.path.exists(WATER_LEVEL):
        print(f"[ERROR] ไม่พบ {WATER_LEVEL} — ต้องรัน fetch_water_level.py ก่อน", file=sys.stderr)
        sys.exit(1)
    wl = json.load(open(WATER_LEVEL, encoding="utf-8"))
    stations = wl.get("stations") or []
    if not stations:
        print("[ERROR] water-level.json ไม่มีสถานีเลย", file=sys.stderr)
        sys.exit(1)

    agg = defaultdict(lambda: {"o": 0, "h": 0, "n": 0, "th": "", "worst": []})
    for s in stations:
        # ใช้ชื่ออังกฤษจากตารางกลาง ไม่ใช่ province_en ของ API: API เรียก กทม. ว่า
        # "Bangkok" แต่แผนที่ใช้ "Bangkok Metropolis" จะไม่ขึ้นสี · และ ThaiWater
        # มีสถานีในเมียนมาปนมาด้วย ซึ่งไม่อยู่ในตารางจึงถูกตัดทิ้งไปพร้อมกัน
        th = s.get("province_th")
        en = PROVINCE_TH_EN.get(th)
        if not en:
            continue
        a = agg[en]
        a["n"] += 1
        a["th"] = th
        lv = s.get("level")
        if lv == OVERBANK_LEVEL:
            a["o"] += 1
        elif lv == HIGH_LEVEL:
            a["h"] += 1
        if lv in (HIGH_LEVEL, OVERBANK_LEVEL):
            a["worst"].append({
                "name": s.get("name_th") or s.get("name_en") or "",
                "amphoe": s.get("amphoe_th") or "",
                "river": s.get("river") or "",
                "level": lv,
                "pct": s.get("pct"),
                "dt": s.get("dt") or "",
            })

    flagged = {}
    for en, a in agg.items():
        sev, why = station_severity(a["o"], a["h"], a["n"])
        if sev:
            flagged[en] = (sev, why, a)

    # ถามข่าวเฉพาะจังหวัดที่ขึ้นสีแล้ว (ไม่กี่จังหวัด) ไม่ใช่ทั้ง 77
    news_total, news_err = 0, None
    for en, (_, _, a) in flagged.items():
        try:
            a["news"] = fetch_news(a["th"])
            news_total += len(a["news"])
        except Exception as e:
            a["news"] = []
            news_err = news_err or f"{type(e).__name__}: {e}"
    if news_err:
        print(f"[WARN] ดึงข่าวบางจังหวัดไม่สำเร็จ: {news_err} — สียังใช้ได้", file=sys.stderr)
    print(f"ข่าวน้ำท่วม 3 วันล่าสุด: {news_total} ข่าว จาก {len(flagged)} จังหวัด")

    provinces = {}
    for en, (sev, why, a) in flagged.items():
        # สถานีหนักสุดก่อน (ล้นตลิ่ง > น้ำมาก) แล้วค่อยเรียงตาม %
        a["worst"].sort(key=lambda w: (-(w["level"] or 0), -(w["pct"] or 0)))
        provinces[en] = {
            "province_th": a["th"],
            "severity": sev,
            "severity_th": "ท่วม" if sev == 2 else "ใกล้ล้นตลิ่ง",
            "reason_th": why,
            "stations_overbank": a["o"],
            "stations_high": a["h"],
            "stations_total": a["n"],
            "stations": a["worst"][:5],
            "news": a["news"],
        }

    provinces = dict(sorted(provinces.items(),
                            key=lambda kv: (-kv[1]["severity"],
                                            -kv[1]["stations_overbank"],
                                            -kv[1]["stations_high"])))
    n2 = sum(1 for p in provinces.values() if p["severity"] == 2)

    result = {
        "_meta": {
            "kind": "observed",
            "updated": bkk_today(),
            "source": "ThaiWater (สสน./HII) — ระดับน้ำรายสถานี",
            "source_url": "https://www.thaiwater.net/",
            "water_level_updated_at": (wl.get("_meta") or {}).get("updated_at"),
            "news_source": "Google News RSS",
            "news_count": news_total,
            "news_error": news_err,
            "provinces_flooded": n2,
            "provinces_flagged": len(provinces),
            "stations_total": len(stations),
            "thresholds": {
                "flood": "มีสถานีระดับ 5 (ล้นตลิ่ง) ≥1 จุด",
                "near": f"สถานีระดับ 4 (น้ำมาก) ≥{HIGH_MIN_COUNT} จุด และ ≥{HIGH_MIN_SHARE:.0%} ของสถานีในจังหวัด",
            },
            "note_th": (
                "**สีมาจากสถานีวัดระดับน้ำจริงของ สสน. เท่านั้น ข่าวเป็นบทสรุปประกอบ "
                "ไม่มีผลกับสี** (พาดหัวข่าวหลอกได้ เช่นข่าวเรื่องแล้งที่มีคำว่าน้ำท่วมอยู่ในเนื้อหา) · "
                "จังหวัดที่ไม่ขึ้นสี = ไม่มีสถานีเข้าเกณฑ์ **ไม่ใช่ยืนยันว่าไม่ท่วม** — "
                "น้ำท่วมขังนอกลำน้ำหรือพื้นที่ที่ไม่มีสถานีวัด ระบบนี้มองไม่เห็น"
            ),
            "note_en": (
                "Colour comes only from measured ThaiWater river-gauge levels; news is "
                "context and never drives the colour. Unflagged provinces mean no gauge met "
                "the threshold — not a confirmation that nowhere is flooded."
            ),
        },
        "provinces": provinces,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ ขึ้นสี {len(provinces)}/77 จังหวัด · ท่วมจริง {n2} → {OUTPUT}")
    for en, p in list(provinces.items())[:12]:
        tag = "🔴 ท่วม " if p["severity"] == 2 else "🟠 ใกล้ล้น"
        print(f"   {tag} {p['province_th']:16s} {p['reason_th']:38s} ข่าว {len(p['news'])}")


def _selftest():
    lv = lambda o, h, n: station_severity(o, h, n)[0]
    assert lv(1, 0, 20) == 2                 # ล้นตลิ่งแค่จุดเดียวก็คือท่วม
    assert lv(0, 3, 10) == 1                 # 3 จุด 30% พอดี = เข้าเกณฑ์
    assert lv(0, 3, 11) == 0                 # 27% ไม่ถึง แม้ครบ 3 จุด
    assert lv(0, 2, 2) == 0                  # 100% แต่แค่ 2 จุด ไม่พอ
    assert lv(0, 0, 0) == 0                  # ไม่มีสถานี ไม่หารศูนย์
    assert lv(2, 9, 14) == 2                 # ล้นตลิ่งชนะเสมอ
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
