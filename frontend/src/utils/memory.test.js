import test from 'node:test';
import assert from 'node:assert/strict';
import { memoryQuery, OUTCOME_TONE } from './memory.js';

test('query only carries the filters in use', () => {
    assert.equal(memoryQuery({ q: '  motos ', kind: '', year: '' }), '?q=motos');
    assert.equal(memoryQuery({ q: '', kind: 'ESTUDIO', year: '2026' }), '?kind=ESTUDIO&year=2026');
    assert.equal(memoryQuery({ q: '', kind: '', year: '' }), '');
});

test('outcome tone flags rejections and unmeasured work', () => {
    assert.equal(OUTCOME_TONE('Rechazada: sin presupuesto'), 'text-amber-800');
    assert.equal(OUTCOME_TONE('Finalizada sin evaluar'), 'text-amber-800');
    assert.equal(OUTCOME_TONE('Cumplida'), 'text-emerald-800');
    assert.equal(OUTCOME_TONE('3 recomendaciones, 1 adoptadas'), 'text-slate-700');
});
