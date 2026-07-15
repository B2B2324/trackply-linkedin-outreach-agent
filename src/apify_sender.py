"""
Send LinkedIn voyager API requests from inside an Apify Actor run, instead of
connecting to Apify's proxy directly from Railway.

Why: Apify's docs (https://docs.apify.com/proxy#external-connection) say
connecting to Apify Proxy from *outside* the Apify platform requires a paid
Apify plan. Railway calling proxy.apify.com:8000 directly hit a blanket 403
on every attempt — before LinkedIn was ever contacted — even after fixing the
proxy-password fetch bug, because the connection itself was being rejected as
an external client. That restriction doesn't apply to requests made *from
inside* an Actor run, which is exactly how Maya's lead-sourcing (harvestapi,
network scraper) already gets residential-proxy access successfully.

This module runs the actual send as a small `apify/web-scraper` Actor call:
it loads a linkedin.com page with our session cookies attached, then fires
the voyager API request via `fetch()` from that page's own context, on an
Apify residential IP — the same "connection from Actors" path, not the
external one.

Usage (replaces _live_send in nodes.py):
    from src.apify_sender import apify_live_send
    result = apify_live_send(action, profile_url, message, target)
"""
from __future__ import annotations

import os

from apify_client import ApifyClient

from src.apify_linkedin import _run_field

SEND_ACTOR = "apify/web-scraper"

# Executed inside the Actor's browser page (JS, not Python). Re-implements
# LinkedInSender.get_profile_urn / send_connection_request / send_dm from
# src/linkedin_sender.py as a single fetch()-based page function so the
# request runs on the Actor's own (proxied) page context.
_PAGE_FUNCTION = """
async function pageFunction(context) {
    const { customData } = context;
    const { action, profileUrl, message, memberId, csrfToken } = customData;
    const BASE = 'https://www.linkedin.com/voyager/api';

    function trackingId() {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let raw = '';
        for (let i = 0; i < 16; i++) raw += chars[Math.floor(Math.random() * chars.length)];
        return btoa(raw);
    }

    const headers = {
        'Accept': 'application/vnd.linkedin.normalized+json+2.1',
        'X-Restli-Protocol-Version': '2.0.0',
        'X-Li-Lang': 'en_US',
        'Csrf-Token': csrfToken,
        'Content-Type': 'application/json',
    };

    async function getProfileUrn() {
        if (memberId) return `urn:li:member:${memberId}`;
        const parts = profileUrl.replace(/\\/$/, '').split('/in/');
        if (parts.length < 2) return null;
        const publicId = parts[1].split('/')[0].split('?')[0];
        const url = `${BASE}/identity/dash/profiles?q=memberIdentity&memberIdentity=${encodeURIComponent(publicId)}&decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-91`;
        const res = await fetch(url, { headers, credentials: 'include' });
        if (!res.ok) return null;
        const data = await res.json();
        const el = (data.elements || [])[0];
        return el ? (el.entityUrn || el['*profile']) : null;
    }

    try {
        const urn = await getProfileUrn();
        if (!urn) {
            return { success: false, detail: 'Could not resolve profile URN' };
        }
        const memberNum = urn.split(':').pop();

        let url, payload;
        if (action === 'connection_request') {
            url = `${BASE}/growth/normInvitations`;
            payload = {
                emberEntityName: 'growth/invitation/norm-invitation',
                invitee: { 'com.linkedin.voyager.growth.invitation.InviteeProfile': { profileId: memberNum } },
                trackingId: trackingId(),
            };
            if (message) payload.message = message.slice(0, 300);
        } else if (action === 'dm') {
            url = `${BASE}/messaging/conversations`;
            payload = {
                keyVersion: 'LEGACY_INBOX',
                conversationCreate: {
                    eventCreate: { value: { 'com.linkedin.voyager.messaging.create.MessageCreate': {
                        attributedBody: { text: message, attributes: [] }, attachments: [],
                    } } },
                    recipients: [urn],
                    subtype: 'MEMBER_TO_MEMBER',
                },
            };
        } else {
            return { success: false, detail: `Unknown action: ${action}` };
        }

        const res = await fetch(url, { method: 'POST', headers, credentials: 'include', body: JSON.stringify(payload) });
        const status = res.status;
        const success = status === 200 || status === 201;
        let detail = 'sent';
        if (!success) {
            try { detail = (await res.text()).slice(0, 200); } catch (e) { detail = String(e); }
        }
        return { success, status_code: status, detail };
    } catch (e) {
        return { success: false, detail: String(e) };
    }
}
"""


def _cookie_jar(li_at: str, jsessionid: str) -> list[dict]:
    """Puppeteer Page.setCookie()-format cookies for the Actor's initialCookies input."""
    return [
        {"name": "li_at", "value": li_at, "domain": ".linkedin.com", "path": "/"},
        {"name": "JSESSIONID", "value": f'"{jsessionid.strip(chr(34))}"', "domain": ".linkedin.com", "path": "/"},
    ]


def _creds() -> tuple[dict, str | None]:
    """
    Gather the four required credentials from the environment.
    Returns (creds_dict, error_str). error_str is None when all are present.
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


def _run_voyager_actor(creds: dict, page_function: str, custom_data: dict,
                       *, label: str = "voyager") -> dict:
    """
    Run a page function inside apify/web-scraper on a residential proxy with
    the LinkedIn session cookies attached, and return its single result item.

    The page function must return a JSON object (stored as one dataset item).
    Returns {"ok": bool, "item": dict|None, "detail": str, "run_status": str}.
    """
    run_input = {
        "runMode": "PRODUCTION",
        "startUrls": [{"url": "https://www.linkedin.com/feed/"}],
        "linkSelector": "",
        "pageFunction": page_function,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
            "apifyProxyCountry": "US",
        },
        "initialCookies": _cookie_jar(creds["li_at"], creds["jsessionid"]),
        "ignoreCorsAndCsp": True,
        "injectJQuery": False,
        "maxPagesPerCrawl": 1,
        "maxRequestRetries": 0,
        "customData": custom_data,
    }

    client = ApifyClient(creds["token"])
    try:
        # NOTE: this apify-client version rejects wait_secs/timeout_secs on
        # .call() (see src/apify_linkedin.py). Bound the run via the Actor's
        # own input instead so a stuck page can't hang the request forever.
        run_input["pageFunctionTimeoutSecs"] = 60
        run_input["pageLoadTimeoutSecs"] = 45
        run = client.actor(SEND_ACTOR).call(run_input=run_input)
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
                "detail": "Page function produced no result — it may have thrown before returning",
                "run_status": status}

    return {"ok": True, "item": items[0], "detail": "", "run_status": status}


def apify_live_send(action: str, profile_url: str, message: str, target: dict) -> dict:
    """
    Send a connection request or DM via the LinkedIn voyager API, executed
    inside an apify/web-scraper Actor run (residential proxy, no external-
    connection restriction).

    Drop-in replacement for _live_send in nodes.py.
    Returns {"success": bool, "detail": str}.
    """
    creds, err = _creds()
    if err:
        return {"success": False, "detail": err}

    run = _run_voyager_actor(
        creds, _PAGE_FUNCTION,
        {
            "action": action,
            "profileUrl": profile_url,
            "message": message,
            "memberId": target.get("_linkedin_member_id", ""),
            "csrfToken": creds["csrf_token"],
        },
        label=action,
    )
    if not run["ok"]:
        return {"success": False, "detail": run["detail"]}

    result = run["item"]
    print(f"[ApifySender] {action} → {profile_url}: {result.get('status_code', '?')} (via Apify Actor)")
    return {
        "success": bool(result.get("success")),
        "status_code": result.get("status_code"),
        "detail": result.get("detail", ""),
    }


# ── Self-test (read-only) ─────────────────────────────────────────────────────

# Read-only page function: GETs /voyager/api/me through the Actor's proxied,
# cookie-authenticated page context. Proves the exact path that was 403'ing
# (authenticated voyager call via Apify proxy) WITHOUT sending any outreach.
_SELFTEST_PAGE_FUNCTION = """
async function pageFunction(context) {
    const BASE = 'https://www.linkedin.com/voyager/api';
    const headers = {
        'Accept': 'application/vnd.linkedin.normalized+json+2.1',
        'X-Restli-Protocol-Version': '2.0.0',
        'X-Li-Lang': 'en_US',
        'Csrf-Token': context.customData.csrfToken,
    };
    try {
        const res = await fetch(`${BASE}/me`, { headers, credentials: 'include' });
        const status = res.status;
        let authed = false;
        let who = '';
        if (res.ok) {
            try {
                const data = await res.json();
                // /me returns the logged-in member; presence of a miniProfile/plainId means auth worked
                const mp = (data && (data.miniProfile || (data.included || []).find(x => x && x.publicIdentifier))) || null;
                authed = !!mp || !!(data && data.plainId);
                who = mp ? (mp.publicIdentifier || mp.firstName || '') : '';
            } catch (e) { /* body parse best-effort */ }
        }
        return { status_code: status, authenticated: authed, who, ok: res.ok };
    } catch (e) {
        return { status_code: null, authenticated: false, detail: String(e), ok: false };
    }
}
"""


def apify_selftest() -> dict:
    """
    Verify the proxied-Actor voyager path end-to-end WITHOUT sending anything.

    Runs a read-only GET /voyager/api/me inside the same Actor + residential
    proxy + cookie setup the sender uses. A 200 with authenticated=true proves
    the fix (the old external-proxy path 403'd here before ever reaching a real
    send). Returns a JSON-serialisable dict for the /selftest endpoint.
    """
    creds, err = _creds()
    if err:
        return {"success": False, "stage": "credentials", "detail": err}

    run = _run_voyager_actor(
        creds, _SELFTEST_PAGE_FUNCTION,
        {"csrfToken": creds["csrf_token"]},
        label="selftest",
    )
    if not run["ok"]:
        return {"success": False, "stage": "actor_run",
                "run_status": run["run_status"], "detail": run["detail"]}

    item = run["item"]
    status_code = item.get("status_code")
    authenticated = bool(item.get("authenticated"))
    success = status_code in (200, 201) and authenticated
    print(f"[ApifySender] selftest → GET /me: {status_code} authenticated={authenticated}")
    return {
        "success": success,
        "stage": "voyager_call",
        "status_code": status_code,
        "authenticated": authenticated,
        "who": item.get("who", ""),
        "detail": item.get("detail", "")
                  or ("Authenticated voyager call succeeded through the Apify proxy — send path is unblocked."
                      if success else
                      f"Voyager call returned {status_code}, authenticated={authenticated}."),
    }
