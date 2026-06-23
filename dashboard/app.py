import streamlit as st

st.set_page_config(page_title="Agentic Marketing OS - Trackply", layout="wide")
st.title("Agentic Marketing OS Dashboard")
st.caption("Trackply Marketing powered by Agentic Labs + Langfuse")

# Sidebar
st.sidebar.header("Controls")
st.sidebar.selectbox("Campaign", ["june-2026-outreach", "test"])
st.sidebar.button("Run LinkedIn Agent (Review Mode)")
st.sidebar.button("Run SEO Content Pipeline")
st.sidebar.button("Run Reddit Engagement")

# Main metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Leads Generated (Today)", "47", "+12")
col2.metric("Messages Sent", "31", "+8")
col3.metric("Reply Rate", "18%", "+3%")
col4.metric("Est. Token Spend", "$4.20", "-$1.10")

st.divider()

# Agent Status
st.subheader("Agent Status")
st.dataframe([
    {"Agent": "LinkedIn Outreach", "Status": "Running (Review)", "Last Run": "2 min ago", "Leads": 47, "Cost": "$2.80"},
    {"Agent": "Reddit Agent", "Status": "Idle", "Last Run": "Yesterday", "Posts": 3, "Cost": "$0.90"},
    {"Agent": "SEO Content", "Status": "Ready", "Last Run": "This morning", "Articles": 2, "Cost": "$1.50"},
], use_container_width=True)

st.divider()

# Langfuse Quick Link
st.subheader("Observability (Langfuse)")
st.link_button("Open Langfuse Dashboard", "https://cloud.langfuse.com")
st.caption("View detailed token usage, costs, and traces per agent/node")

# Recent Activity
st.subheader("Recent Activity")
st.write("- LinkedIn: Personalized message generated for Jordan Hale (AI Evaluator)")
st.write("- SEO: Article drafted for 'managing multiple AI freelance gigs'")
st.write("- Reddit: Post drafted for r/jobsearch (pending review)")

st.info("This is a prototype dashboard. Connect to real Supabase + Langfuse for live data.")