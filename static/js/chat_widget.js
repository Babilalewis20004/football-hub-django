(function () {
    const root = document.getElementById('chat-widget');
    if (!root) return;

    const bubbleBtn = document.getElementById('chat-bubble-btn');
    const panel = document.getElementById('chat-panel');
    const closeBtn = document.getElementById('chat-close-btn');
    const endBtn = document.getElementById('chat-end-btn');
    const statusText = document.getElementById('chat-status-text');
    const badge = document.getElementById('chat-unread-badge');

    const prechat = document.getElementById('chat-prechat');
    const prechatForm = document.getElementById('chat-prechat-form');
    const nameField = document.getElementById('chat-name-field');
    const nameInput = document.getElementById('chat-name-input');
    const firstMessageInput = document.getElementById('chat-first-message');

    const messagesEl = document.getElementById('chat-messages');
    const messageForm = document.getElementById('chat-message-form');
    const messageInput = document.getElementById('chat-message-input');

    const endedActions = document.getElementById('chat-ended-actions');
    const newChatBtn = document.getElementById('chat-new-btn');

    const startUrl = root.dataset.startUrl;
    const wsScheme = root.dataset.wsScheme;
    const isAuthenticated = root.dataset.authenticated === '1';
    const displayName = root.dataset.displayName;

    const STORAGE_KEY = 'footballhub_chat_session_id';

    let socket = null;
    let sessionId = localStorage.getItem(STORAGE_KEY);
    let unread = 0;
    let panelOpen = false;

    if (isAuthenticated) {
        nameField.classList.add('d-none');
    } else {
        nameInput.required = true;
    }

    function csrfToken() {
        return document.querySelector('meta[name="csrf-token"]').content;
    }

    function scrollToBottom() {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function renderMessage(msg) {
        const el = document.createElement('div');

        let variant = 'chat-message-other';
        if (msg.system) {
            variant = 'chat-message-system';
        } else if (!msg.is_staff_message) {
            variant = 'chat-message-self';
        }
        el.classList.add('chat-message', variant);

        const bodyEl = document.createElement('span');
        bodyEl.textContent = msg.message;
        el.appendChild(bodyEl);

        if (!msg.system) {
            const meta = document.createElement('small');
            meta.className = 'chat-message-meta';
            const time = new Date(msg.timestamp);
            const label = msg.is_staff_message ? 'Support' : msg.sender_name;
            meta.textContent = `${label} · ${time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
            el.appendChild(meta);
        }

        messagesEl.appendChild(el);
        scrollToBottom();
    }

    function setUnread(n) {
        unread = n;
        if (unread > 0) {
            badge.textContent = String(unread);
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    }

    function markEnded() {
        statusText.textContent = 'Chat ended';
        endBtn.classList.add('d-none');
        messageInput.disabled = true;
        messageForm.classList.add('d-none');
        endedActions.classList.remove('d-none');
    }

    function markActive() {
        statusText.textContent = "We're online";
        endBtn.classList.remove('d-none');
        messageInput.disabled = false;
        messageForm.classList.remove('d-none');
        endedActions.classList.add('d-none');
    }

    function closeSocket() {
        if (socket) {
            socket.onclose = null;
            socket.close();
            socket = null;
        }
    }

    function openSocket() {
        if (!sessionId || socket) return;

        socket = new WebSocket(`${wsScheme}://${window.location.host}/ws/chat/${sessionId}/`);

        socket.addEventListener('message', (event) => {
            const data = JSON.parse(event.data);
            renderMessage(data);

            if (data.system) {
                markEnded();
                closeSocket();
            } else if (!panelOpen && data.is_staff_message) {
                setUnread(unread + 1);
            }
        });

        socket.addEventListener('close', () => {
            socket = null;
        });
    }

    function loadHistory() {
        return fetch(`/chat/${sessionId}/messages/`, { credentials: 'same-origin' })
            .then((res) => {
                if (!res.ok) throw new Error('invalid session');
                return res.json();
            })
            .then((data) => {
                messagesEl.innerHTML = '';
                data.messages.forEach(renderMessage);

                if (data.status === 'closed') {
                    markEnded();
                } else {
                    markActive();
                }
            });
    }

    function showThread() {
        prechat.classList.add('d-none');
        messagesEl.classList.remove('d-none');
        endedActions.classList.add('d-none');
    }

    function showPrechat() {
        prechat.classList.remove('d-none');
        messagesEl.classList.add('d-none');
        messageForm.classList.add('d-none');
        endedActions.classList.add('d-none');
        messageInput.disabled = false;
    }

    function forgetSession() {
        localStorage.removeItem(STORAGE_KEY);
        sessionId = null;
        closeSocket();
        showPrechat();
    }

    function startChat(firstMessage) {
        return fetch(startUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify({ name: nameInput.value.trim() }),
        })
            .then((res) => res.json())
            .then((data) => {
                sessionId = data.session_id;
                localStorage.setItem(STORAGE_KEY, sessionId);
                showThread();
                openSocket();
                return loadHistory();
            })
            .then(() => {
                if (firstMessage) sendMessage(firstMessage);
            });
    }

    function sendMessage(text) {
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        socket.send(JSON.stringify({
            message: text,
            sender_name: isAuthenticated ? displayName : (nameInput.value.trim() || 'Visitor'),
        }));
    }

    bubbleBtn.addEventListener('click', () => {
        panelOpen = panel.classList.contains('d-none');
        panel.classList.toggle('d-none');
        if (!panelOpen) return;

        setUnread(0);
        if (!sessionId) return;

        showThread();
        openSocket();
        loadHistory().catch(forgetSession);
    });

    closeBtn.addEventListener('click', () => {
        panel.classList.add('d-none');
        panelOpen = false;
    });

    prechatForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const firstMessage = firstMessageInput.value.trim();
        if (!firstMessage) return;
        if (!isAuthenticated && !nameInput.value.trim()) {
            nameInput.focus();
            return;
        }

        firstMessageInput.value = '';
        startChat(firstMessage);
    });

    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = messageInput.value.trim();
        if (!text) return;
        sendMessage(text);
        messageInput.value = '';
    });

    endBtn.addEventListener('click', () => {
        if (!sessionId) return;
        fetch(`/chat/${sessionId}/close/`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken() },
        }).then(() => {
            localStorage.removeItem(STORAGE_KEY);
            markEnded();
            closeSocket();
        });
    });

    newChatBtn.addEventListener('click', () => {
        forgetSession();
    });
})();
