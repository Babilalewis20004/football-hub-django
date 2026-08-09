(function () {
    const root = document.getElementById('support-room');
    if (!root) return;

    const sessionId = root.dataset.sessionId;
    const wsScheme = root.dataset.wsScheme;

    const messagesEl = document.getElementById('support-room-messages');
    const form = document.getElementById('support-room-form');
    const input = document.getElementById('support-room-input');
    const endBtn = document.getElementById('support-end-btn');
    const statusEl = document.getElementById('support-room-status');

    function csrfToken() {
        return document.querySelector('meta[name="csrf-token"]').content;
    }

    function scrollToBottom() {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function renderMessage(msg) {
        const el = document.createElement('div');

        let variant = msg.is_staff_message ? 'chat-message-self' : 'chat-message-other';
        if (msg.system) variant = 'chat-message-system';
        el.classList.add('chat-message', variant);

        const bodyEl = document.createElement('span');
        bodyEl.textContent = msg.message;
        el.appendChild(bodyEl);

        if (!msg.system) {
            const meta = document.createElement('small');
            meta.className = 'chat-message-meta';
            const time = new Date(msg.timestamp);
            meta.textContent = `${msg.sender_name} · ${time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
            el.appendChild(meta);
        }

        messagesEl.appendChild(el);
        scrollToBottom();
    }

    function markClosed() {
        statusEl.textContent = 'Chat closed';
        input.disabled = true;
        endBtn.disabled = true;
    }

    scrollToBottom();

    const socket = new WebSocket(`${wsScheme}://${window.location.host}/ws/chat/${sessionId}/`);

    socket.addEventListener('message', (event) => {
        const data = JSON.parse(event.data);
        renderMessage(data);
        if (data.system) markClosed();
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text || !socket || socket.readyState !== WebSocket.OPEN) return;
        socket.send(JSON.stringify({ message: text }));
        input.value = '';
    });

    endBtn.addEventListener('click', () => {
        fetch(`/chat/${sessionId}/close/`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken() },
        }).then(() => markClosed());
    });
})();
