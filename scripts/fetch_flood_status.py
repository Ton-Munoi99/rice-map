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
HISTORY = "data/water-level-history.json"
OUTPUT = "data/flood-status.json"

# ── เกณฑ์ตัดสินสี (จากสถานีวัดจริงเท่านั้น) ────────────────────────────────
OVERBANK_LEVEL = 5      # ล้นตลิ่ง
HIGH_LEVEL = 4          # น้ำมาก (ยังไม่ล้น)
HIGH_MIN_COUNT = 3      # ต้องมีหลายจุด ไม่ใช่สถานีเดียวโดดๆ
HIGH_MIN_SHARE = 0.30   # และต้องเป็นสัดส่วนมีนัยของสถานีในจังหวัดนั้น

# ── น้ำขึ้นเร็วผิดปกติที่สถานีเดียว (เพิ่ม 8 ก.ย. 69) ──────────────────────
# เกณฑ์ "หลายจุด + สัดส่วน" ข้างบนออกแบบมาสำหรับน้ำท่วมทั้งลุ่มน้ำ และมองไม่เห็น
# เหตุการณ์แม่น้ำสายเดียว/อำเภอเดียวโดยโครงสร้าง — 7 ก.ย. 69 แม่น้ำสายที่ อ.แม่สาย
# ขึ้นจาก 48% เป็น 90.5% ของตลิ่ง (เหลือ 0.46 ม.) จนน้ำล้นแนวกำแพงเป็นข่าวหน้าหนึ่ง
# แต่เชียงรายมี 29 สถานี ติดระดับ 4 แค่ 1-2 จุด จึงตกทั้งสองเงื่อนไข ไม่ขึ้นสีเลย
#
# เทียบกับ "ยอดสูงสุดของช่วงก่อนหน้า" ไม่ใช่ค่าล่าสุด เพราะสถานีปากแม่น้ำ/ประตู
# ระบายน้ำแกว่งตามน้ำขึ้นน้ำลงทุกวัน (เช่น ปตร.คลองลัดบางยอ 10% → 94% ทุกวัน)
# ถ้าวัดจากค่าล่าสุดมันจะติดทุกวันไม่มีวันหยุด แต่พอเทียบกับยอดเดิมของตัวเอง
# มันขึ้นไม่เกินยอดเดิมจึงไม่ติด ส่วนแม่น้ำที่น้ำมาจริงจะทำยอดใหม่
#
# วัดกับข้อมูลจริง 10 วัน: เกณฑ์นี้เพิ่มเฉลี่ย 1.0 จังหวัด/วัน (เทียบกับกฎ
# "สถานีเดี่ยว ≥90%" ที่เพิ่ม 10.7 จังหวัด/วันและติดจังหวัดเดิมซ้ำทุกวัน)
# และจับแม่สาย 7 ก.ย. ได้ถูกต้อง โดยไม่มีสถานีน้ำขึ้นน้ำลงหลุดเข้ามาเลย
SURGE_MIN_PCT = 70      # ต้องใกล้ตลิ่งจริงตอนนี้
SURGE_MIN_JUMP = 20     # และสูงกว่ายอดเดิมของตัวเองในช่วง ~40 ชม. เท่านี้ (จุด %)
# หน้าต่างเทียบ "ยอดเดิม" — ต้องตรงกับที่ใช้ตอนวัดเกณฑ์ ไม่งั้นเกณฑ์ที่คาลิเบรตไว้
# จะเพี้ยน: หน้าต่างยาวขึ้น = ยอดเดิมสูงขึ้น = rise เล็กลง = จับไม่ได้
# (ตั้ง 16 ไว้ตอนแรกแล้วท่าโป่งแดง 7 ก.ย. หล่นจาก +1.06 เหลือ +0.93 ม. ไม่ติดเกณฑ์)
# ของจริง water-level.json ลงจริงราว 4.7 ครั้ง/วัน (ไม่ใช่ 8 ตาม cron ทุก 3 ชม.
# เพราะบางรอบไม่มี commit) → 8 ค่า ≈ 40 ชม. ซึ่งเป็นหน้าต่างที่วัดเกณฑ์ทั้งสองไว้
HISTORY_KEEP = 8

# ── สถานีที่ไม่มีค่าอ้างอิงตลิ่ง (เพิ่ม 9 ก.ย. 69) ─────────────────────────
# 43% ของสถานี ThaiWater ส่งมาแต่ระดับน้ำดิบ (msl) ไม่มี level/pct จึงเข้าเกณฑ์
# %ตลิ่งข้างบนไม่ได้เลยไม่ว่าน้ำจะสูงแค่ไหน — แม่ฮ่องสอนมี 8 สถานี 7 สถานีเป็นแบบนี้
# วันน้ำป่า 7 ก.ย. 69 จึงไม่ขึ้นสี ทั้งที่สถานี "ปางหมู" ซึ่งเป็นหมู่บ้านที่เป็นข่าว
# บันทึกไว้ครบ: 193.89 → 194.86 ม. ในราว 13 ชม. (ท่าโป่งแดงขึ้น 1.10 ม. พร้อมกัน)
#
# การเทียบสถานีกับ "ยอดเดิมของตัวเอง" ไม่ต้องใช้ค่าตลิ่ง จึงใช้กับสถานีกลุ่มนี้ได้
# วัดกับข้อมูลจริง 14 วัน: ≥0.5 ม. ได้ 5.6 จว./วัน · ≥0.75 ม. 2.7 · **≥1.0 ม. 1.7**
# · ≥1.5 ม. 0.6 แต่จับแม่ฮ่องสอนไม่ได้แล้ว — เลือก 1.0 ม. เป็นจุดที่ยังจับของจริงได้
# โดยไม่ท่วมแผนที่ (จังหวัดที่ติดบ่อยสุดติดแค่ 2-3 ครั้งใน 14 วัน = เหตุการณ์ฝนจริง)
#
# ⚠️ บอกได้แค่ "น้ำขึ้นเร็ว" ไม่ใช่ "ใกล้ล้นตลิ่ง" เพราะไม่รู้ว่าตลิ่งอยู่ตรงไหน
MSL_SURGE_MIN_RISE = 1.0   # เมตร เหนือยอดเดิมของตัวเองใน ~40 ชม.

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


def station_key(s):
    """คีย์ประจำสถานี — **ห้ามใช้ฟิลด์ id** ThaiWater เปลี่ยน id ทุกครั้งที่ดึง
    (มันคือ id ของค่าที่อ่าน ไม่ใช่ของสถานี) ไล่ตามสถานีข้ามเวลาด้วย id จะไม่เจอ
    อะไรเลยแบบเงียบๆ

    ต้องมีพิกัดด้วย ไม่ใช่แค่ชื่อ: มี 187 คีย์ที่ชื่อซ้ำกันในอำเภอเดียวกัน และหนึ่งใน
    นั้นอันตรายจริง — "พิษณุโลก|บางระกำ|บางระกำ" มี 5 record จาก 2 หน่วยงาน (ชป.
    กับ สสน.) คนละพิกัด ค่า %ตลิ่งคือ 63.78 / 62.98 / 10.57 ต่างกัน 53 จุด
    ถ้าคีย์เป็นชื่ออย่างเดียว ประวัติจะสลับไปมาระหว่างสองสถานีตามลำดับที่ API ส่งมา
    แล้วสร้าง "น้ำขึ้นเร็ว +53 จุด" ปลอมขึ้นมาเอง (พิษณุโลกโผล่ในผลทดสอบ 5 ครั้ง
    ก่อนแก้จุดนี้) · เติมพิกัดแล้วคีย์อันตรายเหลือ 0 และคีย์คงที่ข้าม snapshot 99.6%"""
    return (f"{s.get('province_th')}|{s.get('amphoe_th')}|{s.get('name_th')}"
            f"|{s.get('lat')}|{s.get('lon')}")


def keep_surge(surges, en, cand):
    """จังหวัดหนึ่งเก็บจุดที่ขึ้นแรงสุดจุดเดียว · เทียบข้ามหน่วยไม่ได้ (จุด% vs เมตร)
    จึงให้สถานีที่มีค่าตลิ่งชนะเสมอ เพราะบอกได้ว่าใกล้ล้นแค่ไหน ไม่ใช่แค่ขึ้นเร็ว"""
    if not en:
        return
    cur = surges.get(en)
    if cur is None:
        surges[en] = cand
        return
    if cur["kind"] != cand["kind"]:
        if cand["kind"] == "pct":
            surges[en] = cand
        return
    if cand["rise"] > cur["rise"]:
        surges[en] = cand


def surge_reason(surge):
    if surge["kind"] == "pct":
        return (f"น้ำขึ้นเร็วผิดปกติที่ {surge['name']} — "
                f"{surge['was']:.0f}% → {surge['now']:.0f}% ของตลิ่ง")
    # สถานีไม่มีค่าตลิ่ง บอกได้แค่ว่าขึ้นกี่เมตร ห้ามเขียนว่า "ใกล้ล้นตลิ่ง"
    return (f"น้ำขึ้นเร็วผิดปกติที่ {surge['name']} — สูงขึ้น {surge['rise']:.2f} ม. "
            f"ใน ~40 ชม. (สถานีนี้ไม่มีค่าอ้างอิงตลิ่ง บอกได้แค่ว่าขึ้นเร็ว)")


def station_severity(o, h, n, surge=None):
    """คืน (ระดับ, เหตุผล) — ตัดสินจากสถานีวัดจริงล้วน"""
    if o >= 1:
        return 2, f"มีสถานีล้นตลิ่ง {o} จุด"
    if h >= HIGH_MIN_COUNT and n and h / n >= HIGH_MIN_SHARE:
        return 1, f"สถานีน้ำมาก {h} จุด จาก {n} สถานี ({100 * h / n:.0f}%)"
    if surge:
        return 1, surge_reason(surge)
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

    # ประวัติย้อนหลัง ~40 ชม. — ใช้หา "ยอดเดิม" ของแต่ละสถานี (ทั้ง %ตลิ่ง และเมตร)
    # ไฟล์หายหรือพังไม่เป็นไร รอบนี้แค่ไม่มี surge แล้วสร้างใหม่
    try:
        _h = json.load(open(HISTORY, encoding="utf-8"))
        history = _h.get("stations") or {}
        history_msl = _h.get("stations_msl") or {}   # ไฟล์รุ่นเก่าไม่มีคีย์นี้ — เริ่มสะสมใหม่
    except Exception:
        history, history_msl = {}, {}
        print(f"[WARN] อ่าน {HISTORY} ไม่ได้ — รอบนี้ข้ามการตรวจน้ำขึ้นเร็ว", file=sys.stderr)

    surges, new_history, new_history_msl = {}, {}, {}
    for s in stations:
        k = station_key(s)
        en_s = PROVINCE_TH_EN.get(s.get("province_th"))
        pct, msl = s.get("pct"), s.get("msl")

        if pct is not None:
            # สถานีที่มีค่าอ้างอิงตลิ่ง — วัดเป็น %ตลิ่ง
            past = history.get(k) or []
            if pct >= SURGE_MIN_PCT and past and pct - max(past) >= SURGE_MIN_JUMP:
                keep_surge(surges, en_s, {
                    "name": s.get("name_th") or "", "amphoe": s.get("amphoe_th") or "",
                    "kind": "pct", "was": max(past), "now": pct,
                    "rise": round(pct - max(past), 1), "dt": s.get("dt") or "",
                })
            new_history[k] = (past + [round(pct, 1)])[-HISTORY_KEEP:]
        elif msl is not None:
            # สถานีที่ไม่มีค่าอ้างอิงตลิ่ง — วัดเป็นเมตรเหนือยอดเดิมของตัวเอง
            past = history_msl.get(k) or []
            if past and msl - max(past) >= MSL_SURGE_MIN_RISE:
                keep_surge(surges, en_s, {
                    "name": s.get("name_th") or "", "amphoe": s.get("amphoe_th") or "",
                    "kind": "msl", "was": max(past), "now": msl,
                    "rise": round(msl - max(past), 2), "dt": s.get("dt") or "",
                })
            new_history_msl[k] = (past + [round(msl, 2)])[-HISTORY_KEEP:]

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
        sev, why = station_severity(a["o"], a["h"], a["n"], surges.get(en))
        if sev:
            a["surge"] = surges.get(en)
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
            # จังหวัดที่ติดจากสถานีไม่มีค่าตลิ่ง ห้ามติดป้าย "ใกล้ล้นตลิ่ง" — เราไม่รู้ว่า
            # ตลิ่งอยู่ตรงไหน รู้แค่ว่าน้ำขึ้นเร็วผิดปกติ
            "severity_th": ("ท่วม" if sev == 2 else
                            "น้ำขึ้นเร็ว" if (a.get("surge") or {}).get("kind") == "msl" else
                            "ใกล้ล้นตลิ่ง"),
            "severity_en": ("Flooding" if sev == 2 else
                            "Rising fast" if (a.get("surge") or {}).get("kind") == "msl" else
                            "Near Overbank"),
            "reason_th": why,
            "stations_overbank": a["o"],
            "stations_high": a["h"],
            "stations_total": a["n"],
            "stations": a["worst"][:5],
            "surge": a.get("surge"),
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
                "surge": f"หรือมีสถานีเดียวที่ ≥{SURGE_MIN_PCT}% ของตลิ่ง และสูงกว่ายอดเดิมของตัวเองใน ~40 ชม. ≥{SURGE_MIN_JUMP} จุด",
                "surge_msl": f"หรือสถานีที่ไม่มีค่าอ้างอิงตลิ่ง มีระดับน้ำสูงกว่ายอดเดิมของตัวเองใน ~40 ชม. ≥{MSL_SURGE_MIN_RISE} ม.",
            },
            "provinces_surge": sum(1 for p in provinces.values() if p.get("surge")),
            "provinces_surge_msl": sum(1 for p in provinces.values()
                                       if (p.get("surge") or {}).get("kind") == "msl"),
            "stations_rated": sum(1 for s in stations if s.get("pct") is not None),
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
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump({"_meta": {"updated": bkk_today(), "keep": HISTORY_KEEP,
                             "note": "ประวัติรายสถานี ใช้หาน้ำขึ้นเร็วผิดปกติ · stations = %ตลิ่ง "
                                     "(สถานีที่มีค่าอ้างอิง) · stations_msl = ระดับน้ำดิบเป็นเมตร "
                                     "(สถานีที่ไม่มีค่าอ้างอิง) · คีย์คือ จังหวัด|อำเภอ|ชื่อสถานี "
                                     "ไม่ใช่ id (id เปลี่ยนทุกครั้งที่ดึง)"},
                   "stations": new_history, "stations_msl": new_history_msl}, f, ensure_ascii=False)

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

    surge = {"name": "สะพานมิตรภาพแม่น้ำสายแห่งที่ 1", "kind": "pct",
             "was": 60.4, "now": 90.5, "rise": 30.1}
    # แม่สาย 7 ก.ย. 69: เชียงรายมี 29 สถานี ติดระดับ 4 แค่ 1 จุด — เกณฑ์นับจุดตกหมด
    # แต่ต้องขึ้นสีเพราะสถานีเดียวนั้นทำยอดใหม่ 60% → 90.5% ของตลิ่ง
    assert station_severity(0, 1, 29)[0] == 0
    assert station_severity(0, 1, 29, surge)[0] == 1
    assert "น้ำขึ้นเร็ว" in station_severity(0, 1, 29, surge)[1]
    assert station_severity(1, 0, 29, surge)[0] == 2   # ล้นตลิ่งจริงยังชนะ surge
    st = {"province_th": "เชียงราย", "amphoe_th": "แม่สาย", "name_th": "ก",
          "lat": 20.1, "lon": 99.9, "id": 123}
    assert station_key(st) == "เชียงราย|แม่สาย|ก|20.1|99.9"        # ไม่ผูกกับ id
    assert station_key({**st, "id": 999}) == station_key(st)        # id เปลี่ยนไม่กระทบ
    # สถานีคนละพิกัดที่ชื่อซ้ำกันต้องแยกคีย์ ไม่งั้นประวัติสลับกันจนเกิด surge ปลอม
    assert station_key({**st, "lat": 20.2}) != station_key(st)
    assert SURGE_MIN_PCT >= 70 and SURGE_MIN_JUMP >= 20   # กันหย่อนเกณฑ์จนเตือนมั่ว

    # สถานีไม่มีค่าตลิ่ง (แม่ฮ่องสอน 7 ก.ย. 69) — บอกเป็นเมตร ห้ามอ้างว่าใกล้ล้นตลิ่ง
    msl_surge = {"name": "ปางหมู", "kind": "msl", "was": 193.89, "now": 194.86, "rise": 0.97}
    why = station_severity(0, 0, 8, msl_surge)[1]
    assert station_severity(0, 0, 8, msl_surge)[0] == 1
    assert "สูงขึ้น" in why and "ม." in why
    assert "ตลิ่ง" not in why.split("(")[0]      # ส่วนที่เป็นข้อสรุปห้ามพูดถึงตลิ่ง
    assert MSL_SURGE_MIN_RISE >= 1.0             # กันหย่อนจนสถานีแกว่งปกติติดหมด

    # เทียบข้ามหน่วยไม่ได้ — สถานีที่มีค่าตลิ่งต้องชนะเสมอ ไม่ว่าตัวเลข rise จะน้อยกว่า
    box = {}
    keep_surge(box, "X", {"kind": "msl", "rise": 9.9, "name": "a"})
    keep_surge(box, "X", {"kind": "pct", "rise": 20.0, "name": "b"})
    assert box["X"]["kind"] == "pct", box
    keep_surge(box, "X", {"kind": "msl", "rise": 99.0, "name": "c"})
    assert box["X"]["kind"] == "pct", box       # msl ห้ามแย่งคืน
    keep_surge(box, None, {"kind": "pct", "rise": 99.0, "name": "d"})   # จังหวัดไม่รู้จัก
    assert len(box) == 1
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
