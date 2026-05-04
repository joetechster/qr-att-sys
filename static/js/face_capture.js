/* Live webcam preview + single-shot capture into a hidden field as a data URL.
 * Used by the registration form. */

function initFaceCapture(opts) {
    const { video, canvas, captureBtn, retakeBtn, hiddenInput, statusEl, onReady, onCleared } = opts;
    let stream = null;

    async function startCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
            video.srcObject = stream;
            statusEl.textContent = 'Center your face in the frame, then click "Take photo".';
        } catch (err) {
            statusEl.textContent = 'Could not access camera: ' + err.message;
        }
    }

    function stopCamera() {
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    }

    captureBtn.addEventListener('click', () => {
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
        hiddenInput.value = dataUrl;
        canvas.style.display = '';
        video.style.display = 'none';
        captureBtn.style.display = 'none';
        retakeBtn.style.display = '';
        statusEl.textContent = 'Photo captured. Click Retake if you want to try again.';
        stopCamera();
        if (onReady) onReady();
    });

    retakeBtn.addEventListener('click', async () => {
        hiddenInput.value = '';
        canvas.style.display = 'none';
        video.style.display = '';
        captureBtn.style.display = '';
        retakeBtn.style.display = 'none';
        if (onCleared) onCleared();
        await startCamera();
    });

    startCamera();
}
window.initFaceCapture = initFaceCapture;
