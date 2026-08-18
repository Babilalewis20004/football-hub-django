# Data Dictionary

Flat, field-by-field reference across all project-defined models. For type/constraint detail see [schema.md](schema.md); for FK/M2M behavior see [relationships.md](relationships.md).

## `users.CustomUser`

| Field | Type | Default | Description |
|---|---|---|---|
| `username` | CharField | — | Inherited from `AbstractUser`; login identifier |
| `email` | EmailField | `""` | Inherited |
| `password` | CharField | — | Inherited; stored as a salted hash via Django's password hashing (PBKDF2 by default) |
| `bio` | TextField | `None`/blank | Free-text profile bio |
| `avatar` | ImageField | `avatars/default.jpg` | Profile picture, stored under `MEDIA_ROOT/avatars/` |
| `favorite_team` | CharField | `""` | Free-text; not linked to any structured team/league data |
| `role` | CharField | `reader` | One of `admin`, `editor`, `author`, `contributor`, `reader` — the application-level role, kept in sync with Django Group membership by `users.signals.sync_role_group` (see [security-architecture.md](../architecture/security-architecture.md)). Defaults to `reader` for every new account; a public user can never set it directly (`RegisterForm` has no `role` field). |

## `users.LoginAttempt`

| Field | Type | Default | Description |
|---|---|---|---|
| `username` | CharField | — | Raw submitted login username (may not correspond to a real account) |
| `ip_address` | GenericIPAddressField | `None` | Derived from `X-Forwarded-For` (first entry) or `REMOTE_ADDR` |
| `successful` | BooleanField | `False` | Whether this attempt authenticated successfully |
| `reason` | CharField | `""` | Machine-readable failure/success reason code (see [schema.md](schema.md) for the full list) |
| `timestamp` | DateTimeField | now | When the attempt was recorded |

## `blog.Category`

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | CharField | — | Display name (e.g. "Premier League", "Transfers") — these are editorial content buckets, not live league/competition data |
| `slug` | SlugField | auto-derived | URL segment, e.g. `/category/premier-league/` |

## `blog.Post`

| Field | Type | Default | Description |
|---|---|---|---|
| `title` | CharField | — | Post headline; minimum 5 characters enforced by `PostForm.clean_title` |
| `slug` | SlugField | auto-derived | Permalink segment; recomputed only when the title changes |
| `author` | FK(CustomUser) | — | Set to `request.user` on creation; not editable via the form |
| `category` | FK(Category) | — | Selected by the author/editor |
| `content` | RichTextField | — | CKEditor 4 HTML content; sanitized server-side with `nh3.clean()` |
| `featured_image` | ImageField | `None` | Stored under `MEDIA_ROOT/posts/` |
| `excerpt` | TextField | auto-derived | Auto-filled from stripped `content[:200]` if left blank |
| `tags` | TaggableManager | `[]` | Free-form tags via django-taggit |
| `views` | PositiveIntegerField | `0` | Incremented once per `post_detail` request (no dedup/throttling) |
| `likes` | M2M(CustomUser) | `[]` | Toggled via the like button |
| `created_at` | DateTimeField | now | Set once, at creation |
| `updated_at` | DateTimeField | now | Updated on every save |
| `is_published` | BooleanField | `False` | Public-visibility flag, set by `post_publish` |
| `is_approved` | BooleanField | `False` | Editorial-approval flag, set by `post_approve`/`post_publish` |
| `status` | CharField | `draft` | Workflow state — see [data-flow.md](../architecture/data-flow.md) for the full transition diagram |
| `editor_feedback` | TextField | `""` | Editor's free-text note when requesting changes |
| `status_changed_at` | DateTimeField | `None` | Timestamp of the most recent `status` transition |
| `published_at` | DateTimeField | `None` | Set when `post_publish` runs |
| `telegram_announced_at` | DateTimeField | `None` | Set only if the Telegram announcement send succeeded |
| `seo_title` | CharField | `""` | Optional override for `<title>`/OG title |
| `seo_description` | TextField | `""` | Optional override for meta description/OG description |

## `blog.Comment`

| Field | Type | Default | Description |
|---|---|---|---|
| `post` | FK(Post) | — | Parent post |
| `user` | FK(CustomUser) | — | Comment author; anonymous users are redirected to login before this is ever set |
| `parent` | FK(Comment) | `None` | Self-referential; models one level of reply-threading (schema-level only — no UI writes a non-null `parent`) |
| `content` | TextField | — | Comment body, no length cap and no server-side HTML sanitization applied (rendered as plain text in the template, not `\|safe`) |
| `created_at` | DateTimeField | now | |

## `blog.Bookmark`

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | FK(CustomUser) | — | |
| `post` | FK(Post) | — | |
| `created_at` | DateTimeField | now | |

## `blog.Notification`

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | FK(CustomUser) | — | Recipient |
| `message` | CharField | — | Free-text notification body, e.g. `"Your post '…' was approved and is pending publication."` |
| `created_at` | DateTimeField | now | |
| `is_read` | BooleanField | `False` | Marked read in bulk when the author/editor dashboard is opened |

## `chat.ChatSession`

| Field | Type | Default | Description |
|---|---|---|---|
| `visitor` | FK(CustomUser) | `None` | Set only if the visitor was logged in when the chat started |
| `visitor_name` | CharField | — | Display name shown to staff; either the account's name or a free-text name entered anonymously |
| `session_key` | CharField | — | Django session key, used to let an anonymous visitor reconnect after a page reload |
| `agent` | FK(CustomUser) | `None` | Assigned to the first staff member (`admin`/`editor`) who opens the `ChatConsumer` WebSocket for this session |
| `status` | CharField | `open` | `open` or `closed` |
| `created_at` | DateTimeField | now | |
| `updated_at` | DateTimeField | now | Bumped on every new message and status change |

## `chat.ChatMessage`

| Field | Type | Default | Description |
|---|---|---|---|
| `session` | FK(ChatSession) | — | |
| `sender` | FK(CustomUser) | `None` | Null for anonymous-visitor messages and system messages (e.g. "This chat has been closed.") |
| `sender_name` | CharField | — | Denormalized display name, preserved even if `sender` is later deleted |
| `is_staff_message` | BooleanField | `False` | Distinguishes visitor vs. staff messages for styling and unread-count logic |
| `body` | TextField | — | Message text |
| `created_at` | DateTimeField | now | |
| `is_read` | BooleanField | `False` | Only meaningfully tracked for non-staff (visitor) messages; drives `chat.services.get_unread_count` |

## `pages.Feedback`

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | FK(CustomUser) | `None` | Populated automatically if the submitter is authenticated |
| `name` | CharField | `""` | Falls back to the user's full name/username if authenticated and left blank |
| `email` | EmailField | `""` | Falls back to the user's account email if authenticated and left blank |
| `rating` | PositiveSmallIntegerField | — | 1–5 star rating, required |
| `comment` | TextField | `""` | Optional free-text |
| `created_at` | DateTimeField | now | |

## `pages.Subscriber`

| Field | Type | Default | Description |
|---|---|---|---|
| `email` | EmailField | — | Unique; newsletter signup, no confirmation/double opt-in flow exists |
| `created_at` | DateTimeField | now | |
