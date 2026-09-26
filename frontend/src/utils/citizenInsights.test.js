import test from 'node:test';
import assert from 'node:assert/strict';
import {
    buildCitizenInsights,
    filtersToSearchParams,
    formatVariation,
    parsePublicFilters,
} from './citizenInsights.js';

test('public filters round-trip through shareable query parameters', () => {
    const filters = {
        year: '2025',
        periodMode: 'custom',
        comparison: 'previous_period',
        startDate: '2025-03-01',
        endDate: '2025-03-31',
        conducta: 'HURTO_PERSONAS',
        zona: 'URBANA',
        territorio: 'TERRANOVA',
    };
    const params = filtersToSearchParams(filters, 'transparency');
    assert.equal(params.get('page'), 'transparency');
    assert.deepEqual(parsePublicFilters(`?${params}`), filters);
});

test('invalid filter modes fall back to public defaults', () => {
    const filters = parsePublicFilters('?period=anything&compare=unknown');
    assert.equal(filters.periodMode, 'year_to_date');
    assert.equal(filters.comparison, 'same_period_previous_year');
});

test('insights are deterministic and explain the comparison base', () => {
    const data = {
        metadata: { comparison_label: 'Mismo periodo del año anterior' },
        kpis: { total_hechos: 90, previous_total: 100, variation_pct: -10 },
        conductas: [
            { name: 'Hurto a personas', value: 30, previous_value: 20, difference: 10, variation_pct: 50 },
            { name: 'Lesiones personales', value: 15, previous_value: 18, difference: -3, variation_pct: -16.7 },
        ],
        weekly_trend: [{ name: 'S10', total: 8 }, { name: 'S11', total: 5 }],
        territories: [{ name: 'TERRANOVA', total: 12 }],
    };
    const insights = buildCitizenInsights(data, 4);
    assert.equal(insights.length, 4);
    assert.match(insights[0].summary, /90 casos, frente a 100/);
    assert.equal(insights[1].title, 'Hurto a personas');
    assert.match(insights[2].summary, /3 casos menos/);
    assert.equal(insights[3].title, 'TERRANOVA');
});

test('missing comparison produces an honest label', () => {
    assert.equal(formatVariation(null), 'Sin base comparable');
});

test('weekly insight uses the last complete week and skips non-consecutive weeks', () => {
    const base = { metadata: {}, kpis: { total_hechos: 10, previous_total: 10 }, conductas: [], territories: [] };
    const week = (name, start, total, complete = true, preliminary = false) => ({ name, start, total, complete, preliminary });
    const ongoing = buildCitizenInsights({ ...base, weekly_trend: [week('S35', '2026-08-24', 30), week('S36', '2026-08-31', 16, true, true), week('S37', '2026-09-07', 11, false, true)] }, 4)
        .find((item) => item.id === 'latest-week');
    assert.equal(ongoing.title, 'S36: 16 casos');
    assert.match(ongoing.summary, /14 casos menos/);
    assert.match(ongoing.summary, /preliminar/);
    assert.match(ongoing.summary, /S37 sigue en curso/);
    const gap = buildCitizenInsights({ ...base, weekly_trend: [week('S32', '2026-08-03', 2), week('S34', '2026-08-17', 1)] }, 4)
        .find((item) => item.id === 'latest-week');
    assert.match(gap.summary, /No hay una semana anterior completa/);
});
