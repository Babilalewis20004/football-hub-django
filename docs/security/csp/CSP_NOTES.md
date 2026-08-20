# Content Security Policy — Report-Only Rollout

**Project:** MyFootballBlog (Django, `django-csp` 4.0)
**Status:** **Report-Only**. Nothing is blocked yet; violations are logged to
`logs/csp_violations.log` via the `/csp-report/` endpoint
(`config/views.py:csp_report_view`).
**Last browser-verified:** 2026-08-10 (local dev server, Chrome DevTools)

---

## 1. Policy configuration

| Directive | Value | Why |
|---|---|---|
| `default-src` | `'self'` | Fallback for anything not listed below. |
| `script-src` | `'self' 'nonce-<random>' https://cdn.jsdelivr.net https://unpkg.com` | `'self'` for local static JS (htmx CSRF wiring aside — see below); jsdelivr for Bootstrap's bundle, unpkg for htmx; the nonce covers the two static inline `<script>` blocks in `base.html` and the conditional one in `profile.html`. |
| `style-src` | `'self' 'unsafe-inline' https://cdn.jsdelivr.net` | jsdelivr for Bootstrap/Bootstrap Icons CSS. `'unsafe-inline'` is here **only because of CKEditor 4** — see below, it can't be avoided by nonces. |
| `font-src` | `'self' https://cdn.jsdelivr.net` | Bootstrap Icons' `.woff2` files are served from the same jsdelivr host as its CSS. |
| `img-src` | `'self' data:` | Posts/avatars are same-origin. `data:` was added for the 2FA setup page's QR code, which is generated server-side per request (`users/views.py:_qr_data_uri`) and embedded inline rather than served from its own URL — this may also explain the previously-unidentified inline `data:` SVG violations noted below. **Still inaccurate** — the homepage's country flags are actually loaded from `https://flagcdn.com`, not same-origin; see "Known gap" below. |
| `connect-src` | `'self'` | Covers both the chat app's same-origin `fetch()` calls and its `ws://`/`wss://` WebSocket connections (Django Channels) — `'self'` matches ws/wss on the current host. |
| `frame-src` | `'none'` | No iframes are embedded anywhere in the app. |
| `frame-ancestors` | `'none'` | Mirrors the existing `X_FRAME_OPTIONS = 'DENY'`; nothing should be allowed to frame this site. |
| `object-src` | `'none'` | No plugins/Flash; standard hardening default. |
| `base-uri` | `'self'` | Blocks `<base>` tag injection. |
| `form-action` | `'self'` | Every form in the app posts to a same-origin URL. |
| `report-uri` | `/csp-report/` | Where violation reports are sent (Report-Only only, for now). |

**Flagged for review:** `https://cdn.jsdelivr.net` and `https://unpkg.com` are
allowed in `script-src`; `cdn.jsdelivr.net` is also allowed in `font-src` and
`style-src`. Confirm these are only as broad as CKEditor/dependencies
actually require.

**Known gap:** `img-src 'self'` does **not** currently allow
`https://flagcdn.com`, but `blog/services/homepage.py:22-23` hardcodes flag
images from there (`france_flag`, `morocco_flag`, rendered via `<img>` in
`templates/components/match_block.html`). This is the single largest source
of violations in `logs/csp_violations.log` (26 of 46 logged reports) and
fires on nearly every page. Must be resolved — either add
`https://flagcdn.com` to `img-src` or self-host the flag images — before
switching to enforced mode. See section 4.

### Where `'unsafe-inline'` was needed, and why a nonce doesn't work there

`style-src` needs `'unsafe-inline'` because of **CKEditor 4** (`django-ckeditor`,
used for post content). CSP nonces only apply to `<script>` and `<style>`
*tags* — they cannot cover the `style=""` *attribute*, which is the
mechanism CKEditor's own JS uses at runtime to position its dialogs, skin
its toolbar, and style its editing iframe. There's no fixed set of styles to
hash either, since CKEditor generates them dynamically. Short of forking
CKEditor or replacing it, `'unsafe-inline'` for `style-src` is unavoidable.
(It also happens to cover the handful of static `style="display:inline;"` /
`style="font-size:..."` attributes already in the templates and the one
CKEditor puts on its own widget wrapper `<div>` — none of those forced the
`'unsafe-inline'` decision on their own, since eliminating them wouldn't let
the policy drop it anyway.)

`script-src` did **not** need `'unsafe-inline'` — the three inline
`<script>` blocks in `base.html`/`profile.html` now carry
`nonce="{{ request.csp_nonce }}"` (from django-csp), and the one inline
`onclick=` handler (`back_button.html`) was moved into an external file,
`static/js/back-button.js`, with a delegated click listener instead.

### Why django-csp instead of Django's built-in CSP middleware

The project runs Django 5.2.3. Django's own CSP support (`django.middleware.csp`)
was only added in Django 6.0, so it isn't available here. `django-csp==4.0`
was added to `requirements.txt` instead — its settings shape
(`CONTENT_SECURITY_POLICY_REPORT_ONLY = {"DIRECTIVES": {...}}`, the `NONCE`
sentinel) mirrors Django 6's built-in middleware, so upgrading later and
switching to the built-in version, if you ever want to, should be a small
change rather than a rewrite.

---

## 2. Browser verification

Full step-by-step verification (DevTools walkthrough, screenshots,
violation-by-violation detail) lives in
[`CSP_BROWSER_TESTING.md`](CSP_BROWSER_TESTING.md). Summary as of
2026-08-10 (local dev server, Chrome DevTools):

- Report-Only header confirmed sent, correctly formatted, with a fresh
  per-request nonce.
- `object-src 'none'` and `frame-ancestors 'none'` confirmed locked down.
- **Three** distinct violation types found across the 46 reports logged
  during testing (not two — see `CSP_BROWSER_TESTING.md` for how the third
  was identified):
  1. `img-src` — inline `data:` SVG (17 reports). Source element not yet
     identified.
  2. `img-src` — `https://flagcdn.com/w40/{fr,ma}.png` (26 reports, the
     most frequent). Confirmed source: see "Known gap" above.
  3. `script-src` — deliberate `evil.example.com` test (3 reports).
     Confirms the reporting pipeline works end-to-end; not a real issue.
- All violations confirmed landing in `logs/csp_violations.log` via
  `POST /csp-report/` → `204`.

See `CSP_BROWSER_TESTING.md` for the outstanding-items table and full
click-through status.

---

## 3. What to watch for in `logs/csp_violations.log` over the coming weeks

- **False positives from real users** — different browsers, extensions, or
  cached older pages can trigger reports that aren't real problems (e.g. a
  browser extension injecting its own script). Look for a `blocked-uri` that
  isn't `cdn.jsdelivr.net`, `unpkg.com`, or one of your own routes/static
  paths — those are the interesting ones.
- **Anything under `script-src` or `style-src`** you didn't expect — this is
  the strongest signal of either a missed legitimate source (fix the policy)
  or actual injected content (investigate as a security incident).
- **`connect-src` violations** pointing at unfamiliar hosts — would indicate
  something making requests you don't know about.
- **Volume from admin/editor pages** — CKEditor is the most likely source of
  noisy-but-harmless reports; confirm they're all `style-src`/`style-src-attr`
  before writing them off.
- **Report volume and diversity generally** — a policy that's too strict for
  real usage will show up as a small number of *sources* generating a very
  large number of *reports* (i.e. one broken thing firing on every
  pageview), which is different from a wide variety of one-off legitimate
  misses.

---

## 4. What's needed before switching to enforced mode

1. Let this run in Report-Only for a realistic stretch of real traffic
   (days to a couple of weeks, covering admin/editor workflows, not just the
   public pages) and clear out anything unexpected in
   `logs/csp_violations.log`.
2. Confirm there are no legitimate `blocked-uri` entries outside the current
   allowlist. If there are, add them to
   `CONTENT_SECURITY_POLICY_REPORT_ONLY["DIRECTIVES"]` in `config/settings.py`
   and keep watching. **Known outstanding:** `https://flagcdn.com` (see
   "Known gap" in section 1) must be added to `img-src` — or the flag images
   self-hosted instead — before enforcing, since it's a confirmed,
   frequent, legitimate source that isn't in the allowlist yet.
3. Once the log is clean, rename
   `CONTENT_SECURITY_POLICY_REPORT_ONLY` to `CONTENT_SECURITY_POLICY` in
   `config/settings.py` (django-csp reads both independently and will set
   both headers if both are defined, so this is a rename, not new work).
   Keep `CONTENT_SECURITY_POLICY_REPORT_ONLY` around pointed at a *new*,
   stricter draft if you want to keep iterating after enforcing the current
   one.
4. Re-test the full app manually after switching (not just automated
   checks) — CSP violations that were merely logged before will now actually
   block content: check post creation/editing (CKEditor), the live chat
   widget (WebSocket + fetch), login/registration (CAPTCHA image), and the
   admin site.
5. Consider whether `frame-ancestors 'none'` should be reported on too during
   this window — it's already effectively enforced by `X_FRAME_OPTIONS = 'DENY'`,
   so it's low-risk to promote alongside everything else.

## 5. Next steps

1. Identify the element/script generating the inline SVG `data:` URI and
   confirm whether adding `data:` to `img-src` is the right fix.
2. Decide the fix for `https://flagcdn.com` (add to `img-src`, or self-host
   the France/Morocco flag images used in `blog/services/homepage.py`) and
   apply it.
3. Complete the click-through of remaining pages (admin, CKEditor save flow,
   comments/AJAX features) with the log tailing.
4. Test in an Incognito window with extensions disabled to rule out
   extension-injected false positives.
5. Once the violation log is clean over a real traffic window, revisit
   section 4's checklist for promoting
   `CONTENT_SECURITY_POLICY_REPORT_ONLY` to enforced `CONTENT_SECURITY_POLICY`.
