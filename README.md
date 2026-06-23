# Agentic Marketing OS for Trackply

**LangGraph-powered multi-agent system** that runs cheap, precise, automated marketing for Trackply.

Built on top of **Agentic Labs** (same patterns as the Job Coach, Meta Agent, etc.).

## Vision
Instead of burning money on broad LinkedIn/Google ads that bring low-intent users, we run an **Agentic Marketing OS**:
- LinkedIn Outreach Agent (high-intent "Open to Work" + AI freelancers)
- Reddit Agent (content + engagement, posting as you until karma builds)
- SEO Content Agent (daily/regular posts to trackply.com/blogs)
- Future: X/Twitter, email sequences, etc.

All powered by the same LangGraph + Supabase stack as the rest of Agentic Labs.

## Current Status
- LinkedIn Outreach Agent: Full LLM-driven loop + human approval queue + Job Coach integration
- Reddit Agent: Skeleton with post-as-me mode
- SEO Content Agent: Initial researcher → writer → publisher flow
- Shared patterns across all agents

## Why This Matters
- Extremely low cost (mostly LLM + Apify calls)
- High precision targeting
- Compounds over time (content + relationships)
- Reusable across Trackply and future Agentic Labs products

## Quick Start (LinkedIn Agent)
```bash
python src/runner.py --mode review --campaign test
```