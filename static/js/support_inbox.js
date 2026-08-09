(function () {
    const list = document.getElementById('support-session-list');
    if (!list) return;

    const wsScheme = list.dataset.wsScheme;
    const emptyMsg = document.getElementById('support-empty-msg');

    function removeEmptyMsg() {
        if (emptyMsg) emptyMsg.remove();
    }

    function rowTemplate(sessionId, visitorName) {
        const a = document.createElement('a');
        a.href = `/chat/support/${sessionId}/`;
        a.className = 'list-group-item list-group-item-action support-session-row support-session-new';
        a.dataset.sessionId = sessionId;
        a.innerHTML = `
            <div class="d-flex justify-content-between">
                <strong>${visitorName}</strong>
                <small class="text-muted">just now</small>
            </div>
            <span class="badge bg-warning text-dark mt-1">New chat</span>
        `;
        return a;
    }

    function bumpRow(sessionId) {
        const row = list.querySelector(`[data-session-id="${sessionId}"]`);
        if (!row) return;
        list.prepend(row);
        row.classList.add('support-session-new');
        setTimeout(() => row.classList.remove('support-session-new'), 2000);
    }

    const socket = new WebSocket(`${wsScheme}://${window.location.host}/ws/chat/support/`);

    socket.addEventListener('message', (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'session.started') {
            removeEmptyMsg();
            if (!list.querySelector(`[data-session-id="${data.session_id}"]`)) {
                list.prepend(rowTemplate(data.session_id, data.visitor_name));
            }
        } else if (data.type === 'chat.notify') {
            bumpRow(data.session_id);
        } else if (data.type === 'session.closed') {
            const row = list.querySelector(`[data-session-id="${data.session_id}"]`);
            if (row) row.remove();
        }
    });
})();
