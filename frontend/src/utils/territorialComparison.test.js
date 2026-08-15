import assert from 'node:assert/strict';
import test from 'node:test';

import { buildPrioritizedTotalComparison } from './territorialComparison.js';

const comparison = (delito, periodEndMonth, rows) => ({
    delito,
    period_end_month: periodEndMonth,
    territorial_comparison: {
        rows,
        expected_municipalities: 2,
        cutoff: '2026-07-22'
    }
});

const jamundi = (casos) => ({
    codigo_dane: '76364',
    municipio: 'Jamundí',
    poblacion: 100000,
    casos,
    es_objetivo: true
});

const palmira = (casos) => ({
    codigo_dane: '76520',
    municipio: 'Palmira',
    poblacion: 200000,
    casos,
    es_objetivo: false
});

test('sums comparable prioritized conductas and recalculates municipal rates', () => {
    const result = buildPrioritizedTotalComparison([
        comparison('Hurto Personas', 12, [jamundi(10), palmira(30)]),
        comparison('Lesiones Personales', 12, [jamundi(20), palmira(10)])
    ]);

    assert.equal(result.label, 'Total de conductas priorizadas (2)');
    assert.equal(result.period_end_month, 12);
    assert.equal(result.territorial_comparison.observed_municipalities, 2);
    assert.deepEqual(
        result.territorial_comparison.rows.map(row => [row.municipio, row.casos, row.tasa_por_100k, row.posicion, row.diferencia_tasa_objetivo]),
        [
            ['Jamundí', 30, 30, 1, 0],
            ['Palmira', 40, 20, 2, -10]
        ]
    );
});

test('does not aggregate conductas with different period coverage', () => {
    const result = buildPrioritizedTotalComparison([
        comparison('Hurto Personas', 12, [jamundi(10), palmira(30)]),
        comparison('Lesiones Personales', 6, [jamundi(20), palmira(10)])
    ]);

    assert.equal(result, null);
});
