# Private Finance Agent — End-to-End Test Plan

Companion to `agentic-expense-tracker-plan.md`. Manual test pass over
`private-finance-agent-v1`. Automated unit coverage already exists under
`backend/tests/` — this plan is for the flows those don't reach (HTTP layer,
UI, cross-service wiring, live Ollama/Gmail).

Back up `backend/data/finance.db` before this pass — `pytest` in this repo
reseeds that same file and will wipe it.

## 0. Running the app end-to-end

Three processes, in this order: local model → backend → frontend.

### 0.1 Local model (Ollama)

```bash
ollama pull qwen3:8b        # or any other tool-capable local model
ollama serve                # if not already running as a background service
```

`ollama serve` erroring with `address already in use` on port `11434` just
means it's already running (e.g. as a launchd/system service) — that's fine,
skip straight to the check below.

Confirm it's reachable: `curl http://127.0.0.1:11434/api/tags`.

Optional — use a different model:

```bash
export FINANCE_OLLAMA_MODEL=<your-local-model>
export FINANCE_OLLAMA_CATEGORIZER_MODEL=<a-smaller-model>   # optional, per-transaction categorization
```

### 0.2 Backend

```bash
cd backend
python -m venv .venv          # first time only
source .venv/bin/activate
pip install -e ".[dev]"       # first time only, or after dependency changes
uvicorn app.main:app --reload --port 8000
```

Leave this running. Verify with `curl http://localhost:8000/api/health`.

For section 2 (Gmail import), also complete the one-time OAuth setup in
**2.0** before starting the backend, and set `FINANCE_GMAIL_QUERY` if you
want to scope the sync to your own bank's sender address.

### 0.3 Frontend

In a second terminal:

```bash
cd frontend
npm install       # first time only, or after package.json changes
npm run dev
```

Open `http://localhost:5173` — the dashboard talks to the backend on
`localhost:8000`. Both the backend and frontend dev servers need to stay up
for the rest of this plan; the chat agent (section 5) additionally needs
Ollama running.

## 1. CSV import (fallback path)

| Step | Action | Expected |
|---|---|---|
| 1.1 | Upload `sample_transactions.csv` via "Import CSV" | Success banner with inserted/skipped counts; dashboard totals update |
| 1.2 | Re-upload the same file | `skipped_duplicates` equals the row count; `inserted` is 0 (dedup by `source_id` hash) |
| 1.3 | Upload a `.csv` missing the `category` column | HTTP 422, clear "Missing required columns" message, no partial insert |
| 1.4 | Upload a non-`.csv` file | HTTP 400, rejected before parsing |

## 2. Gmail import (primary path)

### 2.0 One-time OAuth setup

1. At [console.cloud.google.com](https://console.cloud.google.com), sign in with the
   Gmail account to read from and create/select a project.
2. **APIs & Services → Library** → enable the **Gmail API**.
3. **APIs & Services → OAuth consent screen** → User type **External** → fill in
   app name and contact email → add scope `https://www.googleapis.com/auth/gmail.readonly`
   → add your own Gmail address as a **test user** (keeps the app in "Testing"
   status, no Google verification review needed for personal use).
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID** →
   Application type **Desktop app** (required — matches the local-server
   consent flow the script uses) → create → download the JSON.
5. Move that file to `backend/.secrets/gmail_credentials.json` (create the
   folder if missing; it's gitignored).
6. From `backend/` with the venv active: `python -m scripts.gmail_auth`.
   Browser opens → you'll likely see an "unverified app" warning (expected)
   → **Advanced → Go to [app name] (unsafe) → Continue** → grant read-only
   access. Saves `backend/.secrets/gmail_token.json`.
7. Optional: set `FINANCE_GMAIL_QUERY` (e.g. `from:alerts@hdfcbank.net`) to
   scope the sync to your bank's actual sender address.

Caveat: unverified "Testing" apps sometimes need re-consent (step 6 again)
after about a week — a Google-imposed limit, not app-specific.

| Step | Action | Expected |
|---|---|---|
| 2.1 | No token file present, click "Sync Gmail" | HTTP 428 with instructions to run `scripts.gmail_auth`; no crash |
| 2.2 | Run `scripts/gmail_auth.py`, complete consent | `backend/.secrets/gmail_token.json` written |
| 2.3 | Click "Sync Gmail" against a real inbox with HDFC alert emails | Response reports `scanned_emails`, `inserted`, `skipped_duplicates`, `unparsed_emails`; matching emails appear as transactions with `source: "gmail"` |
| 2.4 | Sync again immediately | Same emails now show up as `skipped_duplicates` (dedup by `gmail:<message-id>`), `inserted` is 0 |
| 2.5 | Inbox has a transaction email from an unsupported bank/format | Counted in `unparsed_emails`, not silently dropped as an error, not inserted as garbage |
| 2.6 | Inspect a newly imported Gmail transaction's category | Category is auto-assigned (rule match, or model fallback if Ollama is running) — never blank |
| 2.7 | Revoke/expire the token (or corrupt `gmail_token.json`) and sync | Clear auth error surfaced to the UI, not a raw 500 |

## 3. Dashboard / summary

| Step | Action | Expected |
|---|---|---|
| 3.1 | Load the dashboard after imports | Spending/income/net/transaction-count metrics match `GET /api/summary/{year}/{month}` for the current period shown |
| 3.2 | Check category breakdown bars | Each bar's width is proportional to spend; sums match the category totals in the summary response |
| 3.3 | Check recent transactions list | Newest-first, amounts formatted in INR, debit shown as `−`, credit as `+` |

## 4. Budgets

| Step | Action | Expected |
|---|---|---|
| 4.1 | Set a budget for a category with no prior budget | `POST /api/budgets` succeeds; category now shows a progress bar against spend |
| 4.2 | Set the same category again with a new amount | Amount updates (upsert), no duplicate row |
| 4.3 | Spend exceeds the set budget | `over_budget: true` in `/api/budgets/status/{year}/{month}`; UI shows the category in the debit color |
| 4.4 | Category with no budget set | `budget`/`remaining`/`over_budget` are `null`; no progress bar rendered, no crash |

## 5. Chat agent (requires Ollama running with a tool-capable model)

| Step | Action | Expected |
|---|---|---|
| 5.1 | Ask "How much did I spend on Food this month?" | Agent calls `aggregate_spending` or `get_month_summary`; answer matches actual data; trace shows the tool call(s) |
| 5.2 | Ask "Compare my dining spend to last month" | `compare_months` called; percentage change in the answer matches `change_percent` |
| 5.3 | Ask "Any recurring charges I should know about?" | `detect_recurring` called; matches Watcher's recurring findings |
| 5.4 | Ask "Anything I should worry about this month?" | Agent checks `get_recent_insights` (system prompt rule 10) before answering broad review questions |
| 5.5 | Stop Ollama, then send a chat message | HTTP 503 with a clear "could not reach local Ollama" message, not a hang or stack trace |
| 5.6 | Ask something requiring 6+ tool calls to fully resolve | Agent stops at the step limit and returns a partial-answer message rather than looping forever |

## 6. Budget-change proposal + human confirmation

| Step | Action | Expected |
|---|---|---|
| 6.1 | Ask the agent to "increase my Food budget to 8000" | `propose_budget_change` called; response has `requires_confirmation: true`; **no budget is changed yet** — verify via `GET /api/budgets` |
| 6.2 | Click **Confirm** on the proposal card | `POST /api/budgets` fires with the proposed values; budget updates; dashboard refreshes |
| 6.3 | Click **Dismiss** on a different proposal | Card disappears; `GET /api/budgets` confirms nothing changed |

## 7. Watcher / insights

| Step | Action | Expected |
|---|---|---|
| 7.1 | Click "Scan now" with an unusually large transaction and a repeated merchant+amount present | New `anomaly` and/or `recurring` rows appear in the insights panel |
| 7.2 | Click "Scan now" again immediately | No duplicate insights (dedup by `dedup_key`); `new_insights` empty in the response |
| 7.3 | Click "Resolve" on an insight | Row disappears from the default (`unresolved_only=true`) view; `GET /api/insights?unresolved_only=false` still shows it, marked resolved |
| 7.4 | Leave the app running past the scheduled hour (`FINANCE_WATCHER_HOUR`, default 2am) | Nightly APScheduler job runs unattended and produces the same result as a manual scan |

## 8. Privacy checks

| Step | Action | Expected |
|---|---|---|
| 8.1 | Capture network traffic during a chat session (no Gmail sync) | Only traffic to `127.0.0.1:11434` (Ollama) — nothing else outbound |
| 8.2 | Capture network traffic during a Gmail sync | Traffic to `gmail.googleapis.com`/Google OAuth only, plus Ollama for categorization — no other destinations |
| 8.3 | Inspect a chat tool-trace response in the browser | `account_last4` and `source_id` fields read `[REDACTED]`, never the real values |
| 8.4 | Ask the agent to reveal an account number or source id | Agent cannot, since the value never reached its context |

## 9. Cross-cutting error handling

| Step | Action | Expected |
|---|---|---|
| 9.1 | Request `/api/summary/2026/13` (invalid month) | HTTP 422, not a 500 |
| 9.2 | Resolve a non-existent insight id | HTTP 404 |
| 9.3 | `POST /api/budgets` with a negative `new_amount` | Rejected by validation (`ge=0`), HTTP 422 |
| 9.4 | Any unknown tool name reaching `OllamaAgent` (simulate via a malformed model response) | Raises `AgentError` → HTTP 503, fails closed rather than executing |
