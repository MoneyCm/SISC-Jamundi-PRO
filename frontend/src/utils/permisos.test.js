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

test('el gestor de actas archiva actas pero no hace seguimiento', async () => {
    const { puedeGestionarActas, puedeHacerSeguimiento } = await import('./permisos.js');
    assert.equal(puedeGestionarActas(['ACTAS_OPERATOR', 'SOURCE_UPLOADER']), true);
    assert.equal(puedeHacerSeguimiento(['ACTAS_OPERATOR', 'SOURCE_UPLOADER']), false);
    assert.equal(puedeHacerSeguimiento(['DIRECTIVE']), true);
});
