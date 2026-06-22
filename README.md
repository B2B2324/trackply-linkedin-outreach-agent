# Trackply LinkedIn Outreach Agent

**LangGraph-powered agent for precise, high-intent LinkedIn outreach.**

Part of Agentic Labs marketing system. Targets "Open to Work" profiles + AI freelancers (RLHF, prompt engineering, data annotation, Mercor/Micro1/Outlier users) in the US.

## Why This Agent
- LinkedIn shows us the exact customers (Open to Work banner + keywords).
- Broad ads hit too many low-intent international users.
- This agent lets us reach high-signal profiles directly with personalized messages.
- Builds on existing Trackply job coach agents and Apify usage.

## Critical Safety & Legal Notes (READ FIRST)
- **LinkedIn ToS strictly prohibits automation/scraping/mass messaging.**
- Risk of account restriction or ban is real.
- **Start in review mode only** (generate messages, log actions, do not send automatically).
- Use rate limits (max 20-30 actions/day initially).
- Human-in-the-loop for every send initially.
- Vary messages heavily, add delays, engage naturally.
- This is for legitimate business outreach, not spam.
- You are responsible for compliance.

## Architecture Overview (LangGraph)
Multi-agent system with stateful workflows:

1. **Scout Agent** - Find & qualify high-intent profiles (Apify LinkedIn search or controlled browser).
2. **Personalizer Agent** - Research profile, craft natural message.
3. **Outreach Agent** - Log/send connection request or DM (review mode first).
4. **Conversational Agent** - Handle replies with small talk and qualification.
5. **Logger Agent** - Save everything to Supabase (leads, conversations, outcomes).
6. **Supervisor** - Rate limiting, escalation, daily caps, human review triggers.

State persists in Supabase for long-running campaigns.

## Quick Start
1. Clone repo
2. `pip install -r requirements.txt`
3. Set up Supabase (tables below)
4. Add Apify token if using actors
5. Run in review mode first

## Supabase Schema (recommended)
- `linkedin_leads` (profile_url, name, headline, location, fit_score, status, created_at)
- `outreach_logs` (lead_id, action, message, timestamp, outcome)
- `conversations` (lead_id, thread_json, last_updated)

## Next Steps / TODO
- Implement Scout with Apify LinkedIn Profile Search actor
- Add browser automation layer (Playwright) for safer sending
- Integrate with Trackply Supabase
- Add daily briefing / campaign dashboard
- A/B testing for message templates

## Files in this repo
- `prompts/` - All agent prompts
- `src/` - Core code

Built for Trackply + Agentic Labs. Let's get the right customers.