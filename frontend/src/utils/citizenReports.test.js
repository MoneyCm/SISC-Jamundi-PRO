import test from 'node:test';
import assert from 'node:assert/strict';
import { REPORT_ACTIONS, daysWaiting, waitingText } from './citizenReports.js';

test('closing and reopening need a note, starting does not', () => {
    assert.deepEqual(REPORT_ACTIONS.RECIBIDO.map((action) => [action.to, action.needsNote]), [['EN_GESTION', false], ['CERRADO', true]]);
    assert.deepEqual(REPORT_ACTIONS.CERRADO.map((action) => action.needsNote), [true]);
});

test('waiting time for open reports only', () => {
    assert.equal(daysWaiting('2026-02-19T20:27:18', '2026-09-26'), 219);
    assert.equal(waitingText({ estado: 'RECIBIDO', recibido: '2026-09-25T10:00:00' }, '2026-09-26'), '1 día abierto');
    assert.equal(waitingText({ estado: 'EN_GESTION', recibido: '2026-09-26T08:00:00' }, '2026-09-26'), 'Recibido hoy');
    assert.equal(waitingText({ estado: 'CERRADO', recibido: '2026-02-19T20:27:18' }, '2026-09-26'), '');
});
