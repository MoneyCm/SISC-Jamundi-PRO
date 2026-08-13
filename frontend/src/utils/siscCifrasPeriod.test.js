import test from 'node:test';
import assert from 'node:assert/strict';

import { suggestedSiscCifrasPeriod } from './siscCifrasPeriod.js';

const sources = [
  { code: 'POLICIA_SEMANAL', last_cutoff_date: '2026-07-31' },
  { code: 'INSPECCIONES_RNMC', last_cutoff_date: '2026-03-10' },
  { code: 'COMISARIAS_FAMILIA', last_cutoff_date: '2025-09-30' },
];

test('monthly period uses the newest core source cutoff', () => {
  assert.deepEqual(suggestedSiscCifrasPeriod(sources, 'monthly'), {
    start: '2026-07-01',
    end: '2026-07-31',
  });
});

test('weekly period ends at the newest core source cutoff', () => {
  assert.deepEqual(suggestedSiscCifrasPeriod(sources, 'weekly'), {
    start: '2026-07-25',
    end: '2026-07-31',
  });
});

test('period falls back to the newest available complementary source', () => {
  assert.deepEqual(suggestedSiscCifrasPeriod([
    { code: 'COMISARIAS_FAMILIA', last_cutoff_date: '2026-04-30' },
    { code: 'OTRA_FUENTE', last_cutoff_date: '2026-06-15' },
  ], 'monthly'), {
    start: '2026-06-01',
    end: '2026-06-15',
  });
});
