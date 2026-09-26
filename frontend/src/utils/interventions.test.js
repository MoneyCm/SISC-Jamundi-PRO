import test from 'node:test';
import assert from 'node:assert/strict';
import { allowedStages, describeWindow, missingFor } from './interventions.js';

test('each stage asks for what the backend will require', () => {
    assert.deepEqual(missingFor({}, 'BORRADOR'), []);
    assert.equal(missingFor({}, 'DECIDIDA').length, 5);
    const decided = { recommendation: 'r', decision: 'd', responsible: 'p', decision_date: '2026-06-01', deadline: '2026-07-01' };
    assert.deepEqual(missingFor(decided, 'EN_EJECUCION'), ['qué se hizo', 'fecha de inicio']);
    assert.deepEqual(missingFor({ ...decided, intervention: 'x', started_on: '2026-06-02', completed_on: '2026-06-20' }, 'FINALIZADA'), ['al menos una evidencia']);
    assert.deepEqual(allowedStages('DECIDIDA').map((stage) => stage.code), ['DECIDIDA', 'EN_EJECUCION']);
});

test('follow-up windows use cases for small bases and percent otherwise', () => {
    assert.equal(describeWindow({ status: 'MEDIDO', before: 10, after: 19, difference: 9, variation_pct: null }), '10 → 19 (+9 hechos)');
    assert.equal(describeWindow({ status: 'MEDIDO', before: 43, after: 57, difference: 14, variation_pct: 32.6 }), '43 → 57 (+32,6%)');
    assert.equal(describeWindow({ status: 'PENDIENTE', detail: 'Se podrá medir desde el 01/10/2026.' }), 'Se podrá medir desde el 01/10/2026.');
});
