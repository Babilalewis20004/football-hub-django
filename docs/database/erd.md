# Entity-Relationship Diagram

Source of truth: the model classes in `blog/models/*.py`, `users/models.py`, `chat/models.py`, `pages/models.py`, plus the Django/third-party tables installed via `INSTALLED_APPS` (`django.contrib.auth`, `django.contrib.sessions`, `django.contrib.contenttypes`, `taggit`, `django_otp`, `captcha`).

All application models use `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` (`config/settings.py`), so every `id` primary key is a `BigAutoField` unless noted otherwise.

## Application models

```mermaid
erDiagram
    CUSTOMUSER ||--o{ POST : "authors"
    CUSTOMUSER ||--o{ COMMENT : "writes"
    CUSTOMUSER ||--o{ BOOKMARK : "saves"
    CUSTOMUSER ||--o{ NOTIFICATION : "receives"
    CUSTOMUSER }o--o{ POST : "likes"
    CUSTOMUSER ||--o{ CHATSESSION : "visitor (nullable)"
    CUSTOMUSER ||--o{ CHATSESSION : "agent (nullable)"
    CUSTOMUSER ||--o{ CHATMESSAGE : "sender (nullable)"
    CUSTOMUSER ||--o{ FEEDBACK : "submitter (nullable)"
    CUSTOMUSER ||--o{ LOGINATTEMPT : "audit trail (by username, not FK)"

    CATEGORY ||--o{ POST : "classifies"
    POST ||--o{ COMMENT : "has"
    COMMENT ||--o{ COMMENT : "replies (self-FK)"
    POST ||--o{ BOOKMARK : "bookmarked as"
    POST }o--o{ TAG : "tagged with (django-taggit)"

    CHATSESSION ||--o{ CHATMESSAGE : "contains"

    CUSTOMUSER {
        bigint id PK
        string username UK
        string email
        string password
        string bio
        string avatar
        string favorite_team
        string role "admin|editor|author|contributor|reader"
        bool is_staff
        bool is_superuser
        bool is_active
        datetime date_joined
    }

    LOGINATTEMPT {
        bigint id PK
        string username "not a FK - raw submitted value"
        string ip_address
        bool successful
        string reason
        datetime timestamp
    }

    CATEGORY {
        bigint id PK
        string name UK
        string slug UK
    }

    POST {
        bigint id PK
        string title
        string slug UK
        bigint author_id FK
        bigint category_id FK
        text content "RichTextField (CKEditor)"
        string featured_image
        text excerpt
        int views
        datetime created_at
        datetime updated_at
        bool is_published
        bool is_approved
        string status "draft|in_review|needs_changes|approved|published"
        text editor_feedback
        datetime status_changed_at
        datetime published_at
        datetime telegram_announced_at
        string seo_title
        text seo_description
    }

    COMMENT {
        bigint id PK
        bigint post_id FK
        bigint user_id FK
        bigint parent_id FK "nullable, self-referential"
        text content
        datetime created_at
    }

    BOOKMARK {
        bigint id PK
        bigint user_id FK
        bigint post_id FK
        datetime created_at
    }

    NOTIFICATION {
        bigint id PK
        bigint user_id FK
        string message
        datetime created_at
        bool is_read
    }

    CHATSESSION {
        bigint id PK
        bigint visitor_id FK "nullable"
        string visitor_name
        string session_key
        bigint agent_id FK "nullable"
        string status "open|closed"
        datetime created_at
        datetime updated_at
    }

    CHATMESSAGE {
        bigint id PK
        bigint session_id FK
        bigint sender_id FK "nullable"
        string sender_name
        bool is_staff_message
        text body
        datetime created_at
        bool is_read
    }

    FEEDBACK {
        bigint id PK
        bigint user_id FK "nullable"
        string name
        string email
        smallint rating "1-5"
        text comment
        datetime created_at
    }

    TAG {
        bigint id PK
        string name
        string slug
    }
```

## Supporting third-party tables (not application-defined, but part of the live schema)

These are created by installed apps and are used by the application, but their models live outside this codebase:

| Table (approx.) | Provided by | Used for |
|---|---|---|
| `auth_group`, `auth_permission`, `*_groups`, `*_user_permissions` | `django.contrib.auth` | Django Groups/Permissions — see [Roles created by `setup_roles`](#) in `security-architecture.md`. |
| `django_session` | `django.contrib.sessions` | Server-side session store (DB-backed). Decoded manually by `users/signals.py` to enforce single-session-per-privileged-user. |
| `django_content_type` | `django.contrib.contenttypes` | Backs the permission system and `setup_roles`'s `ContentType.objects.get(app_label="blog", model="post")` lookup. |
| `taggit_tag`, `taggit_taggeditem` | `django-taggit` | `Post.tags` (`TaggableManager`) — a generic, reusable many-to-many tagging system. |
| `otp_totp_totpdevice` | `django-otp` (`otp_totp`) | TOTP 2FA devices (`users/twofactor.py`). |
| `otp_static_staticdevice`, `otp_static_statictoken` | `django-otp` (`otp_static`) | One-time recovery codes for 2FA. |
| `captcha_captchastore` | `django-simple-captcha` | Generated CAPTCHA challenge/answer pairs (login form, registration form). |

Not determinable from the current codebase: exact column-level DDL for these third-party tables (they are defined in their respective packages, not in this project's migrations).

See [schema.md](schema.md) for field-level detail, [relationships.md](relationships.md) for FK/M2M behavior, and [data-dictionary.md](data-dictionary.md) for a flat field reference.
