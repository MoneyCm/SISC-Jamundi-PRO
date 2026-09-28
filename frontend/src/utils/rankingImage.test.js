import test from 'node:test';
import assert from 'node:assert/strict';
import { leyendaAutomatica, prepararRanking, recomendacionSugerida } from './rankingImage.js';

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

const base = { objetivo: 'Jamundí', conducta: 'Homicidio intencional', periodo: 'enero a agosto de 2026', alcance: 'Valle del Cauca y Cauca' };

test('la leyenda explica la tasa y usa solo cifras de la tabla', () => {
    const texto = leyendaAutomatica({ ...base, rows });
    assert.match(texto, /por cada 100\.000 habitantes/);
    assert.match(texto, /79 casos de homicidio intencional de enero a agosto de 2026/);
    assert.match(texto, /puesto 3 entre 3 municipios/);
    assert.match(texto, /Santander de Quilichao \(64,24\)/);
    assert.match(texto, /El más cercano por debajo es Palmira \(31,88\)/);
});

test('la recomendación cambia según la posición', () => {
    const medio = [...rows.slice(0, 3), { posicion: 4, municipio: 'Tuluá', casos: 59, tasa_por_100k: 26.12, diferencia_tasa_objetivo: -14.01 },
        { posicion: 5, municipio: 'Yumbo', casos: 29, tasa_por_100k: 25.07, diferencia_tasa_objetivo: -15.06 }]
        .map((r) => (r.municipio === 'Jamundí' ? { ...r, posicion: 3 } : r.municipio === 'Palmira' ? { ...r, posicion: 2 } : r));
    assert.match(recomendacionSugerida({ ...base, rows: medio }), /mitad de la tabla.*Yumbo/);
    const primero = rows.map((r) => (r.municipio === 'Jamundí' ? { ...r, posicion: 1, tasa_por_100k: 90 } : r));
    assert.match(recomendacionSugerida({ ...base, rows: primero }), /Consejo de Seguridad/);
    const ultimo = rows.map((r) => (r.municipio === 'Jamundí' ? { ...r, posicion: 9, tasa_por_100k: 1 } : r));
    assert.match(recomendacionSugerida({ ...base, rows: ultimo }), /menor tasa/);
});
