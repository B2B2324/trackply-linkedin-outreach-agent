import os
import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone

st.set_page_config(page_title="Trackply Agentic Marketing OS", layout="wide")

# ── Supabase connection ─────────────────────────────────────────────────────
# Reads from Streamlit Cloud secrets → env vars → hardcoded fallbacks (prod DB).
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
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def count(table: str, filter_sql: str = "") -> int:
    """Return COUNT(*) from a table with an optional WHERE clause."""
    sb = get_client()
    try:
        q = f"SELECT COUNT(*) AS n FROM {table}"
        if filter_sql:
            q += f" WHERE {filter_sql}"
        result = sb.rpc("exec_sql", {"query": q}).execute()
        # Prefer the REST count approach instead
        raise Exception("use rest")
    except Exception:
        pass
    # REST approach: head=True count
    try:
        q = sb.table(table).select("*", count="exact", head=True)
        if filter_sql:
            # parse simple "col > val" style — use .gte/.gt etc only for known patterns
            pass
        resp = q.execute()
        return resp.count or 0
    except Exception:
        return 0


@st.cache_data(ttl=300)
def fetch_metrics():
    sb = get_client()

    def cnt(table: str) -> int:
        try:
            r = sb.table(table).select("*", count="exact", head=True).execute()
            return r.count or 0
        except Exception:
            return 0

    def cnt_recent(table: str, days: int = 30) -> int:
        try:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            r = (sb.table(table)
                   .select("*", count="exact", head=True)
                   .gte("created_at", cutoff)
                   .execute())
            return r.count or 0
        except Exception:
            return 0

    def cnt_recent_distinct_users(table: str, days: int = 30) -> int:
        try:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            r = (sb.table(table)
                   .select("user_id")
                   .gte("created_at", cutoff)
                   .execute())
            return len({row["user_id"] for row in (r.data or [])})
        except Exception:
            return 0

    total_users       = cnt("profiles")
    new_users_30d     = cnt_recent("profiles", 30)
    new_users_prev30  = cnt_recent("profiles", 60) - new_users_30d
    total_apps        = cnt("applications")
    apps_30d          = cnt_recent("applications", 30)
    total_job_hunts   = cnt("job_hunt_results")
    total_meta_runs   = cnt("meta_agent_runs")
    coach_sessions    = cnt("coach_sessions")
    active_users_30d  = cnt_recent_distinct_users("applications", 30)
    total_resumes     = cnt("resumes")
    total_cover_letters = cnt("cover_letters")
    scam_scans        = cnt("scam_scans")
    connection_searches = cnt("connection_searches")

    return {
        "total_users":        total_users,
        "new_users_30d":      new_users_30d,
        "new_users_delta":    new_users_30d - new_users_prev30,
        "total_apps":         total_apps,
        "apps_30d":           apps_30d,
        "total_job_hunts":    total_job_hunts,
        "total_meta_runs":    total_meta_runs,
        "coach_sessions":     coach_sessions,
        "active_users_30d":   active_users_30d,
        "total_resumes":      total_resumes,
        "total_cover_letters": total_cover_letters,
        "scam_scans":         scam_scans,
        "connection_searches": connection_searches,
    }


# ── UI ──────────────────────────────────────────────────────────────────────
st.title("🚀 Trackply Agentic Marketing OS")
st.caption("Live data · Trackply Supabase · refreshes every 5 min")

with st.spinner("Loading live data…"):
    m = fetch_metrics()

# ── Row 1: Growth KPIs ──────────────────────────────────────────────────────
st.subheader("📈 Growth")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Users",        m["total_users"],       f"+{m['new_users_30d']} this month")
c2.metric("New Users (30d)",    m["new_users_30d"],     f"+{m['new_users_delta']:+d} vs prior month")
c3.metric("Active Users (30d)", m["active_users_30d"])
c4.metric("Applications Tracked", m["total_apps"],      f"+{m['apps_30d']} this month")

st.divider()

# ── Row 2: AI Feature Usage ──────────────────────────────────────────────────
st.subheader("🤖 AI Feature Usage")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("AI Job Hunts",     m["total_job_hunts"])
c2.metric("Meta Agent Runs",  m["total_meta_runs"])
c3.metric("Coach Sessions",   m["coach_sessions"])
c4.metric("Resumes Built",    m["total_resumes"])
c5.metric("Cover Letters",    m["total_cover_letters"])

st.divider()

# ── Row 3: Outreach & Engagement ────────────────────────────────────────────
st.subheader("🔗 Outreach & Engagement")
c1, c2 = st.columns(2)
c1.metric("Connection Searches", m["connection_searches"])
c2.metric("Scam Scans",          m["scam_scans"])

st.divider()

# ── Agent Status ─────────────────────────────────────────────────────────────
st.subheader("Agent Status")
st.sidebar.header("Controls")
st.sidebar.button("Run LinkedIn Outreach (Review)")
st.sidebar.button("Run Reddit Engagement")
st.sidebar.button("Run SEO Content (1-2 posts)")

st.dataframe([
    {"Agent": "LinkedIn Outreach",  "Status": "Review Mode", "Notes": "Approval queue not yet connected"},
    {"Agent": "Reddit Agent",       "Status": "Standby",     "Notes": "—"},
    {"Agent": "SEO Content",        "Status": "Standby",     "Notes": "—"},
], use_container_width=True)

st.divider()
st.subheader("Observability")
st.link_button("Open Langfuse Dashboard", "https://cloud.langfuse.com")

st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · Data source: Trackply Supabase (vglfaviliadxevfillbb)")
