/* A single form split across several [data-step] panels.
 *
 * The form still posts once, with every field in the payload — the panels are purely a
 * way to stop asking for nine things at once, and to delay the camera permission prompt
 * until the student has a reason to grant it. With JavaScript off, every panel is
 * visible and the form behaves exactly as it did before.
 */

function initFormWizard(opts) {
    const { form, onEnterStep, beforeSubmit } = opts;
    const panels = Array.prototype.slice.call(form.querySelectorAll('[data-step]'));
    const markers = Array.prototype.slice.call(form.querySelectorAll('[data-step-nav]'));
    const submitBtn = form.querySelector('[type="submit"]');
    const visited = {};
    let current = null;

    function panelAt(step) {
        return panels.find(function (panel) {
            return Number(panel.dataset.step) === step;
        });
    }

    function show(step, focus) {
        const panel = panelAt(step);
        if (!panel) return; // Nothing above the last step or below the first.
        current = step;
        panels.forEach(function (panel) {
            panel.hidden = Number(panel.dataset.step) !== step;
        });
        markers.forEach(function (marker) {
            const at = Number(marker.dataset.stepNav);
            marker.classList.toggle('is-current', at === step);
            marker.classList.toggle('is-done', at < step);
        });
        if (focus !== false) {
            panel.scrollIntoView({ block: 'start', behavior: 'smooth' });
            const firstControl = panel.querySelector('input:not([type="hidden"]), select, button');
            if (firstControl) firstControl.focus({ preventScroll: true });
        }
        if (!visited[step]) {
            visited[step] = true;
            if (onEnterStep) onEnterStep(step);
        }
    }

    /* Don't advance past a panel that still has problems: mark everything, then put the
     * cursor on the first thing that needs fixing. */
    function leaveIsBlocked(step) {
        const panel = panelAt(step);
        const firstInvalid = window.formValidate.validateAll(panel);
        if (firstInvalid) {
            firstInvalid.focus();
            firstInvalid.scrollIntoView({ block: 'center', behavior: 'smooth' });
            return true;
        }
        return false;
    }

    form.addEventListener('click', function (event) {
        const next = event.target.closest('[data-step-next]');
        if (next) {
            if (!leaveIsBlocked(current)) show(current + 1);
            return;
        }
        const prev = event.target.closest('[data-step-prev]');
        if (prev) show(current - 1);
    });

    const lastStep = Math.max.apply(null, panels.map(function (panel) {
        return Number(panel.dataset.step);
    }));

    form.addEventListener('submit', function (event) {
        // Enter inside a field submits the form implicitly. On an earlier panel that
        // would post a half-finished form, so treat it as "next" instead.
        if (current < lastStep) {
            event.preventDefault();
            if (!leaveIsBlocked(current)) show(current + 1);
            return;
        }
        for (let step = 1; step < current; step += 1) {
            if (leaveIsBlocked(step)) {
                event.preventDefault();
                show(step);
                return;
            }
        }
        if (leaveIsBlocked(current)) {
            event.preventDefault();
            return;
        }
        // Anything the panels themselves can't express — a missing photo, say.
        if (beforeSubmit && beforeSubmit() === false) {
            event.preventDefault();
            return;
        }
        if (submitBtn) {
            if (submitBtn.classList.contains('is-busy')) {
                event.preventDefault(); // Face encoding takes a moment; ignore double clicks.
                return;
            }
            submitBtn.classList.add('is-busy');
            submitBtn.textContent = submitBtn.dataset.busyLabel || 'Working…';
        }
    });

    /* On a re-render, open the earliest panel the server complained about rather than
     * dropping the student back at step one with no idea what went wrong. */
    function stepToOpen() {
        const withError = panels.find(function (panel) {
            return Array.prototype.some.call(panel.querySelectorAll('.error'), function (node) {
                return node.textContent.trim();
            });
        });
        if (withError) return Number(withError.dataset.step);
        const alert = form.querySelector('[data-non-field-step]');
        if (alert) return Number(alert.dataset.nonFieldStep);
        return Number(panels[0].dataset.step);
    }

    const opening = stepToOpen();
    show(opening, false);
    return { show: show, current: function () { return current; } };
}

window.initFormWizard = initFormWizard;
