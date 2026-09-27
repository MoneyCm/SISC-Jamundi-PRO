// Misma política que el backend (api/users.py::_validate_password_strength); el servidor vuelve a validar.

export const MIN_PASSWORD_LENGTH = 12;

export const passwordChecks = (password = '') => ({
    length: password.length >= MIN_PASSWORD_LENGTH,
    lower: /[a-z]/.test(password),
    upper: /[A-Z]/.test(password),
    digit: /\d/.test(password),
    symbol: /[^A-Za-z0-9]/.test(password),
});

export const passwordIssues = ({ current = '', next = '', confirm = '', username = '' }) => {
    const checks = passwordChecks(next);
    const kinds = [checks.lower, checks.upper, checks.digit, checks.symbol].filter(Boolean).length;
    const issues = [];
    if (!current) issues.push('Escriba su contraseña actual.');
    if (!checks.length) issues.push(`La nueva contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`);
    if (kinds < 3) issues.push('Combine al menos tres de estos: mayúsculas, minúsculas, números o símbolos.');
    if (username && next.toLowerCase().includes(username.toLowerCase())) issues.push('No puede contener su nombre de usuario.');
    if (next && current && next === current) issues.push('Debe ser diferente de la actual.');
    if (next !== confirm) issues.push('La confirmación no coincide.');
    return issues;
};
