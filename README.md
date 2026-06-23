# Agentic Marketing OS for Trackply

**LangGraph-powered multi-agent marketing system** built on Agentic Labs.

## Langfuse Integration (Token & Cost Tracking)
We now have **Langfuse** integrated for full observability:
- Track token usage per agent (LinkedIn Outreach, Reddit, SEO, etc.)
- See costs broken down by node/model
- Nice dashboard to spot expensive agents or prompts

### Setup
1. Create a free/project account at [langfuse.com](https://langfuse.com) or self-host
2. Add these to your `.env`:
```
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted URL
LLM_PROVIDER=anthropic   # or xai / openai
ANTHROPIC_API_KEY=...     # or XAI_API_KEY / OPENAI_API_KEY
```
3. Run any agent → traces appear in Langfuse dashboard

This gives you clear visibility into where agents are spending tokens so you can optimize (cheaper models for simple tasks, better prompts, etc.).

## Current Agents
- LinkedIn Outreach (with Job Coach handoff)
- Reddit (post-as-you mode)
- SEO Content
- Central Marketing Supervisor

All share the same LangGraph + observability patterns.