# Live Chat (Visitor Widget)

**Template:** `templates/components/chat_widget.html`
**JS:** `static/js/chat_widget.js`
**Included:** globally via `base.html`, on every page **except** `chat/support_inbox.html` and `chat/support_room.html` (those have their own dedicated chat UI — see [support-inbox.md](support-inbox.md))
**Backing endpoints:** `POST /chat/start/`, `GET /chat/<id>/messages/`, `POST /chat/<id>/close/`, WebSocket `ws(s)://<host>/ws/chat/<session_id>/`
**Users/roles:** Any visitor — anonymous or authenticated.

## Wireframe

```text
Collapsed state (default, floating over page content):
                                                    +--------+
                                                    | 💬 Chat|  <- #chat-bubble-btn
                                                    +--------+

Expanded state — pre-chat (no active session yet):
                                          +---------------------------+
                                          | Chat with Football Hub  X |
                                          |---------------------------|
                                          | Name (hidden if logged in) |
                                          | [.......................] |
                                          |                             |
                                          | Message:                    |
                                          | [.......................]   |
                                          | [.......................]   |
                                          |                             |
                                          |        [ Start chat ]       |
                                          +---------------------------+

Expanded state — active chat:
                                          +---------------------------+
                                          | Chat with Football Hub  X |
                                          |---------------------------|
                                          | #chat-messages              |
                                          |  Visitor: hi, quick question|
                                          |  Staff: hey, how can I help?|
                                          |  ...                        |
                                          |---------------------------|
                                          | [........................] [Send] |
                                          |          [ End chat ]       |
                                          +---------------------------+

Expanded state — chat ended:
                                          +---------------------------+
                                          | "This chat has been closed."|
                                          |    [ Start new chat ]       |
                                          +---------------------------+
```

## Data flow

1. Visitor fills pre-chat form → `chat_widget.js` `POST`s to `data-start-url` (`/chat/start/`) with `{name}` JSON body and an `X-CSRFToken` header.
2. Server reuses an existing open `ChatSession` for this user/browser session, or creates a new one; returns `{session_id, visitor_name, status}`.
3. `session_id` is persisted to `localStorage` (`footballhub_chat_session_id`) so a page reload can reconnect without restarting the pre-chat form.
4. Widget opens a WebSocket to `/ws/chat/<session_id>/`, loads message history via `GET /chat/<id>/messages/`, and sends/receives further messages over the socket.
5. "End chat" → `POST /chat/<id>/close/`, then the widget resets to the ended state.

See [architecture/realtime-chat-flow.md](../architecture/realtime-chat-flow.md) for the full sequence diagram, including how messages reach staff.

## Access control

- `start_chat`/`chat_messages`/`close_chat` allow any visitor (no `@login_required`) — access to a *specific* session's messages/close action is checked in `chat/views.py: _can_access_session` (must be a support agent, the session's own authenticated visitor, or hold the matching browser `session_key`).
- The WebSocket connection performs the same ownership check in `ChatConsumer.connect()` before accepting.

## States / error handling

- If the WebSocket connection errors, `chat_widget.js` clears the stored session and resets the UI to the pre-chat form ("forgets" the session) rather than showing a persistent error state.
- A closed session's widget shows the "chat ended" state with a "Start new chat" button, which begins the flow again from step 1.

## Responsive behaviour

Fixed-position floating widget (per its component structure); no separate mobile-specific layout was found in the CSS beyond whatever `static/css/components/chat.css` defines — not independently verified line-by-line during this audit.
