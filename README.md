# Trackply LinkedIn Outreach Agent

**LangGraph + LLM powered high-intent outreach for Trackply.**

## Latest Progress
- LLM calls in Personalizer, Outreach Decider, and Conversational nodes
- Human approval queue system added
- Robust error handling and retry logic
- Campaign configuration support
- Initial Reddit agent skeleton started
- Supabase persistence throughout
- Review mode by default (safe)

## Safety Reminder
Always start in review mode. Human approval is required before any real LinkedIn actions. Monitor everything.

## Quick Commands
```bash
python src/runner.py --mode review --campaign test
```

The agent now generates personalized outreach, decides actions, handles conversations, and queues items for your review before sending.