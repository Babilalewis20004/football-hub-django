# Real-Time Chat Architecture

Built entirely on **Django Channels** over ASGI. There is no polling fallback — the widget, support inbox, and support room all depend on a live WebSocket connection. Traced from `config/asgi.py`, `chat/routing.py`, `chat/consumers.py`, `chat/views.py`, `chat/services.py`, `chat/permissions.py`, and the three chat-related JS files.

## Components

| Component | File | Role |
|---|---|---|
| ASGI entrypoint | `config/asgi.py` | Routes `websocket` scope to `AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter(chat.routing.websocket_urlpatterns)))` — origin-checked, session/auth-aware |
| WebSocket routes | `chat/routing.py` | `ws/chat/support/` → `SupportInboxConsumer`; `ws/chat/<session_id>/` → `ChatConsumer` |
| Visitor-facing HTTP endpoints | `chat/views.py` | `start_chat` (creates/reuses a `ChatSession`), `chat_messages` (history, GET), `close_chat` (POST) |
| Staff-facing HTTP endpoints | `chat/views.py` | `support_inbox` (list of open sessions), `support_chat_room` (one session's transcript + reply form) |
| `ChatConsumer` | `chat/consumers.py` | One instance per connection to a specific `ChatSession`'s room group (`chat_<id>`); shared code path for visitor and staff |
| `SupportInboxConsumer` | `chat/consumers.py` | One instance per connected staff member, joined to the shared `support_agents` group; pushes new-session/new-message/unread-count events |
| Channel layer | `config/settings.py: CHANNEL_LAYERS` | `InMemoryChannelLayer` (dev default) or `channels_redis.core.RedisChannelLayer` (if `REDIS_URL` set) |
| Persistence | `chat/models.py` | `ChatSession`, `ChatMessage` — every message is written to PostgreSQL before being broadcast |
| `ChatSession` model | | Ties an anonymous visitor to their browser session via `session_key` so a page reload doesn't lose the chat |
| Client — widget | `static/js/chat_widget.js` | Visitor-facing chat bubble, used on every page except the two staff chat pages |
| Client — support inbox | `static/js/support_inbox.js` | Live-updating list on `chat/support_inbox.html` |
| Client — support room | `static/js/support_room.js` | Live message stream on `chat/support_room.html` |
| Client — badge | `static/js/support_notifications.js` | Unread-count badge in the navbar (`masthead.html`), shown only to `admin`/`editor` roles |

## Sequence diagram — visitor message reaching a support agent

```mermaid
sequenceDiagram
    participant Visitor as Visitor (browser)
    participant Widget as chat_widget.js
    participant HTTP as Django (chat.views)
    participant Consumer as ChatConsumer
    participant Layer as Channel layer<br/>(InMemory or Redis)
    participant InboxConsumer as SupportInboxConsumer
    participant Agent as Support agent (browser)

    Visitor->>Widget: Opens chat, enters name + first message
    Widget->>HTTP: POST /chat/start/ {name}
    HTTP->>HTTP: Reuse open ChatSession (by user or session_key)<br/>or create a new one
    HTTP-->>Widget: {session_id, visitor_name, status}
    HTTP->>Layer: group_send("support_agents", type=session.started)
    Layer->>InboxConsumer: session.started event (if agent connected)
    InboxConsumer-->>Agent: New session row prepended to inbox

    Widget->>Consumer: WebSocket connect ws/chat/<session_id>/
    Consumer->>Consumer: Verify ownership (user id or session_key)
    Consumer->>Layer: group_add("chat_<session_id>", channel)

    Visitor->>Widget: Types and sends a message
    Widget->>Consumer: WS send {message}
    Consumer->>Consumer: Save ChatMessage (PostgreSQL)<br/>Update ChatSession.updated_at
    Consumer->>Layer: group_send("chat_<session_id>", chat.message)
    Consumer->>Layer: group_send("support_agents", chat.notify)
    Layer->>InboxConsumer: chat.notify event
    InboxConsumer-->>Agent: Row bumped to top + highlighted
    Consumer->>Layer: group_send("support_agents", unread.count)
    Layer-->>Agent: Badge count updated (support_notifications.js)

    Agent->>HTTP: Opens support_chat_room (session_id)
    HTTP->>HTTP: Marks unread visitor messages as read<br/>Notifies support_agents of new unread count
    Agent->>Consumer: WebSocket connect ws/chat/<session_id>/
    Consumer->>Layer: group_add("chat_<session_id>", channel)<br/>(agent assigned if session.agent was null)

    Agent->>Consumer: Sends a reply
    Consumer->>Consumer: Save ChatMessage (is_staff_message=True)
    Consumer->>Layer: group_send("chat_<session_id>", chat.message)
    Layer-->>Widget: Message delivered to visitor in real time
```

## Sequence diagram — closing a chat

```mermaid
sequenceDiagram
    participant Agent as Agent or Visitor
    participant HTTP as Django (chat.views.close_chat)
    participant Layer as Channel layer
    participant Room as ChatConsumer (both parties)
    participant Inbox as SupportInboxConsumer (all staff)

    Agent->>HTTP: POST /chat/<id>/close/
    HTTP->>HTTP: ChatSession.status = "closed"
    HTTP->>Layer: group_send("chat_<id>", system message "This chat has been closed.")
    Layer-->>Room: Delivered to both visitor and agent widgets
    HTTP->>Layer: group_send("support_agents", type=session.closed)
    Layer-->>Inbox: Row removed from the open-sessions list
    HTTP->>Layer: group_send("support_agents", type=unread.count, recalculated)
    Layer-->>Inbox: Badge updated
```

## Access control on WebSocket connections

- `ChatConsumer.connect()`: closes the socket immediately if the `ChatSession` doesn't exist. For non-staff connections, it further requires that either the authenticated user's ID matches `session.visitor_id`, or the browser's session key matches `session.session_key` — this is how an anonymous visitor's own chat stays private from other anonymous visitors.
- `SupportInboxConsumer.connect()`: closes immediately unless `chat.permissions.is_support_agent(user)` is true (`user.role in ('admin', 'editor')`).
- Both consumers rely on `AuthMiddlewareStack` (in `config/asgi.py`) to populate `self.scope['user']` and `self.scope['session']` from the same session cookie used by regular HTTP requests — no separate WebSocket authentication scheme exists.
- `AllowedHostsOriginValidator` (also in `config/asgi.py`) rejects WebSocket connections whose `Origin` header doesn't match `ALLOWED_HOSTS`.

## A structural note (not a bug, but worth documenting for architecture accuracy)

On `chat/support_inbox.html`, a signed-in `admin`/`editor` viewer has **two independent WebSocket connections open to the same `ws/chat/support/` endpoint simultaneously**: one from `support_notifications.js` (loaded in `masthead.html`, included on every page including the inbox) and one from `support_inbox.js` (loaded specifically by the inbox template). Both are legitimate, independently-authorized connections to the same consumer/group — this doubles the `SupportInboxConsumer` instances (and thus channel-layer group membership) for that one browser tab, though it doesn't cause incorrect behavior since both simply render the same broadcast events.

## Why Redis matters here specifically

`InMemoryChannelLayer` only delivers `group_send()` calls to consumers connected to the **same process**. A `ChatConsumer` and a `SupportInboxConsumer` both need to receive the same `group_send()` call for the flows above to work — if a production deployment runs multiple ASGI worker processes without Redis, a visitor's message could land in a `ChatConsumer` on worker A while the assigned agent's `SupportInboxConsumer`/`ChatConsumer` is connected to worker B, and the broadcast would never cross that boundary. See [deployment-architecture.md](deployment-architecture.md).
