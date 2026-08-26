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

# ── ตัดกับ mask นาข้าว (GEE) ────────────────────────────────────────────────
# scale 250 ม.: วัดแล้วสุ่มได้ 98.4% ของพื้นที่ที่ GISTDA แจ้ง (1 กม. ได้ 94.1%)
# polygon ตำบลเฉลี่ยแค่ ~1.6 ตร.กม. จึงต้องละเอียดกว่า 1 กม. ไม่งั้นตกกริด
GEE_SCALE = 250
# payload ของ GEE จำกัด 10 MB — ทั้งชุด 359 polygon = 20 MB (ปัดพิกัดแล้ว) ต้องแบ่งส่ง
GEE_CHUNK = 25
COORD_PRECISION = 5    # ~1 ม. เกินพอสำหรับ mask 250 ม. และลด payload 25→20 MB


def fix_thai(s):
    """ถอด mojibake latin-1 → ไทย · ถ้าเป็นไทยอยู่แล้วปล่อยผ่าน (เผื่อต้นทางแก้วันหลัง)

    ต้นทางส่ง cp874 มาแต่ติดป้ายเป็น UTF-8 — Python มี codec `cp874` อยู่แล้ว
    ไม่ต้องไล่แปลงทีละไบต์เอง (เทียบกับตัวแปลงมือบนข้อมูลจริง 1,795 ค่า ตรงกันหมด)
    """
    if not isinstance(s, str) or not s:
        return s
    if any("฀" <= c <= "๿" for c in s):
        return s
    try:
        return s.encode("latin-1").decode("cp874")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def strip_prefix(name, prefix):
    """'จ.นครราชสีมา' → 'นครราชสีมา'"""
    return (name or "").strip().removeprefix(prefix).strip()


def scene_fingerprint(features):
    """ลายนิ้วมือของฉาก — ชุด (ตำบล, พื้นที่ท่วม) ที่เรียงแล้ว

    ใช้ตรวจว่า GISTDA ปล่อยฉากใหม่หรือยัง เพราะ feature ไม่มีวันที่ให้ดู
    และใช้ข้ามขั้นตอน GEE (แพง ~5 นาที) เมื่อฉากไม่เปลี่ยน
    """
    parts = sorted(
        f"{f.get('properties', {}).get('TB_IDN')}:{f.get('properties', {}).get('flood_area')}"
        for f in features
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _round_coords(c, nd=COORD_PRECISION):
    if isinstance(c, (int, float)):
        return round(c, nd)
    return [_round_coords(x, nd) for x in c]


def rice_in_flood(features):
    """ตัดพื้นที่น้ำท่วม × mask นาข้าว → {(prov, amphoe): ไร่นาที่จมน้ำ}

    ใช้ mask ชุดเดียวกับ layer "สภาพนาข้าว" (GLAD rice ∪ MCD12Q1 cropland
    กรองด้วย phenology gate) — วัดจริง 25 ส.ค. 69: GEE สุ่มได้ 98.4% ของ
    พื้นที่ที่ GISTDA แจ้ง และสัดส่วนนากระจาย 18.9–74.6% ตามภูมิศาสตร์จริง
    (ถ้า mask ไม่มีข้อมูลค่าจะเกาะกลุ่มกัน)

    **ค่าที่ได้น่าจะต่ำกว่าจริง** — mask ชุดนี้จับนาได้ ~0.70× ของ สศก.
    (บันทึกใน CHANGELOG หมวดทราบปัญหา) หน้าเว็บจึงต้องเขียนว่า "ประมาณ"

    โยน exception เมื่อคำนวณไม่ได้ — ผู้เรียกดักแล้วปล่อยให้ rice_rai เป็น null
    ข้อมูลน้ำท่วมยังใช้ได้ตามปกติ (ห้ามเดาค่าแทน)
    """
    import ee  # lazy — workflow นี้ลง earthengine-api แต่ไม่ควรพังถ้าไม่มี
    from riceutils import (init_gee, load_rice_mask, load_exclusion_mask,
                           build_rice_phenology_mask, PHENOLOGY_MONTHS,
                           latest_q1_periods)

    init_gee()
    periods = latest_q1_periods(n=2)
    if not periods:
        raise RuntimeError("ไม่พบ composite MOD13Q1")
    union_mask, _glad, src = load_rice_mask()
    excl, _desc = load_exclusion_mask()
    if excl is not None:
        union_mask = union_mask.And(excl.Not())
    pheno, win = build_rice_phenology_mask(periods[0][0], PHENOLOGY_MONTHS)
    rice = pheno.updateMask(union_mask)
    area = ee.Image.pixelArea()
    combo = rice.unmask(0).multiply(area).rename("rice_m2").addBands(area.rename("m2"))
    print(f"  mask: {src[:60]} · pheno {win}")

    out, sampled_m2, total_m2 = {}, 0.0, 0.0
    for i in range(0, len(features), GEE_CHUNK):
        batch = []
        for f in features[i:i + GEE_CHUNK]:
            g = f.get("geometry")
            if not g:
                continue
            p = f.get("properties") or {}
            batch.append(ee.Feature(
                ee.Geometry({**g, "coordinates": _round_coords(g["coordinates"])}),
                {
                    "prov": strip_prefix(fix_thai(p.get("PV_TN")), "จ."),
                    "amph": strip_prefix(fix_thai(p.get("AP_TN")), "อ."),
                    "frai": float(p.get("flood_area") or 0),
                },
            ))
        if not batch:
            continue
        rows = (combo.reduceRegions(collection=ee.FeatureCollection(batch),
                                    reducer=ee.Reducer.sum(), scale=GEE_SCALE)
                .select(["prov", "amph", "frai", "rice_m2", "m2"]).getInfo()["features"])
        for r in rows:
            pr = r["properties"]
            out[(pr["prov"], pr["amph"])] = out.get((pr["prov"], pr["amph"]), 0.0) + \
                (pr.get("rice_m2") or 0) / SQM_PER_RAI
            sampled_m2 += pr.get("m2") or 0
            total_m2 += (pr.get("frai") or 0) * SQM_PER_RAI
        print(f"  GEE {min(i + GEE_CHUNK, len(features))}/{len(features)} polygon", flush=True)

    cover = 100 * sampled_m2 / total_m2 if total_m2 else 0
    print(f"  GEE สุ่มได้ {cover:.1f}% ของพื้นที่ที่ GISTDA แจ้ง")
    if cover < 80:
        raise RuntimeError(f"GEE สุ่มได้แค่ {cover:.1f}% — ต่ำผิดปกติ ไม่ใช้ผลนี้")
    return out, round(cover, 1)


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
    same_scene = prev_meta.get("scene_id") == fp and prev_meta.get("scene_first_seen")
    if same_scene:
        scene_first_seen = prev_meta["scene_first_seen"]
        print(f"  ฉากเดิม ({fp}) เห็นครั้งแรก {scene_first_seen}")
    else:
        scene_first_seen = fetched_at
        print(f"  ฉากใหม่ ({fp})")

    # ── ตัดกับ mask นาข้าว — ทำเฉพาะตอนฉากเปลี่ยน (GEE ใช้เวลา ~5 นาที) ──────
    rice_by_key, rice_cover, rice_err = None, None, None
    reuse_rice = same_scene and prev_meta.get("rice_scene_id") == fp
    if reuse_rice:
        print("  ข้ามการคำนวณนา — ฉากเดิม ใช้ค่าที่คำนวณไว้แล้ว")
    else:
        try:
            rice_by_key, rice_cover = rice_in_flood(features)
        except Exception as e:
            rice_err = f"{type(e).__name__}: {e}"
            print(f"[WARN] คำนวณพื้นที่นาไม่สำเร็จ: {rice_err}", file=sys.stderr)
            print("       → ข้อมูลน้ำท่วมยังใช้ได้ แต่ไม่มีตัวเลขนา (ไม่เดาค่าแทน)",
                  file=sys.stderr)

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

    # เติมพื้นที่นาที่จมน้ำ (ถ้าคำนวณได้รอบนี้ / หรือใช้ค่าเดิมเมื่อฉากไม่เปลี่ยน)
    prev_provs = prev.get("provinces") or {}
    for prov_en, entry in provinces.items():
        for amphoe_th, amp in entry["amphoe"].items():
            if rice_by_key is not None:
                amp["rice_rai"] = round(rice_by_key.get((entry["province_th"], amphoe_th), 0.0), 1)
            elif reuse_rice:
                amp["rice_rai"] = ((prev_provs.get(prov_en) or {}).get("amphoe") or {})                     .get(amphoe_th, {}).get("rice_rai")
            else:
                amp["rice_rai"] = None
        vals = [a["rice_rai"] for a in entry["amphoe"].values() if a.get("rice_rai") is not None]
        entry["rice_rai"] = round(sum(vals), 1) if vals else None
        # ไม่เก็บ % — หารเอาจาก rice_rai/flood_rai ตอนแสดงผลได้ ไม่ต้องมีค่าซ้ำให้เพี้ยนกัน

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
    _rv = [p["rice_rai"] for p in provinces.values() if p.get("rice_rai") is not None]
    total_rice = round(sum(_rv), 1) if _rv else None
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
            "total_rice_rai": total_rice,
            "rice_scene_id": fp if (rice_by_key is not None or reuse_rice) else None,
            "rice_kind": "derived",   # ต่างจากพื้นที่ท่วมที่เป็น observed
            "rice_mask_scale_m": GEE_SCALE,
            "rice_coverage_pct": rice_cover if rice_cover is not None else prev_meta.get("rice_coverage_pct"),
            "rice_error": rice_err,
            "rice_note_th": (
                "พื้นที่นาที่จมน้ำ = พื้นที่น้ำท่วม (GISTDA) ตัดกับ mask นาข้าวจากดาวเทียมของเราเอง "
                "(ชุดเดียวกับ layer สภาพนาข้าว) · **เป็นค่าประมาณและน่าจะต่ำกว่าจริง** เพราะ mask ชุดนี้ "
                "จับพื้นที่นาได้ราว 0.70 เท่าของตัวเลข สศก. · ใช้ดูขนาดความเสียหายคร่าวๆ "
                "ไม่ใช่ตัวเลขสำหรับเคลมชดเชย"
            ),
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

    rice_txt = (f" · เป็นนาข้าวประมาณ {total_rice:,.0f} ไร่ ({100 * total_rice / total_rai:.0f}%)"
                if total_rice is not None and total_rai else " · ไม่มีตัวเลขนา")
    print(f"\n✅ {len(provinces)} จังหวัด · น้ำท่วมรวม {total_rai:,.0f} ไร่{rice_txt} → {OUTPUT}")
    for en, p in list(provinces.items())[:5]:
        r = (f"นา ~{p['rice_rai']:,.0f} ({100 * p['rice_rai'] / p['flood_rai']:.0f}%)"
             if p.get("rice_rai") is not None and p["flood_rai"] else "นา —")
        print(f"   {p['province_th']:15s} ท่วม {p['flood_rai']:10,.0f} ไร่ ({p['tambon_count']} ตำบล) · {r}")


if __name__ == "__main__":
    main()
