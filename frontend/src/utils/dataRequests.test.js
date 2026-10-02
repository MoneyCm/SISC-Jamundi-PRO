import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultRequest, previousMonth, previousWeek, reminderMessage, reminderSummary, stateDetail } from './dataRequests.js';

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

test('reminder message and summary', () => {
    const request = { what: 'Informe mensual de gestión', period_start: '2026-08-01', period_end: '2026-08-31',
        requested_on: '2026-09-25', due_on: '2026-09-28', reminders: 0 };
    const text = reminderMessage({ name: 'Comisaría Primera de Familia' }, request);
    assert.match(text, /^Buen día, Comisaría Primera de Familia\./);
    assert.match(text, /el 25 de septiembre de 2026 le pedimos: Informe mensual de gestión, del 1 de agosto de 2026 al 31 de agosto de 2026\./);
    assert.match(text, /El plazo de respuesta era el 28 de septiembre de 2026/);
    assert.doesNotMatch(text, /Ya le habíamos escrito/);
    assert.match(reminderMessage({ name: 'X' }, { ...request, reminders: 1 }), /Ya le habíamos escrito antes/);
    assert.equal(reminderSummary({ reminders: 0 }), '');
    assert.equal(reminderSummary({ reminders: 1, last_reminded_on: '2026-10-01' }), 'Recordado el 01/10');
    assert.equal(reminderSummary({ reminders: 3, last_reminded_on: '2026-10-01' }), 'Recordado 3 veces, la última el 01/10');
});
