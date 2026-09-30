import test from 'node:test';
import assert from 'node:assert/strict';
import { puedePublicar } from './permisos.js';

test('solo la Secretaria (permiso Publica boletines) y la administración publican', () => {
    assert.equal(puedePublicar(['DIRECTIVE', 'PUBLICATION_APPROVER']), true);
    assert.equal(puedePublicar(['FUNC_ADMIN']), true);
    assert.equal(puedePublicar(['DIRECTIVE']), false);
    assert.equal(puedePublicar(['ANALYST']), false);
    assert.equal(puedePublicar([]), false);
});
