import test from 'node:test';
import assert from 'node:assert/strict';
import { formatVersusLastYear, goalReading } from './pisccGoals.js';

test('comparison with last year is stated in cases', () => {
    assert.equal(formatVersusLastYear({ count: 78, previous: 79 }), '-1 frente al año pasado (79)');
    assert.equal(formatVersusLastYear({ count: 5, previous: 5 }), 'igual que el año pasado (5)');
    assert.equal(formatVersusLastYear({ count: 5, previous: null }), 'sin año anterior comparable');
});

test('small goals read the accumulated count, larger ones the pace', () => {
    assert.equal(goalReading({ status: 'EN_META', compares: 'acumulado', detail: 'Van 2 en lo corrido del año' }), 'Van 2 en lo corrido del año');
    assert.equal(goalReading({ status: 'DESVIACION', compares: 'proyeccion', projection: 112, goal_2027: 105 }), 'Ritmo anual ≈112 frente a meta 105.');
});
