# Support Inbox (Staff Chat Management)

**Users/roles:** `admin`, `editor` only (`chat.permissions.is_support_agent` / `support_agent_required` decorator — `chat.models.SUPPORT_ROLES = ('admin', 'editor')`). `author`/`reader` accounts get a 403 if they navigate here directly.

## Support Inbox

**Template:** `templates/chat/support_inbox.html`
**JS:** `static/js/support_inbox.js`
**Route:** `/chat/support/` (`chat.views.support_inbox`, name=`support_inbox`)

```text
+----------------------------------------------------------------+
| MASTHEAD (badge: Support Inbox N)  / NAVBAR                      |
| (note: chat widget bubble is NOT rendered on this page)          |
+----------------------------------------------------------------+
| < Back                                                            |
|                                                                    |
|  Support Inbox                                                    |
|  #support-session-list                                            |
|  +--------------------------------------------------------+       |
|  | Visitor name        Updated Xm ago                       |     |
|  | "last message preview..."             [ Agent: username ] |     |
|  |                                        or [ Unassigned ]   |     |
|  |--------------------------------------------------------- |      |
|  | Visitor name        Updated Xm ago                        |     |
|  | "last message preview..."             [ Unassigned ]       |     |
|  +--------------------------------------------------------+       |
|                                                                    |
|  #support-empty-msg  ("No open chats" — shown when list is empty)  |
+----------------------------------------------------------------+
```

Each row is an `<a>` to `support_chat_room` for that session's ID. Only `status='open'` sessions are listed (`chat.views.support_inbox`, `.select_related('agent', 'visitor').prefetch_related('messages')`).

**Real-time behavior:** `support_inbox.js` opens `ws/chat/support/` and handles three event types without a page reload: `session.started` (prepend new row), `chat.notify` (bump an existing row to top + brief highlight), `session.closed` (remove the row).

## Support Chat Room

**Template:** `templates/chat/support_room.html`
**JS:** `static/js/support_room.js`
**Route:** `/chat/support/<session_id>/` (`chat.views.support_chat_room`, name=`support_chat_room`)

```text
+----------------------------------------------------------------+
| < Back to inbox                                                   |
|                                                                    |
|  Chat with {{ session.visitor_name }}    [ Open / Closed ]         |
|                                              [ End chat ]           |
|  (End chat button disabled if session already closed)              |
|                                                                    |
|  #support-room-messages (server-rendered history on first paint,    |
|   then live-appended via WebSocket)                                 |
|  +--------------------------------------------------------+        |
|  | Visitor: message text                       time         |      |
|  | Staff (you): message text                    time         |      |
|  +--------------------------------------------------------+        |
|                                                                    |
|  #support-room-form                                                |
|  [.......................................] [ Send ]                |
|  (disabled if session is closed)                                    |
+----------------------------------------------------------------+
```

**Side effect on page load:** opening this view marks all unread visitor messages in this session as read and broadcasts an updated unread-count to `support_agents` — so opening a chat clears its own unread badge contribution immediately.

**Assignment:** if no agent is yet assigned to this session, connecting to the WebSocket here assigns the current staff user as `ChatSession.agent` (`ChatConsumer.connect()`).

## Unread badge (embedded in the global masthead, staff only)

**Template:** `components/masthead.html` (conditional block), **JS:** `static/js/support_notifications.js`

```text
Masthead (admin/editor only):
  [ Support Inbox  🔴 3 ]   <- #support-unread-badge, hidden via d-none
                               unless support_unread_count > 0 initially,
                               then kept live by its own WebSocket
```

This badge script opens its own independent WebSocket to `ws/chat/support/` — so on `support_inbox.html` itself, a staff member has **two simultaneous connections** to that same endpoint (one from the badge script in the masthead, one from `support_inbox.js`). Both display the same underlying event stream; this is a structural inefficiency, not a functional bug (see [architecture/realtime-chat-flow.md](../architecture/realtime-chat-flow.md)).

## Access control summary

| Action | Requirement |
|---|---|
| View support inbox / room (HTTP) | `chat.permissions.support_agent_required` → `@login_required` + `role in ('admin', 'editor')`, else `PermissionDenied` (403) |
| Connect to `ws/chat/support/` | Same role check inside `SupportInboxConsumer.connect()` |
| Connect to `ws/chat/<id>/` as staff | Any support agent may join any session's room (no per-session assignment restriction on who *can* join, only who gets auto-assigned as `agent`) |
