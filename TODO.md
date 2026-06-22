High-priority next steps:
1. Implement Scout node with Apify LinkedIn Profile Search actor (or SerpAPI + manual).
2. Add Supabase client for logging leads and conversations.
3. Build review mode UI or CLI flag (generate but don't send).
4. Integrate message A/B testing and performance tracking.
5. Add Conversational agent that uses existing Trackply job coach logic.
6. Daily scheduler (cron or LangGraph persistent).
7. Safety dashboard: track reply rates, flags.

Safety first: All sending should start with human approval.