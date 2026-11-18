#!/usr/bin/env bash
# ดึงราคา สศก. รายสัปดาห์จากเครื่องเจ้าของ (IP ไทย) แล้ว push data/prices-live.json
#
# ทำไม: agriapi.nabc.go.th อยู่หลัง Cloudflare ที่บล็อก runner ของ GitHub และตั้งแต่
# พ.ย. 69 บล็อก Firecrawl / Jina ด้วย — ยิงจาก IP ไทยผ่านอย่างเดียว
# Windows Task Scheduler เรียกวันละครั้ง (งาน "RiceMap OAE refresh")
# ใช้ clone แยกของตัวเอง ไม่แตะ checkout ที่เจ้าของทำงานอยู่ · log อยู่ที่ $DIR.log
# ทั้งหมดอยู่ใน { } เพราะ Task Scheduler เรียกไฟล์นี้จากใน clone ที่ checkout ทับระหว่างรัน
# — bash ต้องอ่านจบก่อนเริ่ม ไม่งั้นไฟล์ที่เปลี่ยนกลางทางจะถูกอ่านต่อผิดบรรทัด
#
# ไม่ใช้ push-verified.sh: ไฟล์นี้มีราคาโรงสี (cron บน GitHub) อยู่ด้วย ถ้าชนกัน
# push-verified จะเอาฝั่งเรา = เขียนทับราคาโรงสีใหม่ด้วยของเก่า
# จึง push ธรรมดา (ปฏิเสธเองถ้า main ขยับ) แล้วเริ่มใหม่บนฐานล่าสุด ดึงราคาซ้ำ
{
set -euo pipefail
export PYTHONIOENCODING=utf-8
DIR="${RICE_MAP_OAE_DIR:-$LOCALAPPDATA/rice-map-oae}"
exec >>"$DIR.log" 2>&1
echo "=== $(date '+%F %T')"
[ -d "$DIR/.git" ] || git clone -q https://github.com/Ton-Munoi99/rice-map.git "$DIR"
cd "$DIR"
for try in 1 2 3 4 5; do
  git fetch -q origin main && git checkout -q -B main origin/main
  python scripts/fetch_oae_prices.py
  git diff --quiet -- data/prices-live.json && { echo "ไม่มีอะไรเปลี่ยน"; exit 0; }
  git add data/prices-live.json
  git commit -q -m "🤖 Auto-update: OAE national prices (local, Thai IP)"
  if git push -q origin HEAD:main; then
    echo "✅ push แล้ว: $(git rev-parse --short HEAD)"; exit 0
  fi
  echo "   รอบ $try: main ขยับ — เริ่มใหม่บนฐานล่าสุด"; sleep 20
done
echo "❌ push ไม่ผ่าน 5 รอบ"; exit 1
}
