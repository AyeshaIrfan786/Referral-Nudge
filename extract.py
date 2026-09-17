"""
Phase 1: Extraction
Takes a raw, messy chat message and turns it into structured referral data.

Run this file directly to test extraction against all fake messages.
"""

import os
import json
import time
from dotenv import load_dotenv
import google.generativeai as genai

from fake_referrals import FAKE_MESSAGES

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- Schema Gemini must follow ---
# is_referral: false for non-referral chatter (greetings, reminders, etc.)
# urgency: derived from explicit keywords + context, not a blind guess
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_referral": {
            "type": "boolean",
            "description": "True only if this message is actually a patient referral request. False for greetings, reminders, or unrelated chat.",
        },
        "specialty": {
            "type": "string",
            "description": "Medical specialty needed (e.g. cardiology, neurology, ortho). Empty string if not stated or not a referral.",
        },
        "urgency": {
            "type": "string",
            "enum": ["urgent", "routine", "unclear"],
            "description": "urgent if explicit urgency language is used (urgent, STAT, emergency, immediate, critical, collapsed, etc). routine if explicitly stated as not urgent / whenever. unclear if urgency isn't indicated either way.",
        },
        "reason": {
            "type": "string",
            "description": "The clinical reason EXACTLY as stated or directly quoted from the message (e.g. chest pain, headache, fracture). Leave as an empty string if no specific reason/symptom was mentioned - do NOT infer, guess, or add a possible clinical reason that wasn't stated.",
        },
        "patient_context": {
            "type": "string",
            "description": "Any patient details mentioned - age, sex, location, hospital. Empty string if none given.",
        },
    },
    "required": ["is_referral", "specialty", "urgency", "reason", "patient_context"],
}

SYSTEM_INSTRUCTION = """You extract structured data from doctor referral group chat messages.
These messages are informal, sometimes mixed Roman Urdu/English, and often incomplete.
Only mark is_referral=true if the message is actually asking for a specialist/referral for a patient.
Do not diagnose or add clinical judgment beyond what's stated in the message.
Never invent or guess a reason/symptom that wasn't explicitly mentioned - if no reason is given, leave that field empty rather than filling it with a plausible-sounding guess.
Urgency must be based on explicit language in the message, not inferred medical severity."""

model = genai.GenerativeModel(
    model_name="gemini-flash-lite-latest",
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": EXTRACTION_SCHEMA,
    },
)


def extract_referral(message: str) -> dict:
    """Takes a raw chat message, returns structured referral data as a dict."""
    response = model.generate_content(message)
    return json.loads(response.text)


if __name__ == "__main__":
    print("Testing extraction against all fake messages...\n")
    # Flash-Lite free tier allows more requests/min than the full model - 5s is a safe gap.
    DELAY_SECONDS = 5
    for i, msg in enumerate(FAKE_MESSAGES, 1):
        result = extract_referral(msg)
        print(f"--- Message {i} ---")
        print(f"Raw: {msg}")
        print(f"Extracted: {json.dumps(result, indent=2)}")
        print()
        if i < len(FAKE_MESSAGES):
            time.sleep(DELAY_SECONDS)