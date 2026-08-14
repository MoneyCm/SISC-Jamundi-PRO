import test from 'node:test';
import assert from 'node:assert/strict';

import { institutionalSiscCifrasPeriods, suggestedSiscCifrasPeriod } from './siscCifrasPeriod.js';

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

test('six-month period covers the latest six calendar months through the cutoff', () => {
  assert.deepEqual(suggestedSiscCifrasPeriod(sources, 'semester'), {
    start: '2026-02-01',
    end: '2026-07-31',
  });
});

test('annual period is accumulated from January through the cutoff', () => {
  assert.deepEqual(suggestedSiscCifrasPeriod(sources, 'annual'), {
    start: '2026-01-01',
    end: '2026-07-31',
  });
});

test('institutional presets use closed calendar periods', () => {
  assert.deepEqual(institutionalSiscCifrasPeriods(sources), [
    {
      id: 'first_semester',
      edition: 'semester',
      label: 'Enero a junio de 2026',
      start: '2026-01-01',
      end: '2026-06-30',
    },
    {
      id: 'second_semester',
      edition: 'semester',
      label: 'Julio a diciembre de 2025',
      start: '2025-07-01',
      end: '2025-12-31',
    },
    {
      id: 'closed_year',
      edition: 'annual',
      label: 'Año completo 2025',
      start: '2025-01-01',
      end: '2025-12-31',
    },
  ]);
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
