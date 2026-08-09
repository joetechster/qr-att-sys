/* Real-time field validation with a per-field pass/fail badge.
 *
 * The rules come from native constraint attributes (required, minlength, pattern,
 * type=email) that Django renders from the form's widget attrs, so there is only one
 * copy of them. Anything that cannot be expressed natively — password match, for
 * instance — is registered here as a named custom rule.
 *
 * Timing is the point: a field stays neutral until the first blur, so nobody is told
 * they are wrong halfway through typing. After that it tracks every keystroke, which
 * is what makes the checkmark appear the moment the value becomes good.
 */

(function () {
    const VALID = 'is-valid';
    const INVALID = 'is-invalid';
    const TOUCHED = 'validateTouched';

    function fieldOf(input) {
        return input.closest('[data-field]');
    }

    function labelTextOf(field) {
        const label = field.querySelector('label');
        return label ? label.textContent.replace(/\s*\(optional\)\s*/i, '').trim() : 'This field';
    }

    /* Native constraints, checked explicitly rather than via validationMessage so the
     * copy is ours and does not vary between browsers. */
    function nativeError(input, field) {
        const value = input.value.trim();
        if (input.hasAttribute('required') && !value) {
            return labelTextOf(field) + ' is required.';
        }
        if (!value) return '';

        const min = parseInt(input.getAttribute('minlength'), 10);
        if (min && value.length < min) {
            return 'Use at least ' + min + ' characters.';
        }
        const pattern = input.getAttribute('pattern');
        if (pattern && !new RegExp('^(?:' + pattern + ')$').test(value)) {
            return input.getAttribute('title') || 'Use a valid format.';
        }
        if (input.type === 'email' && input.validity.typeMismatch) {
            return 'Enter a valid email address.';
        }
        if (!input.checkValidity()) {
            return input.validationMessage;
        }
        return '';
    }

    function inputsOf(container) {
        return Array.prototype.slice
            .call(container.querySelectorAll('[data-field]'))
            .map(function (field) {
                return field.querySelector('input, select, textarea');
            })
            .filter(Boolean);
    }

    /* Wire up every [data-field] inside `container`.
     * `rules` maps an input name to fn(value, input) -> error string or ''. */
    function init(container, rules) {
        rules = rules || {};
        const inputs = inputsOf(container);

        function evaluate(input) {
            const field = fieldOf(input);
            const message = nativeError(input, field) ||
                (rules[input.name] ? rules[input.name](input.value, input) : '');
            return { field: field, message: message, empty: !input.value.trim() };
        }

        function paint(input) {
            const state = evaluate(input);
            const field = state.field;
            const errorNode = field.querySelector('.error');
            const optionalAndBlank = state.empty && !input.hasAttribute('required');

            if (!field.dataset[TOUCHED] || optionalAndBlank) {
                // Untouched, or an optional field left blank: no verdict either way.
                field.classList.remove(VALID, INVALID);
                if (errorNode) errorNode.textContent = '';
                input.removeAttribute('aria-invalid');
                return !state.message;
            }

            field.classList.toggle(INVALID, !!state.message);
            field.classList.toggle(VALID, !state.message);
            if (errorNode) errorNode.textContent = state.message;
            if (state.message) {
                input.setAttribute('aria-invalid', 'true');
            } else {
                input.removeAttribute('aria-invalid');
            }
            return !state.message;
        }

        inputs.forEach(function (input) {
            const field = fieldOf(input);
            const errorNode = field.querySelector('.error');

            if (errorNode) {
                if (!errorNode.id) errorNode.id = (input.id || input.name) + '-error';
                // Django may already point this at the help text; keep both.
                const described = (input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
                if (described.indexOf(errorNode.id) === -1) described.push(errorNode.id);
                input.setAttribute('aria-describedby', described.join(' '));
                // A message rendered by the server means this field already failed once.
                if (errorNode.textContent.trim()) {
                    field.dataset[TOUCHED] = '1';
                    field.classList.add(INVALID);
                    input.setAttribute('aria-invalid', 'true');
                }
            }

            input.addEventListener('blur', function () {
                field.dataset[TOUCHED] = '1';
                paint(input);
            });
            ['input', 'change'].forEach(function (event) {
                input.addEventListener(event, function () {
                    paint(input);
                    // A field may depend on another (confirm password on password).
                    inputs.forEach(function (other) {
                        if (other !== input && other.dataset.validateWith === input.name) {
                            paint(other);
                        }
                    });
                });
            });
        });

        container.validateAll = function () {
            let firstInvalid = null;
            inputs.forEach(function (input) {
                fieldOf(input).dataset[TOUCHED] = '1';
                if (!paint(input) && !firstInvalid) firstInvalid = input;
            });
            return firstInvalid;
        };

        return container.validateAll;
    }

    /* Returns the first invalid input in `container`, or null. Marks everything as
     * touched on the way through so nothing fails silently. */
    function validateAll(container) {
        return container.validateAll ? container.validateAll() : null;
    }

    window.formValidate = { init: init, validateAll: validateAll };
})();
