#!/usr/bin/env bash
# push-verified.sh — push ขึ้น main แล้ว "พิสูจน์" ว่าขึ้นจริง
#
# ทำไมต้องมี: รีโปนี้มี cron ~20 ตัวที่ push เข้า main ตลอดเวลา การ push
# ด้วยมือจึงชนบ่อย และ loop แบบ retry ที่เขียนสดๆ เคยพลาดมาแล้วจริง
# (25 ส.ค. 69): `git rebase … 2>/dev/null` กลืน error ของ merge conflict
# ทำให้ repo ค้างใน detached HEAD โดยไม่มีใครรู้ แล้วไปเช็คผลด้วย sha ของ
# main ลอยๆ ซึ่งบังเอิญเป็น commit ของ cron — สรุปว่ารายงานว่า "push แล้ว"
# ทั้งที่โค้ดไม่เคยขึ้น และ CI ก็ยังเขียวเพราะรันโค้ดเก่า
#
# กฎ 3 ข้อที่สคริปต์นี้บังคับ:
#   1. ไม่กลืน error ของ rebase — conflict ต้องถูกจัดการหรือหยุด
#   2. auto-resolve เฉพาะ data/*.json (ไฟล์ที่ generate ใหม่ได้)
#      โค้ด/เอกสารชนเมื่อไหร่ = หยุด ให้คนตัดสิน
#   3. ยืนยันด้วยการเทียบ sha ของ remote กับ local — ไม่ grep ข้อความ push
#
# ใช้:  bash scripts/push-verified.sh [remote] [branch]
#       (ค่าเริ่มต้น origin main)
set -uo pipefail

REMOTE="${1:-origin}"
BRANCH="${2:-main}"
MAX_TRIES=8

die() { echo "❌ $*" >&2; exit 1; }

command -v git >/dev/null || die "ไม่มี git"
git rev-parse --git-dir >/dev/null 2>&1 || die "ไม่ได้อยู่ใน git repo"

# กันกรณีเรียกทั้งที่ยังมี rebase/merge ค้างจากรอบก่อน
GIT_DIR_PATH="$(git rev-parse --git-dir)"
if [ -d "$GIT_DIR_PATH/rebase-merge" ] || [ -d "$GIT_DIR_PATH/rebase-apply" ]; then
  die "มี rebase ค้างอยู่ — สั่ง 'git rebase --abort' หรือ '--continue' ให้จบก่อน"
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  die "working tree ยังไม่สะอาด — commit หรือเก็บงานให้เรียบร้อยก่อน push"
fi

for try in $(seq 1 "$MAX_TRIES"); do
  LOCAL="$(git rev-parse HEAD)"

  if git push "$REMOTE" "HEAD:$BRANCH" 2>&1; then
    # push ผ่าน — แต่ยังไม่เชื่อจนกว่าจะเทียบ sha จริง
    git fetch "$REMOTE" "$BRANCH" --quiet
    ACTUAL="$(git rev-parse "$REMOTE/$BRANCH")"
    if [ "$LOCAL" = "$ACTUAL" ]; then
      echo "✅ ยืนยันแล้ว: $REMOTE/$BRANCH = ${LOCAL:0:7} (ตรงกับ local HEAD)"
      exit 0
    fi
    # push บอกว่าสำเร็จแต่ sha ไม่ตรง = มีคน push แซงทันที วนต่อ
    echo "   push ผ่านแต่ $REMOTE/$BRANCH เป็น ${ACTUAL:0:7} แล้ว (มีคน push แซง) — rebase ใหม่"
  else
    echo "   รอบ $try: push ไม่ผ่าน (น่าจะมี commit ใหม่บน $BRANCH) — rebase"
  fi

  git fetch "$REMOTE" "$BRANCH" --quiet || die "fetch ไม่สำเร็จ"

  # ไม่ซ่อน error ของ rebase — ถ้าไม่ผ่านต้องรู้ว่าติดตรงไหน
  if ! git rebase "$REMOTE/$BRANCH"; then
    CONFLICTS="$(git diff --name-only --diff-filter=U)"
    [ -n "$CONFLICTS" ] || die "rebase ล้มโดยไม่มี conflict — หยุดให้ตรวจเอง"

    # ชนเฉพาะไฟล์ข้อมูลที่ generate ใหม่ได้ → เอาฝั่งเราแล้วไปต่อ
    # (cron เขียนไฟล์เดียวกันบ่อย เป็นสาเหตุ conflict อันดับหนึ่ง)
    NON_DATA="$(echo "$CONFLICTS" | grep -v '^data/.*\.json$' || true)"
    if [ -n "$NON_DATA" ]; then
      echo "conflict ในไฟล์ที่ไม่ใช่ข้อมูล:" >&2
      echo "$NON_DATA" >&2
      git rebase --abort
      die "ต้องให้คนตัดสิน — สคริปต์ไม่ auto-resolve โค้ด/เอกสาร (rebase ถูก abort คืนสภาพเดิมแล้ว)"
    fi

    echo "   conflict เฉพาะไฟล์ข้อมูล เอาฝั่งเรา: $(echo "$CONFLICTS" | tr '\n' ' ')"
    # ระหว่าง rebase ฝั่ง "เรา" (commit ที่กำลัง replay) คือ --theirs
    echo "$CONFLICTS" | while read -r f; do
      [ -n "$f" ] && git checkout --theirs -- "$f" && git add -- "$f"
    done
    GIT_EDITOR=true git rebase --continue || die "rebase --continue ไม่ผ่าน — ตรวจด้วยตัวเอง"
  fi
done

die "ครบ $MAX_TRIES รอบแล้วยัง push ไม่สำเร็จ — main ถูกเขียนถี่เกินไป ลองใหม่ภายหลัง"
