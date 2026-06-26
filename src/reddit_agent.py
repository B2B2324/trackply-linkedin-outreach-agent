"""
Reddit engagement agent — finds relevant threads via Grok, generates Kemba-voiced
comments with natural Trackply mentions, and posts them via PRAW.

Flow:
  1. discover  — Grok live-searches Reddit for fresh job-hunt / AI-freelance threads
  2. filter    — score threads; keep only high-fit ones; skip already-engaged
  3. generate  — Claude writes a genuine Kemba comment (max 3 per run)
  4. post      — PRAW posts in live mode; shows drafts in review mode

Persona: Kemba is Trackply's AI job coach (a friendly Husky).
Voice: helpful, casual, personal — never sounds like an ad.
Trackply mention: only when it fits; always "try trackply.com" not a hard sell.
"""
from __future__ import annotations

import json
import os

from src.llm          import call_llm
from src.supabase_client import log_activity

# Trackply knowledge injected into every generation prompt so Kemba is accurate.
TRACKPLY_FACTS = """
Trackply (trackply.com) is a free AI-powered job application tracker built for:
- People juggling multiple job applications who lose track of where they applied
- AI freelancers (RLHF, annotation, prompt engineers) managing gigs across Outlier, Scale AI, etc.
- Anyone who hates spreadsheets and wants an automated job coach

Key features:
- Auto-tracks applications from any source (LinkedIn, email, direct apply)
- Meta Agent: AI that applies to jobs on your behalf (finds + applies)
- Kemba AI Coach: answers job hunting questions, reviews resumes, preps interviews
- Free tier available — no credit card required

What Trackply is NOT: it's not a job board, not a resume builder, not a recruiter tool.
"""

KEMBA_SYSTEM = f"""You are Kemba, Trackply's AI job coach — a friendly, smart Husky who helps people
with their job search and AI freelance careers. You're posting on Reddit as a helpful community member.

Rules:
- Sound like a real person helping another person — never like marketing copy
- Be specific to what the OP said — reference their exact situation
- Only mention Trackply if it genuinely solves the OP's problem
- When you mention Trackply say something like "I built a free tool for this exact thing — trackply.com"
  or "there's a free app called Trackply that handles this" — casual, not a pitch
- Keep comments under 150 words
- Never use phrases like "I'd like to introduce", "check out my product", "shameless plug"
- If the thread doesn't naturally call for a Trackply mention, just give helpful advice

Trackply facts (use only when relevant):
{TRACKPLY_FACTS}
"""

# Minimum fit score to act on a thread
FIT_THRESHOLD = 0.35

# Max engagements per run (safety limit — enforced here AND in reddit_sender)
MAX_PER_RUN = 3


def discover_threads(max_threads: int = 15) -> list[dict]:
    """Grok live-searches Reddit for relevant threads."""
    try:
        from src.reddit_grok import find_reddit_threads
        return find_reddit_threads(max_threads=max_threads)
    except Exception as e:
        print(f"[reddit_agent] discover failed: {e}")
        return []


def filter_threads(threads: list[dict]) -> list[dict]:
    """Score and rank threads; drop low-fit and already-engaged ones."""
    from src.reddit_grok     import score_thread_for_mention
    from src.reddit_sender   import already_commented

    scored = []
    for t in threads:
        score = score_thread_for_mention(t)
        if score < FIT_THRESHOLD:
            continue
        url = t.get("url", "")
        if already_commented(url):
            print(f"[reddit_agent] Already engaged {url}, skipping")
            continue
        scored.append({**t, "_fit_score": round(score, 2)})

    scored.sort(key=lambda x: x["_fit_score"], reverse=True)
    print(f"[reddit_agent] {len(scored)} threads passed filter (threshold={FIT_THRESHOLD})")
    return scored[:MAX_PER_RUN]


def generate_comment(thread: dict) -> str:
    """Ask Claude to write a Kemba-voiced comment for this thread."""
    user_prompt = (
        f"Reddit thread in r/{thread.get('subreddit', '?')}:\n"
        f"Title: {thread.get('title', '')}\n"
        f"Post: {thread.get('body_snippet', '')[:400]}\n\n"
        f"Write a helpful comment as Kemba. Fit score for Trackply mention: {thread.get('_fit_score', 0):.2f} "
        f"(only mention Trackply if score > 0.5)."
    )
    try:
        return call_llm(KEMBA_SYSTEM, user_prompt).strip()
    except Exception as e:
        print(f"[reddit_agent] generate_comment failed: {e}")
        return ""


def run_reddit_agent(review_mode: bool = True) -> dict:
    """
    Full agent run.

    review_mode=True  → generate comments, return drafts, don't post
    review_mode=False → generate and post via PRAW

    Returns:
        {
          "success": bool,
          "threads_found": int,
          "engagements": [{"thread_url", "subreddit", "title", "comment", "fit_score", "posted"}],
          "errors": [str],
        }
    """
    errors      : list[str] = []
    engagements : list[dict] = []

    # 1. Discover
    threads = discover_threads()
    if not threads:
        # Fallback: no Grok key or no results — try PRAW search directly
        print("[reddit_agent] No Grok threads; attempting PRAW keyword search fallback")
        threads = _praw_fallback_search()

    if not threads:
        return {
            "success": False,
            "threads_found": 0,
            "engagements": [],
            "errors": ["No relevant Reddit threads found. Check XAI_API_KEY or REDDIT_* credentials."],
        }

    # 2. Filter
    targets = filter_threads(threads)
    if not targets:
        return {
            "success": True,
            "threads_found": len(threads),
            "engagements": [],
            "errors": ["No threads passed the fit filter — nothing natural to engage."],
        }

    # 3. Generate
    prepared = []
    for t in targets:
        comment = generate_comment(t)
        if not comment:
            errors.append(f"Comment generation failed for {t.get('title', '?')}")
            continue
        prepared.append({
            "thread_url":  t.get("url", ""),
            "subreddit":   t.get("subreddit", ""),
            "title":       t.get("title", ""),
            "comment":     comment,
            "fit_score":   t.get("_fit_score", 0),
        })

    # 4. Post (or dry-run)
    from src.reddit_sender import run_engagement
    results = run_engagement(prepared, dry_run=review_mode)

    for item, result in zip(prepared, results):
        engagements.append({
            **item,
            "posted":  result.get("success", False) and not review_mode,
            "drafted": review_mode,
        })

    log_activity(
        "reddit",
        "run_complete",
        None,
        "success" if not errors else "partial",
        {
            "mode": "review" if review_mode else "live",
            "threads_found": len(threads),
            "engaged": len(engagements),
        },
    )

    return {
        "success":       True,
        "threads_found": len(threads),
        "engagements":   engagements,
        "errors":        errors,
    }


def _praw_fallback_search(limit: int = 20) -> list[dict]:
    """
    PRAW-based keyword search — used when Grok is unavailable.
    Searches target subreddits for relevant hot/new threads.
    """
    from src.reddit_sender import reddit_from_env
    from src.reddit_grok   import TARGET_SUBS

    reddit = reddit_from_env()
    if not reddit:
        return []

    keywords = ["job applications", "job search", "AI freelance", "RLHF", "track applications"]
    threads  = []

    try:
        for sub_name in TARGET_SUBS[:4]:
            sub = reddit.subreddit(sub_name)
            for submission in sub.new(limit=50):
                text = (submission.title + " " + (submission.selftext or "")).lower()
                if any(kw.lower() in text for kw in keywords):
                    threads.append({
                        "url":          f"https://reddit.com{submission.permalink}",
                        "subreddit":    sub_name,
                        "title":        submission.title,
                        "body_snippet": (submission.selftext or "")[:200],
                        "age_hint":     "recent",
                        "upvotes_hint": str(submission.score),
                    })
                if len(threads) >= limit:
                    break
            if len(threads) >= limit:
                break
    except Exception as e:
        print(f"[reddit_agent] PRAW fallback failed: {e}")

    print(f"[reddit_agent] PRAW fallback found {len(threads)} threads")
    return threads
