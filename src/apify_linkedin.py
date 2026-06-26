"""
Lead discovery via Apify's harvestapi/linkedin-profile-search actor.
No LinkedIn cookies required — uses Apify's infrastructure.
"""
from __future__ import annotations

import os
from apify_client import ApifyClient


SEARCH_ACTOR = "harvestapi/linkedin-profile-search"   # 24k users, 4.7★, no cookies


def search_leads(
    keywords: list[str],
    max_items: int = 10,
    apify_token: str | None = None,
) -> list[dict]:
    """
    Search LinkedIn for people matching the given keywords.
    Returns a list of normalised lead dicts compatible with OutreachState targets.
    """
    token = apify_token or os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN not set — cannot search LinkedIn leads.")

    client = ApifyClient(token)

    # Build a fuzzy search query from the keyword list
    query = " OR ".join(f'"{kw}"' for kw in keywords)

    run_input = {
        "profileScraperMode": "Full",
        "searchQuery": query,
        "maxItems": max_items,
        # Only people actively signalling openness — high intent
        "currentJobTitles": ["Open to Work"],
    }

    print(f"[Apify] Searching LinkedIn for: {query} (max {max_items})")
    run = client.actor(SEARCH_ACTOR).call(run_input=run_input)

    items = list(
        client.dataset(run["defaultDatasetId"]).iterate_items()
    )
    print(f"[Apify] Found {len(items)} profiles")

    leads = []
    for item in items:
        profile_url = (
            item.get("profileUrl")
            or item.get("url")
            or item.get("linkedinUrl")
            or f"https://www.linkedin.com/in/{item.get('publicIdentifier', '')}"
        )
        if not profile_url or "/in/" not in profile_url:
            continue

        # Extract name
        name = item.get("fullName") or (
            f"{item.get('firstName', '')} {item.get('lastName', '')}".strip()
        )

        # Fit score heuristic: boost for "open to work" signal and AI keywords
        headline = item.get("headline") or ""
        about = item.get("about") or item.get("summary") or ""
        ai_keywords = ["ai", "prompt", "rlhf", "evaluator", "annotation", "freelance", "gig"]
        keyword_hits = sum(1 for kw in ai_keywords if kw in headline.lower() or kw in about.lower())
        fit_score = min(10.0, 6.0 + keyword_hits * 0.5)

        leads.append({
            "name": name,
            "profile_url": profile_url,
            "headline": headline,
            "location": item.get("location") or item.get("geoLocationName") or "",
            "about_snippet": about[:300],
            "fit_score": round(fit_score, 1),
            "why_qualified": f"Found via LinkedIn search: {query}",
            "recent_activity_keywords": ai_keywords[:3],
            # relationship unknown without cookies — treated as 2nd degree in routing
            "relationship_type": "unknown",
            "is_open_link": bool(item.get("openLink") or item.get("isOpenLink")),
            # Store the numeric LinkedIn ID for the sender module
            "_linkedin_member_id": str(item.get("memberId") or item.get("profileId") or ""),
        })

    return leads
