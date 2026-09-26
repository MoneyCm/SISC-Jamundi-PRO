import test from 'node:test';
import assert from 'node:assert/strict';
import { reviewLabel, sortFieldNotes, studyUpdate } from './studies.js';

test('field notes: newest first', () => {
    const notes = [
        { id: 'a', on_date: '2026-09-01', at: '1' },
        { id: 'b', on_date: '2026-09-10', at: '1' },
        { id: 'c', on_date: '2026-09-10', at: '2' },
    ];
    assert.deepEqual(sortFieldNotes(notes).map((note) => note.id), ['c', 'b', 'a']);
});

test('study update drops read-only fields, empties to null, clears pause reason', () => {
    const study = { id: 'x', code: 'OBS-1', version: 4, created_by: 'a', field_notes: [], title: 'T', status: 'EN_CURSO', status_note: 'viejo' };
    const body = studyUpdate(study, { findings: '', review_on: '' });
    assert.equal(body.expected_version, 4);
    assert.equal(body.findings, null);
    assert.equal(body.review_on, null);
    assert.equal(body.status_note, null);
    assert.equal('field_notes' in body || 'id' in body || 'code' in body, false);
    assert.equal(studyUpdate(study, { status: 'PAUSADO', status_note: 'Tercer estudio urgente' }).status_note, 'Tercer estudio urgente');
});

test('review label', () => {
    assert.equal(reviewLabel({ review_on: '2026-12-01' }, '2026-09-26'), 'Revisión posterior: 01/12/2026');
    assert.equal(reviewLabel({ review_on: '2026-09-01' }, '2026-09-26'), 'Revisión posterior pendiente');
    assert.equal(reviewLabel({}, '2026-09-26'), '');
});
