import test from 'node:test';
import assert from 'node:assert/strict';
import { localToday } from './localDate.js';

test('today is the local calendar day, not the UTC one', () => {
    // 25 de septiembre a las 8 p. m. en hora local: en UTC ya sería 26.
    assert.equal(localToday(new Date(2026, 8, 25, 20, 0)), '2026-09-25');
    assert.equal(localToday(new Date(2026, 0, 5, 0, 5)), '2026-01-05');
});
