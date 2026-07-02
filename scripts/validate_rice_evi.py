#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/validate_rice_evi.py
ตรวจสอบความแม่นของ data/rice-evi.json เทียบกับพื้นที่ปลูกข้าวจริงจาก OAE
(rice-data.js นาปี + naprang-data.js นาปรัง) รายจังหวัด — จับ overcount/drift
อัตโนมัติ เช่น จังหวัดที่ EVI นับพื้นที่นาเกินจริงหลายเท่า (มักปนยาง/ปาล์ม)

Run:  python scripts/validate_rice_evi.py            (รายงาน + เขียน validation json)
      python scripts/validate_rice_evi.py --strict   (exit 1 ถ้ามีจังหวัด BAD)

ใช้ต่อท้าย fetch_rice_evi.py ใน workflow เพื่อ monitor ทุกครั้งที่อัปเดต EVI
เกณฑ์ ratio = rice_rai (EVI, GLAD-preferred) / พื้นที่ข้าว OAE (นาปี+นาปรัง, max ทุกปี)
"""
import sys, io, os, re, json

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── เกณฑ์ ratio (EVI rice_rai / OAE rice area) ───────────────────────────────
WATCH = 2.0    # ≤2× = ใกล้เคียง (OK), >2× = เริ่มปน
WARN  = 5.0    # >5× = ปนพืชอื่นมาก
BAD   = 10.0   # >10× = overcount รุนแรง (มักยาง/ปาล์มทั้งจังหวัด)
MIN_OAE_RAI = 15000  # ต่ำกว่านี้ = ไม่ใช่พื้นที่นาข้าวสำคัญ (mirror frontend filter)


def load_js_rows(path, var_name):
    """ดึง array ของ object จากไฟล์ window.<VAR>=[...]"""
    txt = open(path, encoding="utf-8").read()
    m = re.search(re.escape(var_name) + r"\s*=\s*(\[.*?\])\s*;?\s*$", txt, re.S)
    if not m:
        m = re.search(r"(\[.*\])", txt, re.S)
    return json.loads(m.group(1))


def oae_rice_area(napi_rows, naprang_rows):
    """คืน dict {province_en: {napi, naprang, total}} — max ทุกปี (mirror oaeMaxRiceRai)"""
    def max_by_year(rows, provinces):
        # napi: sum(white+jasmine) ต่อปี → max ; naprang: area ต่อปี → max
        best = {}
        by_year = {}
        for r in rows:
            p = r.get("province_en", "")
            y = str(r.get("year", ""))
            by_year.setdefault((p, y), 0)
            by_year[(p, y)] += r.get("area", 0) or 0
        for (p, y), a in by_year.items():
            if a > best.get(p, 0):
                best[p] = a
        return best

    napi = max_by_year(napi_rows, None)
    naprang = max_by_year(naprang_rows, None)
    out = {}
    for p in set(list(napi) + list(naprang)):
        n, s = napi.get(p, 0), naprang.get(p, 0)
        out[p] = {"napi": n, "naprang": s, "total": n + s}
    return out


def classify(ratio, oae_total):
    if oae_total < MIN_OAE_RAI:
        return "NON_RICE"       # ไม่ใช่พื้นที่นาสำคัญ (ควรถูกกรองในหน้าเว็บ)
    if ratio is None:
        return "NO_OAE"
    if ratio <= WATCH:
        return "OK"
    if ratio <= WARN:
        return "WATCH"
    if ratio <= BAD:
        return "WARN"
    return "BAD"


def main():
    strict = "--strict" in sys.argv

    evi = json.load(open(os.path.join(REPO, "data", "rice-evi.json"), encoding="utf-8"))
    napi_rows = load_js_rows(os.path.join(REPO, "rice-data.js"), "window.RICE_DATA_ROWS")
    naprang_rows = load_js_rows(os.path.join(REPO, "naprang-data.js"), "window.NAPRANG_DATA_ROWS")
    oae = oae_rice_area(napi_rows, naprang_rows)

    month = evi.get("month") or evi.get("_meta", {}).get("month", "—")
    print(f"Validating data/rice-evi.json ({month}) vs OAE rice area (napi+naprang)\n")

    rows = []
    for prov, v in evi.get("provinces", {}).items():
        if v.get("evi") is None:
            continue
        rice_rai = v.get("rice_rai", 0) or 0
        glad_rai = v.get("glad_rai", 0) or 0
        # confirmed_rai = ก่อน GLAD-preferred (json เก่าไม่มี → ใช้ rice_rai)
        confirmed_rai = v.get("confirmed_rai", rice_rai) or rice_rai
        oae_total = oae.get(prov, {}).get("total", 0)
        ratio = (rice_rai / oae_total) if oae_total > 0 else None
        glad_ratio = (glad_rai / oae_total) if oae_total > 0 and glad_rai else None
        rows.append({
            "province": prov,
            "evi": v.get("evi"),
            "stage": v.get("stage"),
            "rice_basis": v.get("rice_basis"),
            "oae_rai": oae_total,
            "rice_rai": rice_rai,
            "glad_rai": glad_rai,
            "confirmed_rai": confirmed_rai,
            "ratio": round(ratio, 2) if ratio is not None else None,
            "glad_ratio": round(glad_ratio, 2) if glad_ratio is not None else None,
            "flag": classify(ratio, oae_total),
        })

    # เรียงจาก ratio มากสุด (overcount รุนแรงก่อน) — None ไปท้าย
    rows.sort(key=lambda r: (r["ratio"] is None, -(r["ratio"] or 0)))

    counts = {}
    for r in rows:
        counts[r["flag"]] = counts.get(r["flag"], 0) + 1

    icon = {"OK": "✅", "WATCH": "🟡", "WARN": "🟠", "BAD": "🔴",
            "NON_RICE": "⬜", "NO_OAE": "❔"}
    print(f"{'จังหวัด':<22}{'OAE(ไร่)':>11}{'EVI(ไร่)':>12}{'GLAD(ไร่)':>11}{'x OAE':>8}  flag")
    print("-" * 74)
    for r in rows:
        rs = f"{r['ratio']:.1f}x" if r["ratio"] is not None else "—"
        print(f"{r['province']:<22}{r['oae_rai']:>11,}{r['rice_rai']:>12,}"
              f"{r['glad_rai']:>11,}{rs:>8}  {icon.get(r['flag'],'')} {r['flag']}")

    print("\nSummary:", " · ".join(f"{icon.get(k,'')}{k}={v}" for k, v in sorted(counts.items())))
    bad = [r["province"] for r in rows if r["flag"] == "BAD"]
    if bad:
        print(f"🔴 BAD (>{BAD:.0f}× OAE — ตรวจ mask/พืชปน): {', '.join(bad)}")

    out = {
        "_meta": {
            "evi_month": month,
            "compared_to": "OAE rice area (rice-data.js napi + naprang-data.js, max year)",
            "thresholds": {"watch": WATCH, "warn": WARN, "bad": BAD, "min_oae_rai": MIN_OAE_RAI},
            "counts": counts,
        },
        "provinces": rows,
    }
    out_path = os.path.join(REPO, "data", "rice-evi-validation.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Wrote {out_path}")

    if strict and bad:
        print(f"\n❌ --strict: {len(bad)} province(s) exceed {BAD:.0f}× OAE")
        sys.exit(1)


if __name__ == "__main__":
    main()
