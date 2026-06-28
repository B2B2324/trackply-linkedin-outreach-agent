"""
Route LinkedIn voyager API calls through Apify's residential proxy pool.

Railway datacenter IPs are blocked by LinkedIn's voyager API (403/404).
Apify's residential proxies use real home/ISP IPs that LinkedIn accepts.

The proxy password is fetched from the Apify API using the existing APIFY_TOKEN
— no separate credential needed. Result is cached for the process lifetime.

Usage (replaces _live_send in nodes.py):
    from src.apify_sender import apify_live_send
    result = apify_live_send(action, profile_url, message, target)
"""
from __future__ import annotations

import os
from functools import lru_cache

from apify_client import ApifyClient


@lru_cache(maxsize=1)
def _get_proxy_password(apify_token: str) -> str | None:
    """
    Fetch the Apify residential proxy password via the API.
    Cached — one call per process, not per send.
    """
    try:
        client = ApifyClient(apify_token)
        user = client.user("me").get()
        password = (user or {}).get("proxy", {}).get("password")
        if not password:
            print("[ApifySender] Could not get proxy password from Apify user info")
        return password
    except Exception as e:
        print(f"[ApifySender] Failed to fetch proxy password: {e}")
        return None


def _build_proxy_url(apify_token: str) -> str | None:
    """
    Build the Apify residential proxy URL.
    Format: http://groups-RESIDENTIAL,country-US:<password>@proxy.apify.com:8000
    """
    password = _get_proxy_password(apify_token)
    if not password:
        return None
    return f"http://groups-RESIDENTIAL,country-US:{password}@proxy.apify.com:8000"


def build_proxied_sender(apify_token: str | None = None):
    """
    Return a LinkedInSender that routes voyager calls through Apify's
    residential proxy. Returns None if credentials are missing.
    """
    token = apify_token or os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    li_at = os.environ.get("LINKEDIN_LI_AT") or os.environ.get("li_at", "")
    jsessionid = os.environ.get("LINKEDIN_JSESSIONID") or os.environ.get("JSESSIONID", "")
    csrf_token = os.environ.get("LINKEDIN_CSRF_TOKEN") or os.environ.get("csrf-token", "")
    own_url = os.environ.get("LINKEDIN_OWN_PROFILE_URL") or os.environ.get("OWN_PROFILE_URL", "")

    if not all([token, li_at, jsessionid, csrf_token, own_url]):
        missing = [k for k, v in {
            "APIFY_TOKEN": token, "LINKEDIN_LI_AT": li_at,
            "LINKEDIN_JSESSIONID": jsessionid, "LINKEDIN_CSRF_TOKEN": csrf_token,
            "LINKEDIN_OWN_PROFILE_URL": own_url,
        }.items() if not v]
        print(f"[ApifySender] Missing env vars: {', '.join(missing)}")
        return None

    proxy_url = _build_proxy_url(token)
    if not proxy_url:
        print("[ApifySender] No proxy URL — falling back to direct (may 403)")

    from src.linkedin_sender import LinkedInSender
    return LinkedInSender(
        li_at=li_at,
        jsessionid=jsessionid,
        csrf_token=csrf_token,
        own_profile_url=own_url,
        proxy_url=proxy_url,  # None → direct (no proxy)
    )


def apify_live_send(action: str, profile_url: str, message: str, target: dict) -> dict:
    """
    Send a connection request or DM via the LinkedIn voyager API, routing
    through Apify's residential proxy so Railway's datacenter IP isn't used.

    Drop-in replacement for _live_send in nodes.py.
    Returns {"success": bool, "detail": str}.
    """
    sender = build_proxied_sender()
    if not sender:
        return {
            "success": False,
            "detail": (
                "LinkedIn credentials or APIFY_TOKEN not set. "
                "Required: APIFY_TOKEN, LINKEDIN_LI_AT, LINKEDIN_JSESSIONID, "
                "LINKEDIN_CSRF_TOKEN, LINKEDIN_OWN_PROFILE_URL"
            ),
        }

    member_id = target.get("_linkedin_member_id", "")

    if action == "connection_request":
        result = sender.send_connection_request(profile_url, note=message, member_id=member_id)
    elif action == "dm":
        result = sender.send_dm(profile_url, message=message, member_id=member_id)
    else:
        result = {"success": False, "detail": f"Unknown action: {action}"}

    # Log proxy status for Railway debugging
    proxy_label = "via Apify proxy" if sender.proxy_url else "direct (no proxy)"
    print(f"[ApifySender] {action} → {profile_url}: {result.get('status_code', '?')} ({proxy_label})")
    return result
