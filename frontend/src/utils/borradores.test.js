import test from 'node:test';
import assert from 'node:assert/strict';
import { etiquetaEdicion, textoBorrador } from './borradores.js';

test('nombres de edición legibles', () => {
    assert.equal(etiquetaEdicion('monthly'), 'Mensual');
    assert.equal(etiquetaEdicion('otro'), 'otro');
    assert.equal(textoBorrador({ edition_type: 'weekly', period_start: '2026-09-20', period_end: '2026-09-26' }),
        'semanal del 2026-09-20 al 2026-09-26');
});
