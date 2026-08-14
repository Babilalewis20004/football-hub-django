# Profile

**Template:** `templates/users/profile.html`
**Route:** `/users/profile/` (`users.views.profile`, name=`profile`)
**Users/roles:** Any authenticated user (`@login_required`).

## Wireframe

```text
+----------------------------------------------------------------+
| MASTHEAD / NAVBAR                                                |
+----------------------------------------------------------------+
| < Back                                                           |
|                                                                    |
|  [ Avatar image ]                                                 |
|                                                                    |
|  Update Profile                                                   |
|  +--------------------------------------------------------+       |
|  | Avatar:         [ Choose file ]                          |     |
|  | Bio:             [........................]              |     |
|  | Favorite team:   [........................]              |     |
|  | [ Update Profile ]                                        |     |
|  +--------------------------------------------------------+       |
|                                                                    |
|  Two-Factor Authentication                                        |
|  +--------------------------------------------------------+       |
|  | {% if two_factor_enabled %}                                |   |
|  |   Status: Enabled     Recovery codes remaining: N            | |
|  |   [ Regenerate recovery codes ] -> modal (password required)  ||
|  |   {% if not two_factor_required %}                            ||
|  |     [ Disable 2FA ] -> modal (password required)              ||
|  |   {% endif %}                                                  ||
|  | {% else %}                                                     ||
|  |   [ Enable two-factor authentication ] -> /users/2fa/setup/    ||
|  | {% endif %}                                                    ||
|  +--------------------------------------------------------+       |
|                                                                    |
|  Danger Zone                                                      |
|  +--------------------------------------------------------+       |
|  | [ Delete Your Account ] -> modal (password required)      |     |
|  +--------------------------------------------------------+       |
+----------------------------------------------------------------+
| FOOTER                                                            |
+----------------------------------------------------------------+
```

## Forms

| Form | Fields | Action | Notes |
|---|---|---|---|
| Profile update | `avatar` (file), `bio`, `favorite_team` | `POST`, `enctype="multipart/form-data"`, self (`/users/profile/`) | `ProfileUpdateForm` (ModelForm on `CustomUser`) |
| Regenerate recovery codes | `password` | `POST /users/2fa/recovery-codes/regenerate/` | Bootstrap modal `#regenerateCodesModal`; only shown if 2FA already enabled |
| Disable 2FA | `password` | `POST /users/2fa/disable/` | Bootstrap modal `#disable2faModal`; only shown if 2FA enabled **and** the account's role doesn't mandate it |
| Delete account | `password` | `POST /users/profile/delete/` | Bootstrap modal `#deleteAccountModal`; auto-opens via inline script if a `delete_error` (wrong password) is in context |

## Interactions

- No HTMX on this page — all actions are full-page POST/redirect cycles.
- Modals are standard Bootstrap 5 JS components (bundle loaded globally in `base.html`).

## Validation / error states

- Profile form: standard Django `ModelForm` validation (image file type/size limits are whatever `ImageField`/Pillow enforce; no explicit custom validators were found on these fields).
- All three password-confirmation actions (regenerate codes, disable 2FA, delete account) show an inline error message ("Incorrect password...") and keep the user on the page if the password is wrong — none of them reveal any other account information on failure.

## Related

- Back button falls back to `/dashboard/` if there's no same-origin referrer.
- See [2fa.md](2fa.md) for the full enrollment/verification flow this page links out to.
