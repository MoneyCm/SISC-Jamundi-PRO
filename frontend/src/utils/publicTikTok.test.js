import test from 'node:test';
import assert from 'node:assert/strict';
import { buildTikTokStory, tikTokCandidates, tikTokScript, tikTokSubtitles, drawTikTokFrame } from './publicTikTok.js';

const fixture = () => ({
  status: 'PUBLISHED', period: { start: '2026-08-01', end: '2026-08-31' },
  comparison_period: { start: '2025-08-01', end: '2025-08-31' },
  sources: [{ code: 'POLICIA_SEMANAL', name: 'Policía Nacional', publication_level: 'PUBLICO', included: true, publishable: true }],
  indicators: [{ id: 'hurto', indicator_name: 'Hurto a personas', publication_level: 'PUBLICO', quality_status: 'VALIDADO',
    value: 40, comparison_value: 50, source_code: 'POLICIA_SEMANAL', source: 'Policía Nacional', unit: 'registros',
    period_start: '2026-08-01', period_end: '2026-08-31', cutoff_date: '2026-09-15' }],
});

test('only approved public data from the actual period can become a TikTok', () => {
  const pub = fixture();
  assert.equal(tikTokCandidates(pub).length, 1);
  for (const status of ['DRAFT', undefined]) assert.equal(tikTokCandidates({ ...pub, status }).length, 0);
  for (const change of [{ publication_level: 'INTERNO' }, { value: null }, { value: NaN }, { geography: 'Centro' },
    { period_start: '2026-01-01' }, { metadata: { coverage_type: 'CONTEXT' } }, { cutoff_date: null }]) {
    assert.equal(tikTokCandidates({ ...pub, indicators: [{ ...pub.indicators[0], ...change }] }).length, 0);
  }
  assert.equal(tikTokCandidates({ ...pub, sources: [{ ...pub.sources[0], included: false }] }).length, 0);
  assert.equal(tikTokCandidates({ ...pub, governance: { review_blockers: ['Pendiente'] } }).length, 0);
});

test('one story keeps exact counts, dates, source and sequential subtitles', () => {
  const story = buildTikTokStory(fixture());
  assert.equal(story.value, 40); assert.equal(story.previous, 50);
  assert.equal(story.change, '10 registros menos');
  assert.equal(story.scenes.length, 5); assert.equal(story.scenes.at(-1).end, 30);
  assert.match(tikTokScript(story), /2025-08-01 al 2025-08-31/);
  assert.match(tikTokScript(story), /no incluye voz/);
  assert.match(tikTokSubtitles(story), /00:00:24,000 --> 00:00:30,000/);
  assert.match(tikTokScript(story), /Policía Nacional/);
});

test('zero and unavailable comparison are distinct and preliminary warnings persist', () => {
  const pub = fixture(); pub.indicators[0].comparison_value = 0;
  assert.equal(buildTikTokStory(pub).previous, 0);
  pub.indicators[0].comparison_value = null;
  assert.equal(buildTikTokStory(pub).previous, null);
  assert.match(buildTikTokStory(pub).scenes[2].narration, /No podemos afirmar/);
  pub.indicators[0].cutoff_date = '2026-09-01';
  assert.equal(buildTikTokStory(pub).preliminary, true);
  assert.match(buildTikTokStory(pub).scenes[3].narration, /preliminar/);
});

test('every animation scene retains the source and unmodified numeric values', () => {
  const texts = [];
  const context = new Proxy({ measureText: (value) => ({ width: value.length * 20 }), fillText: (value) => texts.push(value) }, {
    get: (target, name) => target[name] || (() => {}),
  });
  const story = buildTikTokStory(fixture());
  for (const seconds of [0, 4.5, 11.5, 18.5, 24.5, 30]) {
    texts.length = 0;
    drawTikTokFrame(context, story, seconds);
    assert.ok(texts.some((text) => text.includes('Corte 2026-09-15')));
    assert.ok(texts.some((text) => text.includes('2026-08-01 al 2026-08-31')));
  }
});
