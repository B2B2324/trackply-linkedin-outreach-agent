"""
Local (no-Apify) LinkedIn voyager sender.

Runs the send path directly from THIS machine's IP instead of through the
owned Apify actor. Purpose: test the standing hypothesis that LinkedIn accepts
voyager *writes* from a residential/home IP but 401s them from cloud
datacenter IPs (Railway, and — as the 2026-07-19 run showed — Apify's exits
too), while *reads* pass from anywhere.

This is a faithful Python port of apify-actor/main.js. The three details that
make it work (and whose absence made the old src/linkedin_sender.py 401 for
unrelated reasons) are:

  1. /feed/ warmup — follow redirects by hand, merge every Set-Cookie, re-pin
     li_at, so Cloudflare (__cf_bm) and LinkedIn (bcookie/lidc) cookies are in
     place before any voyager XHR.
  2. csrf-token is ALWAYS re-derived from the live JSESSIONID cookie, never
     from the env var — LinkedIn rotates JSESSIONID during warmup and validates
     csrf on POST but not GET. Freezing it was the old sender's bug.
  3. Writes carry a same-origin XHR shape (origin/referer/sec-fetch-*). csrf
     matching the cookie is necessary but NOT sufficient.

Wired in via SENDER_MODE=local (see src/nodes.py::_live_send). SENDER_MODE
defaults to 'apify' so nothing changes unless you opt in.

Entry point matches apify_live_send's contract exactly:
    local_live_send(action, profile_url, message, target)
      -> {"success": bool, "status_code": int, "detail": str}
"""
from __future__ import annotations

import base64
import json
import os
import random
import string

import requests

_BASE = "https://www.linkedin.com/voyager/api"
_TIMEOUT = 20
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _tracking_id() -> str:
    raw = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    return base64.b64encode(raw.encode()).decode()


def _base_headers() -> dict:
    return {
        "User-Agent": _USER_AGENT,
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
    }


class _LocalVoyager:
    """Manual cookie jar + warmup, mirroring the owned Apify actor."""

    def __init__(self, li_at: str, jsessionid: str):
        self._real_li_at = li_at
        self.cookies: dict[str, str] = {
            "li_at": li_at,
            "JSESSIONID": f'"{jsessionid.strip(chr(34))}"',
        }
        self.session = requests.Session()

    # ── cookie plumbing ──────────────────────────────────────────────────────

    def _cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _current_csrf(self) -> str:
        # csrf-token must equal the CURRENT JSESSIONID cookie, quotes stripped.
        return str(self.cookies.get("JSESSIONID", "")).replace('"', "")

    def _merge_set_cookie(self, resp: requests.Response) -> None:
        # requests parses Set-Cookie into resp.cookies; merge names we see.
        for name, value in resp.cookies.get_dict().items():
            self.cookies[name] = value
        # Never let a guest cookie displace the real session token.
        self.cookies["li_at"] = self._real_li_at

    def _headers(self, extra: dict | None = None) -> dict:
        h = _base_headers()
        h["Csrf-Token"] = self._current_csrf()
        h["Cookie"] = self._cookie_header()
        if extra:
            h.update(extra)
        return h

    # ── warmup ───────────────────────────────────────────────────────────────

    def warmup(self, hops: int = 4) -> tuple[bool, str]:
        """GET /feed/ following redirects by hand, merging Set-Cookie each hop.
        Returns (reached_feed, final_url)."""
        cur = "https://www.linkedin.com/feed/"
        final = cur
        for _ in range(hops):
            resp = self.session.get(
                cur,
                headers=self._headers({"Accept": "text/html"}),
                allow_redirects=False,
                timeout=_TIMEOUT,
            )
            self._merge_set_cookie(resp)
            loc = resp.headers.get("location", "")
            final = cur
            if resp.status_code == 200 or not loc:
                break
            cur = loc if loc.startswith("http") else f"https://www.linkedin.com{loc}"
        authwall = any(
            s in final for s in ("authwall", "/login", "/uas/login", "checkpoint", "challenge")
        )
        reached = final.rstrip("/").endswith("/feed") and not authwall
        return reached, final

    # ── urn lookup ───────────────────────────────────────────────────────────

    def get_urn(self, profile_url: str, member_id: str = "") -> str | None:
        if member_id:
            return f"urn:li:member:{member_id}"
        parts = profile_url.rstrip("/").split("/in/")
        if len(parts) < 2:
            return None
        public_id = parts[1].split("/")[0].split("?")[0]
        url = f"{_BASE}/identity/dash/profiles"
        params = {
            "q": "memberIdentity",
            "memberIdentity": public_id,
            "decorationId": (
                "com.linkedin.voyager.dash.deco.identity.profile."
                "FullProfileWithEntities-91"
            ),
        }
        try:
            resp = self.session.get(
                url, params=params, headers=self._headers(), timeout=_TIMEOUT
            )
            self._merge_set_cookie(resp)
            if resp.status_code != 200:
                return None
            elements = resp.json().get("elements", [])
            if elements:
                return elements[0].get("entityUrn") or elements[0].get("*profile")
        except Exception:
            return None
        return None

    # ── send ─────────────────────────────────────────────────────────────────

    def send(self, action: str, profile_url: str, message: str, member_id: str = "") -> dict:
        urn = self.get_urn(profile_url, member_id)
        if not urn:
            return {"success": False, "status_code": 0,
                    "detail": "Could not resolve profile URN"}
        member_num = urn.split(":")[-1]
        msg = (message or "")[:300]

        if action == "connection_request":
            candidates = [
                ("dash/verifyQuotaAndCreateV2",
                 f"{_BASE}/voyagerRelationshipsDashMemberRelationships"
                 f"?action=verifyQuotaAndCreateV2",
                 {"inviteeProfileUrn": urn, **({"customMessage": msg} if msg else {})}),
                ("legacy/normInvitations",
                 f"{_BASE}/growth/normInvitations",
                 {"emberEntityName": "growth/invitation/norm-invitation",
                  "invitee": {
                      "com.linkedin.voyager.growth.invitation.InviteeProfile":
                          {"profileId": member_num}},
                  "trackingId": _tracking_id(),
                  **({"message": msg} if msg else {})}),
            ]
            referer = profile_url or "https://www.linkedin.com/feed/"
        elif action == "dm":
            candidates = [
                ("dash/createMessage",
                 f"{_BASE}/voyagerMessagingDashMessengerMessages?action=createMessage",
                 {"message": {"body": {"text": message, "attributes": []},
                              "renderContentUnions": []},
                  "hostRecipientUrns": [urn],
                  "dedupeByClientGeneratedToken": False}),
                ("legacy/messagingConversations",
                 f"{_BASE}/messaging/conversations",
                 {"keyVersion": "LEGACY_INBOX",
                  "conversationCreate": {
                      "eventCreate": {"value": {
                          "com.linkedin.voyager.messaging.create.MessageCreate": {
                              "attributedBody": {"text": message, "attributes": []},
                              "attachments": []}}},
                      "recipients": [urn],
                      "subtype": "MEMBER_TO_MEMBER"}}),
            ]
            referer = "https://www.linkedin.com/messaging/"
        else:
            return {"success": False, "status_code": 0,
                    "detail": f"Unknown action: {action}"}

        write_headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": "https://www.linkedin.com",
            "Referer": referer,
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }

        attempts: list[str] = []
        last_status = 0
        for name, url, payload in candidates:
            try:
                resp = self.session.post(
                    url,
                    data=json.dumps(payload),
                    headers=self._headers(write_headers),
                    allow_redirects=False,
                    timeout=_TIMEOUT,
                )
            except Exception as e:
                attempts.append(f"{name}=ERR:{str(e)[:80]}")
                continue
            self._merge_set_cookie(resp)
            last_status = resp.status_code
            ok = resp.status_code in (200, 201)
            print(f"[local-send] {name} → http={resp.status_code}")
            if ok:
                return {"success": True, "status_code": resp.status_code,
                        "detail": f"sent via {name}"}
            body = (resp.text or "")[:120]
            err_hdr = (resp.headers.get("x-restli-error-response")
                       or resp.headers.get("x-linkedin-error-response") or "")
            attempts.append(f"{name}={resp.status_code}:{err_hdr or body}")

        return {"success": False, "status_code": last_status,
                "detail": "all endpoints rejected [" + " | ".join(attempts) + "]"}


def _creds() -> tuple[dict, str | None]:
    creds = {
        "li_at": os.environ.get("LINKEDIN_LI_AT") or os.environ.get("li_at", ""),
        "jsessionid": os.environ.get("LINKEDIN_JSESSIONID") or os.environ.get("JSESSIONID", ""),
    }
    label = {"li_at": "LINKEDIN_LI_AT", "jsessionid": "LINKEDIN_JSESSIONID"}
    missing = [label[k] for k, v in creds.items() if not v]
    return creds, (f"Missing env vars: {', '.join(missing)}" if missing else None)


# Warm up once per process, not per lead.
_client: _LocalVoyager | None = None
_warmed: bool = False


def local_live_send(action: str, profile_url: str, message: str, target: dict) -> dict:
    """Drop-in replacement for apify_live_send that sends from this machine."""
    global _client, _warmed
    creds, err = _creds()
    if err:
        return {"success": False, "status_code": 0, "detail": err}

    if _client is None:
        _client = _LocalVoyager(creds["li_at"], creds["jsessionid"])
    if not _warmed:
        reached, final = _client.warmup()
        _warmed = True
        if not reached:
            return {"success": False, "status_code": 0,
                    "detail": f"Warmup did not reach /feed/ (final={final[:90]}). "
                              f"Session cookie likely stale."}

    member_id = str(target.get("_linkedin_member_id", "") or "")
    return _client.send(action, profile_url, message, member_id)
