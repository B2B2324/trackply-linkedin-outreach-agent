import os
from datetime import datetime, timedelta, timezone

import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Trackply Agentic Marketing OS", layout="wide")

# ── Supabase connection ──────────────────────────────────────────────────────
def _secret(key: str, fallback: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, fallback)

SUPABASE_URL = _secret("SUPABASE_URL", "https://vglfaviliadxevfillbb.supabase.co")
SUPABASE_KEY = _secret(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZnbGZhdmlsaWFkeGV2ZmlsbGJiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODUyMjgyOSwiZXhwIjoyMDk0MDk4ODI5fQ.Q-UmRrn559HZCDt9cm_i4K3HJFM0qD7an5kDjFazkko",
)

@st.cache_resource
def get_sb() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Data helpers ─────────────────────────────────────────────────────────────
def cnt(table: str) -> int:
    try:
        r = get_sb().table(table).select("*", count="exact", head=True).execute()
        return r.count or 0
    except Exception:
        return 0

def cnt_recent(table: str, days: int = 30) -> int:
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        r = (get_sb().table(table)
               .select("*", count="exact", head=True)
               .gte("created_at", cutoff)
               .execute())
        return r.count or 0
    except Exception:
        return 0

def cnt_where(table: str, col: str, val: str) -> int:
    try:
        r = (get_sb().table(table)
               .select("*", count="exact", head=True)
               .eq(col, val)
               .execute())
        return r.count or 0
    except Exception:
        return 0

def cnt_recent_distinct_users(table: str, days: int = 30) -> int:
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        r = (get_sb().table(table)
               .select("user_id")
               .gte("created_at", cutoff)
               .execute())
        return len({row["user_id"] for row in (r.data or [])})
    except Exception:
        return 0

@st.cache_data(ttl=300)
def fetch_all():
    # ── Trackply product metrics ──
    total_users        = cnt("profiles")
    new_users_30d      = cnt_recent("profiles", 30)
    new_users_prev30   = cnt_recent("profiles", 60) - new_users_30d
    total_apps         = cnt("applications")
    apps_30d           = cnt_recent("applications", 30)
    active_users_30d   = cnt_recent_distinct_users("applications", 30)
    total_job_hunts    = cnt("job_hunt_results")
    total_meta_runs    = cnt("meta_agent_runs")
    coach_sessions     = cnt("coach_sessions")
    total_resumes      = cnt("resumes")
    total_cover_letters = cnt("cover_letters")
    connection_searches = cnt("connection_searches")
    scam_scans         = cnt("scam_scans")

    # ── Marketing agent metrics ──
    leads_total        = cnt("linkedin_leads")
    leads_discovered   = cnt_where("linkedin_leads", "status", "discovered")
    leads_drafted      = cnt_where("linkedin_leads", "status", "message_drafted")
    leads_sent         = cnt_where("linkedin_leads", "status", "sent")
    leads_replied      = cnt_where("linkedin_leads", "status", "replied")
    leads_converted    = cnt_where("linkedin_leads", "status", "converted")
    activity_total     = cnt("outreach_activity")
    activity_30d       = cnt_recent("outreach_activity", 30)

    # ── Recent leads table ──
    try:
        leads_rows = (
            get_sb().table("linkedin_leads")
            .select("name, headline, status, fit_score, date_sent, response_at, created_at")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        ).data or []
    except Exception:
        leads_rows = []

    # ── Recent activity log ──
    try:
        activity_rows = (
            get_sb().table("outreach_activity")
            .select("agent, action, target, result, created_at")
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        ).data or []
    except Exception:
        activity_rows = []

    return {
        # product
        "total_users": total_users, "new_users_30d": new_users_30d,
        "new_users_delta": new_users_30d - new_users_prev30,
        "total_apps": total_apps, "apps_30d": apps_30d,
        "active_users_30d": active_users_30d,
        "total_job_hunts": total_job_hunts, "total_meta_runs": total_meta_runs,
        "coach_sessions": coach_sessions, "total_resumes": total_resumes,
        "total_cover_letters": total_cover_letters,
        "connection_searches": connection_searches, "scam_scans": scam_scans,
        # marketing
        "leads_total": leads_total, "leads_discovered": leads_discovered,
        "leads_drafted": leads_drafted, "leads_sent": leads_sent,
        "leads_replied": leads_replied, "leads_converted": leads_converted,
        "activity_total": activity_total, "activity_30d": activity_30d,
        "leads_rows": leads_rows, "activity_rows": activity_rows,
    }


# ── Layout ───────────────────────────────────────────────────────────────────
st.title("🚀 Trackply Agentic Marketing OS")
st.caption("Live data · Trackply Supabase · auto-refreshes every 5 min")

st.sidebar.header("Agent Controls")
st.sidebar.button("▶ Run LinkedIn Outreach")
st.sidebar.button("▶ Run Reddit Engagement")
st.sidebar.button("▶ Run SEO Content")
st.sidebar.divider()
if st.sidebar.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.rerun()

with st.spinner("Loading live data…"):
    d = fetch_all()

# ════════════════════════════════════════════════════════════════════════════
# Section 1 — LinkedIn Agent pipeline
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📣 LinkedIn Outreach Agent")

reply_rate = round(d["leads_replied"] / d["leads_sent"] * 100, 1) if d["leads_sent"] else 0
conv_rate  = round(d["leads_converted"] / d["leads_sent"] * 100, 1) if d["leads_sent"] else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Leads",     d["leads_total"])
c2.metric("Discovered",      d["leads_discovered"])
c3.metric("Drafted",         d["leads_drafted"])
c4.metric("Sent",            d["leads_sent"])
c5.metric("Replied",         d["leads_replied"],   f"{reply_rate}% reply rate")
c6.metric("Converted",       d["leads_converted"], f"{conv_rate}% conv. rate")

st.divider()

# ── Recent leads table ───────────────────────────────────────────────────────
st.subheader("📋 Recent LinkedIn Leads")
if d["leads_rows"]:
    import pandas as pd
    df = pd.DataFrame(d["leads_rows"])
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%b %d %H:%M")
    df["date_sent"]  = pd.to_datetime(df["date_sent"],  errors="coerce").dt.strftime("%b %d")
    df["response_at"]= pd.to_datetime(df["response_at"], errors="coerce").dt.strftime("%b %d")
    df = df.rename(columns={
        "name": "Name", "headline": "Headline", "status": "Status",
        "fit_score": "Fit", "date_sent": "Sent", "response_at": "Replied",
        "created_at": "Discovered",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No leads yet — run the LinkedIn agent to populate this table.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# Section 2 — Agent activity log
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🔁 Outreach Activity Log")
c1, c2 = st.columns(2)
c1.metric("Total Actions Logged", d["activity_total"])
c2.metric("Actions Last 30d",     d["activity_30d"])

if d["activity_rows"]:
    import pandas as pd
    adf = pd.DataFrame(d["activity_rows"])
    adf["created_at"] = pd.to_datetime(adf["created_at"]).dt.strftime("%b %d %H:%M")
    adf = adf.rename(columns={
        "agent": "Agent", "action": "Action", "target": "Target",
        "result": "Result", "created_at": "Time",
    })
    st.dataframe(adf, use_container_width=True, hide_index=True)
else:
    st.info("No activity logged yet.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# Section 3 — Trackply product growth
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📈 Trackply Product Growth")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Users",          d["total_users"],       f"+{d['new_users_30d']} this month")
c2.metric("New Users (30d)",      d["new_users_30d"],     f"{d['new_users_delta']:+d} vs prior")
c3.metric("Active Users (30d)",   d["active_users_30d"])
c4.metric("Applications Tracked", d["total_apps"],        f"+{d['apps_30d']} this month")

st.subheader("🤖 AI Feature Usage")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("AI Job Hunts",    d["total_job_hunts"])
c2.metric("Meta Agent Runs", d["total_meta_runs"])
c3.metric("Coach Sessions",  d["coach_sessions"])
c4.metric("Resumes Built",   d["total_resumes"])
c5.metric("Cover Letters",   d["total_cover_letters"])

c1, c2 = st.columns(2)
c1.metric("Connection Searches", d["connection_searches"])
c2.metric("Scam Scans",          d["scam_scans"])

st.divider()
st.link_button("Open Langfuse Dashboard", "https://cloud.langfuse.com")
st.caption(
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
    f"· Trackply Supabase (vglfaviliadxevfillbb)"
)
