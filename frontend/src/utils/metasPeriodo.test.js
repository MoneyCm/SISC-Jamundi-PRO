import test from 'node:test';
import assert from 'node:assert/strict';
import {
    csvMetasPeriodo, mesesResaltados, nombreArchivoMetas, opcionesDeTipo, textoAcumulado, textoCambio, textoReciente,
    tonoCambio, tonoRitmo,
} from './metasPeriodo.js';

test('lo ocurrido después del corte de MinDefensa, con su unidad', () => {
    const reciente = { since: 19, since_start: '2026-10-01', cutoff: '2026-11-06' };
    assert.equal(textoReciente({ id: 'homicidios', reciente }),
        'Después del corte de MinDefensa: +19 víctimas en la sábana de la Policía, del 2026-10-01 al 2026-11-06. No se suman a la cifra de arriba.');
    assert.match(textoReciente({ id: 'motos', reciente: { ...reciente, since: 1 } }), /\+1 hecho en la sábana/);
    assert.equal(textoReciente({ id: 'secuestro', reciente: null }), '');
});

test('ritmo y cambio: menos casos es verde', () => {
    assert.equal(tonoRitmo('EN_RITMO'), 'verde');
    assert.equal(tonoRitmo('SOBRE_RITMO'), 'rojo');
    assert.equal(tonoRitmo('SUPERADA'), 'rojo');
    assert.equal(tonoRitmo('SIN_REFERENCIA'), 'gris');
    assert.equal(tonoCambio({ diferencia: -9 }), 'verde');
    assert.equal(tonoCambio({ diferencia: 3 }), 'rojo');
    assert.equal(tonoCambio({ diferencia: null }), 'gris');
});

test('textos de cambio y acumulado', () => {
    assert.equal(textoCambio({ diferencia: -9, variacion_pct: -34.6 }), '9 menos (-34,6 %)');
    assert.equal(textoCambio({ diferencia: 3, variacion_pct: null }), '3 más');
    assert.equal(textoCambio({ diferencia: 0, variacion_pct: 0 }), 'Igual');
    assert.equal(textoCambio({}), '—');
    assert.equal(textoAcumulado({ year_to_date: 85, goal_2027: 105 }), '85 de 105');
    assert.equal(textoAcumulado({ year_to_date: null, goal_2027: 105 }), '—');
});

test('meses del periodo que se resaltan en la gráfica', () => {
    assert.deepEqual(mesesResaltados({ counted_from: '2026-07', counted_to: '2026-09' }), [6, 7, 8]);
    assert.deepEqual(mesesResaltados({ counted_from: '2025-11', counted_to: '2026-02' }), [0, 1]);
    assert.deepEqual(mesesResaltados({}), []);
});

test('opciones por tipo, CSV y nombre de archivo', () => {
    const opciones = [{ tipo: 'mes', label: 'Septiembre de 2026' }, { tipo: 'trimestre', label: 'Trimestre 3 de 2026' }];
    assert.deepEqual(opcionesDeTipo(opciones, 'trimestre').map((o) => o.label), ['Trimestre 3 de 2026']);
    const data = { periodo: 'julio a septiembre de 2026', desde: '2026-07', hasta: '2026-09', indicators: [{
        label: 'Homicidios', value: 17, previous: 26, diferencia: -9, variacion_pct: -34.6, year_to_date: 85,
        goal_2027: 105, baseline_2023: 115, year_to_date_reference: 78.8, status_label: 'Por encima del ritmo de la meta',
        months_requested: 3, months_counted: 3, source: 'MinDefensa / Policía Nacional (datos.gov.co), año completo',
        published_until: '2026-09' }] };
    const lineas = csvMetasPeriodo(data).split('\r\n');
    assert.equal(lineas.length, 2);
    assert.match(lineas[0], /^Indicador;Periodo;Casos en el periodo/);
    assert.match(lineas[1], /^Homicidios;julio a septiembre de 2026;17;26;-9;-34.6;85;78.8;105;115;Por encima/);
    assert.match(lineas[1], /"MinDefensa \/ Policía Nacional \(datos.gov.co\), año completo";2026-09$/);
    assert.equal(nombreArchivoMetas(data), 'sisc-jamundi-metas-piscc-2026-07_a_2026-09.csv');
    assert.equal(nombreArchivoMetas({ desde: '2026-09', hasta: '2026-09' }), 'sisc-jamundi-metas-piscc-2026-09.csv');
});
