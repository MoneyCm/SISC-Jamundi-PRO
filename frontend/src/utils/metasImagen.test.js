import test from 'node:test';
import assert from 'node:assert/strict';
import { estadoSencillo, frenteAnioPasado, prepararMetas } from './metasImagen.js';

const datos = {
    as_of: '2026-11-05',
    indicators: [
        { label: 'Homicidios', goal_2027: 105, count: 85, previous: 92, projection: 114, status: 'DESVIACION', cutoff: '2026-09-30', source: 'MinDefensa / Policía Nacional (víctimas, datos.gov.co)' },
        { label: 'Secuestro', goal_2027: 3, count: 7, previous: 2, projection: null, status: 'SUPERADA', cutoff: '2026-09-30', source: 'MinDefensa / Policía Nacional' },
        { label: 'Extorsión', goal_2027: 55, count: 41, previous: 33, projection: 55, status: 'EN_META', cutoff: '2026-09-30', source: 'MinDefensa / GAULA Policía' },
        { label: 'Lesiones personales', goal_2027: 430, count: 252, previous: 326, projection: 337, status: 'EN_META', cutoff: '2026-09-30', source: 'MinDefensa / Policía Nacional (víctimas, datos.gov.co)' },
        { label: 'Comportamientos contrarios a la convivencia', goal_2027: 4000, count: 4925, previous: 3718, status: 'SUPERADA', cutoff: '2026-11-02', source: 'RNMC / Inspecciones de Policía' },
    ],
};

test('plain status labels, with "al límite" near the goal', () => {
    assert.deepEqual(estadoSencillo({ status: 'SUPERADA' }), { color: 'rojo', etiqueta: 'Superó la meta' });
    assert.deepEqual(estadoSencillo({ status: 'DESVIACION' }), { color: 'ambar', etiqueta: 'En riesgo' });
    assert.equal(estadoSencillo({ status: 'EN_META', goal_2027: 55, projection: 55 }).etiqueta, 'Bien (al límite)');
    assert.equal(estadoSencillo({ status: 'EN_META', goal_2027: 430, projection: 337 }).etiqueta, 'Bien');
    // Metas pequeñas: sin proyección, se mira el acumulado.
    assert.equal(estadoSencillo({ status: 'EN_META', goal_2027: 3, projection: null, count: 3 }).etiqueta, 'Bien (al límite)');
    assert.equal(estadoSencillo({ status: 'SIN_DATOS' }).etiqueta, 'Sin datos');
});

test('difference against last year in words', () => {
    assert.equal(frenteAnioPasado({ count: 85, previous: 92 }), '▼ 7 menos');
    assert.equal(frenteAnioPasado({ count: 4925, previous: 3718 }), '▲ 1.207 más');
    assert.equal(frenteAnioPasado({ count: 5, previous: 5 }), 'igual');
    assert.equal(frenteAnioPasado({ count: 5, previous: null }), '—');
});

test('rows go worst first and sources are grouped by cutoff', () => {
    const { filas, fuentes, conteo, anio } = prepararMetas(datos);
    assert.deepEqual(filas.map((f) => f.color), ['rojo', 'rojo', 'ambar', 'verde', 'verde']);
    assert.deepEqual(conteo, { rojo: 2, ambar: 1, verde: 2, gris: 0 });
    assert.equal(anio, '2026');
    assert.equal(fuentes.length, 2);
    assert.match(fuentes[0], /^MinDefensa \/ Policía Nacional y MinDefensa \/ GAULA Policía, corte 30 de septiembre de 2026$/);
    assert.match(fuentes[1], /^RNMC \/ Inspecciones de Policía, corte 2 de noviembre de 2026$/);
});
