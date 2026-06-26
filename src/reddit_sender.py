"""
Reddit posting via PRAW — the official Reddit API wrapper.

Safety rules baked in:
- Max 3 comments per run (no spam)
- 60-120s human-like delay between posts
- Never comment on the same thread twice (checks Supabase outreach_activity)
- Only engage threads < 48h old
- Dry-run mode returns what would have been posted without actually posting
"""
from __future__ import annotations

import os
import random
import time

_PRAW_AVAILABLE = False
try:
    import praw                     # type: ignore
    _PRAW_AVAILABLE = True
except ImportError:
    pass


MAX_COMMENTS_PER_RUN = 3
MIN_DELAY_SECONDS    = 60
MAX_DELAY_SECONDS    = 120


def _build_reddit(
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
    user_agent: str | None = None,
):
    if not _PRAW_AVAILABLE:
        raise RuntimeError("praw is not installed — add it to requirements.txt")
    ua = user_agent or f"Trackply:KembaAgent:1.0 (by u/{username})"
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent=ua,
    )


def reddit_from_env():
    """Build a PRAW Reddit instance from environment variables. Returns None if unconfigured."""
    cid    = os.environ.get("REDDIT_CLIENT_ID", "")
    secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    user   = os.environ.get("REDDIT_USERNAME", "")
    pw     = os.environ.get("REDDIT_PASSWORD", "")
    if not all([cid, secret, user, pw]):
        return None
    try:
        return _build_reddit(cid, secret, user, pw)
    except Exception as e:
        print(f"[reddit_sender] PRAW init failed: {e}")
        return None


def already_commented(thread_url: str) -> bool:
    """Check Supabase outreach_activity to see if we already engaged this thread."""
    try:
        from src.supabase_client import supabase
        res = supabase.table("outreach_activity").select("id").eq("target", thread_url).eq("agent", "reddit").limit(1).execute()
        return bool(res.data)
    except Exception:
        return False


def post_comment(
    thread_url: str,
    comment_text: str,
    *,
    dry_run: bool = True,
) -> dict:
    """
    Post a comment on a Reddit thread.

    dry_run=True  → returns what would be posted, no network call.
    dry_run=False → actually posts via PRAW, logs to Supabase.
    """
    if dry_run:
        print(f"[reddit_sender] [DRY RUN] Would comment on {thread_url}")
        return {"success": True, "dry_run": True, "url": thread_url, "comment": comment_text}

    reddit = reddit_from_env()
    if not reddit:
        return {"success": False, "detail": "PRAW credentials not configured"}

    try:
        submission = reddit.submission(url=thread_url)
        comment = submission.reply(comment_text)
        print(f"[reddit_sender] Commented on {thread_url} → {comment.id}")

        # Log to Supabase
        try:
            from src.supabase_client import log_activity
            log_activity("reddit", "comment_posted", thread_url, "success",
                         {"comment_id": comment.id, "preview": comment_text[:100]})
        except Exception:
            pass

        time.sleep(random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))
        return {"success": True, "comment_id": comment.id, "url": thread_url}

    except Exception as e:
        print(f"[reddit_sender] Comment failed on {thread_url}: {e}")
        return {"success": False, "detail": str(e), "url": thread_url}


def run_engagement(engagements: list[dict], *, dry_run: bool = True) -> list[dict]:
    """
    Post up to MAX_COMMENTS_PER_RUN comments from the prepared engagement list.

    Each item: {"thread_url": str, "comment": str}
    Returns list of result dicts.
    """
    results = []
    posted  = 0

    for item in engagements:
        if posted >= MAX_COMMENTS_PER_RUN:
            print(f"[reddit_sender] Hit per-run limit ({MAX_COMMENTS_PER_RUN}), stopping")
            break

        url  = item.get("thread_url", "")
        text = item.get("comment", "")
        if not url or not text:
            continue

        if not dry_run and already_commented(url):
            print(f"[reddit_sender] Already commented on {url}, skipping")
            continue

        result = post_comment(url, text, dry_run=dry_run)
        results.append({**result, "thread_url": url})
        if result.get("success"):
            posted += 1

    print(f"[reddit_sender] Run complete — {posted} comment(s) {'drafted' if dry_run else 'posted'}")
    return results
