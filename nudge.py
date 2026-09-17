"""
Phase 3: Stall Detection + Nudge Logic

Checks for urgent referrals that have been PENDING too long, and generates
a nudge. Escalates to a backup contact if a second nudge also goes unanswered.

For now, nudges are just printed/logged - Phase 4 wires this into a real
Telegram/WhatsApp send.
"""

from datetime import datetime
from state import init_db, get_overdue_urgent_referrals, get_all_referrals

# --- Config (tune these for your demo) ---
FIRST_NUDGE_MINUTES = 30   # nudge the assigned doctor after this long
ESCALATE_MINUTES = 45      # escalate to backup contact if still unanswered

BACKUP_CONTACT = "Dr. Senior (on-call supervisor)"


def _elapsed_label(referral: dict) -> str:
    """Real elapsed time since the referral was created, formatted for humans."""
    created = datetime.fromisoformat(referral["created_at"])
    seconds = (datetime.now() - created).total_seconds()
    if seconds < 90:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)} min"


def check_and_nudge():
    """
    Call this periodically (e.g. every few minutes via a scheduler/cron).
    Returns a list of actions taken, for logging/demo purposes.
    """
    actions = []

    overdue = get_overdue_urgent_referrals(minutes_threshold=FIRST_NUDGE_MINUTES)
    for referral in overdue:
        nudge_msg = build_nudge_message(referral)
        actions.append({
            "type": "nudge",
            "referral_id": referral["id"],
            "target": referral["sender"],
            "message": nudge_msg,
        })

    escalate = get_overdue_urgent_referrals(minutes_threshold=ESCALATE_MINUTES)
    for referral in escalate:
        escalate_msg = build_escalation_message(referral)
        actions.append({
            "type": "escalate",
            "referral_id": referral["id"],
            "target": BACKUP_CONTACT,
            "message": escalate_msg,
        })

    return actions


def build_nudge_message(referral: dict) -> str:
    """The reminder sent to the specific doctor who hasn't responded yet."""
    return (
        f"Reminder: Referral #{referral['id']} ({referral['specialty']}, "
        f"{referral['reason'] or 'no reason specified'}) has been pending for "
        f"{_elapsed_label(referral)}. Please check when you can."
    )


def build_escalation_message(referral: dict) -> str:
    """The message sent to a backup contact if the first nudge went unanswered."""
    return (
        f"Escalation: Referral #{referral['id']} ({referral['specialty']}, "
        f"{referral['reason'] or 'no reason specified'}) is still pending after "
        f"{_elapsed_label(referral)}. Original recipient: {referral['sender']}. "
        f"Escalating to {BACKUP_CONTACT}."
    )


if __name__ == "__main__":
    init_db()
    print("Simulating stall check with 0-minute threshold (for testing)...\n")
    all_referrals = get_all_referrals()
    urgent_pending = [r for r in all_referrals if r["status"] == "PENDING" and r["urgency"] == "urgent"]

    if not urgent_pending:
        print("No urgent+pending referrals found. Run pipeline.py first to populate the DB.")
    else:
        for referral in urgent_pending:
            print(build_nudge_message(referral))