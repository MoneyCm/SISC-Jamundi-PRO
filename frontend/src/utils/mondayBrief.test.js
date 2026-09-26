import test from 'node:test';
import assert from 'node:assert/strict';
import { briefHeadline } from './mondayBrief.js';

test('headline counts what needs attention', () => {
    const answers = [{ level: 'ALTA' }, { level: 'ALTA' }, { level: 'MEDIA' }, { level: 'OK' }, { level: 'INFO' }];
    assert.equal(briefHeadline({ attention: 3, answers }),
        '3 de 8 piden atención; 2 son para actuar ya. Rojo: actuar ya · Ámbar: esta semana · Verde: al día.');
    assert.equal(briefHeadline({ attention: 0, answers: [{ level: 'OK' }] }), 'Las ocho respuestas están al día.');
});
