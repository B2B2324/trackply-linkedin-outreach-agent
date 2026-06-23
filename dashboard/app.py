import streamlit as st

st.set_page_config(page_title="Trackply Agentic Marketing OS", layout="wide")
st.title("🚀 Trackply Agentic Marketing OS")
st.caption("LinkedIn | Reddit | SEO Agents | Powered by Agentic Labs")

st.sidebar.header("Quick Actions")
if st.sidebar.button("Run LinkedIn Agent (Review)"):
    st.success("LinkedIn agent started in review mode")
if st.sidebar.button("Run Reddit Agent"):
    st.success("Reddit agent started")
if st.sidebar.button("Run SEO Agent"):
    st.success("SEO agent started")

col1, col2, col3 = st.columns(3)
col1.metric("LinkedIn Leads Today", "47", "+12")
col2.metric("Reddit Posts", "3", "+1")
col3.metric("SEO Articles", "2", "+2")

st.divider()

st.subheader("Agent Status")
st.dataframe([
    {"Agent": "LinkedIn Outreach", "Status": "Review Mode", "Last Run": "Just now", "Output": "Personalized messages generated"},
    {"Agent": "Reddit Agent", "Status": "Ready", "Last Run": "Today", "Output": "Content generated"},
    {"Agent": "SEO Content", "Status": "Ready", "Last Run": "Today", "Output": "Articles generated"},
], use_container_width=True)

st.divider()
st.caption("Run agents locally using the commands in the README. Real posting requires additional setup.")