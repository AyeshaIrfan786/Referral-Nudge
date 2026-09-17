"""
Fake referral messages for testing extraction.
Mix of clean, messy, mixed-language, and ambiguous cases —
real doctors won't type clean structured input, so test against this reality.
"""

FAKE_MESSAGES = [
    # Clean-ish, clearly urgent
    "Need urgent cardiology referral for patient at XYZ hospital. Any cardiologist available?",

    # Roman Urdu / English mix, urgent
    "bhai isko cardiology bhej do urgent hai, chest pain patient hai",

    # Casual, no explicit urgency keyword but implied
    "42M, severe headache since morning, need neuro opinion. Islamabad based.",

    # Very short, ambiguous urgency
    "any ortho free today? knee patient",

    # Explicit STAT keyword
    "STAT referral needed - suspected stroke, 65F, symptoms started 20 min ago",

    # Routine, explicitly non-urgent
    "routine derm referral whenever someone's free, skin rash, not urgent at all",

    # Reply that should count as acknowledgment (test this separately in state logic)
    "haan main dekh leta hoon isko",

    # Ambiguous - vague acknowledgment, should NOT auto-count as acknowledged
    "acha thek hai dekhta hun",

    # No specialty stated clearly - test extraction robustness
    "patient needs specialist opinion, unsure which one, symptoms: fatigue, weight loss, fever",

    # Multiple patients in one message
    "two referrals needed - 1) pediatric case, fever 3 days 2) ortho case, fracture suspected, both at DHQ",

    # Emergency keyword variant
    "EMERGENCY - need immediate cardiology, patient collapsed",

    # Very casual/short with location
    "gyno chahiye jaldi, Rawalpindi General",

    # Non-referral message (should be ignored/filtered out)
    "good morning everyone, hope you all had a great weekend",

    # Non-referral but healthcare-adjacent (should NOT be extracted as a referral)
    "reminder: staff meeting at 5pm today",

    # Urgent but poorly worded
    "URGENT!!! need someone NOW for cardiac patient, situation critical",
]

if __name__ == "__main__":
    for i, msg in enumerate(FAKE_MESSAGES, 1):
        print(f"{i}. {msg}")