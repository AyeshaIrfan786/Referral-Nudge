# Referral Nudge Agent

An AI agent that watches a doctors' group chat, automatically extracts patient referral requests from messy real-world messages (including mixed Roman Urdu/English), tracks each referral's status, and **nudges** — then **escalates** — when an urgent referral goes unanswered for too long.

Built in phases: extraction → state tracking → nudge/escalation logic → a live chat demo UI.

## The problem

In busy hospital/clinic group chats, referral requests get buried under normal conversation. An urgent case ("bhai isko cardiology bhej do urgent hai") can sit unanswered for a long time simply because it scrolled off screen. This agent reads every message, decides whether it's actually a referral, tracks whether anyone acknowledged it, and proactively reminds (and escalates) if it's still pending past a safe threshold.

## How it works

The pipeline has four stages, each in its own module:

1. **Extract** (`extract.py`) — Sends the raw chat message to Google's Gemini (`gemini-flash-lite-latest`) with a strict JSON schema and system prompt. Gemini decides:
   - `is_referral`: is this actually a referral request, or just chatter/greetings?
   - `specialty`: the medical specialty needed
   - `urgency`: `urgent`, `routine`, or `unclear` — based only on explicit language in the message, never inferred medical severity
   - `reason`: the clinical reason, exactly as stated (never guessed or invented)
   - `patient_context`: any age/sex/location/hospital details mentioned

2. **State** (`state.py`) — Persists every referral to a local SQLite database (`referrals.db`) with a status of `PENDING` → `ACKNOWLEDGED` → `COMPLETED`. Also tracks which chat message and reply-thread each referral belongs to, so a doctor replying to the original message (or to the agent's own confirmation/nudge) correctly marks it acknowledged.

3. **Nudge** (`nudge.py`) — Periodically checks for urgent referrals still `PENDING` past a threshold and builds a reminder message. If a nudge also goes unanswered, it builds an escalation message addressed to a backup/on-call contact.

4. **Demo app** (`app.py` + `templates/index.html`) — A local Flask web app that simulates a WhatsApp/Telegram-style group chat in the browser, running the exact same extract → state → nudge logic behind a background thread. This avoids any real messaging platform's network, approval, or ban risk while demoing the full flow live, with short (seconds-scale) thresholds so nudges/escalations are visible without waiting.

## Project structure

```
Agents/
├── app.py              # Flask demo app: simulated chat UI + background nudge loop
├── extract.py           # Phase 1 - Gemini-powered extraction (run directly to test)
├── state.py              # Phase 2 - SQLite persistence and status tracking
├── nudge.py             # Phase 3 - overdue detection + nudge/escalation message builders
├── pipeline.py          # Connects extraction + state: runs fake messages end-to-end
├── fake_referrals.py    # Realistic, messy sample messages used for testing
├── templates/
│   └── index.html       # Chat UI for the Flask demo
├── requirements.txt
└── .envexample                 
```

## Setup

### Requirements
- Python 3.10+
- A [Google AI Studio](https://aistudio.google.com/) API key for Gemini

### Installation

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
pip install -r requirements.txt
```

### Configure your API key

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

> **Important:** `.env` contains your secret API key. Make sure it's listed in `.gitignore` and never pushed to GitHub — see [Before you push](#before-you-push) below.

## Usage

### Run the interactive demo (recommended)

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. Type messages as if you were in the doctors' group chat. Referral messages get automatically detected and logged; reply to a referral message to acknowledge it. If an urgent referral goes unanswered, the agent posts a reminder after 20 seconds and an escalation after 40 seconds (tuned short for demo purposes — see `NUDGE_AFTER_SECONDS` / `ESCALATE_AFTER_SECONDS` in `app.py`).

### Test extraction alone

Runs every message in `fake_referrals.py` through the Gemini extractor and prints the structured output:

```bash
python extract.py
```

### Run the full extract → store pipeline

```bash
python pipeline.py
```

### Test nudge logic against the stored database

```bash
python nudge.py
```

### Inspect/reset the database directly

```bash
python state.py
```

## Configuration

| Setting | File | Default | Purpose |
|---|---|---|---|
| `NUDGE_AFTER_SECONDS` / `ESCALATE_AFTER_SECONDS` | `app.py` | 20s / 40s | Demo-friendly thresholds for the live web UI |
| `FIRST_NUDGE_MINUTES` / `ESCALATE_MINUTES` | `nudge.py` | 30 / 45 min | Real-world thresholds for production use |
| `BACKUP_CONTACT` | `nudge.py` | `"Dr. Senior (on-call supervisor)"` | Who gets the escalation |
| `model_name` | `extract.py` | `gemini-flash-lite-latest` | Gemini model used for extraction |


## Tech stack

- **Gemini API** (`google-generativeai`) — structured extraction with a JSON schema
- **Flask** — local demo web server
- **SQLite** — lightweight local persistence (swappable for Supabase/Postgres later without changing the `state.py` function signatures)
- **python-telegram-bot** — included for a future real Telegram integration (the current demo runs entirely locally instead)

## Roadmap / possible next steps

- Wire `nudge.py`'s scheduler into a real Telegram or WhatsApp bot (the `python-telegram-bot` dependency is already in place)
- Swap SQLite for a hosted database (Supabase/Postgres) for multi-user deployments
- Add a dashboard view over `get_all_referrals()` for at-a-glance status across all referrals
- Support acknowledgment via emoji reaction, not just replies


