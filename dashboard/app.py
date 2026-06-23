import streamlit as st

st.set_page_config(page_title="Trackply Agentic Marketing OS", layout="wide")
st.title("🚀 Trackply Agentic Marketing OS")
st.caption("LinkedIn | Reddit | SEO | Powered by Agentic Labs")

st.sidebar.header("Controls")
st.sidebar.button("Run LinkedIn Outreach (Review)")
st.sidebar.button("Run Reddit Engagement")
st.sidebar.button("Run SEO Content (1-2 posts)")

col1, col2, col3 = st.columns(3)
col1.metric("LinkedIn Leads", "47", "+12")
col2.metric("Reddit Posts", "4", "+1")
col3.metric("SEO Articles", "2", "+2")

st.divider()

st.subheader("Agent Status")
st.dataframe([
    {"Agent": "LinkedIn Outreach", "Status": "Review Mode", "Leads Processed": 47, "Last Run": "Just now"},
    {"Agent": "Reddit Agent", "Status": "Active", "Posts Today": 2, "Comments": 5},
    {"Agent": "SEO Content", "Status": "Active", "Posts Today": 2},
], use_container_width=True)

st.divider()
st.subheader("Observability")
st.link_button("Open Langfuse Dashboard", "https://cloud.langfuse.com")

st.info("This dashboard is a starting point. Connect to live Supabase + Langfuse data for production use.")