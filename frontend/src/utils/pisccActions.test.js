import test from 'node:test';
import assert from 'node:assert/strict';
import { progressReading, reportPayload, semesterLabel } from './pisccActions.js';

test('semester label', () => {
    assert.equal(semesterLabel('2026-2'), 'Segundo semestre de 2026');
    assert.equal(semesterLabel('2025-1'), 'Primer semestre de 2025');
});

test('progress shows the semester report or flags the last one', () => {
    assert.deepEqual(progressReading({ goal: 24, progress_pct: 50, report: { value: 12 } }), { text: '12 de 24 · 50 %', tone: 'current' });
    assert.deepEqual(progressReading({ goal: 4, progress_pct: 25, report: null, last_report: { value: 1, semester: '2026-1' } }),
        { text: '1 de 4 · 25 % (último reporte: 2026-1)', tone: 'stale' });
    assert.deepEqual(progressReading({ goal: 1, report: null, last_report: null }), { text: 'Sin reportes', tone: 'empty' });
});

test('payload converts decimal comma and carries the version', () => {
    const payload = reportPayload({ value: '2,5', status: 'EN_EJECUCION', reporting_entity: 'AMSO', evidence: '', note: '', received_on: '' },
        { report: { version: 3 } });
    assert.equal(payload.value, 2.5);
    assert.equal(payload.expected_version, 3);
    assert.equal(payload.evidence, null);
    assert.equal(reportPayload({ value: '', status: 'SIN_INICIAR' }, { report: null }).expected_version, null);
});
