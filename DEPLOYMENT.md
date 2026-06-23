# Deployment Guide - Trackply Agentic Marketing OS

## Quick Local Testing

```bash
git clone https://github.com/B2B2324/trackply-linkedin-outreach-agent.git
cd trackply-linkedin-outreach-agent
pip install -r requirements.txt
cp .env.example .env
streamlit run dashboard/app.py
```

## Running Agents Individually

```bash
# LinkedIn (safe review mode)
python src/linkedin_agent.py

# Reddit
python src/reddit_agent.py

# SEO
python src/seo_agent.py
```

## Production Deployment Recommendations

### Option 1: Railway (Easiest)
1. Connect your GitHub repo to Railway
2. Add environment variables from `.env`
3. Deploy as a background worker + web service (for dashboard)

### Option 2: Vercel
- Good for the Streamlit dashboard (with some config)
- Not ideal for long-running agents

### Option 3: VPS (DigitalOcean, Hetzner, etc.)
- Most flexible for running agents 24/7
- Use `systemd` or `supervisor` to keep agents running
- Use `cron` or `APScheduler` for scheduled runs

## Scheduling
Use `APScheduler` or cron jobs to run agents daily at set times.

## Monitoring
- Langfuse for token usage and costs
- Streamlit dashboard for high-level status
- Add logging + alerts for production