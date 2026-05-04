/* Polls the server every 1s for the current QR token and re-renders the QR.
 * When the token changes (because a student scanned), the displayed QR rotates. */

function initQrDisplay(opts) {
    const { currentTokenUrl, canvas, statusEl } = opts;
    let lastToken = null;

    async function tick() {
        try {
            const res = await fetch(currentTokenUrl, { credentials: 'same-origin' });
            if (!res.ok) {
                statusEl.textContent = 'Could not fetch current code (HTTP ' + res.status + ')';
                return;
            }
            const data = await res.json();
            if (data.status !== 'active') {
                statusEl.textContent = 'Lecture is not active.';
                return;
            }
            if (data.token && data.token !== lastToken) {
                lastToken = data.token;
                await window.QRCode.toCanvas(canvas, data.scan_url, { width: 320, margin: 2 });
                statusEl.textContent = 'Live · code rotates after each successful scan.';
            }
        } catch (err) {
            statusEl.textContent = 'Network error: ' + err.message;
        }
    }

    tick();
    setInterval(tick, 1000);
}
window.initQrDisplay = initQrDisplay;
