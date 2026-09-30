import { accentuate } from './accentuate.js';
import { publicFacingText } from './siscCifrasText.js';

export const TIKTOK_DURATION = 30;
export const TIKTOK_SIZE = { width: 1080, height: 1920 };
const number = (value) => Number(value).toLocaleString('es-CO', { maximumFractionDigits: 2 });
const clean = (value) => accentuate(publicFacingText(value || ''));
const range = (period) => `${period.start} al ${period.end}`;
const isNumber = (value) => typeof value === 'number' && Number.isFinite(value) && value >= 0;

export function tikTokCandidates(publication) {
  if (publication?.status !== 'PUBLISHED' || !publication.period?.start || !publication.period?.end) return [];
  if (publication.governance?.public_only === false || publication.governance?.review_blockers?.length
    || publication.governance?.editorial_review?.blocking > 0
    || publication.governance?.editorial_review?.checks?.some((check) => check.level === 'BLOQUEA')) return [];
  const priority = (publication.insights || []).flatMap((item) => item.evidence_indicator_ids || []);
  return (publication.indicators || []).filter((item) => {
    const source = (publication.sources || []).find((entry) => entry.code === item.source_code);
    return item.publication_level === 'PUBLICO' && ['VALIDADO', 'PRELIMINAR'].includes(item.quality_status)
      && isNumber(item.value) && item.indicator_name && !item.geography
      && item.metadata?.coverage_type !== 'CONTEXT'
      && item.period_start === publication.period.start && item.period_end === publication.period.end
      && item.cutoff_date && source?.publication_level === 'PUBLICO'
      && source.included !== false && source.in_bulletin !== false && source.publishable !== false;
  }).sort((a, b) => {
    const rank = (item) => priority.includes(item.id) ? priority.indexOf(item.id) : priority.length;
    return rank(a) - rank(b);
  });
}

export function buildTikTokStory(publication, indicatorId) {
  const candidates = tikTokCandidates(publication);
  const indicator = indicatorId ? candidates.find((item) => item.id === indicatorId) : candidates[0];
  if (!indicator) return null;
  const previous = isNumber(indicator.comparison_value) && publication.comparison_period?.start
    && publication.comparison_period?.end ? indicator.comparison_value : null;
  const delta = previous === null ? null : indicator.value - previous;
  const change = delta === null ? 'Sin comparación disponible'
    : delta === 0 ? 'La misma cantidad de registros'
    : `${number(Math.abs(delta))} ${indicator.unit || 'registros'} ${delta > 0 ? 'más' : 'menos'}`;
  const cutoff = Date.parse(String(indicator.cutoff_date).slice(0, 10));
  const end = Date.parse(indicator.period_end);
  const preliminary = indicator.quality_status === 'PRELIMINAR'
    || (Number.isFinite(cutoff) && end > cutoff)
    || (indicator.source_code === 'POLICIA_SEMANAL' && end > cutoff - 7 * 86400000);
  const title = clean(indicator.indicator_name);
  const unit = clean(indicator.unit || 'registros');
  const source = clean(indicator.source || publication.sources.find((s) => s.code === indicator.source_code)?.name);
  const caveat = preliminary ? 'Cifra preliminar: puede actualizarse con nuevos reportes.'
    : 'Este dato describe registros; por sí solo no explica sus causas.';
  const scenes = [
    { start: 0, end: 4, heading: 'Jamundí, en un dato', narration: '¿Qué muestran los registros de Jamundí? Veamos un dato.', kind: 'hook' },
    { start: 4, end: 11, heading: title, narration: `En el periodo mostrado: ${number(indicator.value)} ${unit} de ${title}.`, kind: 'value' },
    { start: 11, end: 18, heading: 'La comparación', narration: previous === null ? 'No hay una base comparable para este dato. No podemos afirmar que subió o bajó.' : `Frente a ${number(previous)} en el periodo de comparación: ${change.toLowerCase()}.`, kind: 'comparison' },
    { start: 18, end: 24, heading: 'Cómo leer esta cifra', narration: caveat, kind: 'context' },
    { start: 24, end: 30, heading: 'Consulta las fuentes', narration: 'Consulta las cifras y sus fuentes en el portal de la Alcaldía de Jamundí.', kind: 'close' },
  ];
  return { title, unit, value: indicator.value, previous, change, source, cutoff: String(indicator.cutoff_date).slice(0, 10),
    period: range(publication.period), comparison: previous === null ? null : range(publication.comparison_period),
    preliminary, scenes, duration: TIKTOK_DURATION };
}

export function tikTokScript(story) {
  if (!story) return '';
  return ['SISC EN CIFRAS · TikTok · 30 segundos · 9:16', `Indicador: ${story.title}`,
    `Periodo: ${story.period}`, ...(story.comparison ? [`Comparación: ${story.comparison}`] : []),
    `Fuente: ${story.source} · Corte: ${story.cutoff}`, '',
    ...story.scenes.map((scene) => `${scene.start}–${scene.end} s · ${scene.heading}\nNarración: ${scene.narration}`),
    '', 'Añadir la narración siguiendo estos tiempos. El video descargado no incluye voz.',
  ].join('\n');
}

export function tikTokSubtitles(story) {
  const time = (seconds) => `00:00:${String(seconds).padStart(2, '0')},000`;
  return story.scenes.map((scene, index) => `${index + 1}\n${time(scene.start)} --> ${time(scene.end)}\n${scene.narration}\n`).join('\n');
}

const clamp = (value) => Math.max(0, Math.min(1, value));
function text(context, value, x, y, size, color, maxWidth = 800, lineHeight = size * 1.2, maxHeight = 250) {
  const ratio = lineHeight / size;
  let lines;
  do {
    context.font = `700 ${size}px Arial, sans-serif`;
    lines = []; let line = '';
    for (const word of String(value).split(/\s+/)) {
      if (context.measureText(`${line} ${word}`).width > maxWidth && line) { lines.push(line); line = word; }
      else line = `${line} ${word}`.trim();
    }
    lines.push(line);
    if (lines.length * size * ratio <= maxHeight || size <= 20) break;
    size -= 2;
  } while (true);
  context.fillStyle = color;
  lines.forEach((line, i) => context.fillText(line, x, y + i * size * ratio, maxWidth));
  return y + lines.length * size * ratio;
}

export function drawTikTokFrame(context, story, seconds) {
  const { width, height } = TIKTOK_SIZE;
  const scene = story.scenes.find((item) => seconds < item.end) || story.scenes.at(-1);
  const local = Math.max(0, seconds - scene.start);
  const enter = 1 - (1 - clamp(local / 0.55)) ** 3;
  context.clearRect(0, 0, width, height);
  context.fillStyle = '#131044'; context.fillRect(0, 0, width, height);
  context.fillStyle = '#281fd0';
  context.beginPath(); context.arc(970, 240 + Math.sin(seconds / 2) * 35, 370, 0, Math.PI * 2); context.fill();
  text(context, 'SISC EN CIFRAS', 90, 185, 30, '#ffe000');
  text(context, 'ALCALDÍA DE JAMUNDÍ', 90, 235, 24, '#c7c5f2');
  text(context, story.preliminary ? 'CIFRA PRELIMINAR' : 'EDICIÓN PUBLICADA', 90, 315, 24, '#ffe000');
  context.save(); context.globalAlpha = enter; context.translate(0, 45 * (1 - enter));
  const headingBottom = text(context, scene.heading, 90, 440, scene.kind === 'hook' ? 88 : 56, '#ffffff');
  if (scene.kind === 'hook') {
    text(context, 'Una cifra. Su contexto.', 90, Math.max(700, headingBottom + 70), 42, '#c7c5f2');
    text(context, story.title, 90, 940, 45, '#ffe000');
  } else if (scene.kind === 'value') {
    text(context, number(story.value), 90, Math.max(790, headingBottom + 140), 142, '#ffe000');
    text(context, story.unit, 90, 910, 38, '#ffffff');
    text(context, 'Periodo analizado', 90, 1030, 26, '#c7c5f2');
    text(context, story.period, 90, 1085, 30, '#ffffff');
  } else if (scene.kind === 'comparison') {
    if (story.previous !== null) {
      const max = Math.max(story.value, story.previous, 1);
      [[story.previous, 'Comparación', story.comparison], [story.value, 'Actual', story.period]].forEach(([value, label, period], i) => {
        const y = 650 + i * 215;
        text(context, `${label}: ${number(value)} ${story.unit}`, 90, y, 32, '#ffffff');
        text(context, period, 90, y + 43, 24, '#c7c5f2');
        context.fillStyle = i ? '#ffe000' : '#8f89e8';
        context.fillRect(90, y + 72, 780 * value / max * clamp(local / 1.1), 48);
      });
    }
    text(context, story.change, 90, story.previous === null ? 780 : 1130, 46, '#ffe000');
  } else if (scene.kind === 'context') {
    text(context, story.preliminary ? 'Puede actualizarse.' : 'Los registros no explican las causas.', 90, 740, 68, '#ffe000');
  } else {
    text(context, story.source, 90, 650, 44, '#ffffff');
    text(context, `Corte: ${story.cutoff}`, 90, 870, 32, '#c7c5f2');
    text(context, 'jamundi.gov.co', 90, 1040, 58, '#ffe000');
  }
  context.restore();
  // Keep captions above the bottom controls; keep the right-hand edge clear.
  context.fillStyle = '#080722'; context.fillRect(65, 1280, 865, 260);
  text(context, scene.narration, 90, 1330, 42, '#ffffff', 800, 52, 220);
  text(context, `${story.source} · Corte ${story.cutoff}`, 90, 1600, 27, '#c7c5f2', 800, 34, 85);
  text(context, story.period, 90, 1700, 25, '#c7c5f2');
  context.fillStyle = '#ffe000'; context.fillRect(90, 1750, 780 * clamp(seconds / story.duration), 7);
}

export async function recordTikTok(story, onProgress, signal) {
  if (!story || typeof MediaRecorder === 'undefined') throw new Error('Este navegador no permite exportar video. Puede descargar el guion y los subtítulos.');
  const mime = ['video/mp4;codecs=avc1.42E01E', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'].find((type) => MediaRecorder.isTypeSupported(type));
  if (!mime) throw new Error('No hay un formato de video compatible en este navegador.');
  const canvas = document.createElement('canvas'); Object.assign(canvas, TIKTOK_SIZE);
  const context = canvas.getContext('2d');
  drawTikTokFrame(context, story, 0.6);
  const stream = canvas.captureStream(30);
  let recorder;
  let frame;
  let abort;
  try {
    recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 6_000_000 });
    const chunks = [];
    await new Promise((resolve, reject) => {
      abort = () => { if (recorder.state !== 'inactive') recorder.stop(); reject(new DOMException('Grabación cancelada', 'AbortError')); };
      signal?.addEventListener('abort', abort, { once: true });
      if (signal?.aborted) { abort(); return; }
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onerror = () => reject(new Error('No se pudo grabar el video. Inténtelo de nuevo.'));
      recorder.onstop = resolve;
      recorder.start(250);
      const started = performance.now();
      const render = () => {
        if (signal?.aborted) return;
        try {
          const elapsed = (performance.now() - started) / 1000;
          drawTikTokFrame(context, story, Math.min(elapsed, story.duration));
          onProgress(Math.min(100, Math.round(elapsed / story.duration * 100)));
          if (elapsed >= story.duration) recorder.stop();
          else frame = requestAnimationFrame(render);
        } catch (error) { reject(error); }
      };
      frame = requestAnimationFrame(render);
    });
    return { blob: new Blob(chunks, { type: mime.split(';')[0] }), extension: mime.startsWith('video/mp4') ? 'mp4' : 'webm' };
  } finally {
    cancelAnimationFrame(frame);
    signal?.removeEventListener('abort', abort);
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    stream.getTracks().forEach((track) => track.stop());
  }
}
