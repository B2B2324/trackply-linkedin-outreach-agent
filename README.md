# Trackply LinkedIn Outreach Agent

**LangGraph-powered, LLM-driven agent for high-intent LinkedIn outreach.**

Part of the Agentic Labs + Trackply marketing flywheel.

## Current Status (as of latest push)
- Full LangGraph workflow with supervisor loop
- LLM-ready nodes (Personalizer, Outreach decision, Conversational)
- Supabase persistence for leads, logs, conversations
- Review mode (generate + log, no auto-send)
- CLI runner with mode flag
- Strong safety scaffolding

## Safety & Compliance (Read Before Running)
**LinkedIn strictly prohibits automation.**
- Use **review mode** exclusively until you have human approval processes.
- Start with very low daily limits (10-20 actions).
- Monitor reply sentiment closely.
- All real sending must go through human review.
- You are fully responsible for ToS compliance and any account risks.

## Architecture
LangGraph stateful multi-agent system:

1. **Supervisor** - Controls flow, enforces limits, triggers human review
2. **Scout** - Discovers high-intent profiles (Apify or browser)
3. **Personalizer** - LLM crafts natural messages using profile context + prompts
4. **Outreach Decider** - LLM decides connection request vs DM vs skip + generates final text
5. **Logger** - Persists everything to Supabase
6. **Conversational** - Handles replies, qualifies, escalates

## Quick Start
```bash
git clone https://github.com/B2B2324/trackply-linkedin-outreach-agent.git
cd trackply-linkedin-outreach-agent
pip install -r requirements.txt
cp .env.example .env
# Add your keys
python src/runner.py --mode review --campaign june22-test
```

Run in review mode first. Inspect Supabase tables before any live outreach.

## Recommended Next Development
- Connect real Apify LinkedIn actor in Scout
- Add browser automation (Playwright) for sending
- Build simple web UI for reviewing/approving queued messages
- Integrate with Trackply job coach for conversational responses

This agent lets us reach exactly the users we can see on LinkedIn (Open to Work + AI freelancers) with precision instead of broad ads.