"""
Phase 4 (pivot): Simulated WhatsApp-style chat demo.

Runs the exact same agent logic (extract -> state -> nudge) as the
Telegram version, but behind a local web chat UI instead of a real
messaging platform. No network/approval/ban risk - runs 100% locally.

Run: python app.py
Then open http://127.0.0.1:5000 in your browser.
"""

import threading
import time
from datetime import datetime

from flask import Flask, request, jsonify, render_template

from extract import extract_referral
from state import (
    init_db,
    add_referral,
    acknowledge_referral,
    complete_referral,
    get_referral_by_message,
    get_overdue_urgent_referrals,
    get_all_referrals,
    set_nudge_message_id,
    register_referral_message,
)
from nudge import build_nudge_message, build_escalation_message

app = Flask(__name__)

# --- In-memory chat log (simple, resets each run - fine for a demo) ---
messages = []
messages_lock = threading.Lock()
next_message_id = 1

CHAT_ID = "demo-chat"  # single simulated group for this demo

# --- Specialty -> doctor routing table (demo directory) ---
# This is what fixes "requester != assigned specialist": every referral
# gets routed to a specific name, not left implicit.
SPECIALIST_DIRECTORY = {
    "cardiology": "Dr. Bilal",
    "neurology": "Dr. Sara",
    "ortho": "Dr. Ayesha",
    "orthopedics": "Dr. Ayesha",
    "derm": "Dr. Sara",
    "dermatology": "Dr. Sara",
    "gyno": "Dr. Sara",
    "gynecology": "Dr. Sara",
    "pediatric": "Dr. Bilal",
    "pediatrics": "Dr. Bilal",
}


def resolve_assigned_to(specialty: str) -> str:
    if not specialty:
        return "On-call Generalist"
    return SPECIALIST_DIRECTORY.get(specialty.strip().lower(), "On-call Generalist")

# --- Demo-friendly thresholds (seconds, not minutes, so it's visible live) ---
NUDGE_AFTER_SECONDS = 20
ESCALATE_AFTER_SECONDS = 40
BACKGROUND_CHECK_INTERVAL = 5


def _new_message(sender, text, msg_type="user", reply_to=None):
    global next_message_id
    with messages_lock:
        msg = {
            "id": next_message_id,
            "sender": sender,
            "text": text,
            "type": msg_type,  # 'user' or 'bot'
            "reply_to": reply_to,
            "timestamp": datetime.now().strftime("%H:%M"),
        }
        messages.append(msg)
        next_message_id += 1
    return msg


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/messages", methods=["GET"])
def get_messages():
    with messages_lock:
        return jsonify(messages)


@app.route("/status", methods=["GET"])
def get_status():
    """Tiny read-only view into persistent state - every referral and where
    it currently sits in PENDING -> ACKNOWLEDGED -> COMPLETED."""
    referrals = get_all_referrals()
    fields = ["id", "specialty", "urgency", "status", "sender", "assigned_to", "created_at"]
    return jsonify([{k: r.get(k) for k in fields} for r in referrals])


@app.route("/send", methods=["POST"])
def send_message():
    data = request.json
    sender = data.get("sender", "Dr. You")
    text = data.get("text", "").strip()
    reply_to = data.get("reply_to")  # id of message being replied to, or None

    if not text:
        return jsonify({"error": "empty message"}), 400

    user_msg = _new_message(sender, text, msg_type="user", reply_to=reply_to)

    # --- Is this a reply to a tracked referral? Walk the lifecycle:
    # PENDING -> ACKNOWLEDGED -> COMPLETED. Only the assigned specialist can
    # advance it; anyone else gets a routing reminder instead of silently
    # doing nothing (or, worse, being treated as a real new message). ---
    if reply_to:
        referral = get_referral_by_message(CHAT_ID, reply_to)
        if referral:
            status = referral["status"]

            if status == "COMPLETED":
                _new_message(
                    "Agent",
                    f"ℹ️ Referral #{referral['id']} is already marked COMPLETED - no action needed.",
                    msg_type="bot",
                    reply_to=user_msg["id"],
                )
                return jsonify({"ok": True})

            if sender != referral["assigned_to"]:
                # Only the assigned specialist can move a referral forward -
                # not the requester, and not an uninvolved third party.
                who = "you're the requester" if sender == referral["sender"] else "you're not the assigned specialist"
                _new_message(
                    "Agent",
                    f"⚠️ Referral #{referral['id']} is routed to {referral['assigned_to']}. "
                    f"Only they can update it - {who}.",
                    msg_type="bot",
                    reply_to=user_msg["id"],
                )
                return jsonify({"ok": True})

            if status == "PENDING":
                acknowledge_referral(referral["id"])
                _new_message(
                    "Agent",
                    f"✅ Referral #{referral['id']} acknowledged by {sender}. Reply again once it's done.",
                    msg_type="bot",
                    reply_to=user_msg["id"],
                )
                return jsonify({"ok": True})

            if status == "ACKNOWLEDGED":
                complete_referral(referral["id"])
                _new_message(
                    "Agent",
                    f"🏁 Referral #{referral['id']} marked COMPLETED by {sender}.",
                    msg_type="bot",
                    reply_to=user_msg["id"],
                )
                return jsonify({"ok": True})

    # --- Otherwise, run extraction ---
    extracted = extract_referral(text)

    if extracted["is_referral"]:
        assigned_to = resolve_assigned_to(extracted["specialty"])
        referral_id = add_referral(
            extracted, text, sender=sender, assigned_to=assigned_to,
            chat_id=CHAT_ID, message_id=user_msg["id"]
        )
        confirmation = (
            f"📋 Referral #{referral_id} logged → routed to {assigned_to}\n"
            f"{extracted['specialty'] or 'Specialty not specified'} • {extracted['urgency']}"
        )
        bot_msg = _new_message("Agent", confirmation, msg_type="bot", reply_to=user_msg["id"])
        # Track the confirmation's own id too, in case someone replies to THAT
        # instead of the original message - a reply to either now resolves.
        set_nudge_message_id(referral_id, bot_msg["id"])
        register_referral_message(CHAT_ID, bot_msg["id"], referral_id, role="confirmation")

    return jsonify({"ok": True})


def background_nudge_loop():
    """Runs forever in a background thread, checking for overdue referrals."""
    while True:
        time.sleep(BACKGROUND_CHECK_INTERVAL)

        overdue = get_overdue_urgent_referrals(minutes_threshold=0)
        for referral in overdue:
            if referral["chat_id"] != CHAT_ID:
                continue
            age_seconds = _seconds_since(referral["created_at"])

            if age_seconds >= ESCALATE_AFTER_SECONDS:
                # Only escalate once - check we haven't already
                already_escalated = any(
                    m.get("reply_to") == referral["message_id"] and "Escalation" in m["text"]
                    for m in messages
                )
                if not already_escalated:
                    text = build_escalation_message(referral)
                    escalation_msg = _new_message("Agent", text, msg_type="bot", reply_to=referral["message_id"])
                    register_referral_message(CHAT_ID, escalation_msg["id"], referral["id"], role="escalation")

            elif age_seconds >= NUDGE_AFTER_SECONDS:
                already_nudged = any(
                    m.get("reply_to") == referral["message_id"] and "Reminder" in m["text"]
                    for m in messages
                )
                if not already_nudged:
                    text = build_nudge_message(referral)
                    nudge_msg = _new_message("Agent", text, msg_type="bot", reply_to=referral["message_id"])
                    register_referral_message(CHAT_ID, nudge_msg["id"], referral["id"], role="nudge")


def _seconds_since(iso_timestamp: str) -> float:
    then = datetime.fromisoformat(iso_timestamp)
    return (datetime.now() - then).total_seconds()


if __name__ == "__main__":
    init_db()
    bg_thread = threading.Thread(target=background_nudge_loop, daemon=True)
    bg_thread.start()
    print(f"Demo running. Nudges fire after {NUDGE_AFTER_SECONDS}s, escalation after {ESCALATE_AFTER_SECONDS}s.")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=False, port=5000)