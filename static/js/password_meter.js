/**
 * Live checklist under a password field.
 *
 * Deliberately separate from form_validate.js: that module owns the per-field
 * valid/invalid badge and the error text. This one only lights up the criteria
 * list, so the two can be used together (registration) or apart.
 *
 * The rules mirror AUTH_PASSWORD_VALIDATORS in settings.py, with one gap that
 * cannot be closed in the browser: CommonPasswordValidator checks Django's list
 * of ~20,000 leaked passwords. There is no way to reproduce that here, so the
 * list is presented as "checks so far" rather than a promise that submitting
 * will succeed.
 */
(function () {
    'use strict';

    var RULES = {
        length: function (value) {
            return value.length >= 8;
        },
        numeric: function (value) {
            return value !== '' && !/^\d+$/.test(value);
        },
        similar: function (value, context) {
            if (value === '') return false;
            var lowered = value.toLowerCase();
            return !context.related.some(function (part) {
                return part.length >= 3 && lowered.indexOf(part.toLowerCase()) !== -1;
            });
        },
        match: function (value, context) {
            return value !== '' && value === context.confirmValue;
        },
    };

    function init(options) {
        var password = options.password;
        var confirm = options.confirm;
        var list = options.list;
        if (!password || !list) return;

        var items = Array.prototype.slice.call(list.querySelectorAll('[data-rule]'));

        function relatedValues() {
            // Entries may be inputs (registration, where the student can still
            // change their name) or plain strings (password change, where the
            // name is already on the account and isn't on the page). Inputs are
            // read on every paint so the similarity rule notices late edits.
            return (options.related || [])
                .map(function (entry) {
                    if (typeof entry === 'string') return entry.trim();
                    return entry && entry.value ? entry.value.trim() : '';
                })
                .filter(Boolean);
        }

        function paint() {
            var context = {
                related: relatedValues(),
                confirmValue: confirm ? confirm.value : '',
            };
            items.forEach(function (item) {
                var rule = RULES[item.dataset.rule];
                if (!rule) return;
                item.classList.toggle('is-met', rule(password.value, context));
            });
        }

        password.addEventListener('input', paint);
        if (confirm) confirm.addEventListener('input', paint);
        (options.related || []).forEach(function (entry) {
            if (entry && typeof entry !== 'string') entry.addEventListener('input', paint);
        });
        paint();
    }

    window.passwordMeter = { init: init };
})();
