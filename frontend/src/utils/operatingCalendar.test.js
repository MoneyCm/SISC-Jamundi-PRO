import test from 'node:test';
import assert from 'node:assert/strict';
import { councilText } from './operatingCalendar.js';

test('council text says when and where the date comes from', () => {
    assert.equal(councilText({ label: 'última semana de octubre (25 al 31)', days_to: -1, source: 'ESTIMADA' }),
        'Próximo Consejo de Seguridad: última semana de octubre (25 al 31), esta semana (estimado: el Consejo sesiona la última semana del mes).');
    assert.equal(councilText({ label: '28 de octubre', days_to: 1, source: 'REGISTRADA' }),
        'Próximo Consejo de Seguridad: 28 de octubre, mañana (fecha registrada).');
    assert.equal(councilText({ label: '28 de octubre', days_to: 12, source: 'REGISTRADA' }).includes('en 12 días'), true);
});
