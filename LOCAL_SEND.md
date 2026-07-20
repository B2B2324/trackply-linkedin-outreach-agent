# Local send test — run Maya's sends from your own IP

**Why this exists.** As of the 2026-07-19 run, every connection-request write
returns `401` from **both** the current (`verifyQuotaAndCreateV2`) and legacy
(`normInvitations`) endpoints, while every read (`/feed/`, `/me`, profile
lookup) returns `200`, and you can send connection requests **manually** from
your browser. Reads pass from anywhere; manual writes pass; only the agent's
writes fail. The common factor in the failures is the **egress IP** — Railway's
datacenter IP, and Apify's proxy exits. This test removes that variable by
sending directly from your laptop's IP.

- **200/201** → LinkedIn accepts writes from your home IP. The block was the
  cloud IP. Keep sending locally (`SENDER_MODE=local`) or find a residential
  Apify proxy LinkedIn trusts.
- **401** → writes are refused from your IP too. Then it is **not** an IP
  problem — it's account/session level, and no proxy change fixes it. Stop
  changing endpoint code and deal with the LinkedIn account.

Run this on the **same machine + browser** where manual connection requests
work. It sends from that machine's IP, which is the whole point.

---

## 1. Create a `.env` (never commit it — already gitignored)

Copy these values out of the **Railway** dashboard → Maya service → Variables.
They live only there; there is no `.env` in the repo yet.

```
LINKEDIN_LI_AT=<li_at cookie value>
LINKEDIN_JSESSIONID=<JSESSIONID value, WITHOUT the surrounding quotes>
LINKEDIN_CSRF_TOKEN=<csrf-token value>          # optional for local; derived from JSESSIONID
LINKEDIN_OWN_PROFILE_URL=<your own profile url>
SUPABASE_URL=https://vglfaviliadxevfillbb.supabase.co
SUPABASE_SERVICE_KEY=<service key>
APIFY_TOKEN=<apify token>                        # only needed if you also run discovery
ANTHROPIC_API_KEY=<key>                          # only needed for personalization
SENDER_MODE=local
```

Minimum for the **single-shot test** below: just `LINKEDIN_LI_AT` and
`LINKEDIN_JSESSIONID`. The full list is only needed for a complete
discover→personalize→send run.

> Cookies rotate. If you re-set them in the browser, re-copy `li_at` and
> `JSESSIONID` here. Strip the quotes LinkedIn wraps around `JSESSIONID`.

## 2. Install deps (once)

```
cd trackply-linkedin-outreach-agent
python -m venv .venv
.venv\Scripts\activate          # PowerShell
pip install -r requirements.txt
pip install python-dotenv       # so .env loads in the test script
```

## 3. The decisive one-request test (do this first)

Sends exactly **one** real connection request from your IP. Nothing touches
Supabase. Pick any profile you haven't already connected with:

```
python test_local_send.py https://www.linkedin.com/in/<someone>
```

Read the last line it prints. That single result answers the IP question.

## 4. If the one-shot works: a full local run

With `SENDER_MODE=local` in `.env`, the normal runner now sends locally and
still logs to the same Supabase your dashboard reads:

```
python -m src.runner --mode live
```

Watch progress in your **Agentic Labs dashboard** (`app.agenticlabs.com.mx`) —
sends land in `outreach_activity` / `linkedin_leads` in the shared Supabase
exactly as a Railway run would. Only the trigger moves to your laptop; the
monitoring stays where it is.

> **The dashboard "go" button will NOT work for this test.** That button hits
> the Railway backend, which egresses from Railway's cloud IP — the same class
> of IP that's being blocked. To test the IP theory the send must originate
> from your laptop, i.e. the CLI commands above. Trigger locally, monitor in
> the dashboard.

## How it works (for later you)

`SENDER_MODE` (in `src/nodes.py::_live_send`) switches egress:
- `apify` (default) → `src/apify_sender.py`, the owned actor on Apify's IP.
- `local` → `src/local_sender.py`, direct from this machine.

`src/local_sender.py` is a Python port of `apify-actor/main.js`, carrying the
three details that make voyager writes succeed: `/feed/` warmup with manual
Set-Cookie merging, csrf-token re-derived from the live JSESSIONID cookie
(never the env var), and same-origin XHR write headers. The old
`src/linkedin_sender.py` lacked all three and is left untouched.

Nothing about the Apify path changed. `SENDER_MODE` unset = old behaviour.
