#!/usr/bin/env python3
"""
Data freshness monitor — เช็คว่าไฟล์ใน data/ ถูก commit ล่าสุดเกินรอบ cron ไหม

กลไกเดียวครอบทุกไฟล์: อายุ commit ล่าสุด (git log) เทียบ threshold ต่อไฟล์
ไม่ parse _meta เพราะ 4-5 ไฟล์ไม่มี และ commit age สะท้อนว่า cron ทำงานจริง

Exit 1 เมื่อมีไฟล์ stale → workflow แดง → GitHub ส่งอีเมลแจ้งเจ้าของอัตโนมัติ
(นี่คือช่องทางแจ้งเตือน — ไม่ต้องมีโค้ดจัดการ issue)
Run in CI with fetch-depth: 0 (ต้องมี git history)
"""
import subprocess, sys, time

# ponytail: threshold = ~3 เท่าของรอบ cron กันเตือนหลอกจาก run พลาดครั้งเดียว/วันหยุด
MAX_AGE_DAYS = {
    "water-level.json":      1,   # cron ทุก 3 ชม.
    "rain-stations.json":    1,   # ทุก 3 ชม.
    "storm-alerts.json":     2,   # ทุก 6 ชม.
    "rice-news.json":        2,   # 3 ครั้ง/วัน
    "dam-water.json":        3,   # รายวัน ×2
    "disease-risk.json":     3,   # รายวัน
    "rain-daily.json":       3,   # รายวัน
    "rain-forecast.json":    3,
    "rain-gsmap.json":       3,
    "agri-warnings.json":    3,
    "prices-live.json":      3,   # OAE รายวัน + โรงสี 3 ครั้ง/วัน
    "trea-fob.json":         7,   # จ-ศ ×3 (เผื่อวันหยุดยาว)
    "soil-moisture.json":    10,  # รายสัปดาห์ (จันทร์)
    "fertilizer-prices.json": 10,  # รายสัปดาห์ (จันทร์) — ต้องมี FIRECRAWL_API_KEY
    "alert-scoreboard.json":  3,   # ต่อท้าย update-rain รายวัน
    "ndvi.json":             45,  # รายเดือน (วันที่ 8)
    "ndvi-district.json":    45,
    "rice-evi.json":         45,
    "rice-evi-district.json": 45,
    "weather-province.json": 45,  # รายเดือน (วันที่ 1)
    "weather-forecast.json": 45,
}
# ตั้งใจไม่เฝ้า (ระบุไว้เพื่อให้ audit แยกออกว่าไม่ใช่ของที่ลืม):
#   rice-mills, districts-geo, oae_extracted — สร้างด้วยมือ ไม่มี cron
#   rice-evi-validation      — เขียนพร้อม rice-evi.json ที่เฝ้าอยู่แล้ว
#   rice-news-archive        — โตเฉพาะตอนมีข่าวใหม่จริง เฝ้า rice-news.json แทน
#   biomass-plants           — ปีละครั้ง เกณฑ์อายุจะหลวมจนไม่มีประโยชน์
#
# เพิ่ม workflow ที่เขียนไฟล์ใหม่เมื่อไหร่ ให้เพิ่มไฟล์นั้นที่นี่ด้วย — fertilizer-prices
# เคยหลุดรายการนี้ ทำให้ FIRECRAWL_API_KEY หายไปเงียบๆ 2 สัปดาห์โดยไม่มีอะไรเตือน


def last_commit_ts(path):
    out = subprocess.check_output(["git", "log", "-1", "--format=%ct", "--", path], text=True).strip()
    return int(out) if out else None


def main():
    now = time.time()
    stale, rows = [], []
    for name, max_days in sorted(MAX_AGE_DAYS.items()):
        ts = last_commit_ts(f"data/{name}")
        if ts is None:
            stale.append(name)
            rows.append((name, "NO COMMIT FOUND", max_days, "STALE"))
            continue
        age = (now - ts) / 86400
        ok = age <= max_days
        if not ok:
            stale.append(name)
        rows.append((name, f"{age:.1f}d", max_days, "ok" if ok else "STALE"))

    w = max(len(r[0]) for r in rows)
    for name, age, limit, status in rows:
        print(f"{name:<{w}}  age={age:>8}  limit={limit}d  {status}")

    if stale:
        print(f"\nSTALE ({len(stale)}): {', '.join(stale)}", file=sys.stderr)
        print("Check the matching update-*.yml workflow runs.", file=sys.stderr)
        sys.exit(1)
    print(f"\nAll {len(rows)} monitored files fresh.")


if __name__ == "__main__":
    main()
