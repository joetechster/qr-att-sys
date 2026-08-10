/* Subscribes to a per-lecture WebSocket and re-renders the QR each time the
 * server pushes a new token (i.e. after a successful student scan). */

function initQrDisplay(opts) {
    const { wsUrl, canvas, statusEl } = opts;
    const fullUrl = (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + wsUrl;

    let socket = null;
    let backoff = 500;
    let stopped = false;
    let lastToken = null;

    function render(token) {
        const scanUrl = location.origin + '/scan/?t=' + encodeURIComponent(token);
        new window.QRious({ element: canvas, value: scanUrl, size: 320, padding: 16 });
    }

    function clearCode() {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    function onMessage(ev) {
        let data;
        try { data = JSON.parse(ev.data); } catch { return; }
        if (data.status === 'active' && data.token) {
            if (data.token !== lastToken) {
                lastToken = data.token;
                render(data.token);
            }
            statusEl.textContent = 'Live - code rotates after each successful scan.';
        } else if (data.status === 'ended') {
            // Pushed when the lecturer ends the lecture or its scheduled end
            // time is reached. Wipe the code so a stale QR can't be scanned off
            // a screen nobody has closed.
            lastToken = null;
            clearCode();
            statusEl.textContent = 'This lecture has ended.';
        } else {
            lastToken = null;
            clearCode();
            statusEl.textContent = 'Lecture is not active.';
        }
    }

    function connect() {
        if (stopped) return;
        statusEl.textContent = 'Connecting...';
        socket = new WebSocket(fullUrl);
        socket.onopen = () => { backoff = 500; };
        socket.onmessage = onMessage;
        socket.onclose = (ev) => {
            if (stopped) return;
            // Auth failures (4401/4403) should not retry forever.
            if (ev.code === 4401 || ev.code === 4403) {
                stopped = true;
                statusEl.textContent = 'Not authorized to view this lecture.';
                return;
            }
            statusEl.textContent = 'Disconnected. Reconnecting...';
            setTimeout(connect, backoff);
            backoff = Math.min(backoff * 2, 10000);
        };
        socket.onerror = () => { /* close handler will run */ };
    }

    connect();
}
window.initQrDisplay = initQrDisplay;
