# UI Wireframes

These wireframes describe the **actual rendered templates** in `templates/`, cross-checked against `blog/urls.py`, `users/urls.py`, `chat/urls.py`, `pages/urls.py`, and `config/urls.py`. Every page, form field, button, and navigation link listed here was confirmed present in the corresponding `.html` file — nothing is speculative.

## Global layout (present on every page via `base.html`)

```text
+--------------------------------------------------------------------+
| MASTHEAD: [Logo] [Search box.....] [Dark mode toggle]              |
|   Authenticated: [Editor Dashboard?] [Support Inbox+badge?]        |
|                  [Author Dashboard?] [+ Create Post?] [Account v]  |
|   Anonymous:     [Login] [Register]                                |
+--------------------------------------------------------------------+
| NAVBAR: Home | Champions League | La Liga | Premier League |       |
|         Serie A | Transfers | Predictions      [Dashboard|Profile|Logout v] (if authed) |
+--------------------------------------------------------------------+
| Django messages (dismissible alerts)                               |
+--------------------------------------------------------------------+
|                                                                     |
|                         {% block content %}                        |
|                                                                     |
+--------------------------------------------------------------------+
| FOOTER: Brand | Quick Links* | Latest News* | Newsletter form      |
|         Legal: Privacy | Terms | About | Cookies | Careers | Contact|
+--------------------------------------------------------------------+
| [Chat bubble widget] (all pages except support inbox/room)         |
| [Cookie consent banner] (all pages, first visit only)              |
+--------------------------------------------------------------------+
```
`*` = "Quick Links" (News/About/Contact) and "Latest News" (Match Reports/Transfer News/Player Interviews/Match Predictions/**League Standings**) footer columns are rendered but their links are dead `href="#"` placeholders — not wired to any view. Documented here because they are visually present in the UI, but no live functionality exists behind them. **"League Standings" in particular has zero backend support** — no standings/table data exists anywhere in the codebase.

**Important:** the navbar's "Champions League / La Liga / Premier League / Serie A / Transfers / Predictions" items are **not live football data** — they are `Category` model instances (editorial content taxonomy) linked via `category_posts`. There is no fixtures, live-score, or standings feature anywhere in this codebase.

## Pages documented

| Page | File | Route(s) |
|---|---|---|
| [home-page.md](home-page.md) | `blog/home.html` | `/` |
| [authentication.md](authentication.md) | `users/login.html`, `users/register.html`, `users/password_reset_*.html` | `/login/`, `/users/register/`, `/password-reset/...` |
| [blog.md](blog.md) | `blog/category_posts.html`, `tag_posts.html`, `author_posts.html`, `search_results.html` (cross-ref'd with [search.md](search.md)), `dashboard.html`, `saved_posts.html`, `author_dashboard.html`, `editor_dashboard.html`, `post_form.html`, `post_confirm_delete.html` | `/category/<slug>/`, `/tag/<slug>/`, `/author/<username>/`, `/dashboard/`, `/saved/`, `/dashboard/author/`, `/dashboard/editor/`, `/post/create/`, `/post/<slug>/edit/`, `/post/<slug>/delete/` |
| [post-detail.md](post-detail.md) | `blog/post_detail.html`, `partials/post_engagement.html` | `/post/<slug>/` |
| [search.md](search.md) | `blog/search_results.html` | `/search/?q=` |
| [profile.md](profile.md) | `users/profile.html` | `/users/profile/` |
| [comments.md](comments.md) | (embedded in `post_detail.html`, no standalone page) | n/a — comment form is part of post detail |
| [live-chat.md](live-chat.md) | `components/chat_widget.html` | Global widget, backed by `/chat/start/`, `/chat/<id>/messages/`, `/chat/<id>/close/`, `ws/chat/<id>/` |
| [support-inbox.md](support-inbox.md) | `chat/support_inbox.html`, `chat/support_room.html` | `/chat/support/`, `/chat/support/<id>/` |
| [notifications.md](notifications.md) | (embedded in `author_dashboard.html`/`editor_dashboard.html`) | n/a — no standalone notifications page |
| [2fa.md](2fa.md) | `users/two_factor_setup.html`, `two_factor_verify.html`, `two_factor_recovery_codes.html` | `/users/2fa/setup/`, `/users/2fa/verify/`, `/users/2fa/recovery-codes/regenerate/` |
| [feedback.md](feedback.md) | `pages/feedback.html` | `/feedback/` |
| [admin.md](admin.md) | `templates/admin/login.html` + Django's default admin | `/admin/` |

## Pages that exist but are intentionally out of deep-dive scope

The following are static, no-logic pages (`TemplateView`, no forms, no dynamic data), several explicitly marked in their own template text as development placeholders: `about_us.html`, `careers.html`, `contact_us.html`, `cookies.html`, `privacy_policy.html`, `terms_of_use.html`. They all extend `pages/_base_page.html` and follow the same simple layout: a page title, static prose content, and (for `careers.html`/`privacy_policy.html`) a link to Contact Us. `404.html`/`500.html` are minimal error pages (404 has a "Return Home" link; 500 has none).

## Confirmed dead/orphaned frontend code (not part of any live page)

These template components and JS files exist in the repository but are not included/referenced by any live, reachable page — listed here so they are not mistaken for missing documentation of a real feature:

- `templates/components/article_grid.html` (loops a `worldcup_posts` variable no view ever sets)
- `templates/components/bullet_links.html`
- `templates/components/featured_article.html`
- `templates/components/news_feed.html`
- `templates/components/sidebar.html` and `templates/blog/includes/sidebar.html` (two separate, both-unused sidebar implementations)
- `templates/components/slider.html` + `static/js/slider.js` (a full carousel component with no page including it)
- `templates/components/pagination.html` (a generic pager, not included by any paginated-looking page)
- `blog/views/comments.py: delete_comment` (a view with no URL and no template link to it)
- `blog/services/search.py: search_posts_queryset` (duplicated by inline logic in `blog/views/search.py`, never actually called)
