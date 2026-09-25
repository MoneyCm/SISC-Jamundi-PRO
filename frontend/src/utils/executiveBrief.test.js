import test from 'node:test';
import assert from 'node:assert/strict';
import { buildExecutiveBrief, executiveBriefSvg, jpegPdf, briefPublicationPolicy } from './executiveBrief.js';
const snapshot = () => ({ checked_at: '2026-09-24T12:00:00Z', groups: Object.fromEntries(['decisions', 'commitments', 'results'].map(k => [k, {total: 0, items: []}])) });
test('executive drafts and public previews cannot publish automatically', () => {
  for (const args of [[false, true], [true, false], [true, true]]) assert.deepEqual(briefPublicationPolicy(...args), {save_history:false,publish_automatically:false});
  // Modo institucional: se guarda el borrador, pero la publicación requiere aprobación humana.
  assert.deepEqual(briefPublicationPolicy(false, false), {save_history:true,publish_automatically:false});
});
test('missing records remain explicit; warnings take priority over statistical insights', () => {
  const brief = buildExecutiveBrief({governance:{review_blockers:['Cobertura incompleta']}}, snapshot());
  assert.match(brief.sections[0].lines[0], /Sin hallazgos/);
  assert.equal(brief.sections[1].lines[0], 'Cobertura incompleta');
  assert.match(brief.sections[3].lines[0], /No hay compromisos/);
});
test('draft recommendations stay proposals and closures without evidence are not results', () => {
  const followup = snapshot();
  followup.groups.decisions = {total:4,items:[{id:'abcdef123', recommendation:'Propuesta <script> & revisar'}]};
  followup.groups.results = {total:1,items:[{id:'abcdef123', decision:'Cierre', evidence_count:0}]};
  const brief = buildExecutiveBrief({}, followup);
  assert.match(brief.sections[2].lines[0], /Propuesta pendiente/);
  assert.match(brief.sections[2].lines[1], /3 expediente/);
  assert.match(brief.sections[4].lines[0], /no se presenta como resultado comprobado/);
  const svg = executiveBriefSvg(brief);
  assert.ok(!svg.includes('<script>'));
  assert.ok(svg.includes('&lt;script&gt;'));
});
test('PDF uses valid byte offsets even with binary JPEG content', async () => {
  const data = new Uint8Array(await jpegPdf(new Uint8Array([255,216,0,200,255,217]),1080,1600).arrayBuffer());
  const text = new TextDecoder('latin1').decode(data);
  const offsets = [...text.matchAll(/(\d{10}) 00000 n/g)].map(m => Number(m[1]));
  assert.equal(offsets.length, 5);
  offsets.forEach((offset,i) => assert.equal(new TextDecoder().decode(data.slice(offset,offset+7)), `${i+1} 0 obj`));
  assert.match(text, /\/Count 1/);
});
test('council commitments fill the decision and follow-up sections', () => {
  const followup = snapshot();
  const repeated = { code: 'CS-2026-018', text: 'Presentar informe mensual de las cámaras', responsible: 'Policía Nacional', mentions: 5, flags: ['REPETIDO', 'SIN_FECHA'], deadline_date: null, deadline_text: null };
  const overdue = { code: 'CS-2026-001', text: 'Convocar reunión', responsible: 'Secretaría', mentions: 1, flags: ['ATRASADO'], deadline_date: '2026-01-15' };
  followup.council = { total: 50, open: 50, overdue: 5, without_deadline: 45, by_status: { SIN_INFORMACION: 50 }, attention: [repeated, overdue], results: [] };
  const brief = buildExecutiveBrief({}, followup);
  assert.match(brief.sections[2].lines[0], /Pedido 5 veces sin cumplirse: Presentar informe mensual/);
  assert.match(brief.sections[2].lines[1], /45 compromiso/);
  assert.match(brief.sections[3].lines[0], /50 abiertos de 50/);
  assert.match(brief.sections[3].lines[1], /Atrasado: Convocar reunión/);
  assert.match(brief.sections[4].lines[0], /Ningún compromiso del Consejo/);
});
