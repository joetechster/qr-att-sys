/* Student-side scan + verify flow:
 *   1. Open camera.
 *   2. If a token isn't already prefilled (from QR deep-link), keep scanning frames
 *      with jsQR until a valid PCU scan URL is recognised.
 *   3. Capture a selfie frame and POST {token, image} to /scan/verify/.
 *   4. Show success / error to the user. */

function initScanner(opts) {
    const { video, canvas, captureBtn, retakeBtn, switchBtn, statusEl, tokenInput, csrfToken, verifyUrl } = opts;
    let stream = null;
    let scanning = !tokenInput.value;
    let token = tokenInput.value || null;
    let currentFacing = null;

    async function getStream(facingMode) {
        // Prefer the requested camera; fall back to any camera if that exact
        // facing mode isn't available (e.g. laptops with no rear camera).
        try {
            return await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: facingMode } }, audio: false,
            });
        } catch (e) {
            return await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        }
    }

    async function startCamera(facingMode) {
        // Default: rear camera while we still need to read the QR, front camera
        // once we're on to the selfie step.
        if (!facingMode) facingMode = token ? 'user' : 'environment';
        try {
            stopCamera();
            stream = await getStream(facingMode);
            currentFacing = facingMode;
            video.srcObject = stream;
            if (token) {
                statusEl.textContent = 'Code recognised. Center your face and tap "Take selfie".';
                captureBtn.disabled = false;
            } else {
                statusEl.textContent = 'Point the camera at the QR code...';
                scanning = true;
                requestAnimationFrame(scanLoop);
            }
        } catch (err) {
            statusEl.textContent = 'Could not access camera: ' + err.message;
        }
    }

    async function maybeShowSwitchBtn() {
        // Only show the toggle on devices with more than one camera.
        if (!switchBtn || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const cams = devices.filter(d => d.kind === 'videoinput');
            switchBtn.style.display = cams.length > 1 ? '' : 'none';
        } catch (e) { /* leave hidden */ }
    }

    function stopCamera() {
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
        video.srcObject = null;
    }

    function extractTokenFromUrl(text) {
        try {
            const u = new URL(text);
            return u.searchParams.get('t');
        } catch (e) { return null; }
    }

    function scanLoop() {
        if (!scanning) return;
        if (video.readyState >= 2) {
            const ctx = canvas.getContext('2d', { willReadFrequently: true });
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const code = window.jsQR(img.data, img.width, img.height);
            if (code && code.data) {
                const t = extractTokenFromUrl(code.data) || code.data.trim();
                if (t) {
                    token = t;
                    tokenInput.value = t;
                    scanning = false;
                    statusEl.textContent = 'Code recognised. Switching to front camera...';
                    startCamera('user');
                    return;
                }
            }
        }
        requestAnimationFrame(scanLoop);
    }

    async function submit(imageDataUrl) {
        statusEl.textContent = 'Verifying face...';
        const body = new URLSearchParams();
        body.set('token', token);
        body.set('image', imageDataUrl);
        try {
            const res = await fetch(verifyUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: body.toString(),
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) {
                statusEl.innerHTML = '<strong>Success: ' + (data.message || 'Marked present') +
                    '</strong> - ' + (data.course || '') + ' - ' + (data.lecture || '');
                captureBtn.style.display = 'none';
                retakeBtn.style.display = 'none';
            } else {
                statusEl.textContent = 'Error: ' + (data.error || 'Could not mark attendance.');
                retakeBtn.style.display = '';
            }
        } catch (err) {
            statusEl.textContent = 'Network error: ' + err.message;
            retakeBtn.style.display = '';
        }
    }

    captureBtn.addEventListener('click', () => {
        const ctx = canvas.getContext('2d');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
        captureBtn.disabled = true;
        stopCamera();
        submit(dataUrl);
    });

    retakeBtn.addEventListener('click', async () => {
        retakeBtn.style.display = 'none';
        captureBtn.disabled = false;
        // Keep the same token; just retake the selfie with the front camera.
        await startCamera('user');
    });

    if (switchBtn) {
        switchBtn.addEventListener('click', async () => {
            const next = currentFacing === 'user' ? 'environment' : 'user';
            switchBtn.disabled = true;
            await startCamera(next);
            switchBtn.disabled = false;
        });
    }

    startCamera();
    maybeShowSwitchBtn();
}
window.initScanner = initScanner;
