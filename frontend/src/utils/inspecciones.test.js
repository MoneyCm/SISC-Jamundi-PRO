import test from 'node:test';
import assert from 'node:assert/strict';
import { etiquetaInspeccion, porcentajeResuelto, millones } from './inspecciones.js';

test('inspection names read as words', () => {
    assert.equal(etiquetaInspeccion('SEGUNDA'), 'Segunda');
    assert.equal(etiquetaInspeccion('tercera'), 'Tercera');
    assert.equal(etiquetaInspeccion('SIN IDENTIFICAR'), 'Sin identificar');
    assert.equal(etiquetaInspeccion(null), 'Sin identificar');
});

test('resolved share counts paid, ratified and not imposed measures', () => {
    assert.equal(porcentajeResuelto({ pagadas: 99, ratificadas: 0, no_impuestas: 37, en_proceso: 8, otras: 32 }), 77);
    assert.equal(porcentajeResuelto({}), 0);
});

test('money in millions of pesos', () => {
    assert.equal(millones(45107193), '$45,1 M');
    assert.equal(millones(0), '$0,0 M');
});
