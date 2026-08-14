# Two-Factor Authentication (2FA)

**Users/roles:** `admin`, `editor`, `author` (mandatory); `reader` (optional, self-service via Profile). See [architecture/security-architecture.md](../architecture/security-architecture.md) for the full policy.

## 2FA Setup (enrollment)

**Template:** `templates/users/two_factor_setup.html`
**Route:** `/users/2fa/setup/` (`users.views.two_factor_setup`, name=`two_factor_setup`)

```text
+----------------------------------------------------+
|  [ REQUIRED FOR YOUR ROLE ] (badge, only if required) |
|                                                      |
|  Set up two-factor authentication                    |
|                                                      |
|  1. Scan this QR code with your authenticator app:    |
|     +----------------+                                |
|     |  [ QR IMAGE ]  |   (data: URI, server-generated) |
|     +----------------+                                |
|     Can't scan? Enter manually: XXXX XXXX XXXX XXXX    |
|                                                      |
|  2. Enter the 6-digit code from your app:              |
|     Code: [........]                                  |
|     [ Activate & Continue ]                            |
|                                                      |
|  --------------------------------------------------  |
|  [ Log out instead ] (POST form)                       |
+----------------------------------------------------+
```

**Form:** `TwoFactorCodeForm` (single `code` field, POST, CSRF-protected), hidden `next`.

**On success:** device confirmed, any other unconfirmed devices cleaned up, 10 recovery codes generated and shown exactly once → redirects to the recovery-codes screen below.

**On failure:** "Incorrect code. Check your authenticator app and try again." inline field error.

## Recovery Codes (shown once)

**Template:** `templates/users/two_factor_recovery_codes.html`
**Route:** rendered directly by `two_factor_setup` (on success) and by `/users/2fa/recovery-codes/regenerate/` (name=`two_factor_regenerate_codes`)

```text
+----------------------------------------------------+
|  Save your recovery codes                            |
|                                                      |
|  ⚠ These are shown only once. Store them somewhere    |
|    safe — each can be used once if you lose access    |
|    to your authenticator app.                         |
|                                                      |
|  ABCD-1234   EFGH-5678   IJKL-9012                    |
|  MNOP-3456   QRST-7890   UVWX-1234                    |
|  ... (10 total)                                        |
|                                                      |
|  [ ] I have saved these codes                          |
|  [ Continue ] (disabled until checkbox is checked)     |
+----------------------------------------------------+
```

**Behavior:** the "Continue" link is disabled (`aria-disabled`) until the checkbox is checked, toggled by inline JS. Destination differs: fresh enrollment (`just_enrolled=True`) continues to `next` or `/`; a mid-session regeneration continues to `/users/profile/`.

## 2FA Verify (per-session check after login)

**Template:** `templates/users/two_factor_verify.html`
**Route:** `/users/2fa/verify/` (`users.views.two_factor_verify`, name=`two_factor_verify`)

```text
+----------------------------------------------------+
|  Enter your authentication code                      |
|                                                      |
|  Code: [........]  (accepts a live TOTP code          |
|                      OR an unused recovery code)      |
|                                                      |
|  [ error message, if any — throttle wait time or      |
|    "Invalid code" ]                                   |
|                                                      |
|  [ Verify ]                                           |
|  --------------------------------------------------  |
|  [ Log out instead ] (POST form)                        |
+----------------------------------------------------+
```

**Behavior:**
- Every fresh password login lands here (or at Setup) before reaching the rest of the app, regardless of role, if a confirmed device exists.
- `TwoFactorEnforcementMiddleware` re-checks this on **every subsequent request** in an unverified session — including direct navigation to a bookmarked URL and logins that bypass `login_view` entirely (e.g. `/admin/`).
- Verifying with a recovery code shows a warning with the number of codes remaining.
- Both TOTP and recovery-code verification are throttled with exponential backoff (django-otp built-in) after repeated failures — shown as a "wait N seconds" message.

## Disabling 2FA / regenerating codes (embedded in Profile, not a standalone page)

See [profile.md](profile.md) — the "Disable 2FA" and "Regenerate recovery codes" actions live in modals on the profile page and are only available to `reader` accounts (privileged roles cannot self-disable).

## Navigation summary

```text
Login (password step)
   |
   v
two_factor_gate(user)
   |
   +--"setup"--> 2FA Setup --> Recovery Codes shown --> next/home
   |
   +--"verify"-> 2FA Verify --(TOTP or recovery code)--> next/home
   |
   +--None-----> next/home directly
```
