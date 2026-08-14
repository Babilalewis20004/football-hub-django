# Post Detail

**Template:** `templates/blog/post_detail.html` + `templates/partials/post_engagement.html` (included as `#ig-engagement`)
**Route:** `/post/<slug>/` (`blog.views.posts.post_detail`, name=`post_detail`)
**Users/roles:** Public for published posts; the author or anyone with `blog.change_post` may view an unpublished post via this same URL (`blog.services.posts.can_view_post`); anyone else gets `HttpResponseForbidden`.

## Wireframe

```text
+----------------------------------------------------------------+
| MASTHEAD / NAVBAR                                                |
+----------------------------------------------------------------+
| < Back (falls back to home)                                      |
|                                                                    |
|  "Instagram-style" post card (ig-post-card)                        |
|  +--------------------------------------------------------+       |
|  | [author avatar]  author name   posted Xh ago  [status?]  |     |
|  |                                  (edited Yh ago, if updated)|   |
|  |------------------------------------------------------------|   |
|  |  Title                                                       | |
|  |                                                                | |
|  |  [ Featured image, full width ]                                |
|  |                                                                | |
|  |  #ig-engagement (partials/post_engagement.html)                |
|  |  [♥ Like]  [💬 Comment]  [↗ Share]  [🔖 Bookmark]               |
|  |  N likes · M views                                              |
|  |------------------------------------------------------------|   |
|  |  Excerpt (caption style)                                       ||
|  |                                                                | |
|  |  Full body content (CKEditor HTML, rendered |safe)              |
|  +--------------------------------------------------------+       |
|                                                                    |
|  #ig-comments                                                      |
|  +--------------------------------------------------------+       |
|  | [avatar] username   "comment text"   Xh ago               |    |
|  | [avatar] username   "comment text"   Xh ago               |    |
|  | ...                                                        |    |
|  +--------------------------------------------------------+       |
|                                                                    |
|  {% if user.is_authenticated %}                                    |
|    [ Add a comment... ] [ Post ] (#igPostCommentBtn, disabled       |
|                                    until non-empty)                 |
|  {% else %}                                                        |
|    "Login to leave a comment" -> /login/?next=...                   |
|  {% endif %}                                                       |
|                                                                    |
|  Related posts (from blog.services.posts.get_related_posts —        |
|  by shared tags or category, up to 4) — layout not independently    |
|  verified line-by-line during this audit                            |
+----------------------------------------------------------------+
| FOOTER                                                            |
+----------------------------------------------------------------+
```

## Engagement partial detail (`partials/post_engagement.html`, `#ig-engagement`)

| Element | Behavior |
|---|---|
| Like button | Authenticated only. `hx-post="{% url 'like_post' post.slug %}" hx-target="#ig-engagement" hx-swap="outerHTML"`. Toggles filled/outline heart based on `user in post.likes.all`. Anonymous users see a login link instead. |
| Comment icon | In-page anchor jump to `#ig-comments`, not a network request. |
| Share button | `#igShareBtn`, JS-driven (not HTMX) — uses `navigator.share()` if available, falls back to clipboard copy. Delegated listener specifically because HTMX replaces the whole `#ig-engagement` block on like/bookmark. |
| Bookmark button | Authenticated only. `hx-post="{% url 'bookmark_post' slug=post.slug %}" hx-target="#ig-engagement" hx-swap="outerHTML"`. Toggles filled/outline bookmark icon. Anonymous → login link. |
| Footer counts | `post.likes.count` + `post.views` shown as plain text |

## Comment form

**Form:** `CommentForm` (single `content` field), `method="POST"`, CSRF-protected, posts back to the same `post_detail` URL. Submit is disabled client-side until the textarea has content (inline JS), but the server does not separately validate a minimum length.

**On submit:** anonymous users are redirected to login rather than seeing a form-level error (the form is simply not rendered for them). On success, redirects back to `post_detail` (POST-redirect-GET pattern), so the page reloads with the new comment visible.

**No delete-comment control exists in this template** — even though `blog.views.comments.delete_comment` exists in the codebase, it has no URL registered in `blog/urls.py` and nothing links to it. This should be treated as dead/incomplete functionality, not a documented feature.

## View counting

Every request to this view increments `Post.views` atomically (`F("views") + 1`), with no deduplication (e.g. no per-session/per-IP throttling) — reloading the page repeatedly increments the count every time.

## SEO

This template overrides `base.html`'s SEO blocks with post-specific Open Graph/Twitter Card meta tags, a canonical URL, and a dynamic OG image sourced from `post.featured_image` when present.

## Status badge caveat

The template includes a badge branch for a `"pending"` status value that does not appear in `Post.STATUS` choices anywhere else in the codebase (the real values are `draft`/`in_review`/`needs_changes`/`approved`/`published`) — likely stale, dead conditional code rather than a real state a post can be in.
