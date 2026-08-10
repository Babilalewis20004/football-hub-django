# Content Security Policy — Report-Only rollout

Status: **Report-Only**. Nothing is blocked yet; violations are logged to
`logs/csp_violations.log` via the `/csp-report/` endpoint
(`config/views.py:csp_report_view`).

## What's allowed, and why

| Directive | Value | Why |
|---|---|---|
| `default-src` | `'self'` | Fallback for anything not listed below. |
| `script-src` | `'self' 'nonce-<random>' https://cdn.jsdelivr.net https://unpkg.com` | `'self'` for local static JS (htmx CSRF wiring aside — see below); jsdelivr for Bootstrap's bundle, unpkg for htmx; the nonce covers the two static inline `<script>` blocks in `base.html` and the conditional one in `profile.html`. |
| `style-src` | `'self' 'unsafe-inline' https://cdn.jsdelivr.net` | jsdelivr for Bootstrap/Bootstrap Icons CSS. `'unsafe-inline'` is here **only because of CKEditor 4** — see below, it can't be avoided by nonces. |
| `font-src` | `'self' https://cdn.jsdelivr.net` | Bootstrap Icons' `.woff2` files are served from the same jsdelivr host as its CSS. |
| `img-src` | `'self'` | All images (posts, avatars, flags) are same-origin; nothing external found. |
| `connect-src` | `'self'` | Covers both the chat app's same-origin `fetch()` calls and its `ws://`/`wss://` WebSocket connections (Django Channels) — `'self'` matches ws/wss on the current host. |
| `frame-src` | `'none'` | No iframes are embedded anywhere in the app. |
| `frame-ancestors` | `'none'` | Mirrors the existing `X_FRAME_OPTIONS = 'DENY'`; nothing should be allowed to frame this site. |
| `object-src` | `'none'` | No plugins/Flash; standard hardening default. |
| `base-uri` | `'self'` | Blocks `<base>` tag injection. |
| `form-action` | `'self'` | Every form in the app posts to a same-origin URL. |
| `report-uri` | `/csp-report/` | Where violation reports are sent (Report-Only only, for now). |

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

## What to watch for in `logs/csp_violations.log` over the coming weeks

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

## What's needed before switching to enforced mode

1. Let this run in Report-Only for a realistic stretch of real traffic
   (days to a couple of weeks, covering admin/editor workflows, not just the
   public pages) and clear out anything unexpected in
   `logs/csp_violations.log`.
2. Confirm there are no legitimate `blocked-uri` entries outside the current
   allowlist. If there are, add them to
   `CONTENT_SECURITY_POLICY_REPORT_ONLY["DIRECTIVES"]` in `config/settings.py`
   and keep watching.
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
