"""
Reddit thread discovery via Grok live web search.

Uses xAI's Grok-3 with search_parameters to find fresh Reddit threads
about job hunting and AI freelance work — no Reddit API credentials needed
for discovery. Returns structured thread data for the agent to score and act on.
"""
from __future__ import annotations

import json
import os
import re
import requests

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL   = "grok-3"

# Subreddits where organic engagement is welcome and Trackply is relevant.
# Ordered by relevance — the agent targets the top few per run.
TARGET_SUBS = [
    "jobsearch",
    "freelance",
    "artificial",
    "WorkOnline",
    "cscareerquestions",
    "ArtificialIntelligence",
    "remotework",
    "learnmachinelearning",
]

SEARCH_QUERIES = [
    "site:reddit.com job search tracking applications overwhelming",
    "site:reddit.com AI freelance gig management platform",
    "site:reddit.com job hunting spreadsheet organizer tips",
    "site:reddit.com freelancing AI annotation RLHF tracking",
    "site:reddit.com managing multiple job applications chaos",
]


def _call_grok(prompt: str, api_key: str) -> str:
    """Call Grok with live web search restricted to Reddit."""
    payload = {
        "model": GROK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "search_parameters": {
            "mode": "auto",
            "sources": [{"type": "web", "allowed_websites": ["reddit.com"]}],
        },
        "temperature": 0.2,
        "max_tokens": 2000,
    }
    resp = requests.post(
        GROK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"Grok API error {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"] or ""


def find_reddit_threads(max_threads: int = 10) -> list[dict]:
    """
    Use Grok to find fresh Reddit threads about job hunting / AI freelance work.

    Returns a list of dicts:
        url, subreddit, title, body_snippet, age_hint, engagement_hint
    """
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("[reddit_grok] XAI_API_KEY not set — skipping Grok thread discovery")
        return []

    subs = " OR ".join(f"subreddit:{s}" for s in TARGET_SUBS[:6])
    prompt = f"""Search Reddit right now for recent threads (posted in the last 48 hours) where people are:
- Struggling to manage job applications or track their job search
- Managing AI freelance gigs (RLHF, annotation, prompt engineering, Outlier, Scale AI, etc.)
- Looking for tools or advice to stay organized while job hunting
- Talking about using AI tools to find jobs or manage freelance work

Target subreddits: {', '.join(TARGET_SUBS[:6])}

Find up to {max_threads} threads. For each, return a JSON array with objects:
{{
  "url": "https://reddit.com/r/.../comments/...",
  "subreddit": "subreddit name",
  "title": "thread title",
  "body_snippet": "first 200 chars of post or top comment",
  "age_hint": "e.g. '3 hours ago'",
  "upvotes_hint": "e.g. '47 upvotes'"
}}

Return ONLY the JSON array, no prose."""

    try:
        raw = _call_grok(prompt, api_key)
        # Extract JSON array
        match = re.search(r"\[[\s\S]*\]", raw)
        if not match:
            print(f"[reddit_grok] No JSON array in Grok response: {raw[:300]}")
            return []
        threads = json.loads(match.group(0))
        valid = [t for t in threads if t.get("url") and "reddit.com" in t["url"]]
        print(f"[reddit_grok] Grok found {len(valid)} Reddit threads")
        return valid[:max_threads]
    except Exception as e:
        print(f"[reddit_grok] Thread discovery failed: {e}")
        return []


def score_thread_for_mention(thread: dict) -> float:
    """
    Heuristic score 0-1: how naturally can we mention Trackply in this thread?
    Higher = better fit for a Trackply mention.
    """
    text = (thread.get("title", "") + " " + thread.get("body_snippet", "")).lower()
    score = 0.0

    # Strong signals — thread is explicitly about the problem Trackply solves
    if any(kw in text for kw in ["track", "organiz", "spreadsheet", "overwhelm", "keep track", "lost track"]):
        score += 0.4
    if any(kw in text for kw in ["job application", "applications", "job hunt", "job search"]):
        score += 0.3
    if any(kw in text for kw in ["rlhf", "annotation", "outlier", "scale ai", "ai gig", "freelance ai"]):
        score += 0.35
    if any(kw in text for kw in ["tool", "app", "platform", "software", "recommend"]):
        score += 0.2

    # Penalty — already has a promo / spam feel or is off-topic
    if any(kw in text for kw in ["hiring", "job posting", "we are hiring", "[hiring]"]):
        score -= 0.5
    if any(kw in text for kw in ["politics", "rant", "venting", "frustrated"]):
        score -= 0.2

    return max(0.0, min(1.0, score))
