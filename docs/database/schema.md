# Database Schema

Engine: **PostgreSQL** only (`config/settings.py` → `DATABASES.default.ENGINE = 'django.db.backends.postgresql'`, config supplied via `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` env vars, read with `python-decouple`). SQLite is not used anywhere — `db.sqlite3` is gitignored defensively but no code path creates or reads one; tests run against the same `postgresql` engine defined in settings.

All tables below are current as of migrations: `blog` 0001–0015, `users` 0001–0004, `chat` 0001, `pages` 0001–0002.

## `users` app

### `CustomUser` (table: `users_customuser`)
Extends `django.contrib.auth.models.AbstractUser` (`AUTH_USER_MODEL = 'users.CustomUser'`), so it also carries every standard Django auth field (`username`, `first_name`, `last_name`, `email`, `password`, `is_staff`, `is_superuser`, `is_active`, `date_joined`, `last_login`).

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `bio` | TextField | blank, null | |
| `avatar` | ImageField | upload_to `avatars/`, default `avatars/default.jpg`, blank | |
| `favorite_team` | CharField(100) | blank | Free-text, not a FK to any team model — no `Team` model exists in this project |
| `role` | CharField(20) | choices: `admin`, `editor`, `author`, `reader`; default `reader` | Drives permission checks, 2FA requirement, single-session enforcement (see [relationships.md](relationships.md)) |

### `LoginAttempt` (table: `users_loginattempt`)
Migration `0003_loginattempt`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `username` | CharField(150) | db_index | **Not a ForeignKey** — stores the raw submitted username string, including attempts against usernames with no matching account, deliberately (see `users/security.py` docstring — avoids turning lockout into a username-enumeration oracle) |
| `ip_address` | GenericIPAddressField | null, blank | |
| `successful` | BooleanField | default `False` | |
| `reason` | CharField(32) | blank | e.g. `locked_out`, `captcha_failed`, `invalid_role`, `invalid_credentials`, `role_mismatch`, `admin_locked_out`, `admin_captcha_failed`, `admin_invalid_login`, `admin_success` |
| `timestamp` | DateTimeField | auto_now_add, db_index | |

`Meta.ordering = ["-timestamp"]`.

## `blog` app

### `Category` (table: `blog_category`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `name` | CharField(100) | unique | |
| `slug` | SlugField | unique, blank, db_index | Auto-generated from `name` in `save()` if not set, with numeric-suffix collision handling |

`Meta.ordering = ["name"]`; `verbose_name_plural = "Categories"`.

### `Post` (table: `blog_post`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `title` | CharField(255) | | |
| `slug` | SlugField | unique, blank, db_index | Auto-generated/re-generated in `save()` only when the title changes or on creation (see code comment — prevents permalink drift) |
| `author_id` | FK → `CustomUser` | on_delete=CASCADE, db_index | related_name `posts` |
| `category_id` | FK → `Category` | on_delete=CASCADE, db_index | related_name `posts` |
| `content` | RichTextField (django-ckeditor) | | Server-side sanitized via `nh3.clean()` in `PostForm.clean_content` before save |
| `featured_image` | ImageField | upload_to `posts/`, blank, null | |
| `excerpt` | TextField | blank | Auto-filled from stripped `content[:200]` in `save()` if left blank |
| `tags` | TaggableManager (django-taggit) | blank | M2M through `taggit.TaggedItem` |
| `views` | PositiveIntegerField | default 0, db_index | Incremented atomically (`F("views") + 1`) on each `post_detail` view |
| `likes` | ManyToManyField → `CustomUser` | blank | related_name `liked_posts` |
| `created_at` | DateTimeField | auto_now_add, db_index | |
| `updated_at` | DateTimeField | auto_now | |
| `is_published` | BooleanField | default `False`, db_index | |
| `is_approved` | BooleanField | default `False`, db_index | |
| `status` | CharField(20) | choices: `draft`, `in_review`, `needs_changes`, `approved`, `published`; default `draft`, db_index | Editorial workflow state (see [data-flow.md](../architecture/data-flow.md)) |
| `editor_feedback` | TextField | blank, default `""` | Set by `post_request_changes` |
| `status_changed_at` | DateTimeField | null, blank | Set manually on every status transition, not `auto_now` (an unrelated content edit must not bump it) |
| `published_at` | DateTimeField | null, blank | Set on `post_publish` |
| `telegram_announced_at` | DateTimeField | null, blank | Set only if the Telegram announcement actually sent |
| `seo_title` | CharField(255) | blank | |
| `seo_description` | TextField | blank | |

`Meta.ordering = ["-created_at"]`. Indexes: `views`, `author`, `is_published` (explicit `models.Index` entries, in addition to the `db_index=True` columns above). Custom permissions: `can_publish_post`, `can_feature_post`, `can_approve_post` (in addition to Django's default `add_post`/`change_post`/`delete_post`/`view_post`).

### `Comment` (table: `blog_comment`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `post_id` | FK → `Post` | on_delete=CASCADE | related_name `comments` |
| `user_id` | FK → `CustomUser` | on_delete=CASCADE | related_name `comments` |
| `parent_id` | FK → `Comment` (self) | on_delete=CASCADE, null, blank, db_index | related_name `replies` — one level of threading is modeled, though no template currently renders reply UI (see wireframes) |
| `content` | TextField | | |
| `created_at` | DateTimeField | auto_now_add, db_index | |

`Meta.ordering = ["created_at"]`.

### `Bookmark` (table: `blog_bookmark`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `user_id` | FK → `CustomUser` | on_delete=CASCADE, db_index | related_name `bookmarks` |
| `post_id` | FK → `Post` | on_delete=CASCADE, db_index | related_name `bookmarked_by` |
| `created_at` | DateTimeField | auto_now_add | |

`UniqueConstraint(fields=["user", "post"], name="unique_bookmark")` — a user can bookmark a given post only once.

### `Notification` (table: `blog_notification`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `user_id` | FK → `CustomUser` | on_delete=CASCADE | No `related_name` set (default reverse accessor `notification_set`) |
| `message` | CharField(255) | | |
| `created_at` | DateTimeField | auto_now_add | |
| `is_read` | BooleanField | default `False` | |

No `Meta` class — default ordering (insertion order / PK order).

## `chat` app

### `ChatSession` (table: `chat_chatsession`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `visitor_id` | FK → `CustomUser` | on_delete=SET_NULL, null, blank | related_name `chat_sessions`; null for anonymous visitors |
| `visitor_name` | CharField(100) | | Display name, always set even for anonymous visitors |
| `session_key` | CharField(40) | db_index | Django session key, used to reconnect anonymous visitors across page reloads |
| `agent_id` | FK → `CustomUser` | on_delete=SET_NULL, null, blank | related_name `assigned_chats` — set to the first staff member who opens the session |
| `status` | CharField(10) | choices: `open`, `closed`; default `open`, db_index | |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now, db_index | |

`Meta.ordering = ["-updated_at"]`.

### `ChatMessage` (table: `chat_chatmessage`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `session_id` | FK → `ChatSession` | on_delete=CASCADE | related_name `messages` |
| `sender_id` | FK → `CustomUser` | on_delete=SET_NULL, null, blank | Null for anonymous-visitor or system messages |
| `sender_name` | CharField(100) | | |
| `is_staff_message` | BooleanField | default `False` | |
| `body` | TextField | | |
| `created_at` | DateTimeField | auto_now_add, db_index | |
| `is_read` | BooleanField | default `False` | Tracked for visitor-sent messages only; drives the unread-count badge |

`Meta.ordering = ["created_at"]`.

## `pages` app

### `Feedback` (table: `pages_feedback`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `user_id` | FK → `CustomUser` | on_delete=SET_NULL, null, blank | related_name `feedback_entries` |
| `name` | CharField(150) | blank | |
| `email` | EmailField | blank | |
| `rating` | PositiveSmallIntegerField | choices 1–5 | |
| `comment` | TextField | blank | |
| `created_at` | DateTimeField | auto_now_add | |

`Meta.ordering = ["-created_at"]`; `verbose_name_plural = "Feedback"`.

### `Subscriber` (table: `pages_subscriber`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `email` | EmailField | unique | |
| `created_at` | DateTimeField | auto_now_add | |

`Meta.ordering = ["-created_at"]`.

## Migration history (for traceability)

| App | Migrations |
|---|---|
| `blog` | `0001_initial` → `0002_post_views_bookmark` → `0003_comment_parent` → `0004_post_seo_description_post_seo_title` → `0005_post_likes` → `0006_post_excerpt_alter_post_category_and_more` → `0007_alter_category_options_alter_bookmark_post_and_more` → `0008_alter_bookmark_unique_together_and_more` → `0009_post_bookmarks` → `0010_alter_post_options_and_more` → `0011_alter_post_options_post_blog_post_views_9a8dee_idx_and_more` → `0012_alter_post_options` → `0013_post_is_approved_post_status_alter_post_is_published` → `0014_notification` → `0015_post_editor_feedback_post_published_at_and_more` |
| `users` | `0001_initial` → `0002_customuser_role` → `0003_loginattempt` → `0004_alter_customuser_avatar` |
| `chat` | `0001_initial` |
| `pages` | `0001_initial` → `0002_subscriber` |

This confirms the editorial workflow (`status`, `editor_feedback`, `published_at`, `telegram_announced_at`), 2FA/lockout audit trail, and Telegram integration were all added incrementally after the apps' initial creation — see `git log` for exact dates if needed (not duplicated here per the "don't restate git history" guidance).
