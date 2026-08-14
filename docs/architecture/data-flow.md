# Data Flow Diagrams

## 1. User authentication (password + role + optional 2FA)

```text
User
 |
 v
Login form (templates/users/login.html)
 [username, password, role dropdown, optional CAPTCHA]
 |
 v
users.views.login_view
 |
 +--> users.security.check_lockout()      -- reject if locked, same message
 |                                            regardless of whether username exists
 +--> users.security.requires_captcha()   -- require + validate CAPTCHA if recent
 |                                            failure streak crossed threshold
 +--> role in PUBLIC_LOGIN_ROLES check    -- reject invalid/admin role selection
 +--> django.contrib.auth.authenticate()  -- verify password
 +--> user.role == submitted role check   -- reject on mismatch (generic error)
 |
 v
users.security.record_attempt()  --> LoginAttempt row (PostgreSQL)
 |
 v
django.contrib.auth.login()
 |
 v
users.signals.enforce_single_session  -- evicts other Session rows if role in
                                          {admin, editor, author}
 |
 v
users.twofactor.two_factor_gate(user)
 |
 +--> 'setup'  --> /2fa/setup/  --> QR enrollment --> otp_login() --> recovery codes shown
 +--> 'verify' --> /2fa/verify/ --> TOTP or recovery code --> otp_login()
 +--> None     --> (reader with no 2FA)
 |
 v
Authenticated + (if applicable) OTP-verified session
 |
 v
Redirect to safe `next` URL, or home
```

See [authentication-flow.md](authentication-flow.md) for the full flowchart including failure/lockout branches.

## 2. Blog post publishing (editorial workflow)

```text
Author
 |
 v
post_create (blog.views.posts, requires blog.add_post permission)
 |
 v
PostForm  --> clean_title (min 5 chars), clean_content (nh3.clean() sanitization)
 |
 v
Post.save()  -- status="draft", is_published=False, is_approved=False
              -- auto-generates unique slug, auto-fills excerpt if blank
 |
 v
PostgreSQL (blog_post row) + Notification("saved as a draft")
 |
 v
Author clicks "Submit for review"  --> post_submit_for_review
 |     (object-level check: post.author == request.user)
 v
status = "in_review"  --> Notification to author
 |
 v
Editor dashboard (editor_dashboard, requires blog.can_approve_post)
 |
 +--> "Request changes" --> post_request_changes --> status="needs_changes",
 |     is_approved=False, editor_feedback=<text> --> Notification to author
 |     --> Author can edit + post_submit_for_review again (loop)
 |
 +--> "Approve" --> post_approve --> is_approved=True, status="approved"
                     --> Notification to author
 |
 v
Editor clicks "Publish" --> post_publish (requires blog.can_publish_post)
 |
 +--> is_published=True, is_approved=True, status="published",
 |     published_at=now, status_changed_at=now
 |
 +--> blog.services.telegram.send_new_post_announcement()
 |     --> if TELEGRAM_BOT_TOKEN/CHANNEL_ID configured: posts to Telegram channel
 |         --> success: telegram_announced_at=now
 |         --> failure: logged, swallowed, publish still succeeds
 |
 v
Post.save()  --> PostgreSQL + Notification("now published!") to author
 |
 v
Reader (anonymous or authenticated)
 |
 v
post_detail view  -- can_view_post() gate (published, OR owner/editor for drafts)
 |
 v
Atomic view-count increment (F("views") + 1) + related_posts computed
 |
 v
Rendered blog/post_detail.html
```

## 3. Search

```text
User
 |
 v
GET /search/?q=<term>  (masthead search box)
 |
 v
blog.views.search.search_posts
 |
 +--> security logger flags suspicious terms (sql/drop/union/etc. — logging only,
 |     not a real WAF; the actual query is always parameterized via the ORM)
 |
 v
Post.objects.filter(Q(title__icontains) | Q(content__icontains) |
                     Q(category__name__icontains) | Q(tags__name__icontains),
                     is_published=True).distinct()
 |
 v
Paginator (10 per page)
 |
 v
blog/search_results.html
```

Note: `blog/services/search.py: search_posts_queryset` implements the same query independently but is **not called** by this view — the view builds its own queryset inline. This is a duplicated/dead code path, not a real second search flow.

## 4. Live chat (visitor to support agent)

```text
Visitor (anonymous or authenticated)
 |
 v
Chat widget (components/chat_widget.html + chat_widget.js)
 |
 v
POST /chat/start/  (chat.views.start_chat)
 |
 +--> Reuses an existing open ChatSession for this user/session_key if one exists
 +--> Otherwise creates a new ChatSession row --> PostgreSQL
 +--> Notifies support agents via channel layer group "support_agents"
       (type: session.started) -- only reaches other processes if REDIS_URL is set
 |
 v
Browser opens WebSocket: ws(s)://<host>/ws/chat/<session_id>/
 |
 v
chat.consumers.ChatConsumer.connect()
 |
 +--> Ownership check (visitor's user id or browser session_key must match)
 +--> If staff and session.agent is None: assigns this staff member as agent
 +--> Joins channel-layer group "chat_<session_id>"
 |
 v
User sends a message over the socket
 |
 v
ChatConsumer.receive() --> ChatMessage.objects.create() --> PostgreSQL
 |
 +--> channel_layer.group_send("chat_<session_id>", ...) --> both parties in the room
 +--> channel_layer.group_send("support_agents", type=chat.notify) --> all connected
       staff (support inbox list, badge counters)
 +--> If sender is a visitor: recomputed unread count broadcast to "support_agents"
 |
 v
Support agent (in Support Inbox or an open chat room)
```

See [realtime-chat-flow.md](realtime-chat-flow.md) for the full sequence diagram and channel-layer detail, including the Redis-vs-in-memory distinction.

## 5. Telegram announcement

```text
Django (blog.views.posts.post_publish)
 |
 v
blog.services.telegram.send_new_post_announcement(post, absolute_url)
 |
 +--> If TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID is empty: return False immediately,
 |     no network call, no error (integration is off by default)
 |
 v
python-telegram-bot: Bot(token).send_message(chat_id=channel_id, text=...)
 |     (wrapped in asyncio.run() since the library's send_message is async-only)
 |
 v
Telegram Bot API
 |
 v
Telegram channel subscribers
 |
 v
On success: post.telegram_announced_at = now  (surfaced in author/editor dashboards)
On failure: exception logged to the `blog` logger, swallowed — publishing is
            never blocked by a Telegram-side failure
```

This is strictly one-way (outbound announcements only) — the bot does not poll or receive webhooks, and no other post-status transition (approve, request-changes, etc.) triggers a Telegram message, only `post_publish`.

## 6. Feedback & newsletter subscription

```text
User (any, including anonymous)
 |
 v
pages/feedback.html  -- 1-5 star rating (required), optional name/email/comment
 |
 v
pages.views.feedback_view
 |
 +--> If authenticated: user/name/email auto-filled from the account
 |
 v
Feedback.objects.create()  --> PostgreSQL (pages_feedback)
 |
 v
Success message, redirect back to the feedback page

---

User
 |
 v
Newsletter form (footer, on every page)
 |
 v
pages.views.subscribe_view  --> Subscriber.objects.get_or_create(email=...)
 |
 v
PostgreSQL (pages_subscriber)  -- no confirmation/double opt-in email is sent
```
