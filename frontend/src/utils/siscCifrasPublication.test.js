import assert from 'node:assert/strict';
import test from 'node:test';
import { siscCifrasSelectionKey } from './siscCifrasPublication.js';

const baseSelection = {
  edition: 'monthly',
  periodStart: '2026-07-01',
  periodEnd: '2026-07-31',
  comparisonMode: 'year_over_year',
  sourceCodes: ['POLICIA_SEMANAL', 'INSPECCIONES_RNMC'],
};

test('the SISC cifras selection key ignores source order', () => {
  assert.equal(
    siscCifrasSelectionKey(baseSelection),
    siscCifrasSelectionKey({ ...baseSelection, sourceCodes: [...baseSelection.sourceCodes].reverse() })
  );
});

test('the SISC cifras selection key changes when the period changes', () => {
  assert.notEqual(
    siscCifrasSelectionKey(baseSelection),
    siscCifrasSelectionKey({ ...baseSelection, periodEnd: '2026-08-31' })
  );
});
