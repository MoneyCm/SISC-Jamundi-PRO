import test from 'node:test';
import assert from 'node:assert/strict';
import { buildLightSlides, describeChange, lightSlideSvg, shortDate } from './executiveLight.js';

const indicator = (code, name, value, comparison, extra = {}) => ({
  indicator_code: code, indicator_name: name, value, comparison_value: comparison, ...extra,
});
const publication = {
  period: { start: '2026-09-06', end: '2026-09-12' },
  comparison_period: { start: '2025-09-06', end: '2025-09-12' },
  sources: [{ last_cutoff_date: '2026-09-12' }],
  indicators: [
    indicator('seguridad.total', 'Total de hechos registrados', 18, 26),
    indicator('seguridad.conducta.Hurto a personas', 'Hurto a personas', 11, 8),
    indicator('seguridad.conducta.Homicidio', 'Homicidio', 1, 1),
    indicator('seguridad.conducta.Hurto a residencias', 'Hurto a residencias', 3, 4),
    indicator('seguridad.conducta.Lesiones personales', 'Lesiones personales', 1, 8),
    // Contexto de otro periodo y territorio: no entran en "Cómo vamos".
    indicator('familia.indicador.X', 'Medidas de protección', 69, null, { metadata: { coverage_type: 'CONTEXT' } }),
    indicator('seguridad.barrio.Centro', 'Centro', 40, 20, { geography: 'Centro' }),
  ],
};

test('small bases show case differences, not percentages', () => {
  assert.deepEqual(describeChange(11, 8), { tone: 'up', arrow: '▲', text: '+3 casos (antes 8)', smallBase: true });
  assert.equal(describeChange(120, 100).text, '+20 % (antes 100)');
  assert.equal(describeChange(80, 100).tone, 'down');
  assert.equal(describeChange(5, 0).text, '+5 casos (antes 0)');
  assert.equal(describeChange(4, null).text, 'sin comparativo');
  assert.equal(describeChange(7, 7).text, 'igual que antes (7)');
});

test('slide 1: total plus the three conducts with most cases, without context or territory rows', () => {
  const { slides, draft } = buildLightSlides({ publication });
  const [howWeAre] = slides;
  assert.equal(draft, false);
  // El homicidio va siempre (1 caso), antes que conductas con más casos.
  assert.deepEqual(howWeAre.tiles.map((tile) => tile.label), ['Total de hechos', 'Homicidio', 'Hurto a personas', 'Hurto a residencias']);
  assert.match(howWeAre.footer, /12 sept 2026/);
  assert.match(howWeAre.note, /menos de 30 casos/);
  assert.equal(describeChange(35, 20).text, '+15 casos (antes 20)');
  assert.equal(describeChange(45, 30).text, '+50 % (antes 30)');
});

test('slide 2 uses year-to-date territories and only alerts in force', () => {
  const sat = {
    status: 'OK',
    generated_for: { current_year: 2026, previous_year: 2025, window_label: '1 de enero al 12 de septiembre de cada año' },
    territories: [
      { name: 'Potrerito', series: { 2025: 20, 2026: 35 }, top_conductas: [{ label: 'Hurto de Vehiculos', total: 9 }] },
      { name: 'Centro', series: { 2025: 40, 2026: 30 }, top_conductas: [] },
    ],
    groups: [
      { key: 'AT', series: { 2025: 60, 2026: 65 } },
      { key: 'URBANO', series: { 2025: 900, 2026: 850 } },
      { key: 'RURAL_NO_AT', series: { 2025: 40, 2026: 50 } },
    ],
    alerts: [
      { numero: '005-24', tipo: 'Inminencia', estado: 'Vigente según el documento', ambito: 'Media y alta montaña' },
      { numero: '037-18', tipo: 'Estructural', estado: 'Subsumida por la 005-24' },
    ],
  };
  const where = buildLightSlides({ publication, sat }).slides[1];
  assert.equal(where.rows[0].label, 'Potrerito');
  assert.equal(where.rows[0].change.text, '+15 casos (antes 20)');
  assert.equal(where.rows[0].detail, 'Más común: hurto de motos y carros (9 de 35)');
  assert.equal(where.alertCount, 1);
  assert.match(where.subtitle, /Zonas señaladas por la Defensoría/);
  assert.equal(where.title, 'ZONAS CON ALERTA TEMPRANA (DEFENSORÍA)');
  assert.equal(where.comparison.zone.text, '+8 % (antes 60)');
  assert.equal(where.comparison.restValue, 900);
  assert.equal(where.comparison.rest.text, '−4 % (antes 940)');
  assert.match(buildLightSlides({ publication, sat: { status: 'SIN_DATOS', reason: 'No hay hechos' } }).slides[1].empty, /No hay hechos/);
});

test('slide 3 highlights the most repeated commitment and a topic that spans years', () => {
  const council = {
    total: 50, open: 49, overdue: 2, without_information: 48,
    attention: [
      { code: 'CS-2026-020', text: 'Otro compromiso', mentions: 2, flags: ['REPETIDO'] },
      { code: 'CS-2026-018', text: 'Presentar informe de cámaras', mentions: 5, flags: ['REPETIDO'] },
      { code: 'CS-2026-030', text: 'Radios', mentions: 1, flags: ['ATRASADO'] },
    ],
  };
  const recurrence = { topics: [
    { label: 'Motos', open_commitments: 0, years: { 2025: 5, 2026: 1 } },
    { label: 'Denuncias', first_date: '2024-04-08', sessions: 21, open_commitments: 2, years: { 2024: 3, 2025: 8, 2026: 10 } },
    // Mismo asunto que el compromiso más repetido: se salta.
    { label: 'Cámaras y videovigilancia', first_date: '2024-01-12', sessions: 14, open_commitments: 4, open_codes: ['CS-2026-018'], years: { 2024: 4, 2025: 6, 2026: 4 } },
    { label: 'Ocupaciones ilegales', first_date: '2024-01-12', sessions: 7, open_commitments: 4, years: { 2024: 1, 2025: 2, 2026: 4 } },
  ] };
  const pending = buildLightSlides({ publication, council, recurrence }).slides[2];
  assert.deepEqual(pending.stats.map((stat) => stat.value), [49, 2, 48]);
  assert.equal(pending.lines[0].label, 'Pedido 5 veces');
  assert.match(pending.lines[0].detail, /CS-2026-018/);
  assert.equal(pending.lines[1].label, 'Atrasado');
  assert.equal(pending.lines[2].label, 'Tema que vuelve desde 2024');
  assert.match(pending.lines[2].detail, /^Ocupaciones ilegales: 7 sesiones, 4 compromiso/);
});

test('blocking editorial review marks every slide as draft; svg escapes text and stays internal', () => {
  const blocked = { ...publication, governance: { editorial_review: { checks: [{ level: 'BLOQUEA' }] } } };
  const { slides, draft } = buildLightSlides({ publication: blocked });
  assert.equal(draft, true);
  const svg = lightSlideSvg({ ...slides[0], subtitle: 'A < B & "C"' }, 0, { draft });
  assert.match(svg, /BORRADOR/);
  assert.match(svg, /A &lt; B &amp; &quot;C&quot;/);
  assert.match(svg, /Uso interno · no publicar/);
  assert.match(svg, /width="1080" height="1350"/);
  assert.equal(shortDate('2026-09-12'), '12 sept 2026');
});
