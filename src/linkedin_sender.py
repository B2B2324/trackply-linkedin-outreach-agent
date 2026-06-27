"""
LinkedIn message sender using LinkedIn's internal voyager API.

Requires three cookie values from a logged-in LinkedIn browser session:
  LINKEDIN_LI_AT        — the main session token (li_at cookie)
  LINKEDIN_JSESSIONID   — JSESSIONID cookie value (without quotes)
  LINKEDIN_CSRF_TOKEN   — csrf-token cookie value

Also requires:
  LINKEDIN_OWN_PROFILE_URL  — your own LinkedIn profile URL
                              e.g. https://www.linkedin.com/in/stephen-xyz

How to get the cookie values:
  1. Log into LinkedIn in Chrome
  2. Open DevTools → Application → Cookies → www.linkedin.com
  3. Copy the values for li_at, JSESSIONID (strip surrounding quotes), csrf-token
"""
from __future__ import annotations

import base64
import json
import os
import random
import string
import time

import requests


_BASE = "https://www.linkedin.com/voyager/api"
_TIMEOUT = 15


def _tracking_id() -> str:
    """Random base64 string used as a tracking ID on LinkedIn API calls."""
    raw = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    return base64.b64encode(raw.encode()).decode()


class LinkedInSender:
    """
    Thin wrapper around LinkedIn's voyager API for sending
    connection requests and DMs to 1st-degree connections.

    Instantiate once per run; reuse across leads.
    """

    def __init__(
        self,
        li_at: str,
        jsessionid: str,
        csrf_token: str,
        own_profile_url: str,
        user_agent: str | None = None,
    ):
        self.li_at = li_at
        self.jsessionid = jsessionid.strip('"')   # LinkedIn wraps JSESSIONID in quotes
        self.csrf_token = csrf_token
        self.own_profile_url = own_profile_url.rstrip("/")
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Restli-Protocol-Version": "2.0.0",
            "X-Li-Lang": "en_US",
            "X-Li-Track": json.dumps({
                "clientVersion": "1.13.15117",
                "mpVersion": "1.13.15117",
                "osName": "web",
                "timezoneOffset": -7,
                "timezone": "America/Los_Angeles",
                "deviceFormFactor": "DESKTOP",
                "mpName": "voyager-web",
                "displayDensity": 1,
                "displayWidth": 1920,
                "displayHeight": 1080,
            }),
            "Csrf-Token": self.csrf_token,
            "Cookie": (
                f"li_at={self.li_at}; "
                f'JSESSIONID="{self.jsessionid}"; '
                f"lang=v=2&lang=en-us"
            ),
        })
        return s

    # ── Profile lookup ────────────────────────────────────────────────────────

    def get_profile_urn(self, profile_url: str, member_id: str = "") -> str | None:
        """
        Returns the LinkedIn entity URN for a profile.
        Prefers the member_id if already known (avoids an extra API call).
        Falls back to fetching the profile page.
        """
        if member_id:
            return f"urn:li:member:{member_id}"

        # Extract vanity name from URL
        parts = profile_url.rstrip("/").split("/in/")
        if len(parts) < 2:
            return None
        public_id = parts[1].split("/")[0].split("?")[0]

        url = f"{_BASE}/identity/dash/profiles"
        params = {
            "q": "memberIdentity",
            "memberIdentity": public_id,
            "decorationId": "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-91",
        }
        try:
            r = self.session.get(url, params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            elements = data.get("elements", [])
            if elements:
                return elements[0].get("entityUrn") or elements[0].get("*profile")
        except Exception as e:
            print(f"[LinkedInSender] get_profile_urn failed for {profile_url}: {e}")
        return None

    # ── Connection request ────────────────────────────────────────────────────

    def send_connection_request(
        self,
        profile_url: str,
        note: str = "",
        member_id: str = "",
    ) -> dict:
        """
        Send a connection request with an optional note (≤300 chars).
        Returns {"success": bool, "status_code": int, "detail": str}.
        """
        urn = self.get_profile_urn(profile_url, member_id)
        if not urn:
            return {"success": False, "detail": "Could not resolve profile URN"}

        # Extract the numeric member ID from the URN
        member_num = urn.split(":")[-1]

        payload = {
            "emberEntityName": "growth/invitation/norm-invitation",
            "invitee": {
                "com.linkedin.voyager.growth.invitation.InviteeProfile": {
                    "profileId": member_num,
                }
            },
            "trackingId": _tracking_id(),
        }
        if note:
            payload["message"] = note[:300]

        url = f"{_BASE}/growth/normInvitations"
        try:
            r = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=_TIMEOUT,
            )
            success = r.status_code in (200, 201)
            detail = "sent" if success else r.text[:200]
            print(f"[LinkedInSender] connection_request → {profile_url}: {r.status_code}")
            return {"success": success, "status_code": r.status_code, "detail": detail}
        except Exception as e:
            return {"success": False, "detail": str(e)}

    # ── Direct message ────────────────────────────────────────────────────────

    def send_dm(
        self,
        profile_url: str,
        message: str,
        member_id: str = "",
    ) -> dict:
        """
        Send a DM to a 1st-degree connection or OpenLink profile.
        Creates a new conversation (or reuses existing one if LinkedIn returns it).
        Returns {"success": bool, "status_code": int, "detail": str}.
        """
        urn = self.get_profile_urn(profile_url, member_id)
        if not urn:
            return {"success": False, "detail": "Could not resolve profile URN"}

        # Step 1: create or get conversation
        conv_payload = {
            "keyVersion": "LEGACY_INBOX",
            "conversationCreate": {
                "eventCreate": {
                    "value": {
                        "com.linkedin.voyager.messaging.create.MessageCreate": {
                            "attributedBody": {
                                "text": message,
                                "attributes": [],
                            },
                            "attachments": [],
                        }
                    }
                },
                "recipients": [urn],
                "subtype": "MEMBER_TO_MEMBER",
            },
        }
        url = f"{_BASE}/messaging/conversations"
        try:
            r = self.session.post(
                url,
                json=conv_payload,
                headers={"Content-Type": "application/json"},
                timeout=_TIMEOUT,
            )
            success = r.status_code in (200, 201)
            detail = "sent" if success else r.text[:200]
            print(f"[LinkedInSender] dm → {profile_url}: {r.status_code}")
            return {"success": success, "status_code": r.status_code, "detail": detail}
        except Exception as e:
            return {"success": False, "detail": str(e)}


    # ── Fetch own connections ─────────────────────────────────────────────────

    def get_my_connections(self, limit: int = 80, keywords: str = "") -> list[dict]:
        """
        Fetch the user's 1st-degree LinkedIn connections via the voyager API.
        Returns normalised lead-compatible dicts (relationship_type='1st').
        Used when connection budget is exhausted and we can only DM.
        """
        results: list[dict] = []
        start = 0
        batch = 40

        while len(results) < limit:
            count = min(batch, limit - len(results))
            # Try two endpoints in order — both return 1st-degree connections
            endpoints = [
                # Endpoint 1: classic connections list (most reliable)
                (f"{_BASE}/relationships/connectionsList", {
                    "start": start, "count": count,
                    "sortType": "RECENTLY_ADDED",
                }),
                # Endpoint 2: older connections endpoint
                (f"{_BASE}/relationships/connections", {
                    "q": "viewer", "start": start, "count": count,
                    "sortType": "RECENTLY_ADDED",
                }),
            ]

            data = None
            for url, params in endpoints:
                try:
                    r = self.session.get(url, params=params, timeout=_TIMEOUT)
                    print(f"[LinkedInSender] {url.split('/')[-1]} → HTTP {r.status_code}")
                    if r.ok:
                        data = r.json()
                        break
                except Exception as e:
                    print(f"[LinkedInSender] endpoint failed: {e}")

            if not data:
                print("[LinkedInSender] All connection endpoints failed — no connections returned")
                break

            elements = data.get("elements", [])
            print(f"[LinkedInSender] page start={start}: {len(elements)} elements")
            if not elements:
                break

            for el in elements:
                mini = (
                    el.get("miniProfile")
                    or el.get("connectedMember", {}).get("miniProfile")
                    or {}
                )
                fn  = mini.get("firstName", "")
                ln  = mini.get("lastName", "")
                name = f"{fn} {ln}".strip()
                pid  = mini.get("publicIdentifier", "")
                if not pid or not name:
                    continue
                profile_url = f"https://www.linkedin.com/in/{pid}"
                headline    = mini.get("occupation", "")
                member_id   = str(mini.get("objectUrn", "")).split(":")[-1]
                results.append({
                    "name":                     name,
                    "profile_url":              profile_url,
                    "headline":                 headline,
                    "location":                 el.get("geoRegion", ""),
                    "about_snippet":            "",
                    "fit_score":                7.0,
                    "why_qualified":            "1st-degree LinkedIn connection — can DM directly",
                    "recent_activity_keywords": [],
                    "relationship_type":        "1st",
                    "is_open_link":             False,
                    "_linkedin_member_id":      member_id,
                })
                if len(results) >= limit:
                    break

            if len(elements) < batch:
                break
            start += batch

        print(f"[LinkedInSender] get_my_connections → {len(results)} connections fetched")
        return results


# ── Factory ───────────────────────────────────────────────────────────────────

def sender_from_env() -> LinkedInSender | None:
    """
    Build a LinkedInSender from environment variables / Streamlit secrets.
    Returns None if required credentials are missing.
    """
    li_at = os.environ.get("LINKEDIN_LI_AT") or os.environ.get("li_at", "")
    jsessionid = os.environ.get("LINKEDIN_JSESSIONID") or os.environ.get("JSESSIONID", "")
    csrf_token = os.environ.get("LINKEDIN_CSRF_TOKEN") or os.environ.get("csrf-token", "")
    own_url = os.environ.get("LINKEDIN_OWN_PROFILE_URL") or os.environ.get("OWN_PROFILE_URL", "")

    if not all([li_at, jsessionid, csrf_token, own_url]):
        return None

    return LinkedInSender(
        li_at=li_at,
        jsessionid=jsessionid,
        csrf_token=csrf_token,
        own_profile_url=own_url,
    )
