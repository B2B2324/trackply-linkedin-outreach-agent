# Trackply Agentic Marketing OS

Professional multi-agent system for running LinkedIn outreach, Reddit engagement, and SEO content generation.

Built on LangGraph + Agentic Labs patterns with Langfuse observability.

## Quick Start (Tomorrow)

### 1. Setup
```bash
git clone https://github.com/B2B2324/trackply-linkedin-outreach-agent.git
cd trackply-linkedin-outreach-agent
pip install -r requirements.txt
cp .env.example .env
```

Fill in your `.env` file with Supabase, Langfuse (optional), and LLM API keys.

### 2. Run the Dashboard (Recommended first step)
```bash
streamlit run dashboard/app.py
```

### 3. Run Individual Agents

**LinkedIn Outreach Agent** (Review mode by default):
```bash
python src/runner.py --mode review --campaign test
```

**Reddit Agent**:
```bash
python src/reddit_agent.py
```

**SEO Content Agent**:
```bash
python src/seo_agent.py
```

## Current Status
- All agents generate content and log activity.
- Real posting/sending requires additional integration (planned).
- Langfuse integration enabled for token & cost tracking.

## Next Steps
- Wire up real posting logic
- Add more user-facing MCP tools (on hold for now)
- Deploy to production (Railway / Vercel recommended)