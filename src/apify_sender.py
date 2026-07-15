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


def apify_live_send(action: str, profile_url: str, message: str, target: dict) -> dict:
    """
    Send a connection request or DM via the LinkedIn voyager API, executed
    inside an apify/web-scraper Actor run (residential proxy, no external-
    connection restriction).

    Drop-in replacement for _live_send in nodes.py.
    Returns {"success": bool, "detail": str}.
    """
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    li_at = os.environ.get("LINKEDIN_LI_AT") or os.environ.get("li_at", "")
    jsessionid = os.environ.get("LINKEDIN_JSESSIONID") or os.environ.get("JSESSIONID", "")
    csrf_token = os.environ.get("LINKEDIN_CSRF_TOKEN") or os.environ.get("csrf-token", "")

    if not all([token, li_at, jsessionid, csrf_token]):
        missing = [k for k, v in {
            "APIFY_TOKEN": token, "LINKEDIN_LI_AT": li_at,
            "LINKEDIN_JSESSIONID": jsessionid, "LINKEDIN_CSRF_TOKEN": csrf_token,
        }.items() if not v]
        return {"success": False, "detail": f"Missing env vars: {', '.join(missing)}"}

    member_id = target.get("_linkedin_member_id", "")

    run_input = {
        "runMode": "PRODUCTION",
        "startUrls": [{"url": "https://www.linkedin.com/feed/"}],
        "linkSelector": "",
        "pageFunction": _PAGE_FUNCTION,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
            "apifyProxyCountry": "US",
        },
        "initialCookies": _cookie_jar(li_at, jsessionid),
        "ignoreCorsAndCsp": True,
        "injectJQuery": False,
        "maxPagesPerCrawl": 1,
        "maxRequestRetries": 0,
        "customData": {
            "action": action,
            "profileUrl": profile_url,
            "message": message,
            "memberId": member_id,
            "csrfToken": csrf_token,
        },
    }

    client = ApifyClient(token)
    try:
        run = client.actor(SEND_ACTOR).call(run_input=run_input, timeout_secs=90)
    except Exception as e:
        print(f"[ApifySender] Actor run failed to start: {e}")
        return {"success": False, "detail": f"Actor run failed to start: {e}"}

    status = _run_field(run, "status")
    dataset_id = _run_field(run, "defaultDatasetId", "default_dataset_id")
    if status and status != "SUCCEEDED":
        msg = _run_field(run, "statusMessage", "status_message")
        print(f"[ApifySender] send Actor run did NOT succeed ({status}): {msg}")

    if not dataset_id:
        return {"success": False, "detail": f"No dataset returned from send Actor (status={status})"}

    items = list(client.dataset(dataset_id).iterate_items())
    if not items:
        return {"success": False, "detail": "Send Actor produced no result — page function may have failed silently"}

    result = items[0]
    print(f"[ApifySender] {action} → {profile_url}: {result.get('status_code', '?')} (via Apify Actor)")
    return {
        "success": bool(result.get("success")),
        "status_code": result.get("status_code"),
        "detail": result.get("detail", ""),
    }
