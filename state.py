"""
Phase 2: State Tracking
Stores each extracted referral and tracks its status:
PENDING -> ACKNOWLEDGED -> COMPLETED

Uses local SQLite for now - swap to Supabase later without changing
the functions below, just the connection logic.
"""

import sqlite3
from datetime import datetime, timedelta

DB_PATH = "referrals.db"


def init_db():
    """Creates the referrals table if it doesn't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_message TEXT NOT NULL,
            specialty TEXT,
            urgency TEXT,
            reason TEXT,
            patient_context TEXT,
            status TEXT DEFAULT 'PENDING',
            sender TEXT,
            assigned_to TEXT,
            created_at TEXT NOT NULL,
            acknowledged_at TEXT,
            chat_id TEXT,
            message_id INTEGER,
            nudge_message_id INTEGER
        )
    """)
    # Link table: every message that represents a given referral (the
    # original request, the confirmation, the nudge, the escalation - any
    # of them) gets registered here. A reply to ANY of these resolves back
    # to the same referral, instead of only the original message working.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referral_messages (
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            referral_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (chat_id, message_id)
        )
    """)
    conn.commit()
    conn.close()


def register_referral_message(chat_id: str, message_id: int, referral_id: int, role: str):
    """
    Registers a message (original / confirmation / nudge / escalation) as
    belonging to a referral, so a reply to it resolves back correctly.
    Call this every time a new message about an existing referral is sent.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT OR REPLACE INTO referral_messages (chat_id, message_id, referral_id, role)
        VALUES (?, ?, ?, ?)
        """,
        (chat_id, message_id, referral_id, role),
    )
    conn.commit()
    conn.close()


def add_referral(extracted: dict, raw_message: str, sender: str = "unknown",
                  assigned_to: str = "Unassigned",
                  chat_id: str = None, message_id: int = None) -> int:
    """
    Inserts a new referral from extraction output. Only call this when
    extracted['is_referral'] is True.
    sender = who requested it. assigned_to = the specialist it was routed to.
    These must stay distinct - a requester replying to their own referral
    is NOT the same as the assigned specialist acknowledging it.
    chat_id/message_id are the Telegram identifiers needed to reply in-thread later.
    Returns the new referral's id.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        INSERT INTO referrals (raw_message, specialty, urgency, reason, patient_context, status, sender, assigned_to, created_at, chat_id, message_id)
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?)
        """,
        (
            raw_message,
            extracted.get("specialty", ""),
            extracted.get("urgency", "unclear"),
            extracted.get("reason", ""),
            extracted.get("patient_context", ""),
            sender,
            assigned_to,
            datetime.now().isoformat(),
            chat_id,
            message_id,
        ),
    )
    conn.commit()
    referral_id = cursor.lastrowid
    conn.close()

    # Register the original message in the link table too, so lookups can
    # go through one consistent path regardless of which message a reply
    # lands on.
    if chat_id is not None and message_id is not None:
        register_referral_message(chat_id, message_id, referral_id, role="original")

    return referral_id


def get_referral_by_message(chat_id: str, message_id: int) -> dict:
    """
    Looks up a referral by ANY message tied to it - the original request,
    the confirmation, a nudge, or an escalation - used to match a reply
    back to the right referral no matter which message it's a reply to.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT referrals.* FROM referrals
        JOIN referral_messages
          ON referral_messages.referral_id = referrals.id
        WHERE referral_messages.chat_id = ? AND referral_messages.message_id = ?
        """,
        (chat_id, message_id),
    ).fetchone()

    if row is None:
        # Fallback for rows created before the link table existed (their
        # original message was never backfilled into referral_messages).
        row = conn.execute(
            "SELECT * FROM referrals WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id),
        ).fetchone()

    conn.close()
    return dict(row) if row else None


def set_nudge_message_id(referral_id: int, nudge_message_id: int):
    """Stores the message ID of the nudge itself, in case someone replies to the nudge instead of the original."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE referrals SET nudge_message_id = ? WHERE id = ?",
        (nudge_message_id, referral_id),
    )
    conn.commit()
    conn.close()


def acknowledge_referral(referral_id: int):
    """Marks a referral as ACKNOWLEDGED - call this when a reply/reaction is detected on its thread."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE referrals SET status = 'ACKNOWLEDGED', acknowledged_at = ? WHERE id = ?",
        (datetime.now().isoformat(), referral_id),
    )
    conn.commit()
    conn.close()


def complete_referral(referral_id: int):
    """Marks a referral as COMPLETED."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE referrals SET status = 'COMPLETED' WHERE id = ?", (referral_id,))
    conn.commit()
    conn.close()


def get_overdue_urgent_referrals(minutes_threshold: int = 30) -> list[dict]:
    """
    Returns urgent referrals still PENDING past the threshold.
    This is what Phase 3's nudge logic will call.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now() - timedelta(minutes=minutes_threshold)).isoformat()
    rows = conn.execute(
        """
        SELECT * FROM referrals
        WHERE status = 'PENDING' AND urgency = 'urgent' AND created_at < ?
        """,
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_referrals() -> list[dict]:
    """Returns every referral, most recent first - useful for a dashboard/demo view."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM referrals ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    # Quick manual test - run this file directly to sanity check the DB logic
    init_db()

    fake_extraction = {
        "is_referral": True,
        "specialty": "cardiology",
        "urgency": "urgent",
        "reason": "chest pain",
        "patient_context": "",
    }
    new_id = add_referral(fake_extraction, "bhai isko cardiology bhej do urgent hai", sender="Dr. A")
    print(f"Created referral #{new_id}")

    print("\nAll referrals:")
    for r in get_all_referrals():
        print(r)

    print("\nOverdue urgent referrals (0 min threshold, so this one should show up):")
    for r in get_overdue_urgent_referrals(minutes_threshold=0):
        print(r)

    acknowledge_referral(new_id)
    print(f"\nAcknowledged referral #{new_id}")

    print("\nOverdue urgent referrals now (should be empty - it's acknowledged):")
    for r in get_overdue_urgent_referrals(minutes_threshold=0):
        print(r)

        #.\.venv\Scripts\Activate.ps1