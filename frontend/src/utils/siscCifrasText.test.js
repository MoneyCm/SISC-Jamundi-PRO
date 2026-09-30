import test from 'node:test';
import assert from 'node:assert/strict';
import { publicInsightText, buildWhatsappText } from './siscCifrasText.js';

test('simplifies a technical term without losing the figures or comparison', () => {
  const text = publicInsightText('MULTA GENERAL TIPO 4: 40 registros frente a 50 en el periodo anterior; disminuyo 20.0%.', 'periodo anterior');
  assert.match(text, /Comparendos con multa de mayor cuantía: 40 registros frente a 50/);
  assert.match(text, /disminuyó 20.0%/);
});

test('shared text identifies legacy unnamed figures and custom consultation', () => {
  const text = buildWhatsappText({
    insights: [{ title: 'Hurtos', detail: '25 registros en el periodo; sin base comparable.' }],
    comparison_period: { start: '2025-07-01', end: '2025-07-31' },
  }, 'https://example.org/boletines');
  assert.match(text, /Hurtos: 25 registros/);
  assert.match(text, /Consulta personalizada; no es una edición oficial/);
  assert.match(text, /2025-07-01 al 2025-07-31/);
  assert.doesNotMatch(text, /Boletín completo:/);
});

test('shared text distinguishes drafts and official editions and omits excluded sources', () => {
  const publication = {
    governance: { history_saved: true },
    sources: [{ name: 'Fuente excluida', publication_level: 'PUBLICO', included: false }],
  };
  assert.match(buildWhatsappText(publication, '/boletines'), /Borrador pendiente de aprobación/);
  const official = buildWhatsappText({ ...publication, status: 'PUBLISHED' }, '/boletines');
  assert.match(official, /Edición oficial publicada/);
  assert.doesNotMatch(official, /Fuente excluida|Borrador pendiente/);
});

test('empty source values are not published', () => {
  for (const value of ['NAN', 'nan', ' Sin especificar ', 'NULL']) assert.equal(publicInsightText(value), '');
});
