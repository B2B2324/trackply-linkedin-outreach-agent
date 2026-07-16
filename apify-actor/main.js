/**
 * linkedin-voyager-send — a small Apify Actor OWNED by the Maya account.
 *
 * Performs a LinkedIn voyager connection-request / DM / selftest from inside
 * Apify on a residential IP. Actors you own need no full-permissions grant, so
 * this runs on the FREE plan (unlike apify/web-scraper).
 *
 * Auth model (matches a real browser / requests.Session):
 *   - a tough-cookie jar seeded with li_at + JSESSIONID, so LinkedIn's
 *     cookie-bootstrap 302s (Set-Cookie lidc/bcookie/…, redirect to same URL)
 *     resolve instead of looping;
 *   - csrf-token header derived from JSESSIONID (LinkedIn requires them equal);
 *   - got-scraping for browser-like TLS/header fingerprint.
 *
 * Input: { action, profileUrl, message, memberId, csrfToken, liAt, jsessionid }
 *   action ∈ "connection_request" | "dm" | "selftest"
 * Output (one dataset item): { success, status_code, detail, ... }
 */
import { Actor } from 'apify';
import { gotScraping } from 'got-scraping';
import { CookieJar } from 'tough-cookie';

await Actor.init();

const input = (await Actor.getInput()) ?? {};
const {
    action,
    profileUrl = '',
    message = '',
    memberId = '',
    liAt = '',
    jsessionid = '',
} = input;

const BASE = 'https://www.linkedin.com/voyager/api';

const proxyConfiguration = await Actor.createProxyConfiguration({
    groups: ['RESIDENTIAL'],
    countryCode: 'US',
});
const proxyUrl = await proxyConfiguration.newUrl();

// LinkedIn's csrf-token header MUST equal the JSESSIONID cookie value; deriving
// it from JSESSIONID makes a mismatch impossible.
const jsess = String(jsessionid).replace(/"/g, '');

// Cookie jar, seeded like a logged-in browser. LinkedIn will add lidc/bcookie
// via Set-Cookie on the first request; the jar carries them on the retry.
const jar = new CookieJar();
async function seed(cookieStr) {
    try { await jar.setCookie(cookieStr, 'https://www.linkedin.com'); } catch { /* best effort */ }
}
await seed(`li_at=${liAt}; Domain=.linkedin.com; Path=/; Secure`);
await seed(`JSESSIONID="${jsess}"; Domain=.linkedin.com; Path=/; Secure`);

const apiHeaders = {
    accept: 'application/vnd.linkedin.normalized+json+2.1',
    'accept-language': 'en-US,en;q=0.9',
    'x-restli-protocol-version': '2.0.0',
    'x-li-lang': 'en_US',
    'x-li-track': JSON.stringify({
        clientVersion: '1.13.15117', mpVersion: '1.13.15117', osName: 'web',
        timezoneOffset: -7, timezone: 'America/Los_Angeles', deviceFormFactor: 'DESKTOP',
        mpName: 'voyager-web', displayDensity: 1, displayWidth: 1920, displayHeight: 1080,
    }),
    'csrf-token': jsess,
};

const common = { cookieJar: jar, proxyUrl, throwHttpErrors: false, followRedirect: true, maxRedirects: 5 };

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
    const res = await gotScraping({ url, headers: apiHeaders, responseType: 'json', ...common });
    if (res.statusCode !== 200) return null;
    const el = (res.body?.elements || [])[0];
    return el ? el.entityUrn || el['*profile'] : null;
}

let result;
try {
    if (action === 'selftest') {
        // Decisive diagnostic: bypass the tough-cookie jar entirely and drive
        // the Cookie header MANUALLY, following LinkedIn's bootstrap by hand up
        // to 3 hops. This separates two very different failure modes:
        //   • li_at genuinely stale  → every hop 302s / lands on authwall
        //   • jar/proxy dropped cookies on the retry → manual hop 2 returns 200
        // Each hop re-reads Set-Cookie and merges it into the Cookie header,
        // exactly what a browser does.
        const cookies = new Map();
        cookies.set('li_at', String(liAt));
        cookies.set('JSESSIONID', `"${jsess}"`);
        const cookieHeader = () => [...cookies].map(([k, v]) => `${k}=${v}`).join('; ');
        const mergeSetCookie = (setC) => {
            for (const raw of (Array.isArray(setC) ? setC : [setC]).filter(Boolean)) {
                const [pair] = String(raw).split(';');
                const idx = pair.indexOf('=');
                if (idx > 0) cookies.set(pair.slice(0, idx).trim(), pair.slice(idx + 1).trim());
            }
        };

        const manual = { proxyUrl, throwHttpErrors: false, followRedirect: false, responseType: 'text' };
        const hops = [];
        let last;
        for (let i = 0; i < 3; i++) {
            last = await gotScraping({
                url: `${BASE}/me`,
                headers: { ...apiHeaders, cookie: cookieHeader() },
                ...manual,
            });
            const loc = String(last.headers?.location || '');
            const setC = last.headers?.['set-cookie'] || [];
            hops.push({
                status: last.statusCode,
                loc: loc.slice(0, 90),
                set: (Array.isArray(setC) ? setC : [setC]).filter(Boolean).map(c => String(c).split('=')[0]),
            });
            if (last.statusCode === 200 || !loc) break;
            mergeSetCookie(setC);
        }

        const finalStatus = last.statusCode;
        const sawAuthwall = hops.some(h => /authwall|\/login|\/uas\/login|checkpoint|challenge/i.test(h.loc));
        const loopToSelf = hops.length >= 3 && hops.every(h => h.status >= 300 && h.status < 400);
        const authed = finalStatus === 200
            && /"(plainId|miniProfile|entityUrn)"/.test(String(last.body || '').slice(0, 400));

        result = {
            success: authed,
            status_code: finalStatus,
            authenticated: authed,
            cookies_sent: [...cookies.keys()].slice(0, 12),
            hops,
            body_snippet: typeof last.body === 'string' ? last.body.slice(0, 200) : undefined,
            detail: authed
                ? 'Authenticated — GET /me returned 200 with a member profile. Send path live.'
                : sawAuthwall
                    ? `STALE COOKIES: LinkedIn sent us to an auth/login/checkpoint page. Re-capture li_at + JSESSIONID from a logged-in session.`
                    : loopToSelf
                        ? `li_at NOT accepted: every hop 302'd back to /me even with all Set-Cookie merged (li_at len=${String(liAt).length}). Almost certainly a stale/invalid li_at — re-capture it.`
                        : `Not authed: final=${finalStatus}. Hops: ${JSON.stringify(hops).slice(0, 200)}`,
        };
    } else {
        const urn = await getUrn();
        if (!urn) {
            result = { success: false, detail: 'Could not resolve profile URN (auth or bad profile URL)' };
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
                url, method: 'POST', headers: { ...apiHeaders, 'content-type': 'application/json' },
                json: payload, responseType: 'json', ...common,
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
