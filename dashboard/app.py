from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from supabase import create_client, Client

# Make src/ importable when running from Streamlit Cloud (repo root is cwd)
_repo_root = Path(__file__).parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

st.set_page_config(page_title="Trackply Marketing OS", layout="wide")

# ── Secrets helper ───────────────────────────────────────────────────────────
def _secret(key: str, fallback: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, fallback)

# ── Supabase connections ─────────────────────────────────────────────────────
SUPABASE_URL = "https://vglfaviliadxevfillbb.supabase.co"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZnbGZhdmlsaWFkeGV2ZmlsbGJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg1MjI4MjksImV4cCI6MjA5NDA5ODgyOX0"
    ".TC5tuxGXGom8TKjzsooYEdr7ZkKtSEHm3CXNHUO202g"
)

@st.cache_resource
def anon_client() -> Client:
    return create_client(SUPABASE_URL, ANON_KEY)

@st.cache_resource
def service_client() -> Client | None:
    key = _secret("SUPABASE_SERVICE_KEY")
    return create_client(SUPABASE_URL, key) if key else None


# ── Data fetching ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_stats() -> dict:
    try:
        row = anon_client().table("marketing_stats").select("*").execute().data
        return row[0] if row else {}
    except Exception as e:
        st.warning(f"Could not load stats: {e}")
        return {}

@st.cache_data(ttl=60)
def fetch_leads() -> list[dict]:
    sb = service_client()
    if not sb:
        return []
    try:
        return (
            sb.table("linkedin_leads")
            .select("name,headline,status,fit_score,date_sent,response_at,created_at")
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        ).data or []
    except Exception:
        return []

@st.cache_data(ttl=60)
def fetch_activity() -> list[dict]:
    sb = service_client()
    if not sb:
        return []
    try:
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        return (
            sb.table("outreach_activity")
            .select("agent,action,target,result,created_at")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        ).data or []
    except Exception:
        return []


# ── Agent runner ─────────────────────────────────────────────────────────────
def run_linkedin_agent(review_mode: bool = True) -> dict:
    """
    Import and invoke the LangGraph LinkedIn agent.
    Returns a dict with keys: success, leads_found, errors, log_lines.
    """
    log_lines: list[str] = []

    anthropic_key = _secret("ANTHROPIC_API_KEY")
    if not anthropic_key:
        return {"success": False, "errors": ["ANTHROPIC_API_KEY not set in Streamlit secrets."]}

    # Inject env vars — always overwrite so stale cached values from a
    # previous Streamlit session don't block fresh secret values.
    os.environ["ANTHROPIC_API_KEY"] = anthropic_key
    svc_key = _secret("SUPABASE_SERVICE_KEY")
    if svc_key:
        os.environ["SUPABASE_KEY"]         = svc_key
        os.environ["SUPABASE_SERVICE_KEY"] = svc_key
    os.environ["SUPABASE_URL"] = SUPABASE_URL
    for k in ("LINKEDIN_LI_AT", "LINKEDIN_JSESSIONID", "LINKEDIN_CSRF_TOKEN",
              "LINKEDIN_OWN_PROFILE_URL", "APIFY_TOKEN"):
        val = _secret(k)
        if val:
            os.environ[k] = val

    # Warn upfront if live-mode creds are incomplete (saves a full graph run)
    if not review_mode:
        missing_creds = [k for k in ("LINKEDIN_LI_AT", "LINKEDIN_JSESSIONID",
                                      "LINKEDIN_CSRF_TOKEN", "LINKEDIN_OWN_PROFILE_URL")
                         if not os.environ.get(k)]
        if missing_creds:
            return {"success": False, "errors": [
                f"Missing LinkedIn secrets: {', '.join(missing_creds)}. "
                "Go to Streamlit Cloud → Settings → Secrets and add them."
            ], "log_lines": []}

    try:
        from src.nodes import build_graph
        from src.campaign_config import load_campaign_config, default_config as config
        config["require_human_approval"] = review_mode
        config["review_mode"] = review_mode
        config["daily_limit"] = 80  # per dashboard run — match human pace

        initial_state = {
            "targets": [],
            "messages_sent_today": 0,
            "status": "active",
            "errors": [],
            "supabase_lead_ids": {},
        }

        graph = build_graph()
        final_state = graph.invoke(initial_state)

        leads_found = final_state.get("_leads_discovered", 0)
        errors      = final_state.get("errors", [])
        conn_used   = final_state.get("connection_requests_this_week", 0)
        send_log    = final_state.get("_send_log", [])

        log_lines.append(f"Leads discovered: {leads_found}")
        log_lines.append(f"Connection requests used this week: {conn_used}/{config.get('weekly_connection_limit', 20)}")
        if review_mode:
            log_lines.append("Review mode — messages drafted, NOT sent.")
        for entry in send_log:
            ol  = " [OpenLink]" if entry.get("ol") else ""
            log_lines.append(f"  • {entry['name']} ({entry['rel']}{ol}) → {entry['action']} [{entry['result']}]")
        if not send_log and not errors:
            log_lines.append("No leads were processed. Check errors below.")
        return {"success": True, "leads_found": leads_found, "errors": errors, "log_lines": log_lines}

    except Exception:
        return {"success": False, "errors": [traceback.format_exc()], "log_lines": log_lines}


# ── Reddit agent runner ──────────────────────────────────────────────────────
def run_reddit_agent(review_mode: bool = True) -> dict:
    """Invoke the Reddit engagement agent."""
    for k in ("ANTHROPIC_API_KEY", "XAI_API_KEY",
              "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
              "REDDIT_USERNAME", "REDDIT_PASSWORD"):
        val = _secret(k)
        if val:
            os.environ[k] = val
    svc_key = _secret("SUPABASE_SERVICE_KEY")
    if svc_key:
        os.environ["SUPABASE_KEY"]         = svc_key
        os.environ["SUPABASE_SERVICE_KEY"] = svc_key
    os.environ["SUPABASE_URL"] = SUPABASE_URL

    try:
        from src.reddit_agent import run_reddit_agent as _run
        return _run(review_mode=review_mode)
    except Exception:
        import traceback
        return {"success": False, "engagements": [], "threads_found": 0,
                "errors": [traceback.format_exc()]}


def _display_reddit_result(result: dict, live: bool) -> None:
    mode = "LIVE" if live else "review"
    if result["success"]:
        found = result.get("threads_found", 0)
        eng   = result.get("engagements", [])
        st.success(f"[{mode}] Reddit agent done — {found} threads found, {len(eng)} engagement(s) prepared.")
        for e in eng:
            action = "Posted" if e.get("posted") else "Drafted"
            st.markdown(f"**{action}** in r/{e.get('subreddit','?')} — [{e.get('title','?')[:60]}]({e.get('thread_url','')})")
            st.code(e.get("comment", ""), language=None)
        if result.get("errors"):
            with st.expander("Notes / non-fatal errors"):
                for err in result["errors"]:
                    st.text(err)
        st.cache_data.clear()
    else:
        st.error("Reddit agent run failed.")
        for err in result.get("errors", []):
            st.code(err)


# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.header("Agent Controls")

test_creds = st.sidebar.button("🔑 Test LinkedIn Credentials", help="Verify cookies are still valid before running")

run_linkedin = st.sidebar.button(
    "▶ Run LinkedIn (Review)", help="Draft messages — nothing is sent to LinkedIn"
)
run_linkedin_live = st.sidebar.button(
    "🚀 Run LinkedIn LIVE",
    type="primary",
    help="Sends real connection requests and DMs via LinkedIn API",
)
run_reddit = st.sidebar.button("▶ Run Reddit Engagement", help="Find Reddit threads and draft Kemba comments")
run_reddit_live = st.sidebar.button("🚀 Run Reddit LIVE", type="primary", help="Actually post Kemba comments to Reddit")
st.sidebar.button("▶ Run SEO Content", disabled=True)
st.sidebar.divider()

# Pre-flight status
with st.sidebar.expander("⚙️ Config status", expanded=True):
    for key, label in [
        ("LINKEDIN_LI_AT",          "li_at cookie"),
        ("LINKEDIN_JSESSIONID",     "JSESSIONID"),
        ("LINKEDIN_CSRF_TOKEN",     "CSRF token"),
        ("LINKEDIN_OWN_PROFILE_URL","Own profile URL"),
        ("APIFY_TOKEN",             "Apify token"),
        ("ANTHROPIC_API_KEY",       "Anthropic key"),
    ]:
        val = _secret(key)
        icon = "✅" if val else "❌"
        preview = (val[:6] + "…") if val else "MISSING"
        st.caption(f"{icon} {label}: `{preview}`")

if st.sidebar.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.rerun()

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🚀 Trackply Agentic Marketing OS")
st.caption("Live data from Trackply Supabase · auto-refreshes every 5 min · v2026-06-26")


def _display_run_result(result: dict, live: bool) -> None:
    if result["success"]:
        mode = "LIVE" if live else "review"
        leads = result.get('leads_found', 0)
        if leads == 0:
            st.warning(f"[{mode}] Agent finished — **0 leads processed**. See details below.")
        else:
            st.success(f"[{mode}] Agent finished — {leads} lead(s) processed.")
        for line in result.get("log_lines", []):
            st.text(line)
        if result.get("errors"):
            st.error("**Errors / warnings (expand to debug):**")
            for e in result["errors"]:
                st.code(e)
        st.cache_data.clear()
        if live:
            st.rerun()
    else:
        st.error("Agent run failed.")
        for err in result.get("errors", []):
            st.code(err)


# ── Test credentials ─────────────────────────────────────────────────────────
if test_creds:
    for k in ("LINKEDIN_LI_AT", "LINKEDIN_JSESSIONID", "LINKEDIN_CSRF_TOKEN", "LINKEDIN_OWN_PROFILE_URL"):
        val = _secret(k)
        if val:
            os.environ[k] = val

    missing = [k for k in ("LINKEDIN_LI_AT", "LINKEDIN_JSESSIONID", "LINKEDIN_CSRF_TOKEN", "LINKEDIN_OWN_PROFILE_URL") if not _secret(k)]
    if missing:
        st.error(f"Missing secrets: {', '.join(missing)}\n\nAdd them in Streamlit Cloud → Settings → Secrets.")
    else:
        with st.spinner("Testing LinkedIn cookies…"):
            try:
                from src.linkedin_sender import sender_from_env
                import requests
                sender = sender_from_env()
                if not sender:
                    st.error("Could not build LinkedIn session — check secrets.")
                else:
                    r = sender.session.get(
                        "https://www.linkedin.com/voyager/api/me",
                        timeout=10,
                    )
                    if r.status_code == 200:
                        data = r.json()
                        name = (data.get("miniProfile") or {}).get("firstName", "") or "unknown"
                        st.success(f"✅ Cookies valid! LinkedIn recognizes you as: {name}")
                    elif r.status_code in (401, 403):
                        st.error(
                            f"❌ Cookies EXPIRED (HTTP {r.status_code}). "
                            "You need to refresh your LinkedIn cookies in Streamlit secrets.\n\n"
                            "**How to get fresh cookies:**\n"
                            "1. Log into LinkedIn in Chrome\n"
                            "2. Open DevTools → Application → Cookies → www.linkedin.com\n"
                            "3. Copy: `li_at`, `JSESSIONID` (strip outer quotes), `csrf-token`\n"
                            "4. Paste into Streamlit Cloud → Settings → Secrets"
                        )
                    else:
                        st.warning(f"Unexpected response: HTTP {r.status_code} — cookies may be stale.")
            except Exception as e:
                st.error(f"Test failed: {e}")

# ── Run agent if button clicked ──────────────────────────────────────────────
if run_linkedin:
    with st.spinner("Running LinkedIn agent in review mode…"):
        result = run_linkedin_agent(review_mode=True)
    _display_run_result(result, live=False)

if run_linkedin_live:
    # Verify LinkedIn credentials are present before starting
    missing = [
        k for k in ("LINKEDIN_LI_AT", "LINKEDIN_JSESSIONID", "LINKEDIN_CSRF_TOKEN",
                    "LINKEDIN_OWN_PROFILE_URL")
        if not _secret(k)
    ]
    if missing:
        st.error(
            f"Missing Streamlit secrets: {', '.join(missing)}\n\n"
            "Go to your Streamlit Cloud app → Settings → Secrets and add:\n"
            "```\n"
            "LINKEDIN_LI_AT = \"your li_at cookie value\"\n"
            "LINKEDIN_JSESSIONID = \"your JSESSIONID value\"\n"
            "LINKEDIN_CSRF_TOKEN = \"your csrf-token value\"\n"
            "LINKEDIN_OWN_PROFILE_URL = \"https://www.linkedin.com/in/your-name\"\n"
            "APIFY_TOKEN = \"your apify token\"  # for real lead discovery\n"
            "```\n"
            "Get cookie values from Chrome DevTools → Application → Cookies → www.linkedin.com"
        )
    else:
        weekly_used = 0
        try:
            from src.supabase_client import count_connection_requests_this_week
            weekly_used = count_connection_requests_this_week()
        except Exception:
            pass
        budget_remaining = max(0, 80 - weekly_used)
        budget_note = (
            f"⚠️ **Connection budget: {weekly_used}/80 used this week.**  \n"
            + ("Budget exhausted — agent will DM your existing 1st-degree connections only."
               if budget_remaining == 0 else
               f"{budget_remaining} connection requests remaining — will also search via Apify.")
        )
        st.warning(f"**LIVE MODE** — real LinkedIn messages will be sent.\n\n{budget_note}")
        with st.spinner("Running LinkedIn agent in LIVE mode… (5–20 min for up to 80 leads)"):
            result = run_linkedin_agent(review_mode=False)
        _display_run_result(result, live=True)

# ── Run Reddit agent if button clicked ──────────────────────────────────────
if run_reddit:
    with st.spinner("Searching Reddit for relevant threads…"):
        result = run_reddit_agent(review_mode=True)
    _display_reddit_result(result, live=False)

if run_reddit_live:
    missing = [k for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                            "REDDIT_USERNAME", "REDDIT_PASSWORD")
               if not _secret(k)]
    if missing:
        st.error(
            f"Missing Streamlit secrets for Reddit: {', '.join(missing)}\n\n"
            "Add to Streamlit Cloud secrets:\n"
            "```\n"
            "REDDIT_CLIENT_ID = \"your_app_client_id\"\n"
            "REDDIT_CLIENT_SECRET = \"your_app_secret\"\n"
            "REDDIT_USERNAME = \"your_reddit_username\"\n"
            "REDDIT_PASSWORD = \"your_reddit_password\"\n"
            "XAI_API_KEY = \"your_grok_api_key\"\n"
            "```\n"
            "Create a Reddit app at reddit.com/prefs/apps (script type)"
        )
    else:
        st.warning("**LIVE MODE** — Kemba will actually post to Reddit.")
        with st.spinner("Running Reddit agent LIVE…"):
            result = run_reddit_agent(review_mode=False)
        _display_reddit_result(result, live=True)

# ── Load data ────────────────────────────────────────────────────────────────
with st.spinner("Loading…"):
    s = fetch_stats()
    leads = fetch_leads()
    activity = fetch_activity()

if not s:
    st.error("No data returned from Supabase. Check the connection.")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# 1 · LinkedIn Outreach pipeline
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📣 LinkedIn Outreach Agent")

sent       = int(s.get("leads_sent", 0))
replied    = int(s.get("leads_replied", 0))
conv       = int(s.get("leads_converted", 0))
reply_rate = f"{replied/sent*100:.1f}%" if sent else "—"
conv_rate  = f"{conv/sent*100:.1f}%"   if sent else "—"

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Leads", s.get("leads_total", 0))
c2.metric("Discovered",  s.get("leads_discovered", 0))
c3.metric("Drafted",     s.get("leads_drafted", 0))
c4.metric("Sent",        sent)
c5.metric("Replied",     replied, reply_rate + " reply rate")
c6.metric("Converted",   conv,    conv_rate  + " conv. rate")

st.divider()

# ── Recent leads table ───────────────────────────────────────────────────────
st.subheader("📋 Recent LinkedIn Leads")
if leads:
    df = pd.DataFrame(leads)
    for col in ("created_at", "date_sent", "response_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%b %d %H:%M").fillna("—")
    df = df.rename(columns={
        "name": "Name", "headline": "Headline", "status": "Status",
        "fit_score": "Fit", "date_sent": "Sent", "response_at": "Replied",
        "created_at": "Discovered",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    if not service_client():
        st.info("ℹ️ Add `SUPABASE_SERVICE_KEY` to Streamlit secrets to see lead details.")
    else:
        st.info("No leads yet — click **▶ Run LinkedIn Outreach** to start.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# 2 · Outreach activity log
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🔁 Outreach Activity Log")
c1, c2 = st.columns(2)
c1.metric("Total Actions", s.get("activity_total", 0))
c2.metric("Last 30 days",  s.get("activity_30d", 0))

if activity:
    adf = pd.DataFrame(activity)
    adf["created_at"] = pd.to_datetime(adf["created_at"], errors="coerce").dt.strftime("%b %d %H:%M").fillna("—")
    adf = adf.rename(columns={
        "agent": "Agent", "action": "Action", "target": "Target",
        "result": "Result", "created_at": "Time",
    })
    st.dataframe(adf, use_container_width=True, hide_index=True)
elif not service_client():
    st.info("ℹ️ Add `SUPABASE_SERVICE_KEY` to Streamlit secrets to see activity details.")
else:
    st.info("No activity logged yet — run the agent first.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# 3 · Trackply product growth
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📈 Trackply Product Growth")

new_30d     = int(s.get("new_users_30d", 0))
prev_30d    = int(s.get("new_users_prev_30d", 0))
delta_users = new_30d - prev_30d

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Users",          s.get("total_users", 0), f"+{new_30d} this month")
c2.metric("New Users (30d)",      new_30d,                  f"{delta_users:+d} vs prior month")
c3.metric("Applications Tracked", s.get("total_apps", 0),  f"+{s.get('apps_30d', 0)} this month")
c4.metric("AI Job Hunts Run",     s.get("total_job_hunts", 0))

st.subheader("🤖 AI Feature Usage")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Meta Agent Runs",  s.get("total_meta_runs", 0))
c2.metric("Coach Sessions",   s.get("coach_sessions", 0))
c3.metric("Resumes Built",    s.get("total_resumes", 0))
c4.metric("Cover Letters",    s.get("total_cover_letters", 0))
c5.metric("Scam Scans",       s.get("scam_scans", 0))

c1, _ = st.columns(2)
c1.metric("Connection Searches", s.get("connection_searches", 0))

st.divider()
st.link_button("Open Langfuse Dashboard", "https://cloud.langfuse.com")
st.caption(
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
    "Trackply Supabase (vglfaviliadxevfillbb)"
)
