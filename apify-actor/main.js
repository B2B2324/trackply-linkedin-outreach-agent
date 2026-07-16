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

// Browser-like warmup: hit the HTML feed so Cloudflare (__cf_bm) and LinkedIn
// (bcookie/bscookie/lidc) seed the jar before any voyager XHR. Without this,
// voyager 302-loops even for a valid li_at. Returns true if we landed on the
// logged-in feed.
async function warmup() {
    const res = await gotScraping({
        url: 'https://www.linkedin.com/feed/',
        headers: { ...apiHeaders, accept: 'text/html' },
        responseType: 'text', ...common,
    });
    const finalUrl = String(res.url || res.requestUrl || '');
    return res.statusCode === 200 && /\/feed\/?$/.test(finalUrl);
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
        // Never let LinkedIn's Set-Cookie overwrite the USER's real li_at with a
        // guest one during merge — that would sabotage every hop after the first.
        const realLiAt = String(liAt);
        const mergeKeepingLiAt = (setC) => { mergeSetCookie(setC); cookies.set('li_at', realLiAt); };

        // STEP 1 — warm up on the HTML app the way a browser does: GET /feed/,
        // following redirects by hand, so Cloudflare (__cf_bm) and LinkedIn
        // (bcookie/bscookie/lidc) issue their cookies and a VALID li_at lands on
        // the real feed. Where this ends is the ground truth for the session:
        //   ends on /feed/ (200)         → logged in
        //   ends on /authwall|/login|... → li_at is dead
        const feedHops = [];
        let feed;
        let feedUrl = 'https://www.linkedin.com/feed/';
        for (let i = 0; i < 4; i++) {
            feed = await gotScraping({ url: feedUrl, headers: { ...apiHeaders, accept: 'text/html', cookie: cookieHeader() }, ...manual });
            const loc = String(feed.headers?.location || '');
            feedHops.push({ status: feed.statusCode, loc: loc.slice(0, 90) });
            mergeKeepingLiAt(feed.headers?.['set-cookie'] || []);
            if (feed.statusCode === 200 || !loc) break;
            feedUrl = loc.startsWith('http') ? loc : `https://www.linkedin.com${loc}`;
        }
        const feedFinalUrl = feedUrl;
        const feedAuthwall = /authwall|\/login|\/uas\/login|checkpoint|challenge/i.test(feedFinalUrl)
            || feedHops.some(h => /authwall|\/login|\/uas\/login|checkpoint|challenge/i.test(h.loc));
        const loggedIn = feed.statusCode === 200 && /\/feed\/?$/.test(feedFinalUrl) && !feedAuthwall;

        // STEP 2 — with the warmed-up cookie set, hit the voyager API.
        const meHops = [];
        let me;
        for (let i = 0; i < 3; i++) {
            me = await gotScraping({ url: `${BASE}/me`, headers: { ...apiHeaders, cookie: cookieHeader() }, ...manual });
            const loc = String(me.headers?.location || '');
            meHops.push({ status: me.statusCode, loc: loc.slice(0, 90) });
            if (me.statusCode === 200 || !loc) break;
            mergeKeepingLiAt(me.headers?.['set-cookie'] || []);
        }
        const authed = me.statusCode === 200
            && /"(plainId|miniProfile|entityUrn)"/.test(String(me.body || '').slice(0, 400));

        result = {
            success: authed,
            status_code: me.statusCode,
            authenticated: authed,
            logged_in_feed: loggedIn,
            feed_final_url: feedFinalUrl.slice(0, 160),
            feed_hops: feedHops,
            me_hops: meHops,
            cookies_after_warmup: [...cookies.keys()].slice(0, 14),
            body_snippet: typeof me.body === 'string' ? me.body.slice(0, 200) : undefined,
            detail: authed
                ? 'Authenticated — /feed/ 200 then voyager /me 200 with a member profile. Send path live.'
                : feedAuthwall || !loggedIn
                    ? `STALE / INVALID li_at: the /feed/ warmup ended on "${feedFinalUrl.slice(0, 90)}" instead of the logged-in feed, so LinkedIn does not accept this session. Re-capture li_at (and JSESSIONID) from a browser where you are logged in.`
                    : `li_at accepted for /feed/ but voyager /me still ${me.statusCode} — API-header issue, not the cookie. me_hops=${JSON.stringify(meHops).slice(0, 150)}`,
        };
    } else {
        // Warm up the session (seed __cf_bm / bcookie / lidc) so the voyager
        // calls below aren't treated as anonymous and 302-looped.
        const warm = await warmup();
        const urn = await getUrn();
        if (!urn) {
            result = {
                success: false,
                detail: warm
                    ? 'Logged in, but could not resolve profile URN (bad profile URL?)'
                    : 'Auth failed: /feed/ warmup did not reach the logged-in feed — li_at is stale/invalid. Re-capture it.',
            };
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
