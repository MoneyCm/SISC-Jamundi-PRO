// Parte ejecutivo "light": 3 láminas verticales (1080x1350) para leer en el celular en 30 segundos.
// Uso interno de directivos: trae compromisos del Consejo y alertas tempranas, nunca va a la web.
import { accentuate } from './accentuate.js';
import { xml } from './executiveBrief.js';

// Con una base anterior menor a 30 casos un porcentaje exagera: "+100 %" puede ser pasar de 1 a 2.
export const SMALL_BASE = 30;
const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];

export const shortDate = (iso) => {
  if (!iso) return 'sin fecha';
  const [year, month, day] = String(iso).slice(0, 10).split('-').map(Number);
  return `${day} ${MONTHS[month - 1]} ${year}`;
};

const clip = (text, max) => {
  const value = accentuate(String(text || '').replace(/\s+/g, ' ').trim());
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
};

/** Cambio frente al comparativo, en el lenguaje que corresponde al tamaño de la base. */
export function describeChange(value, previous) {
  if (previous === null || previous === undefined) return { tone: 'neutral', arrow: '', text: 'sin comparativo' };
  const current = Number(value) || 0;
  const before = Number(previous) || 0;
  const diff = current - before;
  const tone = diff > 0 ? 'up' : diff < 0 ? 'down' : 'neutral';
  const arrow = diff > 0 ? '▲' : diff < 0 ? '▼' : '=';
  if (diff === 0) return { tone, arrow, text: `igual que antes (${before})` };
  // El porcentaje se calcula sobre la base anterior: si esa base es pequeña, exagera.
  if (before < SMALL_BASE) {
    return { tone, arrow, text: `${diff > 0 ? '+' : '−'}${Math.abs(diff)} casos (antes ${before})`, smallBase: true };
  }
  const pct = Math.round((diff / before) * 100);
  return { tone, arrow, text: `${pct > 0 ? '+' : '−'}${Math.abs(pct)} % (antes ${before})` };
}

const isContext = (indicator) => indicator?.metadata?.coverage_type === 'CONTEXT';

function slideHowWeAre(publication) {
  const indicators = (publication.indicators || []).filter((item) =>
    !isContext(item) && !item.geography && item.value !== null && item.value !== undefined
    && String(item.indicator_code || '').startsWith('seguridad.'));
  const total = indicators.find((item) => item.indicator_code === 'seguridad.total');
  // El homicidio va siempre, aunque tenga pocos casos; el resto, los de más casos en el periodo.
  const homicide = indicators.find((item) => /homicidio/i.test(item.indicator_name || '') && !/tr[aá]nsito/i.test(item.indicator_name || ''));
  const others = indicators.filter((item) => item !== total && item !== homicide)
    .sort((a, b) => (Number(b.value) || 0) - (Number(a.value) || 0));
  const conducts = [...(homicide ? [homicide] : []), ...others].slice(0, 3);
  const tiles = [total, ...conducts].filter(Boolean).map((item) => ({
    label: item === total ? 'Total de hechos' : clip(item.indicator_name, 26),
    value: Number(item.value) || 0,
    change: describeChange(item.value, item.comparison_value),
  }));
  const cutoff = (publication.sources || []).map((source) => source.last_cutoff_date).filter(Boolean).sort().pop()
    || publication.period?.end;
  return {
    key: 'como-vamos',
    title: 'CÓMO VAMOS',
    subtitle: `${shortDate(publication.period?.start)} al ${shortDate(publication.period?.end)} · frente al mismo periodo de ${String(publication.comparison_period?.start || '').slice(0, 4) || 'el año anterior'}`,
    tiles,
    empty: tiles.length ? null : 'No hay cifras de la Policía cargadas para este periodo.',
    note: tiles.some((tile) => tile.change.smallBase)
      ? 'Si antes hubo menos de 30 casos se muestra la diferencia en casos, no el porcentaje.'
      : 'Rojo: subió. Verde: bajó.',
    footer: `Datos al ${shortDate(cutoff)} · Sábana Policía Jamundí`,
  };
}

const CONDUCT_NOTES = { 'hurto de vehículos': 'hurto de motos y carros' };

function topConductLine(top, total) {
  const label = accentuate(String(top.label || '').toLowerCase());
  return `Más común: ${CONDUCT_NOTES[label] || label} (${top.total} de ${total})`;
}

function slideWhereAndRisk(sat) {
  const title = 'ZONAS CON ALERTA TEMPRANA (DEFENSORÍA)';
  if (!sat || sat.status !== 'OK') {
    return {
      key: 'donde', title, subtitle: 'Zonas señaladas por la Defensoría del Pueblo', rows: [], alerts: [], comparison: null,
      empty: sat?.reason || 'Sin datos de las zonas en alerta.', footer: 'Fuentes: sábana policial y Defensoría del Pueblo',
    };
  }
  const current = String(sat.generated_for.current_year);
  const previous = String(sat.generated_for.previous_year);
  // Los territorios del radar son solo los de la zona advertida, no los de todo el municipio.
  const rows = (sat.territories || []).slice(0, 3).map((item) => ({
    label: clip(item.name, 24),
    value: item.series?.[current] ?? 0,
    change: describeChange(item.series?.[current] ?? 0, item.series?.[previous] ?? 0),
    // Se dice cuántos son: "predomina" junto al total hacía leer 31 hurtos donde eran 9.
    detail: item.top_conductas?.[0] ? topConductLine(item.top_conductas[0], item.series?.[current] ?? 0) : '',
  }));
  const group = (key) => (sat.groups || []).find((item) => item.key === key);
  const zone = group('AT');
  const rest = ['URBANO', 'RURAL_NO_AT'].map(group).filter(Boolean);
  const sum = (items, year) => items.reduce((total, item) => total + (item.series?.[year] || 0), 0);
  const comparison = zone && rest.length ? {
    zone: describeChange(zone.series?.[current] || 0, zone.series?.[previous] || 0),
    zoneValue: zone.series?.[current] || 0,
    rest: describeChange(sum(rest, current), sum(rest, previous)),
    restValue: sum(rest, current),
  } : null;
  const vigentes = (sat.alerts || []).filter((alert) => /vigente/i.test(alert.estado || ''));
  const window = String(sat.generated_for.window_label || '').replace(/ de cada año$/, '');
  return {
    key: 'donde',
    title,
    subtitle: `Zonas señaladas por la Defensoría · año corrido (${window})`,
    rows,
    comparison,
    alerts: vigentes.slice(0, 1).map((alert) => ({
      label: `Alerta ${alert.numero} (${String(alert.tipo || '').toLowerCase()})`,
      detail: clip(alert.ambito || alert.actor, 70),
    })),
    alertCount: vigentes.length,
    empty: rows.length ? null : 'Sin hechos registrados en las zonas en alerta.',
    footer: 'Fuentes: sábana policial y Defensoría del Pueblo',
  };
}

function slidePending(council, recurrence) {
  if (!council) {
    return { key: 'pendiente', title: 'QUÉ ESTÁ PENDIENTE', stats: [], lines: [], empty: 'Sin compromisos registrados.', footer: '' };
  }
  const repeated = (council.attention || []).filter((item) => (item.flags || []).includes('REPETIDO'))
    .sort((a, b) => (b.mentions || 1) - (a.mentions || 1));
  const overdue = [...(council.overdue_items || []), ...(council.attention || [])]
    .find((item) => (item.flags || []).includes('ATRASADO') && item.code !== repeated[0]?.code);
  // Tema que vuelve: el de más compromisos abiertos hoy entre los que se repiten varios años.
  // Si es el mismo del compromiso más repetido, se toma el siguiente para no decir dos veces lo mismo.
  const topic = (recurrence?.topics || [])
    .filter((item) => item.open_commitments > 0 && Object.keys(item.years || {}).length >= 2)
    .filter((item) => !repeated[0] || !(item.open_codes || []).includes(repeated[0].code))
    .sort((a, b) => b.open_commitments - a.open_commitments
      || Object.keys(b.years).length - Object.keys(a.years).length || b.sessions - a.sessions)[0];
  const lines = [];
  if (repeated[0]) lines.push({ label: `Pedido ${repeated[0].mentions} veces`, detail: `${clip(repeated[0].text, 90)} [${repeated[0].code}]` });
  if (overdue) lines.push({ label: 'Atrasado', detail: `${clip(overdue.text, 90)} [${overdue.code}]` });
  if (topic) {
    const since = String(topic.first_date || '').slice(0, 4);
    lines.push({ label: `Tema que vuelve desde ${since}`, detail: `${topic.label}: ${topic.sessions} sesiones, ${topic.open_commitments} compromiso(s) abiertos hoy.` });
  }
  return {
    key: 'pendiente',
    title: 'QUÉ ESTÁ PENDIENTE',
    subtitle: 'Compromisos del Consejo de Seguridad y comités',
    stats: [
      { label: 'Abiertos', value: council.open, helper: `de ${council.total}` },
      { label: 'Atrasados', value: council.overdue, helper: 'plazo vencido' },
      { label: 'Sin información', value: council.without_information ?? council.by_status?.SIN_INFORMACION ?? 0, helper: 'sin avance reportado' },
    ],
    lines,
    empty: null,
    footer: 'Fuente: actas y seguimiento de la Secretaría de Seguridad',
  };
}

export function buildLightSlides({ publication, council, recurrence, sat }) {
  const blocking = (publication?.governance?.editorial_review?.checks || []).some((check) => check.level === 'BLOQUEA');
  return {
    draft: blocking,
    slides: [slideHowWeAre(publication || {}), slideWhereAndRisk(sat), slidePending(council, recurrence)],
  };
}

// ---------------------------------------------------------------------------
// Dibujo SVG
// ---------------------------------------------------------------------------

const TONES = { up: '#dc2626', down: '#16a34a', neutral: '#64748b' };
const W = 1080;
const H = 1350;

function wrap(text, width, maxLines) {
  const words = String(text || '').split(/\s+/);
  const lines = []; let line = '';
  for (const word of words) {
    if ((`${line} ${word}`).trim().length > width && line) { lines.push(line); line = word; } else line = line ? `${line} ${word}` : word;
  }
  if (line) lines.push(line);
  return lines.length > maxLines ? [...lines.slice(0, maxLines - 1), `${lines[maxLines - 1].slice(0, width - 1)}…`] : lines;
}

const t = (value, x, y, size, color = '#0f172a', weight = 700, anchor = 'start') =>
  `<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}" text-anchor="${anchor}">${xml(value)}</text>`;

function header(slide, index, escudo) {
  const crest = escudo ? `<image href="${escudo}" x="918" y="36" width="110" height="136" preserveAspectRatio="xMidYMid meet"/>` : '';
  return `<rect width="${W}" height="18" fill="#ffe000"/><rect y="18" width="${W}" height="196" fill="#281fd0"/>${crest}`
    + t('ALCALDÍA DE JAMUNDÍ · PARTE EJECUTIVO', 60, 70, 22, '#ffe000')
    + t(slide.title, 60, 140, 62, '#ffffff', 800)
    + t(`${index + 1} / 3`, 60, 190, 24, '#c7d2fe', 700)
    + wrap(slide.subtitle || '', 62, 2).map((line, j) => t(line, 60, 262 + j * 34, 26, '#334155', 600)).join('');
}

function footer(slide, draft) {
  const banner = draft
    ? `<rect x="0" y="1160" width="${W}" height="70" fill="#fef3c7"/>${t('BORRADOR · la revisión editorial tiene bloqueos: no circular todavía', 60, 1205, 24, '#92400e', 700)}`
    : '';
  return `${banner}<rect y="1250" width="${W}" height="100" fill="#0f172a"/>`
    + wrap(slide.footer || '', 70, 1).map((line) => t(line, 60, 1292, 22, '#e2e8f0', 600)).join('')
    + t('Uso interno · no publicar · los cambios no demuestran causas', 60, 1328, 20, '#94a3b8', 500);
}

function howWeAreBody(slide) {
  if (slide.empty) return t(slide.empty, 60, 460, 34, '#475569', 600);
  return slide.tiles.map((tile, i) => {
    const x = 60 + (i % 2) * 490;
    const y = 340 + Math.floor(i / 2) * 380;
    const color = TONES[tile.change.tone];
    return `<rect x="${x}" y="${y}" width="470" height="350" rx="26" fill="#ffffff" stroke="#e2e8f0" stroke-width="3"/>`
      + `<rect x="${x}" y="${y}" width="470" height="12" rx="6" fill="${color}"/>`
      + wrap(tile.label, 22, 2).map((line, j) => t(line, x + 32, y + 68 + j * 36, 32, '#334155', 700)).join('')
      + t(String(tile.value), x + 32, y + 232, 120, '#0f172a', 800)
      + t(`${tile.change.arrow} ${tile.change.text}`, x + 32, y + 305, 27, color, 700);
  }).join('') + t(slide.note, 60, 1120, 24, '#64748b', 600);
}

function whereBody(slide) {
  if (slide.empty && !slide.alerts?.length) return t(slide.empty, 60, 460, 30, '#475569', 600);
  const versus = slide.comparison
    ? `<rect x="60" y="330" width="960" height="120" rx="24" fill="#eef2ff"/>`
      + t('Toda la zona en alerta', 95, 378, 26, '#3730a3', 700)
      + t(`${slide.comparison.zoneValue} · ${slide.comparison.zone.arrow} ${slide.comparison.zone.text}`, 95, 420, 28, TONES[slide.comparison.zone.tone], 800)
      + t('Resto del municipio', 985, 378, 26, '#3730a3', 700, 'end')
      + t(`${slide.comparison.restValue} · ${slide.comparison.rest.arrow} ${slide.comparison.rest.text}`, 985, 420, 28, TONES[slide.comparison.rest.tone], 800, 'end')
    : '';
  const offset = slide.comparison ? 150 : 0;
  const rows = slide.rows.map((row, i) => {
    const y = 340 + offset + i * 165;
    const color = TONES[row.change.tone];
    return `<rect x="60" y="${y}" width="960" height="150" rx="24" fill="#ffffff" stroke="#e2e8f0" stroke-width="3"/>`
      + t(String(i + 1), 105, y + 98, 64, '#281fd0', 800, 'middle')
      + t(row.label, 170, y + 64, 40, '#0f172a', 800)
      + t(clip(row.detail, 50), 170, y + 114, 23, '#64748b', 600)
      + t(String(row.value), 980, y + 82, 64, '#0f172a', 800, 'end')
      + t(`${row.change.arrow} ${row.change.text}`, 980, y + 124, 24, color, 700, 'end');
  }).join('');
  const top = 340 + offset + slide.rows.length * 165 + 5;
  const alerts = slide.alertCount
    ? `<rect x="60" y="${top}" width="960" height="${60 + slide.alerts.length * 88}" rx="24" fill="#fff7ed" stroke="#fdba74" stroke-width="3"/>`
      + t(`⚠ ${slide.alertCount} alerta(s) temprana(s) de la Defensoría vigentes`, 95, top + 52, 30, '#9a3412', 800)
      + slide.alerts.map((alert, i) => t(alert.label, 95, top + 100 + i * 88, 26, '#7c2d12', 700)
        + t(alert.detail, 95, top + 134 + i * 88, 23, '#9a3412', 500)).join('')
    : '';
  return versus + rows + alerts;
}

function pendingBody(slide) {
  if (slide.empty) return t(slide.empty, 60, 460, 34, '#475569', 600);
  const stats = slide.stats.map((stat, i) => {
    const x = 60 + i * 327;
    const color = i === 1 && stat.value > 0 ? '#dc2626' : '#281fd0';
    return `<rect x="${x}" y="340" width="307" height="230" rx="24" fill="#ffffff" stroke="#e2e8f0" stroke-width="3"/>`
      + t(String(stat.value), x + 153, 465, 104, color, 800, 'middle')
      + t(stat.label, x + 153, 515, 30, '#0f172a', 800, 'middle')
      + t(stat.helper, x + 153, 550, 22, '#64748b', 600, 'middle');
  }).join('');
  const lines = slide.lines.map((line, i) => {
    const y = 610 + i * 180;
    return `<rect x="60" y="${y}" width="960" height="160" rx="24" fill="#ffffff" stroke="#e2e8f0" stroke-width="3"/>`
      + `<rect x="60" y="${y}" width="12" height="160" rx="6" fill="${i === 0 ? '#dc2626' : '#f59e0b'}"/>`
      + t(line.label.toUpperCase(), 100, y + 50, 24, i === 0 ? '#dc2626' : '#b45309', 800)
      + wrap(line.detail, 62, 2).map((part, j) => t(part, 100, y + 94 + j * 36, 28, '#0f172a', 600)).join('');
  }).join('');
  return stats + lines;
}

export function lightSlideSvg(slide, index, { escudo = '', draft = false } = {}) {
  const body = slide.key === 'como-vamos' ? howWeAreBody(slide) : slide.key === 'donde' ? whereBody(slide) : pendingBody(slide);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`
    + `<rect width="${W}" height="${H}" fill="#f1f5f9"/><g font-family="Calibri, Arial, sans-serif">`
    + header(slide, index, escudo) + body + footer(slide, draft) + '</g></svg>';
}

export const LIGHT_SIZE = { width: W, height: H };
