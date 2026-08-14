# Database Design

Football Hub persists data in a single **PostgreSQL** database via the Django ORM. There is no read replica, caching layer in front of the database, or secondary datastore for application data — Redis (when configured) is used exclusively as the Django Channels layer for the live-chat feature, not for caching or persistence of model data. See [system-architecture.md](../architecture/system-architecture.md) for how the database fits into the overall system.

## Contents

- [erd.md](erd.md) — Entity-Relationship Diagram (Mermaid) covering every project-defined model, plus a summary of third-party tables that exist in the schema but aren't defined in this codebase.
- [schema.md](schema.md) — Full field-by-field table definitions, grouped by Django app, with the migration history that produced them.
- [relationships.md](relationships.md) — Foreign key `on_delete` behavior, many-to-many relationships, unique constraints, and the delete-cascade risks they create.
- [data-dictionary.md](data-dictionary.md) — Flat reference of every field across every model, with defaults and behavioral notes.

## Apps and their models

| Django app | Models |
|---|---|
| `users` | `CustomUser` (custom `AUTH_USER_MODEL`), `LoginAttempt` |
| `blog` | `Category`, `Post`, `Comment`, `Bookmark`, `Notification` |
| `chat` | `ChatSession`, `ChatMessage` |
| `pages` | `Feedback`, `Subscriber` |

9 project-defined models total. `config` (the Django project package) defines no models of its own.

## Scope note

This documentation covers only what the model classes and migrations actually define. There is no `League`, `Match`, `Fixture`, `Team`, or `Standing` model anywhere in the codebase — the navbar's "Champions League", "La Liga", "Premier League", "Serie A" links are `Category` rows (editorial content taxonomy), not live football data. See [wireframes/home-page.md](../wireframes/home-page.md) for how this is presented in the UI.
