"""
Lead discovery via Apify's harvestapi/linkedin-profile-search actor.
No LinkedIn cookies required — uses Apify's infrastructure.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from apify_client import ApifyClient

SEARCH_ACTOR = "harvestapi/linkedin-profile-search"

# Multiple focused queries run in parallel — each targets a different persona
# so results are complementary rather than overlapping.
KEYWORD_GROUPS = [
    "AI evaluator prompt engineer open to work",
    "RLHF contractor freelance gig",
    "job seeker AI annotation remote",
    "freelance developer open to work job hunting",
    "career transition tech job seeker",
]


def _normalise(item: dict, query: str) -> dict | None:
    """Convert a raw Apify item into a lead dict. Returns None if unusable."""
    profile_url = (
        item.get("profileUrl")
        or item.get("url")
        or item.get("linkedinUrl")
        or (f"https://www.linkedin.com/in/{item.get('publicIdentifier')}"
            if item.get("publicIdentifier") else None)
    )
    if not profile_url or "/in/" not in profile_url:
        return None

    name = item.get("fullName") or (
        f"{item.get('firstName', '')} {item.get('lastName', '')}".strip()
    )
    if not name:
        return None

    headline = item.get("headline") or ""
    about    = item.get("about") or item.get("summary") or ""
    ai_kws   = ["ai", "prompt", "rlhf", "evaluator", "annotation", "freelance", "gig"]
    hits     = sum(1 for kw in ai_kws if kw in headline.lower() or kw in about.lower())
    fit_score = min(10.0, 6.0 + hits * 0.5)

    degree = item.get("connectionDegree") or item.get("distance") or ""
    if str(degree) in ("1", "DISTANCE_1", "F"):
        rel = "1st"
    elif str(degree) in ("2", "DISTANCE_2", "S"):
        rel = "2nd"
    elif str(degree) in ("3", "DISTANCE_3", "O"):
        rel = "3rd"
    else:
        rel = "unknown"

    is_open_link = bool(item.get("openLink") or item.get("isOpenLink"))

    return {
        "name":                     name,
        "profile_url":              profile_url,
        "headline":                 headline,
        "location":                 item.get("location") or item.get("geoLocationName") or "",
        "about_snippet":            about[:300],
        "fit_score":                round(fit_score, 1),
        "why_qualified":            f"Found via LinkedIn search: {query}",
        "recent_activity_keywords": ai_kws[:3],
        "relationship_type":        rel,
        "is_open_link":             is_open_link,
        "_linkedin_member_id":      str(item.get("memberId") or item.get("profileId") or ""),
    }


def _run_single_search(client: ApifyClient, query: str, max_items: int) -> list[dict]:
    """Run one Apify search and return raw items."""
    run_input = {
        "searchQuery": query,
        "maxItems":    max_items,
        # No connectionDegree filter — Apify uses its own session so it can't
        # know YOUR connection degree. We map degree after the fact.
    }
    print(f"[Apify] Query: {query!r} (max {max_items})")
    try:
        run = client.actor(SEARCH_ACTOR).call(run_input=run_input, timeout_secs=300)
        if not run or not run.get("defaultDatasetId"):
            print(f"[Apify] No dataset for query: {query!r}")
            return []
        return list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as e:
        print(f"[Apify] Query failed ({query!r}): {e}")
        return []


def search_leads(
    keywords: list[str],
    max_items: int = 80,
    apify_token: str | None = None,
) -> list[dict]:
    """
    Run multiple parallel LinkedIn searches and merge unique leads.
    Returns normalised lead dicts compatible with OutreachState targets.
    """
    token = apify_token or os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN not set — cannot search LinkedIn leads.")

    client = ApifyClient(token)

    # Split budget across keyword groups; run them in parallel
    per_query = max(5, max_items // len(KEYWORD_GROUPS))
    print(f"[Apify] Running {len(KEYWORD_GROUPS)} parallel searches, {per_query} items each")

    all_raw: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(KEYWORD_GROUPS)) as pool:
        futures = {
            pool.submit(_run_single_search, client, q, per_query): q
            for q in KEYWORD_GROUPS
        }
        for fut in as_completed(futures):
            items = fut.result()
            print(f"[Apify] '{futures[fut]}' → {len(items)} raw items")
            all_raw.extend(items)

    print(f"[Apify] Total raw items: {len(all_raw)}")

    # Normalise + dedupe by profile_url
    seen: set[str] = set()
    leads: list[dict] = []
    for item in all_raw:
        lead = _normalise(item, "multi-search")
        if lead and lead["profile_url"] not in seen:
            seen.add(lead["profile_url"])
            leads.append(lead)

    # Sort: 1st-degree and OpenLink first (can always message)
    leads.sort(key=lambda t: (
        0 if (t["relationship_type"] == "1st" or t["is_open_link"]) else 1,
        -t["fit_score"],
    ))

    print(f"[Apify] {len(leads)} unique leads after dedup (sorted by reachability + fit)")
    return leads[:max_items]
