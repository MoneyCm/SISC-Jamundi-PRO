import test from 'node:test';
import assert from 'node:assert/strict';
import { aniosCerrados, estadoSencillo, prepararMetas } from './metasImagen.js';

const anio = (valor, total, semaforo) => ({ anio: valor, total, semaforo, completo: Boolean(semaforo) });
const datos = {
    as_of: '2026-11-05',
    indicators: [
        { label: 'Homicidios', goal_2027: 105, count: 85, previous: 92, projection: 114, status: 'DESVIACION', cutoff: '2026-09-30', source: 'MinDefensa / Policía Nacional (víctimas, datos.gov.co)', closed_years: [anio(2024, 119, 'ROJO'), anio(2025, 127, 'ROJO')] },
        { label: 'Secuestro', goal_2027: 3, count: 7, previous: 2, projection: null, status: 'SUPERADA', cutoff: '2026-09-30', source: 'MinDefensa / Policía Nacional', closed_years: [anio(2024, 5, 'ROJO'), anio(2025, 5, 'ROJO')] },
        { label: 'Extorsión', goal_2027: 55, count: 41, previous: 33, projection: 55, status: 'EN_META', cutoff: '2026-09-30', source: 'MinDefensa / GAULA Policía', closed_years: [anio(2024, 63, 'ROJO'), anio(2025, 52, 'VERDE')] },
        { label: 'Lesiones personales', goal_2027: 430, count: 252, previous: 326, projection: 337, status: 'EN_META', cutoff: '2026-09-30', source: 'MinDefensa / Policía Nacional (víctimas, datos.gov.co)', closed_years: [anio(2024, 436, 'AMARILLO'), anio(2025, 401, 'VERDE')] },
        { label: 'Comportamientos contrarios a la convivencia', goal_2027: 4000, count: 4925, previous: 3718, status: 'SUPERADA', cutoff: '2026-11-02', source: 'RNMC / Inspecciones de Policía', closed_years: [anio(2024, 4802, null), anio(2025, 4126, 'AMARILLO')] },
    ],
};

test('plain status labels, with "al límite" near the goal', () => {
    assert.deepEqual(estadoSencillo({ status: 'SUPERADA' }), { color: 'rojo', etiqueta: 'Superó' });
    assert.deepEqual(estadoSencillo({ status: 'DESVIACION' }), { color: 'ambar', etiqueta: 'En riesgo' });
    assert.equal(estadoSencillo({ status: 'EN_META', goal_2027: 55, projection: 55 }).etiqueta, 'Al límite');
    assert.equal(estadoSencillo({ status: 'EN_META', goal_2027: 430, projection: 337 }).etiqueta, 'Bien');
    // Metas pequeñas: sin proyección, se mira el acumulado.
    assert.equal(estadoSencillo({ status: 'EN_META', goal_2027: 3, projection: null, count: 3 }).etiqueta, 'Al límite');
    assert.equal(estadoSencillo({ status: 'SIN_DATOS' }).etiqueta, 'Sin datos');
});

test('closed years keep their traffic light; incomplete years are gray', () => {
    const item = { closed_years: [anio(2024, 436, 'AMARILLO'), anio(2025, 4126, null)] };
    assert.deepEqual(aniosCerrados(item, [2024, 2025, 2023]), [
        { anio: 2024, total: 436, color: 'ambar', completo: true },
        { anio: 2025, total: 4126, color: 'gris', completo: false },
        { anio: 2023, total: null, color: 'gris', completo: false },
    ]);
});

test('rows go worst first, last two closed years, sources grouped by cutoff', () => {
    const { filas, fuentes, conteo, anio: actual, anios, incompletos } = prepararMetas(datos);
    assert.deepEqual(filas.map((f) => f.color), ['rojo', 'rojo', 'ambar', 'verde', 'verde']);
    assert.deepEqual(conteo, { rojo: 2, ambar: 1, verde: 2, gris: 0 });
    assert.equal(actual, '2026');
    assert.deepEqual(anios, [2024, 2025]);
    assert.deepEqual(filas.find((f) => f.indicador === 'Extorsión').anios.map((d) => d.color), ['rojo', 'verde']);
    assert.equal(incompletos, true);
    assert.equal(fuentes.length, 2);
    assert.match(fuentes[0], /^MinDefensa \/ Policía Nacional y MinDefensa \/ GAULA Policía, corte 30 de septiembre de 2026$/);
    assert.match(fuentes[1], /^RNMC \/ Inspecciones de Policía, corte 2 de noviembre de 2026$/);
});
