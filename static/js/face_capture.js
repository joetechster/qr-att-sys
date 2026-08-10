/* Live webcam preview + single-shot capture into a hidden field as a data URL.
 * Used by the registration form.
 *
 * Two things worth knowing:
 *
 * - The camera is NOT started on load. Call start() when the student actually reaches
 *   the photo step, so the browser's permission prompt arrives with some context.
 * - On a re-render after a validation error, Django echoes the submitted data URL back
 *   into the hidden input. We restore it into the canvas instead of ignoring it, so a
 *   typo in the username no longer costs the student their photo.
 */

const FACE_DATA_URL_RE = /^data:image\/(?:png|jpeg|jpg);base64,/;

const CAMERA_ERRORS = {
    NotAllowedError:
        'Camera access was blocked. Allow the camera in your browser\'s address bar, then try again.',
    NotFoundError: 'No camera was found on this device.',
    NotReadableError: 'The camera is already in use by another app. Close it and try again.',
    OverconstrainedError: 'No usable camera was found on this device.',
};

function initFaceCapture(opts) {
    const { video, canvas, captureBtn, retakeBtn, hiddenInput, statusEl, onReady, onCleared } = opts;
    const retryBtn = opts.retryBtn || null;
    let stream = null;

    function setStatus(text, state) {
        statusEl.textContent = text;
        statusEl.classList.toggle('is-error', state === 'error');
        statusEl.classList.toggle('is-ok', state === 'ok');
    }

    function showCaptured() {
        canvas.style.display = '';
        video.style.display = 'none';
        captureBtn.style.display = 'none';
        retakeBtn.style.display = '';
        if (retryBtn) retryBtn.style.display = 'none';
    }

    function showLive() {
        canvas.style.display = 'none';
        video.style.display = '';
        captureBtn.style.display = '';
        retakeBtn.style.display = 'none';
        if (retryBtn) retryBtn.style.display = 'none';
    }

    function hasPhoto() {
        return FACE_DATA_URL_RE.test(hiddenInput.value || '');
    }

    async function start() {
        if (stream) return;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setStatus(
                'This browser can only use the camera over HTTPS or on localhost.',
                'error'
            );
            if (retryBtn) retryBtn.style.display = '';
            return;
        }
        setStatus('Starting the camera…');
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                // Ask for a high-resolution frame: the encoder needs a face big
                // enough in pixels to align well, and a scan is captured at the
                // camera's native size, so a small reference is a mismatch.
                // These are `ideal`, so a weaker camera still works.
                video: {
                    facingMode: 'user',
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
                audio: false,
            });
            video.srcObject = stream;
            showLive();
            setStatus('Center your face in the frame, then take the photo.');
        } catch (err) {
            stream = null;
            setStatus(CAMERA_ERRORS[err.name] || ('Could not access the camera: ' + err.message), 'error');
            captureBtn.style.display = 'none';
            if (retryBtn) retryBtn.style.display = '';
        }
    }

    function stop() {
        if (stream) {
            stream.getTracks().forEach(function (track) { track.stop(); });
            stream = null;
        }
    }

    captureBtn.addEventListener('click', function () {
        const ctx = canvas.getContext('2d');
        // Match the canvas to the camera's own frame size before drawing. The
        // element is laid out by CSS, so leaving the backing store at its
        // default 300x150 would store a thumbnail as the reference photo.
        canvas.width = video.videoWidth || canvas.width;
        canvas.height = video.videoHeight || canvas.height;
        // The preview is mirrored in CSS for a natural selfie feel; the canvas is not,
        // so the stored face matches how a camera actually sees the student.
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        hiddenInput.value = canvas.toDataURL('image/jpeg', 0.9);
        showCaptured();
        setStatus('Photo captured. Retake it if you are not happy with this one.', 'ok');
        stop();
        if (onReady) onReady();
    });

    retakeBtn.addEventListener('click', function () {
        hiddenInput.value = '';
        showLive();
        if (onCleared) onCleared();
        start();
    });

    if (retryBtn) retryBtn.addEventListener('click', start);
    window.addEventListener('pagehide', stop);

    /* Bring back the photo submitted with a request that failed validation. */
    function restore() {
        if (!hasPhoto()) return false;
        const image = new Image();
        image.onload = function () {
            // Same sizing rule as capture: redraw at the photo's own resolution
            // so a form redisplay doesn't quietly shrink what gets resubmitted.
            canvas.width = image.naturalWidth || canvas.width;
            canvas.height = image.naturalHeight || canvas.height;
            canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
        };
        image.src = hiddenInput.value;
        showCaptured();
        setStatus(
            opts.photoRejected
                ? 'That photo was not accepted. Retake it, following the tips above.'
                : 'Your photo is still here. Retake it if you want a different one.',
            opts.photoRejected ? 'error' : 'ok'
        );
        if (onReady) onReady();
        return true;
    }

    const restored = restore();
    if (!restored) {
        showLive();
        captureBtn.style.display = 'none';
        setStatus('Turn on your camera to take a reference photo.');
        if (retryBtn) retryBtn.style.display = '';
    }

    return { start: start, stop: stop, hasPhoto: hasPhoto, restored: restored };
}

window.initFaceCapture = initFaceCapture;
