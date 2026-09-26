import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultRequest, previousMonth, previousWeek, stateDetail } from './dataRequests.js';

test('previous week runs Monday to Sunday', () => {
    assert.deepEqual(previousWeek('2026-09-28'), { start: '2026-09-21', end: '2026-09-27' }); // lunes
    assert.deepEqual(previousWeek('2026-09-27'), { start: '2026-09-14', end: '2026-09-20' }); // domingo
});

test('previous month is the full calendar month', () => {
    assert.deepEqual(previousMonth('2026-03-05'), { start: '2026-02-01', end: '2026-02-28' });
    assert.deepEqual(previousMonth('2026-01-10'), { start: '2025-12-01', end: '2025-12-31' });
});

test('default request depends on cadence and gives three days', () => {
    const weekly = defaultRequest('2026-09-28');
    assert.equal(weekly.due_on, '2026-10-01');
    assert.equal(weekly.period_start, '2026-09-21');
    assert.equal(defaultRequest('2026-10-02', 'MENSUAL').period_end, '2026-09-30');
});

test('state detail reads dates as day/month', () => {
    assert.equal(stateDetail({ state: 'ATRASADA', open_since: '2026-09-21', due_on: '2026-09-24' }), 'Pedido el 21/09; el plazo venció el 24/09.');
    assert.equal(stateDetail({ state: 'TOCA_PEDIR', last_received: null }), 'Sin solicitudes registradas.');
});
