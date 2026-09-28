import test from 'node:test';
import assert from 'node:assert/strict';
import { prepararRanking } from './rankingImage.js';

const rows = [
    { posicion: 1, municipio: 'Santander de Quilichao', casos: 84, tasa_por_100k: 64.24, diferencia_tasa_objetivo: 24.11 },
    { posicion: 3, municipio: 'Jamundí', casos: 79, tasa_por_100k: 40.13, es_objetivo: true },
    { posicion: 5, municipio: 'Palmira', casos: 122, tasa_por_100k: 31.88, diferencia_tasa_objetivo: -8.25 },
    { posicion: null, municipio: 'Sin dato', casos: null, tasa_por_100k: null },
];

test('incluye todas las filas con tasa y destaca el municipio objetivo', () => {
    const r = prepararRanking({ rows, objetivo: 'Jamundí' });
    assert.equal(r.total, 3);
    assert.deepEqual(r.objetivo, { posicion: 3, municipio: 'Jamundí', tasa: 40.13, casos: 79 });
    assert.equal(r.filas[0].proporcion, 1);
    assert.equal(r.filas[1].diferencia, null);
    assert.equal(r.filas[2].diferencia, -8.25);
});
