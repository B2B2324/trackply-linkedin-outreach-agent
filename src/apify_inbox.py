"""
Poll a user's LinkedIn inbox for new replies using Apify's
linkedin-conversation-scraper actor.

Actor: simpleapi/linkedin-conversation-scraper
Docs: https://apify.com/simpleapi/linkedin-conversation-scraper

Returns conversations where a known lead has replied since we last reached out.
Uses the known_leads dict {profile_url → lead_name} to filter relevant threads.

Note: this actor has ~50% success rate (LinkedIn has hardened against scraping).
It's the best available option for inbox polling without a verified app.
"""
from __future__ import annotations

import os
import time
from typing import Any


def poll_replies(
    known_leads: dict[str, str],
    max_conversations: int = 50,
    timeout_secs: int = 120,
) -> list[dict[str, Any]]:
    """
    Run the Apify linkedin-conversation-scraper actor and return a list of
    PendingReply-compatible dicts for any lead who has replied.

    Args:
        known_leads: {profile_url: lead_name} — only threads with these profiles
                     are returned
        max_conversations: how many recent conversations to fetch (default 50)
        timeout_secs: how long to wait for the Apify run (default 120s)

    Returns:
        list of {profile_url, name, reply_text, thread_id, conversation_url}
        May be empty if Apify run fails or no relevant replies are found.
    """
    apify_token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    li_at = os.environ.get("LINKEDIN_LI_AT") or os.environ.get("li_at", "")

    if not apify_token or not li_at:
        print("[InboxPoll] Missing APIFY_TOKEN or LINKEDIN_LI_AT — skipping inbox poll")
        return []

    try:
        from apify_client import ApifyClient
    except ImportError:
        print("[InboxPoll] apify-client not installed — skipping inbox poll")
        return []

    client = ApifyClient(apify_token)

    print(f"[InboxPoll] Starting linkedin-conversation-scraper (max {max_conversations} threads)…")
    try:
        run = client.actor("simpleapi/linkedin-conversation-scraper").call(
            run_input={
                "cookie": li_at,
                "count": max_conversations,
            },
            timeout_secs=timeout_secs,
        )
    except Exception as e:
        print(f"[InboxPoll] Actor run failed: {e}")
        return []

    if not run:
        print("[InboxPoll] Actor returned no run — skipping")
        return []

    run_id = run.get("id") or run.get("runId") or ""
    status = run.get("status", "UNKNOWN")
    print(f"[InboxPoll] Run {run_id} finished with status: {status}")

    if status not in ("SUCCEEDED",):
        print(f"[InboxPoll] Non-success status '{status}' — skipping reply extraction")
        return []

    # Fetch dataset items (each item is a conversation thread)
    dataset_id = (run.get("defaultDatasetId") or "")
    if not dataset_id:
        print("[InboxPoll] No dataset ID returned")
        return []

    try:
        items = list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        print(f"[InboxPoll] Dataset fetch failed: {e}")
        return []

    print(f"[InboxPoll] {len(items)} conversation threads returned")

    # Normalise known_leads keys: strip trailing slashes, lowercase
    def normalise_url(url: str) -> str:
        return url.rstrip("/").lower()

    lead_map = {normalise_url(k): v for k, v in known_leads.items()}

    pending: list[dict[str, Any]] = []

    for thread in items:
        # Actor returns threads with a participant list and message array.
        # Shape may vary by actor version — handle both common schemas.
        participants = thread.get("participants") or thread.get("conversationParticipants") or []
        messages = thread.get("messages") or thread.get("conversationMessages") or []
        thread_id = str(thread.get("conversationId") or thread.get("id") or "")
        conversation_url = thread.get("conversationUrl") or ""

        # Find a participant who is a known lead
        matched_url: str | None = None
        matched_name: str | None = None
        for p in participants:
            p_url = normalise_url(
                p.get("profileUrl") or p.get("url") or p.get("publicProfileUrl") or ""
            )
            if not p_url:
                continue
            # Match by URL substring (handles trailing /overlay/ etc.)
            for lead_url, lead_name in lead_map.items():
                if lead_url in p_url or p_url in lead_url:
                    matched_url = lead_url
                    matched_name = lead_name
                    break
            if matched_url:
                break

        if not matched_url:
            continue

        # Find the most recent message that's FROM the lead (not from us)
        own_url = normalise_url(
            os.environ.get("LINKEDIN_OWN_PROFILE_URL") or os.environ.get("OWN_PROFILE_URL", "")
        )
        lead_messages = [
            m for m in messages
            if normalise_url(
                m.get("senderUrl") or m.get("sender", {}).get("profileUrl") or ""
            ) != own_url
        ]

        if not lead_messages:
            continue

        # Take the most recent lead message
        latest = lead_messages[-1] if isinstance(lead_messages, list) else lead_messages[0]
        reply_text = (
            latest.get("body")
            or latest.get("text")
            or latest.get("content")
            or latest.get("message")
            or ""
        ).strip()

        if not reply_text:
            continue

        pending.append({
            "profile_url":      matched_url,
            "name":             matched_name or "unknown",
            "reply_text":       reply_text,
            "thread_id":        thread_id,
            "conversation_url": conversation_url,
        })
        print(f"[InboxPoll] New reply from {matched_name}: "{reply_text[:80]}…"")

    print(f"[InboxPoll] {len(pending)} pending replies from known leads")
    return pending
