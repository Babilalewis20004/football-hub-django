(function () {
    const badge = document.getElementById('support-unread-badge');
    if (!badge) return;

    function setCount(count) {
        if (count > 0) {
            badge.textContent = `🔔 ${count}`;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    }

    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${wsScheme}://${window.location.host}/ws/chat/support/`);

    socket.addEventListener('message', (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'unread.count') {
            setCount(data.count);
        }
    });
})();
