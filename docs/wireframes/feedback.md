# Feedback

**Template:** `templates/pages/feedback.html` (extends `base.html` directly, not `pages/_base_page.html`)
**Route:** `/feedback/` (`pages.views.feedback_view`, name=`feedback`)
**Users/roles:** Public — anonymous or authenticated (form behavior differs slightly by auth state).

## Wireframe

```text
+----------------------------------------------------------------+
| MASTHEAD / NAVBAR                                                |
+----------------------------------------------------------------+
|  Send us your feedback                                            |
|                                                                    |
|  Rating:  ☆ ☆ ☆ ☆ ☆   (5 radio inputs, CSS-driven star display,     |
|                          required, values 5 down to 1)               |
|                                                                    |
|  {% if not user.is_authenticated %}                                |
|    Name (optional):  [.......................]                     |
|    Email (optional): [.......................]                     |
|  {% endif %}                                                       |
|                                                                    |
|  Comment: [........................................]                |
|           [........................................]                |
|                                                                    |
|  [ Submit Feedback ]                                               |
+----------------------------------------------------------------+
| FOOTER                                                            |
+----------------------------------------------------------------+
```

## Form

`FeedbackForm` (`pages/forms.py`) — `rating` (1–5, required), `name` (optional), `email` (optional), `comment` (optional). `method="POST" novalidate`, CSRF-protected.

## Behavior

- Authenticated submitters have `name`/`email` fields hidden and instead auto-filled server-side from the account (`request.user.get_full_name()` or username; `request.user.email`) if left blank — but the view still accepts an explicit override if those fields were somehow submitted.
- On success: `Feedback.objects.create(...)`, a success message ("Thanks for your feedback!..."), redirect back to `/feedback/` (POST-redirect-GET, form resets).
- No feedback is ever surfaced back to the submitter (no "view your past feedback" page) — this is a write-only public form; feedback is only readable via Django admin (`pages/admin.py: FeedbackAdmin`).

## Validation / error states

- `rating` is required (a `PositiveSmallIntegerField` with 1–5 choices) — an unrated submission fails standard Django form validation and re-renders the page with field errors.
- No rate-limiting or CAPTCHA on this form (unlike login/registration) — it can be submitted repeatedly by anonymous users with no throttling found in the codebase.

## Robots

`{% block robots %}noindex, nofollow{% endblock %}`.
