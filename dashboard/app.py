"""
Trackply Agentic Marketing OS — Streamlit dashboard.
Reads from the `marketing_stats` view (anon-readable aggregates) and
the `linkedin_leads` / `outreach_activity` tables (service-role, via
SUPABASE_SERVICE_KEY secret set in Streamlit Cloud settings).
Falls back gracefully to view-only mode if the service key is absent.
"""

import os
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Trackply Marketing OS", layout="wide")

# ── Connection ───────────────────────────────────────────────────────────────
# Anon key is safe in a public repo — only reads the aggregate view.
SUPABASE_URL = "https://vglfaviliadxevfillbb.supabase.co"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZnbGZhdmlsaWFkeGV2ZmlsbGJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg1MjI4MjksImV4cCI6MjA5NDA5ODgyOX0"
    ".TC5tuxGXGom8TKjzsooYEdr7ZkKtSEHm3CXNHUO202g"
)

def _get_service_key() -> str | None:
    """Returns service role key from Streamlit secrets or env — never hardcoded."""
    try:
        return st.secrets["SUPABASE_SERVICE_KEY"]
    except Exception:
        return os.environ.get("SUPABASE_SERVICE_KEY")

@st.cache_resource
def anon_client() -> Client:
    return create_client(SUPABASE_URL, ANON_KEY)

@st.cache_resource
def service_client() -> Client | None:
    key = _get_service_key()
    return create_client(SUPABASE_URL, key) if key else None


# ── Data fetching ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_stats() -> dict:
    """Pull aggregate stats from the anon-readable marketing_stats view."""
    try:
        row = anon_client().table("marketing_stats").select("*").execute().data
        return row[0] if row else {}
    except Exception as e:
        st.warning(f"Could not load stats: {e}")
        return {}

@st.cache_data(ttl=300)
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

@st.cache_data(ttl=300)
def fetch_activity() -> list[dict]:
    sb = service_client()
    if not sb:
        return []
    try:
        return (
            sb.table("outreach_activity")
            .select("agent,action,target,result,created_at")
            .order("created_at", desc=True)
            .limit(40)
            .execute()
        ).data or []
    except Exception:
        return []


# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.header("Agent Controls")
st.sidebar.button("▶ Run LinkedIn Outreach")
st.sidebar.button("▶ Run Reddit Engagement")
st.sidebar.button("▶ Run SEO Content")
st.sidebar.divider()
if st.sidebar.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.rerun()

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🚀 Trackply Agentic Marketing OS")
st.caption("Live data from Trackply Supabase · auto-refreshes every 5 min · v2026-06-26")

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

sent    = int(s.get("leads_sent", 0))
replied = int(s.get("leads_replied", 0))
conv    = int(s.get("leads_converted", 0))
reply_rate = f"{replied/sent*100:.1f}%" if sent else "—"
conv_rate  = f"{conv/sent*100:.1f}%"   if sent else "—"

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Leads",  s.get("leads_total", 0))
c2.metric("Discovered",   s.get("leads_discovered", 0))
c3.metric("Drafted",      s.get("leads_drafted", 0))
c4.metric("Sent",         sent)
c5.metric("Replied",      replied,  reply_rate + " reply rate")
c6.metric("Converted",    conv,     conv_rate  + " conv. rate")

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
    msg = (
        "No leads yet — run the LinkedIn agent to populate this table."
        if service_client()
        else "ℹ️ Add `SUPABASE_SERVICE_KEY` to Streamlit Cloud secrets to see lead details."
    )
    st.info(msg)

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
    st.info("ℹ️ Add `SUPABASE_SERVICE_KEY` to Streamlit Cloud secrets to see activity details.")
else:
    st.info("No activity logged yet.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# 3 · Trackply product growth
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📈 Trackply Product Growth")

new_30d     = int(s.get("new_users_30d", 0))
prev_30d    = int(s.get("new_users_prev_30d", 0))
delta_users = new_30d - prev_30d

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Users",          s.get("total_users", 0),  f"+{new_30d} this month")
c2.metric("New Users (30d)",      new_30d,                   f"{delta_users:+d} vs prior month")
c3.metric("Applications Tracked", s.get("total_apps", 0),   f"+{s.get('apps_30d', 0)} this month")
c4.metric("AI Job Hunts Run",     s.get("total_job_hunts", 0))

st.subheader("🤖 AI Feature Usage")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Meta Agent Runs",  s.get("total_meta_runs", 0))
c2.metric("Coach Sessions",   s.get("coach_sessions", 0))
c3.metric("Resumes Built",    s.get("total_resumes", 0))
c4.metric("Cover Letters",    s.get("total_cover_letters", 0))
c5.metric("Scam Scans",       s.get("scam_scans", 0))

c1, c2 = st.columns(2)
c1.metric("Connection Searches", s.get("connection_searches", 0))

st.divider()
st.link_button("Open Langfuse Dashboard", "https://cloud.langfuse.com")
st.caption(
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
    f"Trackply Supabase (vglfaviliadxevfillbb)"
)
