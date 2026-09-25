import test from 'node:test';
import assert from 'node:assert/strict';
import { groupSignals, nextRecommendationSteps } from './observatory.js';

test('signals are grouped in backend order with the urgent ones first', () => {
    const overview = {
        groups: [{ key: 'DATOS', label: 'Datos' }, { key: 'TERRITORIO', label: 'Territorio' }, { key: 'CONOCIMIENTO', label: 'Conocimiento' }],
        signals: [
            { key: 'a', group: 'TERRITORIO', level: 'OK' },
            { key: 'b', group: 'DATOS', level: 'MEDIA' },
            { key: 'c', group: 'TERRITORIO', level: 'ALTA' },
        ],
    };
    const groups = groupSignals(overview);
    assert.deepEqual(groups.map((group) => group.key), ['DATOS', 'TERRITORIO']);
    assert.deepEqual(groups[1].signals.map((item) => item.key), ['c', 'a']);
    assert.deepEqual(groupSignals(null), []);
});

test('a recommendation only moves forward and closes when rejected or fulfilled', () => {
    assert.deepEqual(nextRecommendationSteps('PROPUESTA'), ['PRESENTADA']);
    assert.deepEqual(nextRecommendationSteps('PRESENTADA'), ['ACEPTADA', 'RECHAZADA']);
    assert.deepEqual(nextRecommendationSteps('RECHAZADA'), []);
    assert.deepEqual(nextRecommendationSteps('CUMPLIDA'), []);
});
