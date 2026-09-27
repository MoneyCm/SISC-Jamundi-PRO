import test from 'node:test';
import assert from 'node:assert/strict';
import { passwordIssues } from './passwordPolicy.js';

const base = { current: 'Actual-2026!', username: 'admin_sisc' };

test('acepta una contraseña que cumple la política', () => {
    assert.deepEqual(passwordIssues({ ...base, next: 'Jamundi-Seguro-2026', confirm: 'Jamundi-Seguro-2026' }), []);
});

test('exige longitud, variedad y confirmación', () => {
    const issues = passwordIssues({ ...base, next: 'corta', confirm: 'otra' });
    assert.ok(issues.some((i) => i.includes('12 caracteres')));
    assert.ok(issues.some((i) => i.includes('tres de estos')));
    assert.ok(issues.some((i) => i.includes('no coincide')));
});

test('no permite el usuario dentro ni repetir la actual', () => {
    assert.ok(passwordIssues({ ...base, next: 'Admin_Sisc-2026!', confirm: 'Admin_Sisc-2026!' }).some((i) => i.includes('usuario')));
    assert.ok(passwordIssues({ ...base, next: 'Actual-2026!', confirm: 'Actual-2026!' }).some((i) => i.includes('diferente')));
});

test('pide la contraseña actual', () => {
    assert.ok(passwordIssues({ username: 'x', next: 'Jamundi-Seguro-2026', confirm: 'Jamundi-Seguro-2026' }).some((i) => i.includes('actual')));
});
