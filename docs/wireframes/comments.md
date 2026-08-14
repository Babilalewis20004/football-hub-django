# Comments

There is no standalone comments page or view — commenting is embedded entirely within [post-detail.md](post-detail.md) (`#ig-comments` section of `blog/post_detail.html`). This document exists to satisfy the requested documentation structure and to record what does and doesn't exist for this feature, since it's easy to assume more exists than does.

## What exists

| Capability | Exists? | Where |
|---|---|---|
| View comments on a post | Yes | `post_detail.html`, `#ig-comments`, ordered oldest-first (`Comment.Meta.ordering = ["created_at"]`) |
| Add a comment | Yes | Same page, `CommentForm`, authenticated users only |
| Reply to a comment (threading) | **Schema only, no UI** | `Comment.parent` self-FK exists in the model (`blog/models/comment.py`) and is queryable via `replies`, but no template renders a reply control or nested comment display |
| Edit a comment | **No** | No edit view, form, or UI exists anywhere |
| Delete a comment | **Dead code, not reachable** | `blog/views/comments.py: delete_comment` exists and correctly checks `comment.user == request.user` before deleting, but it is not registered in `blog/urls.py` and no template links to it — there is currently no way to reach this view through the running application |
| Moderate/report comments | **No** | No moderation queue, flagging mechanism, or admin-side comment moderation UI beyond the default Django admin's generic model list (`blog/admin.py` registers `Comment` with `admin.site.register`, no custom `ModelAdmin`) |
| Comment content sanitization | Relies on template auto-escaping | Unlike `Post.content`, `Comment.content` is not run through `nh3.clean()` — it's rendered without `\|safe`, so Django's default template auto-escaping is the only protection against injected HTML/script content |

## Wireframe (embedded section, repeated from post-detail.md for completeness)

```text
#ig-comments
+--------------------------------------------------------+
| [avatar] username   "comment text"           Xh ago      |
| [avatar] username   "comment text"           Xh ago      |
+--------------------------------------------------------+

{% if user.is_authenticated %}
  [ Add a comment...                    ] [ Post ]
  (submit disabled client-side until non-empty)
{% else %}
  "Login to leave a comment" -> /login/?next=/post/<slug>/
{% endif %}
```

## Form

`CommentForm` (`blog/forms.py`) — single `content` `Textarea` field. `method="POST"`, posts back to the same `post_detail` URL as the page it's embedded in. On success: `blog.services.comments.create_comment()` sets `user`/`post` server-side and saves, then redirects back to `post_detail` (POST-redirect-GET).

## Recommendation flagged for the project owner (not a documentation error — a real functional gap)

Since `delete_comment` already contains correct, working ownership-check logic, wiring it into `blog/urls.py` (and adding a delete affordance to `post_detail.html` for the comment's own author) would be a small, low-risk change to close this gap — noted here rather than silently treated as "no delete feature was ever planned."
