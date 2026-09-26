import { accentuate } from './accentuate.js';
const shorten = (value, max = 180) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
};
export const xml = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]));
// El boletín institucional se guarda como borrador y se publica solo cuando una persona
// lo aprueba tras la revisión editorial. Nunca se publica automáticamente desde la pantalla.
export const briefPublicationPolicy = (publicMode, executive) => ({
  save_history: !publicMode && !executive,
  publish_automatically: false,
});

export function buildExecutiveBrief(publication, followup) {
  // Las cifras de otro periodo (último informe de una dependencia) no son "lo que cambió".
  const allIndicators = publication.indicators || [];
  const isContext = (indicator) => indicator?.metadata?.coverage_type === 'CONTEXT';
  const byId = Object.fromEntries(allIndicators.map((indicator) => [indicator.id, indicator]));
  const insights = (publication.insights || []).filter((insight) =>
    !(insight.evidence_indicator_ids || []).some((id) => isContext(byId[id])));
  const indicators = allIndicators.filter(i => i.value !== null && i.value !== undefined && !isContext(i));
  // "Qué requiere atención" usa la revisión editorial (con nombre de fuente y lenguaje claro);
  // sin ella, las observaciones de cobertura tal como vienen del sistema.
  const reviewChecks = (publication.governance?.editorial_review?.checks || []).filter((check) => check.level !== 'OK');
  const warnings = reviewChecks.length
    ? reviewChecks.map((check) => `${check.level === 'BLOQUEA' ? 'Bloquea la publicación' : 'Revisar'}: ${check.title}. ${check.detail}`)
    : [...(publication.governance?.review_blockers || []), ...(publication.governance?.context_warnings || [])];
  const groups = followup.groups;
  const groupLines = (name, render, empty) => {
    const group = groups[name];
    const lines = group.items.slice(0, 2).map(render);
    if (group.total > lines.length) lines.push(`+ ${group.total - lines.length} expediente(s) adicionales. Consultar seguimiento institucional.`);
    return lines.length ? lines : [empty];
  };
  // Compromisos de los Consejos de Seguridad: si existen, alimentan las tres secciones finales.
  const council = followup.council;
  const commitmentLine = (item) => `${shorten(item.text, 150)} · ${shorten(item.responsible || 'Responsable por definir', 60)}`
    + (item.deadline_date ? ` · plazo ${item.deadline_date}` : item.deadline_text ? ` · plazo: ${shorten(item.deadline_text, 40)}` : ' · sin fecha límite')
    + ` [${item.code}]`;
  const councilSections = council ? [
    { title: 'Qué debemos decidir', lines: [
      ...council.attention.filter((item) => item.flags.includes('REPETIDO')).slice(0, 2)
        .map((item) => `Pedido ${item.mentions} veces sin cumplirse: ${commitmentLine(item)}. Decidir si se reasigna, se redefine o se cierra.`),
      ...(council.without_deadline ? [`${council.without_deadline} compromiso(s) abiertos sin fecha límite: definir fecha y responsable en el próximo Consejo.`] : []),
    ].slice(0, 3) },
    { title: 'Compromisos y seguimiento', lines: [
      `${council.open} abiertos de ${council.total}: ${council.by_status.EN_CURSO || 0} en curso, ${council.by_status.PENDIENTE || 0} pendientes y ${council.by_status.SIN_INFORMACION || 0} sin información; ${council.overdue} atrasados.`,
      ...council.attention.filter((item) => item.flags.includes('ATRASADO')).slice(0, 1).map((item) => `Atrasado: ${commitmentLine(item)}.`),
    ] },
    { title: 'Resultados con soporte', lines: council.results.length
      ? council.results.slice(0, 2).map((item) => `Cumplido: ${commitmentLine(item)}.`)
      : ['Ningún compromiso del Consejo está marcado como cumplido con soporte todavía.'] },
  ] : null;
  const brief = {
    period: `${publication.period?.start || 'Sin fecha'} al ${publication.period?.end || 'Sin fecha'}`,
    comparison: `${publication.comparison_period?.start || 'Sin fecha'} al ${publication.comparison_period?.end || 'Sin fecha'}`,
    checkedAt: followup.checked_at,
    sources: (publication.sources || []).map(s => accentuate(`${s.name}: corte ${s.last_cutoff_date || 'no reportado'}`)).join(' · ') || 'Fuente no reportada',
    sections: [
      { title: 'Qué cambió', lines: insights.length ? insights.slice(0, 2).map(i => `${shorten(i.detail || i.title, 200)} Fuente: ${i.source || 'no reportada'}; corte ${i.cutoff_date || 'no reportado'}.`) : indicators.length ? indicators.slice(0, 3).map(i => `${shorten(i.indicator_name || i.indicator_code, 70)}: ${i.value}${i.unit ? ` ${i.unit}` : ''}${i.variation_percentage !== null && i.variation_percentage !== undefined ? ` (${i.variation_percentage > 0 ? '+' : ''}${Number(i.variation_percentage).toFixed(1)}% frente al comparativo)` : ''}. Fuente: ${i.source || 'no reportada'}; corte ${i.cutoff_date || 'no reportado'}.`) : ['Sin hallazgos estadísticos para este período: no hay cifras de la Policía ni cambios comparables que reportar.'] },
      { title: 'Qué requiere atención', lines: warnings.length ? warnings.slice(0, 2).map(w => shorten(typeof w === 'string' ? w : JSON.stringify(w), 200)) : insights.length > 2 ? [shorten(insights[2].detail || insights[2].title, 210), `Fuente: ${insights[2].source || 'no reportada'}; corte ${insights[2].cutoff_date || 'no reportado'}. Validar en mesa de seguimiento.`] : ['Revisar cobertura, cortes y hallazgos con el equipo antes de priorizar acciones.'] },
      { title: 'Qué debemos decidir', lines: groupLines('decisions', i => `Propuesta pendiente · ${shorten(i.recommendation || 'Recomendación aún no registrada', 165)} [${i.id.slice(0, 8)}]`, 'No hay expedientes en borrador registrados. No se infieren decisiones a partir de las cifras.') },
      { title: 'Compromisos y seguimiento', lines: groupLines('commitments', i => `${shorten(i.decision, 95)} · Responsable: ${shorten(i.responsible || 'sin registrar', 55)} · Plazo: ${i.deadline || 'sin registrar'} · ${i.status === 'EN_EJECUCION' ? 'En ejecución' : 'Decidida'} [${i.id.slice(0, 8)}]`, 'No hay compromisos activos registrados. Registrar decisión, responsable, plazo y evidencia en el expediente.') },
      { title: 'Resultados con soporte', lines: groupLines('results', i => i.evidence_count && i.completed_on ? `Cierre documentado: ${shorten(i.decision, 120)} · ${i.completed_on} · ${i.evidence_count} soporte(s) [${i.id.slice(0, 8)}]` : `Expediente ${i.id.slice(0, 8)}: cierre sin soporte completo; no se presenta como resultado comprobado.`, 'No hay cierres registrados con resultados para presentar. Una reducción estadística no demuestra efecto de una intervención.') },
    ],
  };
  if (councilSections) {
    const replaced = Object.fromEntries(councilSections.map((section) => [section.title, section]));
    brief.sections = brief.sections.map((section) => (replaced[section.title]?.lines.length ? replaced[section.title] : section));
  }
  brief.sections = brief.sections.map((section) => ({ ...section, lines: section.lines.map((line) => accentuate(line)) }));
  return brief;
}

function wrap(text, width = 76, maxLines = 6) {
  const words = text.split(/\s+/).flatMap(word => word.match(new RegExp(`.{1,${width}}`, 'g')) || []);
  const lines = []; let line = '';
  for (const word of words) {
    if ((line + ' ' + word).length > width && line) { lines.push(line); line = word; }
    else line = line ? `${line} ${word}` : word;
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) return [...lines.slice(0, maxLines - 1), `${lines[maxLines - 1].slice(0, width - 1)}…`];
  return lines;
}

export function executiveBriefSvg(brief, escudo = '') {
  const text = (value, x, y, size = 25, color = '#334155', weight = 400) => `<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}">${xml(value)}</text>`;
  const sections = brief.sections.map((s, index) => {
    const y = 330 + index * 205;
    const accent = ['#281fd0', '#eab308', '#0f766e', '#2563eb', '#16a34a'][index];
    return `<rect x="40" y="${y}" width="1000" height="190" rx="18" fill="white" stroke="#dbe3ee" stroke-width="2" filter="url(#shadow)"/><rect x="40" y="${y}" width="10" height="190" rx="5" fill="${accent}"/>${text(`0${index + 1}`, 75, y + 40, 23, accent, 700)}${text(s.title, 125, y + 40, 29, '#111827', 700)}${wrap(s.lines.join(' • '), 76, 4).map((line, j) => text(line, 75, y + 79 + j * 29)).join('')}`;
  }).join('');
  const crest = escudo ? `<image href="${escudo}" x="855" y="28" width="145" height="180" preserveAspectRatio="xMidYMid meet"/>` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1600" viewBox="0 0 1080 1600"><defs><linearGradient id="hero" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#281fd0"/><stop offset="1" stop-color="#17144d"/></linearGradient><filter id="shadow"><feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#64748b" flood-opacity=".18"/></filter></defs><rect width="1080" height="1600" fill="#f4f7fb"/><g font-family="Calibri, Arial, sans-serif"><rect width="1080" height="24" fill="#ffe000"/><path d="M0 24H1080V290C880 260 720 330 540 292C350 250 180 278 0 310Z" fill="url(#hero)"/>${crest}${text('ALCALDÍA DE JAMUNDÍ', 76, 74, 22, '#ffe000', 700)}${text('SISC EN CIFRAS', 76, 140, 54, '#ffffff', 700)}${text('Parte ejecutivo', 76, 190, 34, '#ffffff', 700)}<rect x="76" y="211" width="350" height="34" rx="17" fill="#ffffff" opacity=".16"/>${text('LECTURA INSTITUCIONAL', 98, 235, 16, '#ffffff', 700)}${text(`Cifras: ${brief.period}`, 76, 274, 21, '#ffffff')}${sections}${wrap(`Fuentes: ${brief.sources}`, 100, 3).map((line, j) => text(line, 55, 1410 + j * 24, 19)).join('')}${text(`Seguimiento consultado: ${brief.checkedAt.slice(0, 10)} · Estado actual, independiente del período estadístico.`, 55, 1500, 18)}${text('Extracto: … indica texto abreviado. Revisar expedientes y validar antes de circular.', 55, 1530, 19)}${text('Los cambios observados no demuestran causalidad. Las fuentes no se suman entre sí.', 55, 1560, 19)}</g></svg>`;
}

// One-page image PDF: the image comes from the same SVG shown in the preview.
// Byte offsets, rather than JS string lengths, keep the cross-reference table valid.
export function jpegPdf(jpeg, width, height) {
  const encode = s => new TextEncoder().encode(s);
  const chunks = [encode('%PDF-1.4\n')]; const offsets = [0]; let length = chunks[0].length;
  const append = value => { chunks.push(value); length += value.length; };
  const object = (id, body) => { offsets[id] = length; append(encode(`${id} 0 obj\n${body}\nendobj\n`)); };
  object(1, '<< /Type /Catalog /Pages 2 0 R >>');
  object(2, '<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
  object(3, '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>');
  offsets[4] = length;
  append(encode(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`));
  append(jpeg); append(encode('\nendstream\nendobj\n'));
  const drawWidth = 841.89 * width / height;
  const content = `q ${drawWidth.toFixed(3)} 0 0 841.89 ${((595.28 - drawWidth) / 2).toFixed(3)} 0 cm /Im0 Do Q`;
  object(5, `<< /Length ${encode(content).length} >>\nstream\n${content}\nendstream`);
  const xref = length;
  append(encode(`xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(n => `${String(n).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`));
  return new Blob(chunks, { type: 'application/pdf' });
}
