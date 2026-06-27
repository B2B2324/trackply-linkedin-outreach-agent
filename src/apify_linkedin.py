"""
Lead discovery via Apify's harvestapi/linkedin-profile-search actor.
No LinkedIn cookies required — uses Apify's infrastructure.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from apify_client import ApifyClient

SEARCH_ACTOR = "harvestapi/linkedin-profile-search"


def _run_field(run, *keys):
    """
    Extract a field from an Apify run result that may be a plain dict OR a typed
    object, in either camelCase or snake_case. Returns the first match found.
    The installed apify-client version returns typed `Run` objects (no .get()),
    so we can't assume dict access.
    """
    if run is None:
        return None
    for key in keys:
        if isinstance(run, dict):
            if key in run:
                return run[key]
        elif hasattr(run, key):
            return getattr(run, key)
    # Last resort: some typed objects expose a dict via these methods
    for conv in ("to_dict", "model_dump", "dict"):
        fn = getattr(run, conv, None)
        if callable(fn):
            try:
                d = fn()
                for key in keys:
                    if isinstance(d, dict) and key in d:
                        return d[key]
            except Exception:
                pass
    return None

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
    """Convert a raw Apify item into a lead dict. Returns None if unusable.

    Field names match harvestapi/linkedin-profile-search output (verified):
      linkedinUrl, firstName, lastName, summary, openProfile, premium,
      location.linkedinText, currentPositions[].title/companyName, id
    """
    profile_url = (
        item.get("linkedinUrl")
        or item.get("profileUrl")
        or item.get("url")
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

    # Headline: search actor doesn't return one — synthesise from current position
    headline = item.get("headline") or ""
    positions = item.get("currentPositions") or []
    if not headline and positions:
        p0 = positions[0]
        title = (p0.get("title") or "").strip()
        company = (p0.get("companyName") or "").strip()
        headline = " at ".join(x for x in (title, company) if x)

    about    = item.get("summary") or item.get("about") or ""
    ai_kws   = ["ai", "prompt", "rlhf", "evaluator", "annotation",
                "freelance", "gig", "open to work", "machine learning"]
    text     = f"{headline} {about}".lower()
    hits     = sum(1 for kw in ai_kws if kw in text)
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

    # openProfile members can be DM'd without spending a connection request
    is_open_link = bool(
        item.get("openProfile") or item.get("openLink") or item.get("isOpenLink")
    )

    # Location may be nested ({"linkedinText": "Brazil"}) or a plain string
    loc = item.get("location")
    if isinstance(loc, dict):
        location = loc.get("linkedinText") or loc.get("text") or ""
    else:
        location = loc or item.get("geoLocationName") or ""

    return {
        "name":                     name,
        "profile_url":              profile_url.split("?")[0],
        "headline":                 headline,
        "location":                 location,
        "about_snippet":            about[:300],
        "fit_score":                round(fit_score, 1),
        "why_qualified":            f"Found via LinkedIn search: {query}",
        "recent_activity_keywords": ai_kws[:3],
        "relationship_type":        rel,
        "is_open_link":             is_open_link,
        "_linkedin_member_id":      str(item.get("id") or item.get("memberId") or item.get("profileId") or ""),
    }


def _run_single_search(client: ApifyClient, query: str, max_items: int) -> list[dict]:
    """Run one Apify search and return raw items."""
    run_input = {
        "searchQuery": query,
        "maxItems":    max_items,
    }
    print(f"[Apify] Query: {query!r} (max {max_items})")
    try:
        actor = client.actor(SEARCH_ACTOR)
        # .call() blocks until the run finishes. Pass NO timeout kwarg (this
        # client version rejects both wait_secs and timeout_secs).
        run = actor.call(run_input=run_input)
        status = _run_field(run, "status")
        run_id = _run_field(run, "id")
        print(f"[Apify] search run status={status} id={run_id}")
        if status and status != "SUCCEEDED":
            # FAILED / ABORTED / TIMED-OUT — the run did not complete normally.
            msg = _run_field(run, "statusMessage") or _run_field(run, "status_message")
            print(f"[Apify] search run did NOT succeed ({status}): {msg}")
        dataset_id = _run_field(run, "defaultDatasetId", "default_dataset_id")
        if not dataset_id:
            print(f"[Apify] No dataset for query: {query!r} (run type={type(run).__name__})")
            return []
        return list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        print(f"[Apify] Query failed ({query!r}): {e}")
        return []


CONNECTIONS_ACTOR = "scrapeflow/linkedin-network-scraper"


def fetch_connections_via_apify(limit: int = 200, apify_token: str | None = None) -> list[dict]:
    """
    Fetch the user's 1st-degree LinkedIn connections via Apify's network scraper.
    Uses Apify's residential proxies — works from Railway (voyager API is blocked there).
    Only needs LINKEDIN_LI_AT.
    """
    token = apify_token or os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    li_at = os.environ.get("LINKEDIN_LI_AT") or os.environ.get("li_at", "")

    if not token or not li_at:
        print("[Apify] fetch_connections_via_apify: missing APIFY_TOKEN or LINKEDIN_LI_AT")
        return []

    client = ApifyClient(token)
    run_input = {
        "liAtCookie": li_at,
    }
    print(f"[Apify] Fetching up to {limit} connections via residential proxy...")
    try:
        run = client.actor(CONNECTIONS_ACTOR).call(run_input=run_input)
        status = _run_field(run, "status")
        run_id = _run_field(run, "id")
        print(f"[Apify] connections run status={status} id={run_id}")
        if status and status != "SUCCEEDED":
            msg = _run_field(run, "statusMessage") or _run_field(run, "status_message")
            print(f"[Apify] connections run did NOT succeed ({status}): {msg}")
        dataset_id = _run_field(run, "defaultDatasetId", "default_dataset_id")
        if not dataset_id:
            print("[Apify] fetch_connections: no dataset returned")
            return []
        raw = list(client.dataset(dataset_id).iterate_items())
        print(f"[Apify] fetch_connections: {len(raw)} raw items")
        if raw:
            # Log the keys of the first item once so we can see the real schema in Railway logs
            print(f"[Apify] fetch_connections: sample item keys = {list(raw[0].keys())}")

        leads = []
        for item in raw:
            # Defensive: this actor's exact field names aren't published, so try every
            # plausible variant for name / profile url / headline.
            name = (
                item.get("fullName")
                or item.get("name")
                or f"{item.get('firstName','')} {item.get('lastName','')}".strip()
            )
            profile_url = (
                item.get("profileUrl")
                or item.get("publicProfileUrl")
                or item.get("profile_url")
                or item.get("url")
                or item.get("vanityUrl")
                or item.get("linkedinUrl")
            )
            # Fall back to building a URL from a public identifier if no full URL present
            if not profile_url:
                pid = (
                    item.get("publicIdentifier")
                    or item.get("vanityName")
                    or item.get("publicId")
                    or item.get("username")
                )
                if pid:
                    profile_url = f"https://www.linkedin.com/in/{pid}"

            if not name or not profile_url or "/in/" not in profile_url:
                continue
            leads.append({
                "name": name,
                "profile_url": profile_url.split("?")[0],
                "headline": item.get("headline") or item.get("occupation") or item.get("title") or "",
                "location": item.get("location") or item.get("geoLocationName") or "",
                "about_snippet": "",
                "fit_score": 7.0,
                "why_qualified": "1st-degree LinkedIn connection — can DM directly",
                "recent_activity_keywords": [],
                "relationship_type": "1st",
                "is_open_link": False,
                "_linkedin_member_id": str(item.get("memberId") or item.get("entityUrn") or ""),
            })
        print(f"[Apify] fetch_connections: {len(leads)} normalised leads")
        return leads[:limit]
    except Exception as e:
        print(f"[Apify] fetch_connections error: {e}")
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
