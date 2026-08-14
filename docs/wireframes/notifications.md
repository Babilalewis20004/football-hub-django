# Notifications

There is no standalone notifications page, dropdown, or feed — this is an **in-app editorial-workflow notification list embedded in the author and editor dashboards only**. This document exists to record scope accurately, since "Notifications" could otherwise be assumed to be a site-wide feature (like the chat unread badge, which is separate — see [support-inbox.md](support-inbox.md)).

## What exists

**Model:** `blog.Notification` (`user`, `message`, `created_at`, `is_read`) — see [database/data-dictionary.md](../database/data-dictionary.md).

**Created by** (`blog/views/posts.py`), one row per event, always addressed to `post.author`:
- Post created → "Your post '…' is saved as a draft."
- Submitted for review → "Your post '…' was submitted for review."
- Changes requested → "Changes requested on '…': <feedback>" (or without feedback text if none was given)
- Approved → "Your post '…' was approved and is pending publication."
- Published → "Your post '…' is now published!"

**Read/consumed:** both `author_dashboard` and `editor_dashboard` views fetch the current user's unread `Notification` rows on page load, render them, and immediately mark them as read (`Notification.objects.filter(id__in=[...]).update(is_read=True)`) — so a notification is only ever seen once, the next time its recipient opens their dashboard.

## Wireframe (embedded panel, as seen in author-dashboard.md / blog.md)

```text
Notifications (sidebar on author_dashboard.html; alert box atop editor_dashboard.html)
+--------------------------------------------------------+
| "Your post 'Transfer Deadline Day Recap' was approved   |
|  and is pending publication."                            |
| "Changes requested on 'Preview: Matchday 12':            |
|  Please add a source for the injury claim."               |
+--------------------------------------------------------+
```

No mark-as-read button, no dismiss action, no notification icon/dropdown in the navbar — the entire lifecycle is "created on a workflow event → shown once on next dashboard visit → marked read automatically."

## What does not exist

- No notification bell/dropdown in the navbar or masthead (that UI slot is used exclusively by the unrelated chat unread-count badge — `#support-unread-badge`, staff-only, a completely separate system built on `ChatMessage.is_read`, not `Notification`).
- No notifications for readers, or for any event outside the editorial workflow (no "someone commented on your post," "someone liked your post," etc.).
- No email or push delivery of notifications — everything is in-app only, and only reaches the dashboard views.
- No notification history/archive view — once marked read, a notification's only remaining trace is the raw `Notification` row in the database (still visible via Django admin, not through any user-facing page).
