import test from 'node:test';
import assert from 'node:assert/strict';
import { formatDays, formatPct, monthLabel, reincidenceSummary } from './vifCases.js';

test('formatos', () => {
    assert.equal(formatPct(57.6), '57,6 %');
    assert.equal(formatPct(null), 'sin dato');
    assert.equal(formatDays(1), '1 día');
    assert.equal(formatDays(3.5), '3,5 días');
    assert.equal(monthLabel('2026-03'), 'mar 2026');
    assert.equal(monthLabel('2026-03', true), 'mar 26');
});

test('reincidencia: código de caso primero, luego la columna de la comisaría', () => {
    const byCode = reincidenceSummary({ cases_by_code: 33, repeated_by_code: 19, rate_by_code: 57.6, median_days_to_repeat: 39, flag_known: 60 });
    assert.equal(byCode.value, '57,6 %');
    assert.match(byCode.helper, /19 de 33 casos .* 39 días/);
    const byFlag = reincidenceSummary({ cases_by_code: 0, flag_known: 10, flag_yes: 4, rate_by_flag: 40 });
    assert.equal(byFlag.value, '40 %');
    assert.equal(reincidenceSummary({ cases_by_code: 0, flag_known: 0 }).value, 'sin dato');
});
