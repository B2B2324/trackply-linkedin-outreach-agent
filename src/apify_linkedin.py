"""
Lead discovery via Apify's harvestapi/linkedin-profile-search actor.
No LinkedIn cookies required — uses Apify's infrastructure.
"""
from __future__ import annotations

import os
from apify_client import ApifyClient

SEARCH_ACTOR = "harvestapi/linkedin-profile-search"


def search_leads(
    keywords: list[str],
    max_items: int = 10,
    apify_token: str | None = None,
) -> list[dict]:
    """
    Search LinkedIn for people matching the given keywords.
    Returns normalised lead dicts compatible with OutreachState targets.
    """
    token = apify_token or os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN not set — cannot search LinkedIn leads.")

    client = ApifyClient(token)

    # Simple space-separated query — quoted multi-word OR chains return 0 results
    # on this actor; plain keywords work much better.
    query = " ".join(keywords[:4])

    run_input = {
        "searchQuery": query,
        "maxItems":    max_items,
    }

    print(f"[Apify] Searching LinkedIn for: {query!r} (max {max_items})")
    run = client.actor(SEARCH_ACTOR).call(run_input=run_input)

    if not run or not run.get("defaultDatasetId"):
        print("[Apify] Actor run returned no dataset")
        return []

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"[Apify] Raw items returned: {len(items)}")

    leads = []
    for item in items:
        profile_url = (
            item.get("profileUrl")
            or item.get("url")
            or item.get("linkedinUrl")
            or (f"https://www.linkedin.com/in/{item.get('publicIdentifier')}"
                if item.get("publicIdentifier") else None)
        )
        if not profile_url or "/in/" not in profile_url:
            continue

        name = item.get("fullName") or (
            f"{item.get('firstName', '')} {item.get('lastName', '')}".strip()
        )
        if not name:
            continue

        headline = item.get("headline") or ""
        about    = item.get("about") or item.get("summary") or ""
        ai_kws   = ["ai", "prompt", "rlhf", "evaluator", "annotation", "freelance", "gig"]
        hits     = sum(1 for kw in ai_kws if kw in headline.lower() or kw in about.lower())
        fit_score = min(10.0, 6.0 + hits * 0.5)

        leads.append({
            "name":                     name,
            "profile_url":              profile_url,
            "headline":                 headline,
            "location":                 item.get("location") or item.get("geoLocationName") or "",
            "about_snippet":            about[:300],
            "fit_score":                round(fit_score, 1),
            "why_qualified":            f"Found via LinkedIn search: {query}",
            "recent_activity_keywords": ai_kws[:3],
            "relationship_type":        "unknown",
            "is_open_link":             bool(item.get("openLink") or item.get("isOpenLink")),
            "_linkedin_member_id":      str(item.get("memberId") or item.get("profileId") or ""),
        })

    print(f"[Apify] Normalised {len(leads)} valid leads")
    return leads
