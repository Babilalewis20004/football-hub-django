# Home Page

**Template:** `templates/blog/home.html` (extends `base.html`)
**Route:** `/` (`blog.views.home.home`, name=`home`)
**Context source:** `blog.services.homepage.get_homepage_context()`
**Users/roles:** Public — identical for anonymous and authenticated users (only the masthead/navbar auth state differs, per the global layout).

## Wireframe

```text
+----------------------------------------------------------------------+
| MASTHEAD / NAVBAR (see wireframes/README.md — global layout)         |
+----------------------------------------------------------------------+
|                         #swap-container                              |
|  +------------------------------------------------------------+      |
|  |  HERO (components/hero.html)                                |     |
|  |  +----------------------+  +--------+  +--------+           |     |
|  |  | [Featured image]     |  | side 1 |  | side 2 |            |     |
|  |  | Category kicker      |  +--------+  +--------+           |     |
|  |  | hero_post.title      |  (hero_side_posts, up to 2)        |     |
|  |  | excerpt / author/time|                                   |     |
|  |  +----------------------+                                   |     |
|  +------------------------------------------------------------+      |
|                                                                        |
|  EDITOR'S PICKS (components/editors_picks.html) - 3 col grid          |
|  [ pick 1 ]        [ pick 2 ]        [ pick 3 ]                       |
|  (top 3 by views, excluding hero posts)                               |
|                                                                        |
|  CATEGORY STRIP (components/category_strip.html)                      |
|  ( Premier League 12 )( Serie A 8 )( Transfers 5 )( ... )             |
|  pill-style links to /category/<slug>/, showing published post count  |
|                                                                        |
|  LATEST (components/latest_list.html) - numbered list, up to 6        |
|  1. [thumb] Category tag | Title | author, time                       |
|  2. [thumb] ...                                                       |
|                                                                        |
|  CTA BAND (components/cta_band.html)                                  |
|  "Never miss a post" ......................... [ Get notified ]      |
|  (button is a dead href="#" link — NOT wired to /subscribe/)          |
+----------------------------------------------------------------------+
| FOOTER (see wireframes/README.md — global layout)                    |
+----------------------------------------------------------------------+
```

## Components and data

| Section | Component | Context variable | Logic |
|---|---|---|---|
| Hero | `hero.html` | `hero_post`, `hero_side_posts` | Most recent published post as hero; next 2 most recent as side posts |
| Editor's picks | `editors_picks.html` | `editors_picks` | Top 3 by `views` (descending), excluding posts already used above |
| Category strip | `category_strip.html` | `categories` | All `Category` rows, annotated with a count of published posts, ordered by count descending |
| Latest | `latest_list.html` | `latest_posts` | Next 6 most recent published posts, excluding posts already used above |
| CTA band | `cta_band.html` | (static) | No dynamic data; the "Get notified" button is not functional |

## Navigation

- Logo → home (self)
- Every post card/title/thumbnail → `post_detail` for that post
- Category pills → `category_posts`
- "Editor's picks" category tags → `category_posts`

## Forms

None on this page directly (search is in the masthead, present globally).

## Interactions

- No HTMX or AJAX on this page — fully static server-rendered content per request.
- The `#swap-container` wrapper div has no JS or HTMX behavior attached to it anywhere in the codebase — its `id` suggests it was designed for a dynamic swap (e.g. a "load more" or filter-refresh feature) that was never implemented.

## Error/empty states

Not determinable from the template alone whether an empty-database state (no published posts) has a designed empty state — `hero_post` would be `None` and `hero.html`'s rendering in that case was not verified line-by-line during this audit; flagged as **not fully verified** rather than asserted.

## Responsive behaviour

Bootstrap 5 grid classes are used throughout (per the frontend inventory), so the layout reflows via Bootstrap's standard breakpoints. No custom JS-driven responsive behavior (e.g. a hamburger menu script) beyond Bootstrap's own collapse component was found specific to this page.
