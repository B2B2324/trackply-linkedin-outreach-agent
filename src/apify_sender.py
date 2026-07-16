"""
Send LinkedIn voyager API requests by calling an Apify Actor that Maya OWNS,
instead of connecting to Apify's proxy directly from Railway.

Why: Railway's datacenter IP is blocked by LinkedIn's voyager API. Apify's
residential proxy fixes that, but (1) connecting to Apify Proxy from *outside*
Apify needs a paid plan, and (2) the official code-running scrapers
(apify/web-scraper, cheerio-scraper) require a "full permissions" grant that
the FREE plan won't extend to API/token runs. An Actor you OWN needs no such
grant, so we run the voyager call inside our own actor on a residential IP.

The owned actor lives in this repo under apify-actor/ (name:
linkedin-voyager-send). Deploy it to the Maya Apify account, then set
MAYA_SEND_ACTOR to "<username>/linkedin-voyager-send" (defaults below).

Usage (replaces _live_send in nodes.py):
    from src.apify_sender import apify_live_send
    result = apify_live_send(action, profile_url, message, target)
"""
from __future__ import annotations

import os

from apify_client import ApifyClient

from src.apify_linkedin import _run_field

# The owned actor's full name. Override via env once deployed if the account
# username differs.
SEND_ACTOR = (
    os.environ.get("MAYA_SEND_ACTOR")
    or "b2b2324/linkedin-voyager-send"
)


def _creds() -> tuple[dict, str | None]:
    """
    Gather the required credentials from the environment.
    Returns (creds_dict, error_str). error_str is None when all present.
    """
    creds = {
        "token": os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN"),
        "li_at": os.environ.get("LINKEDIN_LI_AT") or os.environ.get("li_at", ""),
        "jsessionid": os.environ.get("LINKEDIN_JSESSIONID") or os.environ.get("JSESSIONID", ""),
        "csrf_token": os.environ.get("LINKEDIN_CSRF_TOKEN") or os.environ.get("csrf-token", ""),
    }
    label = {"token": "APIFY_TOKEN", "li_at": "LINKEDIN_LI_AT",
             "jsessionid": "LINKEDIN_JSESSIONID", "csrf_token": "LINKEDIN_CSRF_TOKEN"}
    missing = [label[k] for k, v in creds.items() if not v]
    return creds, (f"Missing env vars: {', '.join(missing)}" if missing else None)


def _run_send_actor(creds: dict, actor_input: dict, *, label: str = "voyager") -> dict:
    """
    Call the owned linkedin-voyager-send Actor with actor_input and return its
    single result item.

    Returns {"ok": bool, "item": dict|None, "detail": str, "run_status": str}.
    """
    # Always attach the LinkedIn cookies the actor needs to authenticate.
    actor_input = {
        **actor_input,
        "liAt": creds["li_at"],
        "jsessionid": creds["jsessionid"],
        "csrfToken": creds["csrf_token"],
    }

    client = ApifyClient(creds["token"])
    try:
        # NOTE: this apify-client version rejects wait_secs/timeout_secs on
        # .call() (see src/apify_linkedin.py). The actor bounds its own runtime.
        run = client.actor(SEND_ACTOR).call(run_input=actor_input)
    except Exception as e:
        print(f"[ApifySender] {label}: Actor run failed to start: {e}")
        return {"ok": False, "item": None, "detail": f"Actor run failed to start: {e}", "run_status": "START_FAILED"}

    status = _run_field(run, "status") or "UNKNOWN"
    dataset_id = _run_field(run, "defaultDatasetId", "default_dataset_id")
    if status != "SUCCEEDED":
        msg = _run_field(run, "statusMessage", "status_message")
        print(f"[ApifySender] {label}: Actor run did NOT succeed ({status}): {msg}")

    if not dataset_id:
        return {"ok": False, "item": None,
                "detail": f"No dataset returned (run status={status})", "run_status": status}

    items = list(client.dataset(dataset_id).iterate_items())
    if not items:
        return {"ok": False, "item": None,
                "detail": "Actor produced no result item", "run_status": status}

    return {"ok": True, "item": items[0], "detail": "", "run_status": status}


def apify_live_send(action: str, profile_url: str, message: str, target: dict) -> dict:
    """
    Send a connection request or DM via the owned voyager-send Actor
    (residential proxy, no external-connection restriction, no full-permissions
    grant).

    Drop-in replacement for _live_send in nodes.py.
    Returns {"success": bool, "detail": str}.
    """
    creds, err = _creds()
    if err:
        return {"success": False, "detail": err}

    run = _run_send_actor(
        creds,
        {
            "action": action,
            "profileUrl": profile_url,
            "message": message,
            "memberId": target.get("_linkedin_member_id", ""),
        },
        label=action,
    )
    if not run["ok"]:
        return {"success": False, "detail": run["detail"]}

    result = run["item"]
    print(f"[ApifySender] {action} → {profile_url}: {result.get('status_code', '?')} (owned Actor)")
    return {
        "success": bool(result.get("success")),
        "status_code": result.get("status_code"),
        "detail": result.get("detail", ""),
    }


def apify_selftest() -> dict:
    """
    Verify the owned-Actor voyager path end-to-end WITHOUT sending anything:
    runs the actor with action="selftest" (a read-only GET /voyager/api/me).
    A 200 proves the send path is unblocked. Returns a JSON-serialisable dict
    for the /selftest endpoint.
    """
    creds, err = _creds()
    if err:
        return {"success": False, "stage": "credentials", "detail": err}

    run = _run_send_actor(creds, {"action": "selftest"}, label="selftest")
    if not run["ok"]:
        return {"success": False, "stage": "actor_run",
                "run_status": run["run_status"], "detail": run["detail"],
                "actor": SEND_ACTOR}

    item = run["item"]
    status_code = item.get("status_code")
    authenticated = bool(item.get("authenticated"))
    success = bool(item.get("success")) and authenticated
    print(f"[ApifySender] selftest → GET /me: {status_code} authenticated={authenticated}")
    # Pass the actor's richer diagnostic fields straight through so the caller
    # can see the redirect chain / cookie names without another round-trip.
    passthrough = {
        k: item[k]
        for k in ("logged_in_feed", "feed_final_url", "feed_hops", "me_hops", "control",
                  "cookies_after_warmup", "body_snippet")
        if k in item
    }
    return {
        "success": success,
        "stage": "voyager_call",
        "actor": SEND_ACTOR,
        "status_code": status_code,
        "authenticated": authenticated,
        "detail": item.get("detail", ""),
        **passthrough,
    }
