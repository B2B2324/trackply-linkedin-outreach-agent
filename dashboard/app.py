import streamlit as st

st.set_page_config(page_title="Agentic Marketing OS - Trackply", layout="wide")
st.title("🚀 Agentic Marketing OS Dashboard")
st.caption("Trackply Marketing powered by Agentic Labs + Langfuse")

# Sidebar controls
st.sidebar.header("Agent Controls")
if st.sidebar.button("Run LinkedIn Outreach (Review Mode)"):
    st.success("LinkedIn agent queued in review mode")
if st.sidebar.button("Run SEO Content Pipeline"):
    st.success("SEO agent started")
if st.sidebar.button("Run Reddit Engagement"):
    st.success("Reddit agent started")

# Metrics Row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Leads Today", "47", "+12")
col2.metric("Messages Sent", "31", "+8")
col3.metric("Reply Rate", "18%", "+3%")
col4.metric("Token Spend (24h)", "$4.20", "-$1.10")

st.divider()

# Agent Status
st.subheader("Active Agents")
st.dataframe([
    {"Agent": "LinkedIn Outreach", "Status": "Running (Review)", "Leads": 47, "Cost": "$2.80", "Last Activity": "Just now"},
    {"Agent": "Reddit Agent", "Status": "Idle", "Posts": 3, "Cost": "$0.90", "Last Activity": "2h ago"},
    {"Agent": "SEO Content", "Status": "Ready", "Articles": 2, "Cost": "$1.50", "Last Activity": "Today"},
    {"Agent": "Personal Brain", "Status": "Prototype", "Users": 0, "Cost": "$0.00", "Last Activity": "N/A"},
], use_container_width=True)

st.divider()

# Knowledge Carry-over Section
st.subheader("🧠 Knowledge Carry-over (LinkedIn → Trackply)")
st.success("12 leads this week carried context into their Private Brain / Kemba")
st.caption("Leads arrive with conversation summary + interest signals already in their knowledge base")

st.divider()

# Langfuse
st.subheader("Observability")
st.link_button("Open Full Langfuse Dashboard", "https://cloud.langfuse.com")
st.caption("Detailed token usage and cost breakdown per agent and node")

# Quick Links
st.subheader("Quick Links")
st.link_button("Trackply App", "https://trackply.com")
st.link_button("Agentic Labs Repo", "https://github.com/B2B2324")