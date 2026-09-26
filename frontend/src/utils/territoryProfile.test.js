import test from 'node:test';
import assert from 'node:assert/strict';
import { formatChange, searchText } from './territoryProfile.js';

test('search ignores accents and case', () => {
    assert.equal(searchText('Río Claro'), 'rio claro');
    assert.ok(searchText('Ciudad Alfaguara').includes(searchText('ALFAGUARA')));
});

test('small bases show cases, larger ones percent', () => {
    assert.equal(formatChange({ difference: 5, variation_pct: null }), '+5 hechos');
    assert.equal(formatChange({ difference: -1, variation_pct: null }), '-1 hecho');
    assert.equal(formatChange({ difference: 0, variation_pct: null }), 'igual');
    assert.equal(formatChange({ difference: -11, variation_pct: -26.2 }), '-26,2%');
});
