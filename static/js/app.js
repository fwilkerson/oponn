document.addEventListener('DOMContentLoaded', () => {
    const initValidation = (container) => {
        if (!container || !container.querySelectorAll) return;
        
        container.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('invalid', (e) => {
                e.preventDefault();
                
                if (input.type === 'radio') {
                    const group = input.closest('.radio-group');
                    const name = input.name;
                    if (group && name) {
                        group.querySelectorAll(`input[name="${name}"]`).forEach(radio => {
                            radio.classList.add('invalid');
                            const label = radio.closest('.radio-label');
                            if (label) label.classList.add('invalid');
                            
                            const item = radio.closest('.radio-item');
                            if (item) {
                                let errorDiv = item.querySelector('.field-error-msg');
                                if (!errorDiv) {
                                    errorDiv = document.createElement('div');
                                    errorDiv.className = 'field-error-msg';
                                    item.appendChild(errorDiv);
                                }
                                errorDiv.textContent = input.validationMessage;
                            }
                        });
                    }
                    return;
                }
                
                input.classList.add('invalid');
                const parent = input.parentElement;
                if (!parent) return;
                
                let errorDiv = parent.querySelector('.field-error-msg');
                if (!errorDiv) {
                    errorDiv = document.createElement('div');
                    errorDiv.className = 'field-error-msg';
                    parent.appendChild(errorDiv);
                }
                errorDiv.textContent = input.validationMessage;
            });

            input.addEventListener('input', () => {
                if (input.validity.valid) {
                    if (input.type === 'radio') {
                        const group = input.closest('.radio-group');
                        const name = input.name;
                        if (group && name) {
                            group.querySelectorAll(`input[name="${name}"]`).forEach(radio => {
                                radio.classList.remove('invalid');
                                const label = radio.closest('.radio-label');
                                if (label) label.classList.remove('invalid');
                                const item = radio.closest('.radio-item');
                                if (item) {
                                    const errorDiv = item.querySelector('.field-error-msg');
                                    if (errorDiv) errorDiv.remove();
                                }
                            });
                        }
                        return;
                    }

                    input.classList.remove('invalid');
                    const parent = input.parentElement;
                    if (parent) {
                        const errorDiv = parent.querySelector('.field-error-msg');
                        if (errorDiv) errorDiv.remove();
                    }
                }
            });
        });
    };

    // Use htmx.onLoad if available, otherwise just init body
    if (typeof htmx !== 'undefined') {
        htmx.onLoad((content) => {
            initValidation(content);
        });
    } else {
        initValidation(document.body);
    }
});
