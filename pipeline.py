"""
Connects Phase 1 (extraction) + Phase 2 (state tracking).
Runs each fake message through extraction, and only stores it
as a referral in the DB if is_referral is True.
"""

import time
from extract import extract_referral
from state import init_db, add_referral, get_all_referrals
from fake_referrals import FAKE_MESSAGES

DELAY_SECONDS = 5

if __name__ == "__main__":
    init_db()

    print("Running full pipeline: extract -> store...\n")
    for i, msg in enumerate(FAKE_MESSAGES, 1):
        extracted = extract_referral(msg)

        if extracted["is_referral"]:
            referral_id = add_referral(extracted, msg, sender=f"Dr. Test{i}")
            print(f"[{i}] STORED as referral #{referral_id}: {extracted['specialty']} / {extracted['urgency']}")
        else:
            print(f"[{i}] SKIPPED (not a referral): \"{msg[:50]}...\"")

        if i < len(FAKE_MESSAGES):
            time.sleep(DELAY_SECONDS)

    print("\n--- Final referrals table ---")
    for r in get_all_referrals():
        print(f"#{r['id']} | {r['specialty']} | {r['urgency']} | {r['status']} | {r['reason']}")