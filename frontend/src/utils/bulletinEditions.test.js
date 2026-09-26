import test from 'node:test';
import assert from 'node:assert/strict';
import { bulletinPeriod, editionLabel, groupByEdition } from './bulletinEditions.js';

test('a full-month monthly bulletin reads as the month', () => {
    assert.equal(bulletinPeriod({ edition_type: 'monthly', period_start: '2026-08-01', period_end: '2026-08-31' }), 'Agosto de 2026');
    assert.equal(bulletinPeriod({ edition_type: 'monthly', period_start: '2026-02-01', period_end: '2026-02-28' }), 'Febrero de 2026');
});

test('weeks and partial periods show their dates', () => {
    assert.equal(bulletinPeriod({ edition_type: 'weekly', period_start: '2026-09-06', period_end: '2026-09-12' }), 'Del 6 al 12 de septiembre de 2026');
    assert.equal(bulletinPeriod({ edition_type: 'weekly', period_start: '2026-08-30', period_end: '2026-09-05' }), 'Del 30 de agosto de 2026 al 5 de septiembre de 2026');
    assert.equal(bulletinPeriod({ edition_type: 'monthly', period_start: '2026-09-01', period_end: '2026-09-20' }), 'Del 1 al 20 de septiembre de 2026');
});

test('bulletins are grouped monthly first, weekly next, unknown last', () => {
    const rows = [
        { id: 'w1', edition_type: 'weekly' }, { id: 'm1', edition_type: 'monthly' },
        { id: 'w2', edition_type: 'weekly' }, { id: 'x', edition_type: 'special' },
    ];
    const groups = groupByEdition(rows);
    assert.deepEqual(groups.map((group) => group.group), ['Mensuales', 'Semanales', 'Otros']);
    assert.deepEqual(groups[1].items.map((row) => row.id), ['w1', 'w2']);
    assert.equal(editionLabel('monthly'), 'Boletín mensual');
    assert.equal(editionLabel('special'), 'Boletín');
});
