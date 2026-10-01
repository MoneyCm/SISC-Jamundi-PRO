import test from 'node:test';
import assert from 'node:assert/strict';
import { fechaCorta, semaforoMeta, textoMeta, textoPuesto } from './metasPublicas.js';

test('semáforo de las metas', () => {
    assert.equal(semaforoMeta('EN_META'), 'verde');
    assert.equal(semaforoMeta('DESVIACION'), 'amarillo');
    assert.equal(semaforoMeta('SUPERADA'), 'rojo');
    assert.equal(semaforoMeta('PRELIMINAR'), 'gris');
});

test('textos de fecha, meta y puesto', () => {
    assert.equal(fechaCorta('2026-08-31'), '31 de agosto de 2026');
    assert.match(textoMeta({ goal_2027: 105, baseline_2023: 115 }), /meta 2027: 105 · línea base 2023: 115/);
    assert.equal(textoPuesto({ puesto: 19, de: 42 }), 'Jamundí ocupa el puesto 19 de 42 municipios del Valle (el 1 es la tasa más alta).');
    assert.equal(textoPuesto({}), '');
});
