# Agentic Marketing OS for Trackply

**Full multi-agent marketing system** built on Agentic Labs + LangGraph.

## What's Built
- **LinkedIn Outreach Agent** — High-intent targeting + natural founder voice + Job Coach handoff
- **Reddit Agent** — Post-as-you mode + content + engagement
- **SEO Content Agent** — Research → Write → Publish pipeline for trackply.com/blogs
- **Marketing Supervisor** — Orchestrates everything
- **Langfuse Observability** — Token & cost tracking per agent
- **Streamlit Dashboard** — Quick overview of campaigns, agents, and spend

## Quick Start
```bash
streamlit run dashboard/app.py
python src/runner.py --mode review
```

Run the Streamlit dashboard to see agent status and Langfuse links at a glance.