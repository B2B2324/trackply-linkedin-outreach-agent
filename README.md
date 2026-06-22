# Trackply LinkedIn Outreach Agent

**LangGraph-powered agent for precise, high-intent LinkedIn outreach.**

Part of Agentic Labs marketing system for Trackply.

## Status
- Core architecture + prompts in place
- State management and basic LangGraph loop working
- Safety-first design (review mode recommended)
- Next: Full Apify/Supabase integration + conversational handling

## Why This Matters
LinkedIn shows us the exact high-intent customers ("Open to Work" + AI freelancer keywords). Broad ads were hitting too many low-intent international signups. This agent lets us reach the right people directly with natural, personalized messages while logging everything for learning.

## Safety First (Non-Negotiable)
- LinkedIn ToS prohibits automation. Start in **review mode** only.
- Max 20-30 actions/day initially.
- Human approval for every send in the beginning.
- Heavy message variation + natural delays.
- Log everything. Monitor reply rates.
- You are responsible for compliance.

## Architecture
LangGraph multi-agent system:

1. **Supervisor** - Rate limits, daily caps, human review triggers, campaign control
2. **Scout** - Find qualified profiles (Apify LinkedIn actors or browser)
3. **Personalizer** - Generate natural messages using profile context
4. **Outreach** - Log to Supabase + (optional) send connection/DM in review mode
5. **Conversational** - Handle replies, qualify, funnel to Trackply job coach
6. **Logger** - Persistent state in Supabase

## Quick Start
```bash
git clone https://github.com/B2B2324/trackply-linkedin-outreach-agent.git
cd trackply-linkedin-outreach-agent
pip install -r requirements.txt
cp .env.example .env
# Fill in your keys
python src/runner.py --mode review --campaign test
```

## Supabase Tables
Run these in Supabase SQL editor:
```sql
CREATE TABLE linkedin_leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_url TEXT UNIQUE,
  name TEXT,
  headline TEXT,
  location TEXT,
  fit_score FLOAT,
  why_qualified TEXT,
  status TEXT DEFAULT 'new',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE outreach_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID REFERENCES linkedin_leads(id),
  action TEXT,
  message TEXT,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  outcome TEXT
);

CREATE TABLE conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID REFERENCES linkedin_leads(id),
  thread JSONB,
  last_updated TIMESTAMPTZ DEFAULT NOW()
);
```

## Files
- `prompts/` - All agent prompts
- `src/` - Core Python code
- `src/runner.py` - Easy CLI to run campaigns

Built for Trackply. Let's get the right customers seeing the product.