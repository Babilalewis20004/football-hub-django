# Blog: Listings, Dashboards, Post Editor

## Category / Tag / Author listing pages

**Templates:** `blog/category_posts.html`, `blog/tag_posts.html` (near-identical layout), `blog/author_posts.html` (older/simpler layout)
**Routes:** `/category/<slug>/`, `/tag/<slug>/`, `/author/<username>/`
**Users/roles:** Public.

```text
+----------------------------------------------------------------+
| MASTHEAD / NAVBAR                                                |
+----------------------------------------------------------------+
| category.name  |  "Latest Updates"  |  category.updated_at        |
|                                                                    |
| posts-grid:                                                       |
| +----------+  +----------+  +----------+                          |
| | [image]  |  | [image]  |  | [image]  |                          |
| | Title    |  | Title    |  | Title    |                          |
| | author,  |  | author,  |  | author,  |                          |
| | time     |  | time     |  | time     |                          |
| | Read More-> | Read More-> | Read More-> |                       |
| +----------+  +----------+  +----------+                          |
+----------------------------------------------------------------+
```
`author_posts.html` uses plainer markup (no `posts-grid`/`post-card` classes) and additionally shows a "Popular Posts" `<ul>` (same author's posts by view count). No pagination controls are rendered on any of these three pages despite the views not limiting result counts — `components/pagination.html` exists but is never included here.

Only **published** posts (`is_published=True`) appear on all three.

## Search results

See [search.md](search.md).

## Generic Dashboard (`/dashboard/`)

**Template:** `blog/dashboard.html`
**Route:** `/dashboard/` (`blog.views.dashboard.dashboard`, name=`dashboard`)
**Users/roles:** Any authenticated user.

```text
+----------------------------------------------------------------+
|  My Posts                          |  Bookmarks                  |
|  +-------------------------+       |  +------------------------+ |
|  | post title -> post link  |      |   | post title -> post link | |
|  | post title -> post link  |      |   | post title -> post link | |
|  +-------------------------+       |  +------------------------+ |
+----------------------------------------------------------------+
```
Simple two-column list, no forms, no HTMX. This is the "reader-level" landing page after login for accounts without dashboard permissions; authors/editors are also linked here from other pages even though they have their own dedicated dashboards below.

## Saved Posts (`/saved/`)

**Template:** `blog/saved_posts.html`
**Route:** `/saved/` (name=`saved_posts`)
**Users/roles:** Any authenticated user.

Same `posts-grid`/`post-card` layout as the category/tag pages, one card per `Bookmark`, showing "Saved {{ timesince }} ago" instead of category/author metadata.

## Author Dashboard (`/dashboard/author/`)

**Template:** `blog/author_dashboard.html` + `blog/partials/author_dashboard_lists.html` (HTMX partial)
**Route:** `/dashboard/author/` (requires `blog.add_post` permission)
**Users/roles:** `author`, `contributor` (by permission), and anyone else holding `blog.add_post`.

```text
+----------------------------------------------------------------+
|  My Posts — {{ user }}                    [+ Start new draft]   |
|                                                                    |
|  [ Draft: N ] [ In review: N ] [ Needs changes: N (!) ] [ Published: N ] |
|                                                                    |
|  Filter: [All] [Draft] [In review] [Needs changes] [Published]    |
|                                                                    |
|  #author-dashboard-lists  (hx-get every 10s, auto-refreshing)      |
|  +--------------------------------------------------------+       |
|  | NEEDS CHANGES                                            |     |
|  |   Post title — editor feedback: "..."                    |     |
|  |   [ Edit ] [ Resubmit for review ]                        |     |
|  | DRAFTS                                                    |     |
|  |   Post title                                              |     |
|  |   [ Continue editing ] [ Submit for review ] [ Delete ]    |     |
|  | IN REVIEW / APPROVED                                       |     |
|  |   Post title                                               |     |
|  |   [ View ]  [ Withdraw from review ] (if still in_review)   |     |
|  | PUBLISHED                                                   |     |
|  |   Post title — "Announced to channel" / "Not announced —    |     |
|  |                  bot token unset"                            |     |
|  |   [ View live ]                                              |     |
|  +--------------------------------------------------------+       |
|                                                                    |
|  Notifications (sidebar)                                          |
|  +------------------------+                                       |
|  | "Your post was approved and is pending publication."          | |
|  | "Changes requested on '...': ..."                              ||
|  +------------------------+                                       |
+----------------------------------------------------------------+
```

**Forms (all POST, CSRF-protected):** "Submit for review" → `post_submit_for_review`; "Resubmit for review" → same endpoint; "Withdraw from review" → `post_withdraw_from_review`; "Delete" → link to the confirm-delete page, not an inline form.

**HTMX:** `#author-dashboard-lists` div: `hx-get="{% url 'author_dashboard_partial' %}?status=..." hx-trigger="load, every 10s" hx-target="#author-dashboard-lists" hx-swap="innerHTML"` — polls every 10 seconds so status changes made by an editor appear without a manual refresh.

**Notifications** are fetched once per page load (unread `Notification` rows for this user) and marked read as a side effect of opening the dashboard.

## Editor Dashboard (`/dashboard/editor/`)

**Template:** `blog/editor_dashboard.html` + `blog/partials/editor_dashboard_lists.html` (HTMX partial)
**Route:** `/dashboard/editor/` (requires `blog.can_approve_post` permission)
**Users/roles:** `editor`, `admin` (by permission).

```text
+----------------------------------------------------------------+
|  Editorial Workflow                    Search: [...] [Search]    |
|                                                                    |
|  Notifications: (list, if any)                                    |
|                                                                    |
|  Filter: [All] [Draft] [In review] [Approved] [Published]         |
|                                                                    |
|  #editor-dashboard-lists  (hx-get every 10s, kanban board)         |
|  +----------+  +----------+  +----------+  +----------+            |
|  | DRAFT (n)|  | IN REVIEW| | APPROVED | | PUBLISHED |             |
|  |          |  |   (n)    | |   (n)    | |   (n)     |             |
|  | [card]   |  | [card]   | | [card]   | | [card]    |             |
|  |  Edit    |  |  Edit    | |  Edit    | |  Edit     |             |
|  |  Delete  |  |  Approve | |  Publish | |  Delete   |             |
|  |          |  |  Request | |  Delete  | |  Telegram |             |
|  |          |  |  changes | |          | |  status   |             |
|  |          |  |  Delete  | |          | |           |             |
|  +----------+  +----------+  +----------+  +----------+            |
|                                                                    |
|  Recent activity (narrative list of status transitions)            |
+----------------------------------------------------------------+
```

**Forms:** "Approve" → `post_approve` (POST). "Request changes" → collapsible `<details>` revealing a `textarea[name="feedback"]` (required) → `post_request_changes` (POST). "Publish" → `post_publish` (POST) — card shows "Will announce to Telegram on publish" beforehand. "Delete" → confirm-delete page.

**Search:** `GET` form (`action="{% url 'editor_dashboard' %}"`, `name="q"`), filters by title, preserves the `status` filter as a hidden field.

**HTMX:** same auto-refresh pattern as the author dashboard, targeting `#editor-dashboard-lists`.

## Post Editor (create/edit)

**Template:** `blog/post_form.html`
**Routes:** `/post/create/` (requires `blog.add_post`), `/post/<slug>/edit/` (login required + ownership/permission check in the view)
**Users/roles:** Any role with `blog.add_post` can create; editing is either "any post" (`blog.change_post` — admin/editor) or "own, unpublished post only" (author/contributor, enforced in `post_update`, not by a permission).

```text
+----------------------------------------------------------------+
| < Back                                    [ Status: draft ] (if editing) |
|                                                                    |
|  Create Post / Edit Post                                          |
|  +--------------------------------------------------------+       |
|  | Title:            [.....................................] |    |
|  | Featured image:   +-----------------------+                |    |
|  |                    |  Dropzone (click or    |  (JS: post-form.js|
|  |                    |  drag & drop, previews  |   syncs a hidden |
|  |                    |  the selected image)    |   real file input)|
|  |                    +-----------------------+                |    |
|  | Category:          [ Select v ]                              |   |
|  | Tags:               [ comma, separated, tags ]                 | |
|  | Content:            [ CKEditor rich-text toolbar + editing area ]||
|  | Excerpt:            [.................] (optional, auto-filled  ||
|  |                                           from content if blank)||
|  | SEO title:          [.................] (optional)              |
|  | SEO description:    [.................] (optional)              |
|  |                                                                  |
|  |  [ Cancel ]                                    [ Save ]          |
|  +--------------------------------------------------------+       |
+----------------------------------------------------------------+
```

**Form:** `method="POST" enctype="multipart/form-data" novalidate`, `{% csrf_token %}`. `PostForm` fields: `title`, `category`, `content`, `excerpt`, `featured_image`, `tags`, `seo_title`, `seo_description`.

**Validation:** `title` must be ≥5 characters (`clean_title`); `content` is server-side sanitized with `nh3.clean()` regardless of what CKEditor's client-side sanitization already did.

**Post-save routing:** a new post always goes to `author_dashboard`. An edit lands back on `editor_dashboard` if the editor has `blog.change_post`, else `author_dashboard`.

**Ownership rule (enforced in the view, not the template):** an author/contributor cannot edit someone else's post, and cannot edit their own post once it's `is_published=True` — both return an explicit 403 (`HttpResponseForbidden`), which is not specially styled in the UI (renders as Django's default 403 response unless a custom `403.html` exists — **not determinable**, no `403.html` template was found in `templates/`, only `404.html`/`500.html`).

## Delete confirmation

**Template:** `blog/post_confirm_delete.html`
**Route:** `/post/<slug>/delete/` (requires `blog.delete_post` permission)

```text
+----------------------------------------------------+
| < Back (falls back to the post itself)               |
|                                                      |
|  Delete "{{ post.title }}"?                           |
|  This action cannot be undone.                        |
|                                                      |
|  [ Cancel ]                          [ Yes, delete ]   |
+----------------------------------------------------+
```

Simple confirm form, `POST`, CSRF-protected. On success, redirects to `editor_dashboard` (if the deleter has `blog.change_post`) or `dashboard` otherwise.
