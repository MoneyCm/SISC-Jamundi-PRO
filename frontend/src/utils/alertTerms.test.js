import test from 'node:test';
import assert from 'node:assert/strict';
import { ALERT_TERMS, termLabel } from './alertTerms.js';

test('four distinct terms, only the Defensoría issues Alertas Tempranas', () => {
    assert.equal(ALERT_TERMS.length, 4);
    assert.equal(new Set(ALERT_TERMS.map((term) => term.label)).size, 4);
    const early = ALERT_TERMS.filter((term) => term.label.includes('Alerta Temprana'));
    assert.deepEqual(early.map((term) => term.key), ['DEFENSORIA']);
    assert.equal(termLabel('SENAL'), 'Señal estadística');
});
