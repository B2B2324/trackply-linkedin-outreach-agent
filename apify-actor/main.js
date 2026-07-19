/**
 * linkedin-voyager-send — a small Apify Actor OWNED by the Maya account.
 *
 * Performs a LinkedIn voyager connection-request / DM / selftest from inside
 * Apify on a residential IP. Actors you own need no full-permissions grant, so
 * this runs on the FREE plan (unlike apify/web-scraper).
 *
 * Auth model (matches a real browser / requests.Session):
 *   - MANUAL cookie handling (no jar): redirects are followed by hand and the
 *     real li_at is re-pinned after every Set-Cookie merge — LinkedIn's
 *     bootstrap 302s try to swap in a guest li_at, which is what made the
 *     jar-driven flow loop ("Redirected 5 times") on every live send;
 *   - csrf-token header derived from JSESSIONID (LinkedIn requires them equal);
 *   - got-scraping for browser-like TLS/header fingerprint.
 *
 * Input: { action, profileUrl, message, memberId, csrfToken, liAt, jsessionid }
 *   action ∈ "connection_request" | "dm" | "selftest"
 * Output (one dataset item): { success, status_code, detail, ... }
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
    liAt = '',
    jsessionid = '',
} = input;

const BASE = 'https://www.linkedin.com/voyager/api';

const proxyConfiguration = await Actor.createProxyConfiguration({
    groups: ['RESIDENTIAL'],
    countryCode: 'US',
});
// STICKY SESSION — pin every hop to ONE residential IP.
//
// This id MUST be stable ACROSS RUNS, not just within one. It used to be
// `maya_${Date.now()}_${random}`, which is unique per actor run — and since
// Maya invokes this actor once PER LEAD, a 40-lead run drove the account
// through 40 different residential IPs in minutes. LinkedIn treats an
// established session suddenly hopping IPs as session theft: it silently
// invalidates li_at, which is exactly the observed cycle (re-capture cookies →
// selftest green → run sends → session dead again, three times over).
//
// A day-stable id keeps every request on ONE IP (Apify holds a residential
// session's IP for ~24h), so the account looks like one consistent device.
// It rolls daily so a dead/blocked exit node can't strand us forever, and
// MAYA_PROXY_SESSION can pin it explicitly if a specific IP must be kept.
const daySalt = new Date().toISOString().slice(0, 10).replace(/-/g, '');
const sessionId = (process.env.MAYA_PROXY_SESSION || `maya_us_${daySalt}`)
    .replace(/[^a-zA-Z0-9_]/g, '').slice(0, 50);
const proxyUrl = await proxyConfiguration.newUrl(sessionId);
console.log(`[voyager-send] proxy session=${sessionId} (stable across runs — do not randomise)`);

// LinkedIn's csrf-token header MUST equal the JSESSIONID cookie value; deriving
// it from JSESSIONID makes a mismatch impossible.
const jsess = String(jsessionid).replace(/"/g, '');

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

function trackingId() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let raw = '';
    for (let i = 0; i < 16; i++) raw += chars[Math.floor(Math.random() * chars.length)];
    return Buffer.from(raw).toString('base64');
}

// ── Manual cookie handling for the SEND path ────────────────────────
// The tough-cookie jar + followRedirect approach let LinkedIn's bootstrap
// Set-Cookie overwrite the real li_at with a GUEST cookie mid-redirect, so
// every hop after the first was anonymous and got-scraping aborted with
// "Redirected 5 times. Aborting." (observed on every live send 2026-07-19,
// while the manual-hop selftest passed). This mirrors the selftest exactly:
// follow hops by hand, merge Set-Cookie, and re-pin li_at after every merge.
const realLiAtSend = String(liAt);
const sendCookies = new Map();
sendCookies.set('li_at', realLiAtSend);
sendCookies.set('JSESSIONID', `"${jsess}"`);
const sendCookieHeader = () => [...sendCookies].map(([k, v]) => `${k}=${v}`).join('; ');

// LinkedIn ROTATES JSESSIONID during the /feed/ warmup (Set-Cookie), and the
// csrf-token header must equal the CURRENT cookie value. Freezing the header
// at the env-var value made every write 401 while reads sailed through —
// voyager validates CSRF on POST but not on GET, which is exactly why the
// profile lookup succeeded and normInvitations returned "http=401" with an
// empty body. Always read csrf from the live cookie jar, never from input.
const currentCsrf = () => String(sendCookies.get('JSESSIONID') || jsess).replace(/"/g, '');
const headersNow = (extra = {}) => ({ ...apiHeaders, 'csrf-token': currentCsrf(), ...extra });
const sendMerge = (setC) => {
    for (const raw of (Array.isArray(setC) ? setC : [setC]).filter(Boolean)) {
        const [pair] = String(raw).split(';');
        const idx = pair.indexOf('=');
        if (idx > 0) sendCookies.set(pair.slice(0, idx).trim(), pair.slice(idx + 1).trim());
    }
    sendCookies.set('li_at', realLiAtSend); // never let a guest cookie displace the session
};
const hopOpts = { proxyUrl, throwHttpErrors: false, followRedirect: false };

// GET with hand-rolled redirect following (bounded, loop-proof by design).
async function manualGet(url, headers, { hops = 4, responseType = 'text' } = {}) {
    let res; let cur = url;
    for (let i = 0; i < hops; i++) {
        // csrf-token recomputed per hop: JSESSIONID can rotate on any response.
        res = await gotScraping({ url: cur, headers: { ...headers, 'csrf-token': currentCsrf(), cookie: sendCookieHeader() }, responseType, ...hopOpts });
        sendMerge(res.headers?.['set-cookie'] || []);
        const loc = String(res.headers?.location || '');
        if (res.statusCode === 200 || !loc) break;
        cur = loc.startsWith('http') ? loc : `https://www.linkedin.com${loc}`;
    }
    return { res, finalUrl: cur };
}

// Browser-like warmup: land the session on the logged-in /feed/ so Cloudflare
// (__cf_bm) and LinkedIn (bcookie/bscookie/lidc) cookies are in place before
// any voyager XHR. Returns true only if we genuinely reached the feed.
async function warmup() {
    const { res, finalUrl } = await manualGet(
        'https://www.linkedin.com/feed/',
        { ...apiHeaders, accept: 'text/html' },
    );
    const authwall = /authwall|\/login|\/uas\/login|checkpoint|challenge/i.test(finalUrl);
    return res.statusCode === 200 && /\/feed\/?$/.test(finalUrl) && !authwall;
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
    const { res } = await manualGet(url, apiHeaders, { hops: 3, responseType: 'json' });
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
        const realLiAtProbe = String(liAt);
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

        // CONTROL PROBES — do the proxy + fingerprint reach LinkedIn at all, and
        // does an anonymous request behave differently from our authenticated one?
        //   public_home: GET / with NO cookies. 200 = proxy/fingerprint is fine,
        //     so any auth failure is the COOKIE. Loop/challenge here = the
        //     proxied got-scraping request is bot-bounced regardless of cookie.
        //   anon_feed: GET /feed/ with NO cookies. A normal logged-out response
        //     redirects to /authwall|/login; if instead it loops to /feed/ just
        //     like ours, the loop is fingerprint-driven, not cookie-driven.
        const controlOpts = { proxyUrl, throwHttpErrors: false, followRedirect: true, maxRedirects: 4, responseType: 'text' };
        let publicHome, anonFeed;
        try {
            publicHome = await gotScraping({ url: 'https://www.linkedin.com/', headers: { accept: 'text/html' }, ...controlOpts });
        } catch (e) { publicHome = { statusCode: `ERR:${String(e.message).slice(0, 40)}` }; }
        try {
            anonFeed = await gotScraping({ url: 'https://www.linkedin.com/feed/', headers: { accept: 'text/html' }, ...controlOpts });
        } catch (e) { anonFeed = { statusCode: `ERR:${String(e.message).slice(0, 40)}` }; }
        // li_at ONLY — is a stale/mismatched JSESSIONID poisoning an otherwise
        // valid li_at? If this lands on the logged-in feed, the fix is code-side
        // (don't send JSESSIONID on GETs). If it still loops, the li_at itself
        // is not a valid member session.
        let liatOnly;
        try {
            liatOnly = await gotScraping({
                url: 'https://www.linkedin.com/feed/',
                headers: { ...apiHeaders, accept: 'text/html', cookie: `li_at=${realLiAtProbe}` },
                ...controlOpts,
            });
        } catch (e) { liatOnly = { statusCode: `ERR:${String(e.message).slice(0, 40)}` }; }

        const control = {
            public_home_status: publicHome.statusCode,
            public_home_final: String(publicHome.url || '').slice(0, 90),
            anon_feed_status: anonFeed.statusCode,
            anon_feed_final: String(anonFeed.url || '').slice(0, 90),
            liat_only_status: liatOnly.statusCode,
            liat_only_final: String(liatOnly.url || '').slice(0, 90),
        };
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
            control,
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

            // Single-shot POST with the warmed-up manual cookie set. A redirect
            // on a voyager POST is never "follow me" — it's LinkedIn bouncing
            // the request to auth, so record it as a failure instead of looping.
            const res = await gotScraping({
                url, method: 'POST',
                headers: headersNow({ 'content-type': 'application/json', cookie: sendCookieHeader() }),
                json: payload, responseType: 'json', ...hopOpts,
            });
            const ok = res.statusCode === 200 || res.statusCode === 201;
            let detail = 'sent';
            if (!ok) {
                const loc = String(res.headers?.location || '');
                // Rich diagnostics: LinkedIn's rest.li error envelope carries the
                // real reason in serviceErrorCode/message/errorDetails, not just
                // the raw body — surface HTTP status + those fields + the LI
                // error-response header so a rejection is legible, not a guess.
                const bodyStr = typeof res.body === 'string' ? res.body : JSON.stringify(res.body || {});
                const errHeader = res.headers?.['x-restli-error-response'] || res.headers?.['x-linkedin-error-response'] || '';
                detail = loc
                    ? `voyager POST bounced (http=${res.statusCode} → ${loc.slice(0, 120)}) — session not accepted for this action`
                    : `voyager POST rejected (http=${res.statusCode}${errHeader ? ` x-restli-error-response=${errHeader}` : ''}` +
                      `, csrf_matched_cookie=${currentCsrf() === String(sendCookies.get('JSESSIONID') || '').replace(/"/g, '')}): ${bodyStr.slice(0, 400)}`;
            }
            result = { success: ok, status_code: res.statusCode, detail, request_payload: payload, request_url: url };
        }
    }
} catch (e) {
    result = { success: false, detail: String(e && e.message ? e.message : e) };
}

console.log(`[voyager-send] action=${action} → ${JSON.stringify(result)}`);
await Actor.pushData(result);
await Actor.setValue('OUTPUT', result);
await Actor.exit();
