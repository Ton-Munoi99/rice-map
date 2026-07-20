#!/usr/bin/env python3
"""Offline self-check for telegram_notify.py — no network, no real token.
Run: python scripts/test_telegram_notify.py
"""
import sys
from unittest.mock import patch

import telegram_notify as tn


def test_slug_to_province():
    known = {"Roi Et", "Nakhon Si Thammarat", "Bangkok Metropolis"}
    assert tn.slug_to_province("Roi_Et", known) == "Roi Et"
    assert tn.slug_to_province("Nakhon_Si_Thammarat", known) == "Nakhon Si Thammarat"
    assert tn.slug_to_province("Nowhereland", known) is None


def test_notify_first_subscribe_no_spam():
    """สมัครใหม่ (last_level_num=None) ต้องไม่ส่งข้อความ แค่ตั้งค่า baseline"""
    sent_calls = []
    state = {"subscribers": [{"chat_id": 1, "province_en": "Roi Et", "last_level_num": None}]}
    warn = {"provinces": {"Roi Et": {"level_num": 2, "warnings": [{"icon": "🟠", "message_th": "x"}]}}}
    with patch.object(tn, "api_call", side_effect=lambda *a, **k: sent_calls.append(k) or {"ok": True}):
        sent = tn.notify_level_changes(state, warn)
    assert sent == 0, "first subscribe should not send an alert"
    assert state["subscribers"][0]["last_level_num"] == 2
    assert sent_calls == []


def test_notify_on_level_change():
    """ระดับเปลี่ยนจาก 1 -> 3 ต้องส่งแจ้งเตือน 1 ครั้ง และอัปเดต last_level_num"""
    sent_calls = []
    state = {"subscribers": [{"chat_id": 1, "province_en": "Roi Et", "last_level_num": 1}]}
    warn = {"provinces": {"Roi Et": {"level_num": 3, "warnings": [{"icon": "🔴", "message_th": "ท่วมสูง"}]}}}
    with patch.object(tn, "api_call", side_effect=lambda *a, **k: sent_calls.append(k) or {"ok": True}):
        sent = tn.notify_level_changes(state, warn)
    assert sent == 1
    assert state["subscribers"][0]["last_level_num"] == 3
    assert "ท่วมสูง" in sent_calls[0]["text"]


def test_notify_no_change_no_send():
    state = {"subscribers": [{"chat_id": 1, "province_en": "Roi Et", "last_level_num": 2}]}
    warn = {"provinces": {"Roi Et": {"level_num": 2, "warnings": [{"icon": "🟠", "message_th": "x"}]}}}
    with patch.object(tn, "api_call", side_effect=AssertionError("should not call API")):
        sent = tn.notify_level_changes(state, warn)
    assert sent == 0


def test_notify_removes_blocked_chat():
    state = {"subscribers": [{"chat_id": 1, "province_en": "Roi Et", "last_level_num": 1}]}
    warn = {"provinces": {"Roi Et": {"level_num": 2, "warnings": [{"icon": "🔴", "message_th": "x"}]}}}
    with patch.object(tn, "api_call", return_value={"ok": False, "error": "Forbidden: bot was blocked by the user"}):
        tn.notify_level_changes(state, warn)
    assert state["subscribers"] == [], "blocked chat should be dropped"


def test_process_updates_start_and_stop():
    known = {"Roi Et"}
    state = {"_meta": {"last_update_id": 0}, "subscribers": []}
    updates = {
        "ok": True,
        "result": [
            {"update_id": 5, "message": {"chat": {"id": 42}, "text": "/start Roi_Et"}},
        ],
    }
    with patch.object(tn, "api_call", side_effect=lambda method, **k: updates if method == "getUpdates" else {"ok": True}):
        new_subs, removed = tn.process_updates(state, known)
    assert new_subs == 1 and removed == 0
    assert state["subscribers"][0] == {
        "chat_id": 42, "province_en": "Roi Et",
        "subscribed_at": state["subscribers"][0]["subscribed_at"], "last_level_num": None,
    }
    assert state["_meta"]["last_update_id"] == 5

    # /stop removes the subscriber
    updates2 = {"ok": True, "result": [{"update_id": 6, "message": {"chat": {"id": 42}, "text": "/stop"}}]}
    with patch.object(tn, "api_call", side_effect=lambda method, **k: updates2 if method == "getUpdates" else {"ok": True}):
        new_subs, removed = tn.process_updates(state, known)
    assert new_subs == 0 and removed == 1
    assert state["subscribers"] == []


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n✅ {len(tests)} tests passed")
