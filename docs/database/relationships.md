# Relationships & Referential Behavior

## Foreign key summary

| From | To | On delete | related_name | Nullable | Notes |
|---|---|---|---|---|---|
| `Post.author` | `CustomUser` | CASCADE | `posts` | No | Deleting a user deletes all their posts |
| `Post.category` | `Category` | CASCADE | `posts` | No | Deleting a category deletes all posts in it — **destructive**, see Issues below |
| `Comment.post` | `Post` | CASCADE | `comments` | No | |
| `Comment.user` | `CustomUser` | CASCADE | `comments` | No | Deleting a user deletes all their comments |
| `Comment.parent` | `Comment` (self) | CASCADE | `replies` | Yes | One level of reply-threading is modeled at the schema level; no UI currently exposes replying |
| `Bookmark.user` | `CustomUser` | CASCADE | `bookmarks` | No | |
| `Bookmark.post` | `Post` | CASCADE | `bookmarked_by` | No | Unique together with `user` |
| `Notification.user` | `CustomUser` | CASCADE | (default `notification_set`) | No | |
| `ChatSession.visitor` | `CustomUser` | **SET_NULL** | `chat_sessions` | Yes | A deleted user's past chat sessions survive, becoming anonymous |
| `ChatSession.agent` | `CustomUser` | **SET_NULL** | `assigned_chats` | Yes | A deleted staff user's assigned chats survive, becoming unassigned |
| `ChatMessage.session` | `ChatSession` | CASCADE | `messages` | No | Deleting a session deletes its full transcript |
| `ChatMessage.sender` | `CustomUser` | **SET_NULL** | (default) | Yes | Message text/sender_name persists even if the sending user is deleted |
| `Feedback.user` | `CustomUser` | **SET_NULL** | `feedback_entries` | Yes | Feedback survives account deletion |
| `LoginAttempt.username` | *(none — plain string)* | n/a | n/a | n/a | Deliberately not a FK; see [schema.md](schema.md) |

## Many-to-many relationships

| Relationship | Through | Notes |
|---|---|---|
| `Post.likes` ↔ `CustomUser` | Django-managed implicit M2M table | related_name `liked_posts`; toggled by `blog.views.interactions.like_post` |
| `Post.tags` ↔ `taggit.Tag` | `taggit.TaggedItem` (generic, content-type based) | Managed entirely by `django-taggit`; not a project-defined join table |

## Unique constraints

| Model | Constraint | Purpose |
|---|---|---|
| `Category` | `name` unique, `slug` unique | |
| `Post` | `slug` unique | Collision-avoided in `save()` with a numeric suffix loop |
| `Bookmark` | `UniqueConstraint(user, post)` named `unique_bookmark` | Prevents duplicate bookmarks; the view (`bookmark_post`) uses `get_or_create` + delete-if-exists as a toggle, so this constraint is a backstop, not the primary mechanism |
| `Subscriber` | `email` unique | `subscribe_view` uses `get_or_create` on this to avoid duplicate newsletter signups |

## Delete-behavior implications (traced from the models, not assumed)

- **Deleting a `Category` cascades to delete every `Post` in it.** There is no `SET_NULL`/`PROTECT` fallback category. This is a real risk if an editor deletes a category from Django admin while it still has published posts attached — flagged in [Issues discovered](../../README.md) at the end of the audit.
- **Deleting a `CustomUser` who authored posts deletes all of those posts** (`Post.author` is CASCADE, not SET_NULL). Combined with `blog.views.users.delete_account` (self-service account deletion, see `users/views.py`), an author who deletes their own account also silently deletes every post they've ever published — including live, publicly-visible content — with no confirmation step calling this out specifically (the deletion confirmation only asks for a password).
- **Chat and feedback data intentionally survive user deletion** (`SET_NULL`), preserving support-history and feedback records for site operators even after an account is gone — this is the one place the schema explicitly favors data retention over cascading cleanup.
- **`LoginAttempt` rows are never automatically pruned.** The table grows indefinitely; lockout/CAPTCHA logic only ever reads the most recent `LOGIN_MAX_FAILED_ATTEMPTS` rows per username, so correctness isn't affected, but there is no retention policy or cleanup job in the codebase.

## Role-derived relationships (not FKs, but structurally important)

`CustomUser.role` (a plain `CharField`, not a relation) drives several cross-cutting behaviors documented in [security-architecture.md](../architecture/security-architecture.md):

- `users.twofactor.TWO_FACTOR_REQUIRED_ROLES = {"admin", "editor", "author"}` — which roles must complete TOTP enrollment.
- `users.signals.SINGLE_SESSION_ROLES = {"admin", "editor", "author"}` — which roles get their other sessions evicted on a fresh login.
- `chat.models.SUPPORT_ROLES = ('admin', 'editor')` — which roles can act as live-chat support agents (`chat.permissions.is_support_agent`).
- `users.views.PUBLIC_LOGIN_ROLES = ("editor", "author", "contributor", "reader")` — which roles are selectable on the public login form (`admin` must use `/admin/`).

These are **application-level policy sets**, independent of the separate Django `Group`/`Permission` system created by `blog/management/commands/setup_roles.py` (see [security-architecture.md](../architecture/security-architecture.md) for how the two systems relate).
