#!/usr/bin/env python3
"""
Telegram alert bot — notifies subscribed farmers when their province's flood/
drought risk level changes (data/agri-warnings.json). No server/webhook: this
runs as a GitHub Actions cron step and uses long-polling (getUpdates) to pick
up new /start<province> subscriptions since the last run.

Subscribe flow: farmer.html has a button linking to
  https://t.me/<BOT_USERNAME>?start=<province_slug>
Telegram sends that as a "/start <province_slug>" message to the bot; this
script decodes the slug (underscores → spaces) back to a province_en, matches
it against data/agri-warnings.json provinces, and registers the chat.

Requires env var TELEGRAM_BOT_TOKEN (GitHub Actions secret).
Run: python scripts/telegram_notify.py
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
SUBS_PATH = "data/telegram-subscribers.json"
SITE_URL = "https://ton-munoi99.github.io/rice-map"  # อัปเดตถ้าย้ายไป custom domain
TIMEOUT = 20


def api_call(method, **params):
    url = f"{API}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": e.read().decode("utf-8", "replace")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def load_subs():
    if os.path.exists(SUBS_PATH):
        with open(SUBS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"_meta": {"last_update_id": 0, "updated": ""}, "subscribers": []}


def save_subs(state):
    state["_meta"]["updated"] = date.today().isoformat()
    os.makedirs("data", exist_ok=True)
    with open(SUBS_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def slug_to_province(slug, known_provinces):
    """แปลง deep-link payload (underscore แทนช่องว่าง) กลับเป็นชื่อจังหวัด en"""
    guess = slug.replace("_", " ").strip()
    return guess if guess in known_provinces else None


def process_updates(state, known_provinces):
    """ดึงคำสั่งใหม่ (/start<slug>, /stop) ตั้งแต่ update ล่าสุดที่ประมวลผลแล้ว"""
    offset = state["_meta"].get("last_update_id", 0) + 1
    resp = api_call("getUpdates", offset=offset, timeout=0)
    if not resp.get("ok"):
        print(f"[WARN] getUpdates failed: {resp.get('error')}", file=sys.stderr)
        return 0, 0

    by_chat = {s["chat_id"]: s for s in state["subscribers"]}
    new_subs = removed = 0

    for upd in resp.get("result", []):
        state["_meta"]["last_update_id"] = max(state["_meta"]["last_update_id"], upd["update_id"])
        msg = upd.get("message") or {}
        chat_id = msg.get("chat", {}).get("id")
        text = (msg.get("text") or "").strip()
        if not chat_id or not text:
            continue

        m = re.match(r"^/start\s*(\S+)?", text)
        if m and m.group(1):
            prov = slug_to_province(m.group(1), known_provinces)
            if not prov:
                api_call("sendMessage", chat_id=chat_id,
                         text="ไม่พบจังหวัดนี้ — กรุณากดปุ่มสมัครจากหน้าเว็บอีกครั้ง")
                continue
            by_chat[chat_id] = {"chat_id": chat_id, "province_en": prov,
                                 "subscribed_at": date.today().isoformat(), "last_level_num": None}
            new_subs += 1
            api_call("sendMessage", chat_id=chat_id,
                     text=f"✅ สมัครรับเตือนจังหวัด{prov}แล้ว จะแจ้งเมื่อระดับความเสี่ยงน้ำท่วม/แล้งเปลี่ยนแปลง\n"
                          f"พิมพ์ /stop เพื่อยกเลิกได้ตลอดเวลา")
        elif text == "/stop" and chat_id in by_chat:
            del by_chat[chat_id]
            removed += 1
            api_call("sendMessage", chat_id=chat_id, text="ยกเลิกการแจ้งเตือนแล้ว")

    state["subscribers"] = list(by_chat.values())
    return new_subs, removed


def notify_level_changes(state, warn_data):
    provinces = warn_data.get("provinces", {})
    sent = 0
    for sub in state["subscribers"]:
        info = provinces.get(sub["province_en"])
        if not info:
            continue
        level_num = info.get("level_num", 0)
        top = (info.get("warnings") or [{}])[0]
        if sub.get("last_level_num") is None:
            # ครั้งแรก (เพิ่งสมัคร) — ตั้งค่าเริ่มต้น ไม่ต้องแจ้งซ้ำกับข้อความต้อนรับ
            sub["last_level_num"] = level_num
            continue
        if level_num == sub["last_level_num"]:
            continue
        icon = top.get("icon", "ℹ️")
        msg_th = top.get("message_th", "สถานการณ์เปลี่ยนแปลง")
        link = f"{SITE_URL}/farmer.html?prov={urllib.parse.quote(sub['province_en'])}"
        text = f"{icon} {sub['province_en']}\n{msg_th}\n\nดูรายละเอียด: {link}"
        r = api_call("sendMessage", chat_id=sub["chat_id"], text=text)
        if r.get("ok"):
            sent += 1
        elif "blocked" in str(r.get("error", "")).lower() or "chat not found" in str(r.get("error", "")).lower():
            sub["_remove"] = True  # บอทถูกบล็อก/แชทหาย — ลบทิ้งรอบถัดไป
        sub["last_level_num"] = level_num
    state["subscribers"] = [s for s in state["subscribers"] if not s.pop("_remove", False)]
    return sent


def main():
    if not TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN not set — skipping (bot not configured yet)", file=sys.stderr)
        sys.exit(0)  # ไม่ fail workflow ทั้งเส้นถ้ายังไม่ตั้งค่า token

    if not os.path.exists("data/agri-warnings.json"):
        print("[ERROR] data/agri-warnings.json missing", file=sys.stderr)
        sys.exit(1)
    with open("data/agri-warnings.json", encoding="utf-8") as f:
        warn_data = json.load(f)
    known_provinces = set(warn_data.get("provinces", {}).keys())

    state = load_subs()
    new_subs, removed = process_updates(state, known_provinces)
    sent = notify_level_changes(state, warn_data)
    save_subs(state)

    print(f"Subscribers: {len(state['subscribers'])} (+{new_subs} new, -{removed} stopped) · alerts sent: {sent}")


if __name__ == "__main__":
    main()
