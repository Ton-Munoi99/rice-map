#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fetch_gistda_flood.py
พื้นที่น้ำท่วมจากภาพดาวเทียม (GISTDA) รายจังหวัด/อำเภอ → data/gistda-flood.json

ต่างจาก layer เตือนภัยที่มีอยู่ตรงที่นี่คือ **น้ำที่ท่วมอยู่จริง** ที่ดาวเทียมเห็น
ไม่ใช่การคาดการณ์จากฝน — เติมช่องว่างที่วัดได้: 25 ส.ค. 69 GISTDA เห็นน้ำท่วม
13 จังหวัด เตือนภัยเราจับได้ 12 แต่**พลาดนครราชสีมา** (ท่วมหนักสุด 62 ตำบล
46,178 ไร่) เพราะเราตัดสินจากฝนที่จะตก ส่วนโคราชท่วมจากน้ำที่มาแล้ว

Source: GISTDA flood-innotech WFS (เปิดสาธารณะ ไม่ต้องมี key)
Output: data/gistda-flood.json

ข้อจำกัดสำคัญ 2 ข้อของต้นทาง (ตรวจสอบเองแล้ว 25 ส.ค. 69):

1. **feature ไม่มีวันที่ติดมาเลย** — GetCapabilities ไม่มี Abstract, ไม่มีฟิลด์เวลา
   ในทุก property จึงบอกไม่ได้ว่าดาวเทียมถ่ายเมื่อไหร่ ทำได้แค่บอกว่า "เราดึงมา
   เมื่อไหร่" กับ "ฉากนี้เห็นครั้งแรกเมื่อไหร่" (ลายนิ้วมือฉาก = hash ของชุด
   ตำบล+พื้นที่) — ห้ามเขียนว่า "น้ำท่วมวันนี้" เด็ดขาด
2. **ข้อความไทยเป็น cp874 ที่ถูกติดป้ายผิดเป็น UTF-8** มาถึงเป็น mojibake แบบ
   latin-1 ("µ.à·¾ÒÅÑÂ" = "ต.เทพาลัย") ต้องถอดกลับก่อนใช้

หน่วย: `flood_area` เป็น**ไร่** ยืนยันจาก `F_AREA` (ตร.ม.) ÷ 1600 = flood_area

Run: python scripts/fetch_gistda_flood.py
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

from riceutils import PROVINCE_TH_EN

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WFS_URL = (
    "https://flood-innotech.gistda.or.th/flooding_vis_public"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=flooding_vis:FloodArea_Poly&outputFormat=application/json"
)
OUTPUT = "data/gistda-flood.json"
TIMEOUT = 120          # ตอบ ~23 MB ให้เวลาเยอะหน่อย
SQM_PER_RAI = 1600


def _cp874_byte_to_char(b):
    """cp874 (TIS-620 superset) หนึ่งไบต์ → อักขระ Unicode (บล็อกไทยเรียงต่อกัน)"""
    if b < 0x80:
        return chr(b)
    if 0xA1 <= b <= 0xDA:
        return chr(0x0E01 + (b - 0xA1))
    if 0xDF <= b <= 0xFB:
        return chr(0x0E3F + (b - 0xDF))
    if b == 0xA0:
        return " "
    return "�"


def fix_thai(s):
    """ถอด mojibake latin-1 → ไทย · ถ้าเป็นไทยอยู่แล้วปล่อยผ่าน (เผื่อต้นทางแก้วันหลัง)"""
    if not isinstance(s, str) or not s:
        return s
    if any("฀" <= c <= "๿" for c in s):
        return s
    try:
        return "".join(_cp874_byte_to_char(b) for b in s.encode("latin-1"))
    except UnicodeEncodeError:
        return s


def strip_prefix(name, prefix):
    """'จ.นครราชสีมา' → 'นครราชสีมา'"""
    name = (name or "").strip()
    return name[len(prefix):].strip() if name.startswith(prefix) else name


def scene_fingerprint(features):
    """ลายนิ้วมือของฉาก — ชุด (ตำบล, พื้นที่ท่วม) ที่เรียงแล้ว

    ใช้ตรวจว่า GISTDA ปล่อยฉากใหม่หรือยัง เพราะ feature ไม่มีวันที่ให้ดู
    """
    parts = sorted(
        f"{f.get('properties', {}).get('TB_IDN')}:{f.get('properties', {}).get('flood_area')}"
        for f in features
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def main():
    print(f"Fetching GISTDA flood extent ...")
    r = requests.get(WFS_URL, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    features = data.get("features") or []
    if not features:
        print("[ERROR] WFS ตอบสำเร็จแต่ไม่มี feature เลย", file=sys.stderr)
        sys.exit(1)
    print(f"  ได้ {len(features)} polygon")

    bkk_now = datetime.now(timezone.utc) + timedelta(hours=7)
    fetched_at = datetime.now(timezone.utc).isoformat()
    fp = scene_fingerprint(features)

    # ฉากเดิมหรือฉากใหม่ — เทียบกับที่เคยบันทึกไว้
    prev = {}
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception as e:
            print(f"[WARN] อ่านไฟล์เดิมไม่ได้: {e}", file=sys.stderr)
    prev_meta = prev.get("_meta") or {}
    if prev_meta.get("scene_id") == fp and prev_meta.get("scene_first_seen"):
        scene_first_seen = prev_meta["scene_first_seen"]
        print(f"  ฉากเดิม ({fp}) เห็นครั้งแรก {scene_first_seen}")
    else:
        scene_first_seen = fetched_at
        print(f"  ฉากใหม่ ({fp})")

    provinces = {}
    unknown = set()
    for feat in features:
        p = feat.get("properties") or {}
        prov_th = strip_prefix(fix_thai(p.get("PV_TN")), "จ.")
        prov_en = PROVINCE_TH_EN.get(prov_th)
        if not prov_en:
            unknown.add(prov_th)
            continue
        amphoe_th = strip_prefix(fix_thai(p.get("AP_TN")), "อ.")
        tambon_th = strip_prefix(fix_thai(p.get("TB_TN")), "ต.")
        rai = float(p.get("flood_area") or 0)

        entry = provinces.setdefault(prov_en, {
            "province_th": prov_th, "flood_rai": 0.0, "tambon_count": 0, "amphoe": {},
        })
        entry["flood_rai"] += rai
        entry["tambon_count"] += 1
        amp = entry["amphoe"].setdefault(amphoe_th, {"flood_rai": 0.0, "tambon": []})
        amp["flood_rai"] += rai
        amp["tambon"].append({"name": tambon_th, "flood_rai": round(rai, 1)})

    # ปัดเศษ + เรียงจากหนักไปเบา
    for prov in provinces.values():
        prov["flood_rai"] = round(prov["flood_rai"], 1)
        for amp in prov["amphoe"].values():
            amp["flood_rai"] = round(amp["flood_rai"], 1)
            amp["tambon"].sort(key=lambda t: -t["flood_rai"])
        prov["amphoe"] = dict(sorted(prov["amphoe"].items(), key=lambda kv: -kv[1]["flood_rai"]))
    provinces = dict(sorted(provinces.items(), key=lambda kv: -kv[1]["flood_rai"]))

    if unknown:
        print(f"[WARN] จังหวัดที่แมปไม่ได้ ({len(unknown)}): {', '.join(sorted(unknown))}",
              file=sys.stderr)

    total_rai = round(sum(p["flood_rai"] for p in provinces.values()), 1)
    result = {
        "_meta": {
            "kind": "observed",
            "source": "GISTDA — flood-innotech WFS (FloodArea_Poly)",
            "source_url": "https://flood-innotech.gistda.or.th/",
            "updated": bkk_now.date().isoformat(),
            "fetched_at": fetched_at,
            "scene_id": fp,
            "scene_first_seen": scene_first_seen,
            "observed_at": None,   # ต้นทางไม่ให้มา — ห้ามเดาจาก fetched_at
            "features": len(features),
            "provinces_affected": len(provinces),
            "total_flood_rai": total_rai,
            "unit": "ไร่ (rai)",
            "note_th": (
                "พื้นที่น้ำท่วมที่**ดาวเทียมเห็นจริง** จาก GISTDA รายตำบล รวมเป็นรายจังหวัด/อำเภอ · "
                "ต่างจาก layer เตือนภัยน้ำท่วมที่คำนวณจากพยากรณ์ฝน (คนละเรื่อง ใช้เสริมกัน) · "
                "**ต้นทางไม่ระบุวันที่ถ่ายภาพ** จึงบอกได้แค่วันที่เราดึงข้อมูลกับวันที่เห็นฉากนี้ครั้งแรก "
                "ไม่ใช่ 'น้ำท่วมวันนี้'"
            ),
            "note_en": (
                "Satellite-observed flood extent from GISTDA, tambon-level, aggregated by "
                "province/amphoe. Distinct from the rainfall-derived flood alert layer. "
                "Upstream publishes no observation date — only fetch time and first-seen time "
                "for this scene are known."
            ),
        },
        "provinces": provinces,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(provinces)} จังหวัด · รวม {total_rai:,.0f} ไร่ → {OUTPUT}")
    for en, p in list(provinces.items())[:5]:
        print(f"   {p['province_th']:15s} {p['flood_rai']:12,.0f} ไร่  ({p['tambon_count']} ตำบล)")


if __name__ == "__main__":
    main()
