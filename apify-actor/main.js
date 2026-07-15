/**
 * linkedin-voyager-send — a small Apify Actor OWNED by the Maya account.
 *
 * Why this exists: Maya runs on Railway (a datacenter IP that LinkedIn's
 * voyager API blocks with 403/404). Apify's residential proxy fixes that,
 * but connecting to Apify Proxy from *outside* Apify requires a paid plan,
 * and the official code-running scrapers (apify/web-scraper, cheerio-scraper)
 * require a "full permissions" grant that the FREE plan won't extend to API
 * runs. An Actor you OWN needs no such grant — so this Actor performs the
 * voyager call from inside Apify, on a residential IP, and Maya calls it by
 * name via the API.
 *
 * Input:
 *   { action, profileUrl, message, memberId, csrfToken, liAt, jsessionid }
 *   action ∈ "connection_request" | "dm" | "selftest"
 *
 * Output (single dataset item + OUTPUT key-value record):
 *   { success, status_code, detail, authenticated? }
 */
import { Actor } from 'apify';
import { gotScraping } from 'got-scraping';

await Actor.init();

const input = (await Actor.getInput()) ?? {};
const {
    action,
    profileUrl = '',
    message = '',
    memberId = '',
    csrfToken = '',
    liAt = '',
    jsessionid = '',
} = input;

const BASE = 'https://www.linkedin.com/voyager/api';

const proxyConfiguration = await Actor.createProxyConfiguration({
    groups: ['RESIDENTIAL'],
    countryCode: 'US',
});
const proxyUrl = await proxyConfiguration.newUrl();

const cookie =
    `li_at=${liAt}; ` +
    `JSESSIONID="${String(jsessionid).replace(/"/g, '')}"; ` +
    `lang=v=2&lang=en-us`;

const headers = {
    accept: 'application/vnd.linkedin.normalized+json+2.1',
    'accept-language': 'en-US,en;q=0.9',
    'x-restli-protocol-version': '2.0.0',
    'x-li-lang': 'en_US',
    'csrf-token': csrfToken,
    cookie,
};

function trackingId() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let raw = '';
    for (let i = 0; i < 16; i++) raw += chars[Math.floor(Math.random() * chars.length)];
    return Buffer.from(raw).toString('base64');
}

async function getUrn() {
    if (memberId) return `urn:li:member:${memberId}`;
    const parts = profileUrl.replace(/\/$/, '').split('/in/');
    if (parts.length < 2) return null;
    const publicId = parts[1].split('/')[0].split('?')[0];
    const url =
        `${BASE}/identity/dash/profiles?q=memberIdentity` +
        `&memberIdentity=${encodeURIComponent(publicId)}` +
        `&decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-91`;
    const res = await gotScraping({
        url, headers, proxyUrl, responseType: 'json', throwHttpErrors: false,
    });
    if (res.statusCode !== 200) return null;
    const el = (res.body?.elements || [])[0];
    return el ? el.entityUrn || el['*profile'] : null;
}

let result;
try {
    if (action === 'selftest') {
        // Read-only: proves the proxied, cookie-authenticated voyager path works.
        const res = await gotScraping({
            url: `${BASE}/me`, headers, proxyUrl, responseType: 'json', throwHttpErrors: false,
        });
        const authed = res.statusCode === 200;
        result = {
            success: authed,
            status_code: res.statusCode,
            authenticated: authed,
            detail: authed
                ? 'Authenticated voyager call succeeded through the owned Actor + residential proxy.'
                : `Voyager /me returned ${res.statusCode}.`,
        };
    } else {
        const urn = await getUrn();
        if (!urn) {
            result = { success: false, detail: 'Could not resolve profile URN' };
        } else {
            const memberNum = urn.split(':').pop();
            let url;
            let payload;
            if (action === 'connection_request') {
                url = `${BASE}/growth/normInvitations`;
                payload = {
                    emberEntityName: 'growth/invitation/norm-invitation',
                    invitee: {
                        'com.linkedin.voyager.growth.invitation.InviteeProfile': { profileId: memberNum },
                    },
                    trackingId: trackingId(),
                };
                if (message) payload.message = message.slice(0, 300);
            } else if (action === 'dm') {
                url = `${BASE}/messaging/conversations`;
                payload = {
                    keyVersion: 'LEGACY_INBOX',
                    conversationCreate: {
                        eventCreate: {
                            value: {
                                'com.linkedin.voyager.messaging.create.MessageCreate': {
                                    attributedBody: { text: message, attributes: [] },
                                    attachments: [],
                                },
                            },
                        },
                        recipients: [urn],
                        subtype: 'MEMBER_TO_MEMBER',
                    },
                };
            } else {
                throw new Error(`Unknown action: ${action}`);
            }

            const res = await gotScraping({
                url, method: 'POST', headers,
                proxyUrl, json: payload, responseType: 'json', throwHttpErrors: false,
            });
            const ok = res.statusCode === 200 || res.statusCode === 201;
            let detail = 'sent';
            if (!ok) {
                detail = typeof res.body === 'string'
                    ? res.body.slice(0, 200)
                    : JSON.stringify(res.body || {}).slice(0, 200);
            }
            result = { success: ok, status_code: res.statusCode, detail };
        }
    }
} catch (e) {
    result = { success: false, detail: String(e && e.message ? e.message : e) };
}

console.log(`[voyager-send] action=${action} → ${JSON.stringify(result)}`);
await Actor.pushData(result);
await Actor.setValue('OUTPUT', result);
await Actor.exit();
