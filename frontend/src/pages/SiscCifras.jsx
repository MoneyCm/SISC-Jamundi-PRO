import React, { useEffect, useMemo, useState } from 'react';
import {
  BarChart3, CalendarDays, CheckCircle2, Copy, Download, FileJson, ImageDown, Layers,
  Loader2, MessageCircle, RefreshCw, ShieldCheck, Sparkles, ToggleLeft, ToggleRight
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';
import { institutionalSiscCifrasPeriods, suggestedSiscCifrasPeriod } from '../utils/siscCifrasPeriod';

const QUICK_EDITIONS = [
  { id: 'weekly', label: 'Semanal' },
  { id: 'monthly', label: 'Mensual' },
  { id: 'semester', label: '6 meses' },
  { id: 'annual', label: 'Anual' },
];

const FOCUS_EDITIONS = [
  { id: 'security', label: 'Seguridad' },
  { id: 'convivencia', label: 'Convivencia' },
  { id: 'territory', label: 'Territorio' },
];

const COMPARISON_MODES = [
  { id: 'auto', label: 'Automatica' },
  { id: 'previous_period', label: 'Periodo anterior' },
  { id: 'year_over_year', label: 'Ano anterior' },
];

const DEFAULT_SOURCES = ['POLICIA_SEMANAL', 'INSPECCIONES_RNMC', 'COMISARIAS_FAMILIA'];
const DOMAIN_COLORS = {
  SEGURIDAD: '#281FD0',
  CONVIVENCIA: '#3A30F1',
  'FAMILIA Y PROTECCION': '#FFB600',
  TERRITORIO: '#606175',
};

const fmt = (value) => Number(value || 0).toLocaleString('es-CO');
const NON_PUBLIC_TERRITORY_VALUES = new Set([
  'BARRIO PENDIENTE POR ASIGNAR',
  'PENDIENTE POR ASIGNAR',
  'SIN ASIGNAR',
  'SIN BARRIO',
  'SIN COMUNA',
  'SIN ESPECIFICAR',
  'SIN LOCALIDAD',
  'NO APLICA',
  'NO APLICA LOCALIDAD',
  'NO APLICA LOCALIDAD - COMUNA',
  'NO DEFINIDO',
  'NO REPORTA',
  'NO REGISTRA',
  'N/A',
]);
const NON_PUBLIC_TERRITORY_PATTERNS = [
  'PENDIENTE',
  'POR ASIGNAR',
  'NO APLICA',
  'NO DEFINIDO',
  'SIN LOCALIDAD',
  'SIN COMUNA',
];
const isPublicTerritoryName = (value = '') => {
  const clean = String(value).trim().replace(/\s+/g, ' ').toUpperCase();
  return clean
    && !NON_PUBLIC_TERRITORY_VALUES.has(clean)
    && !NON_PUBLIC_TERRITORY_PATTERNS.some((pattern) => clean.includes(pattern));
};
const todayIso = () => new Date().toISOString().slice(0, 10);
const sevenDaysAgoIso = () => {
  const d = new Date();
  d.setDate(d.getDate() - 6);
  return d.toISOString().slice(0, 10);
};

const authHeaders = () => {
  const token = localStorage.getItem('token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const responseError = async (response, fallback) => {
  try {
    const data = await response.json();
    if (data?.detail) return Array.isArray(data.detail) ? data.detail.map((item) => item.msg || item.detail || JSON.stringify(item)).join(' ') : data.detail;
    if (data?.error) return data.error;
  } catch (_) {
    try {
      const text = await response.text();
      if (text) return text;
    } catch (_) {}
  }
  return `${fallback} (HTTP ${response.status})`;
};

const downloadBlob = (content, filename, type) => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const blobToFile = (blob, filename) => new File([blob], filename, { type: blob.type });
const slideFilename = (idx, slide, extension = 'png') => {
  const clean = String(slide?.title || `lamina-${idx + 1}`)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return `sisc-en-cifras-${String(idx + 1).padStart(2, '0')}-${clean}.${extension}`;
};

const textEncoder = new TextEncoder();
const crcTable = Array.from({ length: 256 }, (_, index) => {
  let value = index;
  for (let bit = 0; bit < 8; bit += 1) {
    value = value & 1 ? 0xEDB88320 ^ (value >>> 1) : value >>> 1;
  }
  return value >>> 0;
});

const crc32 = (bytes) => {
  let crc = 0xFFFFFFFF;
  bytes.forEach((byte) => {
    crc = crcTable[(crc ^ byte) & 0xFF] ^ (crc >>> 8);
  });
  return (crc ^ 0xFFFFFFFF) >>> 0;
};

const writeUint16 = (target, offset, value) => {
  target[offset] = value & 0xFF;
  target[offset + 1] = (value >>> 8) & 0xFF;
};

const writeUint32 = (target, offset, value) => {
  target[offset] = value & 0xFF;
  target[offset + 1] = (value >>> 8) & 0xFF;
  target[offset + 2] = (value >>> 16) & 0xFF;
  target[offset + 3] = (value >>> 24) & 0xFF;
};

const zipDateParts = () => {
  const now = new Date();
  const time = (now.getHours() << 11) | (now.getMinutes() << 5) | Math.floor(now.getSeconds() / 2);
  const date = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
  return { time, date };
};

const createZipBlob = async (files) => {
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  const { time, date } = zipDateParts();

  for (const file of files) {
    const nameBytes = textEncoder.encode(file.name);
    const data = new Uint8Array(await file.blob.arrayBuffer());
    const checksum = crc32(data);

    const local = new Uint8Array(30 + nameBytes.length);
    writeUint32(local, 0, 0x04034B50);
    writeUint16(local, 4, 20);
    writeUint16(local, 6, 0);
    writeUint16(local, 8, 0);
    writeUint16(local, 10, time);
    writeUint16(local, 12, date);
    writeUint32(local, 14, checksum);
    writeUint32(local, 18, data.length);
    writeUint32(local, 22, data.length);
    writeUint16(local, 26, nameBytes.length);
    writeUint16(local, 28, 0);
    local.set(nameBytes, 30);
    localParts.push(local, data);

    const central = new Uint8Array(46 + nameBytes.length);
    writeUint32(central, 0, 0x02014B50);
    writeUint16(central, 4, 20);
    writeUint16(central, 6, 20);
    writeUint16(central, 8, 0);
    writeUint16(central, 10, 0);
    writeUint16(central, 12, time);
    writeUint16(central, 14, date);
    writeUint32(central, 16, checksum);
    writeUint32(central, 20, data.length);
    writeUint32(central, 24, data.length);
    writeUint16(central, 28, nameBytes.length);
    writeUint16(central, 30, 0);
    writeUint16(central, 32, 0);
    writeUint16(central, 34, 0);
    writeUint16(central, 36, 0);
    writeUint32(central, 38, 0);
    writeUint32(central, 42, offset);
    central.set(nameBytes, 46);
    centralParts.push(central);
    offset += local.length + data.length;
  }

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const end = new Uint8Array(22);
  writeUint32(end, 0, 0x06054B50);
  writeUint16(end, 8, files.length);
  writeUint16(end, 10, files.length);
  writeUint32(end, 12, centralSize);
  writeUint32(end, 16, offset);
  writeUint16(end, 20, 0);

  return new Blob([...localParts, ...centralParts, end], { type: 'application/zip' });
};

const svgToPngBlob = (svgText, width = 1080, height = 1350) => new Promise((resolve, reject) => {
  const svgBlob = new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);
  const image = new Image();
  image.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('No se pudo convertir la lamina a PNG.'));
    }, 'image/png', 0.95);
  };
  image.onerror = () => {
    URL.revokeObjectURL(url);
    reject(new Error('No se pudo preparar la imagen para WhatsApp.'));
  };
  image.src = url;
});

const buildWhatsappText = (publication) => {
  if (!publication) return '';
  const period = publication.period ? `${publication.period.start} al ${publication.period.end}` : 'periodo seleccionado';
  const label = comparisonLabel(publication);
  const insightLines = (publication.insights || [])
    .filter((insight) => publicFacingText(insight.title || insight.detail))
    .slice(0, 3)
    .map((insight) => `- ${publicInsightText(insight.detail, label)}`);
  const sourceLines = (publication.sources || [])
    .filter((source) => source.publication_level === 'PUBLICO')
    .map((source) => `${source.name}: corte ${source.last_cutoff_date || 'sin corte'}`);
  const body = insightLines.length
    ? insightLines.join('\n')
    : '- Boletin generado sin hallazgos publicables. Revise disponibilidad y calidad de datos.';

  return [
    'SISC EN CIFRAS',
    `Jamundi | ${period}`,
    `Comparado con: ${label}`,
    '',
    body,
    '',
    `Fuentes: ${sourceLines.join(' | ') || 'SISC'}`,
    'Secretaria de Seguridad y Convivencia',
    'Cifras agregadas para informacion ciudadana.',
  ].join('\n');
};

const escapeSvg = (text = '') => String(text).replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
}[char]));

let escudoDataUrlCache = null;
const getEscudoDataUrl = async () => {
  if (escudoDataUrlCache) return escudoDataUrlCache;
  try {
    const response = await fetch('/assets/escudo-limpio.png');
    const blob = await response.blob();
    escudoDataUrlCache = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    return escudoDataUrlCache;
  } catch (_) {
    return null;
  }
};

const wrapText = (text = '', maxChars = 34, maxLines = 3) => {
  const words = String(text).split(/\s+/).filter(Boolean);
  const lines = [];
  let current = '';
  words.forEach((word) => {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  });
  if (current) lines.push(current);
  if (lines.length > maxLines) {
    const clipped = lines.slice(0, maxLines);
    clipped[maxLines - 1] = `${clipped[maxLines - 1].replace(/\.*$/, '')}...`;
    return clipped;
  }
  return lines;
};

const svgTextBlock = (text, x, y, options = {}) => {
  const {
    size = 30,
    fill = '#000000',
    weight = 800,
    maxChars = 34,
    maxLines = 3,
    lineHeight = Math.round(size * 1.22),
    anchor = 'start',
  } = options;
  return wrapText(text, maxChars, maxLines).map((line, idx) =>
    `<text x="${x}" y="${y + idx * lineHeight}" text-anchor="${anchor}" font-size="${size}" font-weight="${weight}" fill="${fill}" font-family="Calibri, Arial, sans-serif">${escapeSvg(line)}</text>`
  ).join('');
};

const publicMeasureName = (text = '') => {
  const clean = String(text || '').trim().replace(/\s+/g, ' ');
  const upper = clean.toUpperCase();
  if (!clean || ['NAN', 'NONE', 'NULL', 'SIN ESPECIFICAR'].includes(upper)) {
    return '';
  }
  if (upper.includes('PROHIBICION DE INGRESO') || upper.includes('PROHIBICIÃ“N DE INGRESO')) {
    return 'Restricciones de ingreso a eventos publicos';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL') && upper.includes('TIPO 4')) {
    return 'Comparendos con multa de mayor cuantia';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL') && upper.includes('TIPO 3')) {
    return 'Comparendos con multa de cuantia alta';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL') && upper.includes('TIPO 2')) {
    return 'Comparendos con multa de cuantia media';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL') && upper.includes('TIPO 1')) {
    return 'Comparendos con multa de menor cuantia';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL')) {
    return 'Comparendos por convivencia ciudadana';
  }
  if (upper.includes('AMONEST')) return 'Amonestaciones por convivencia ciudadana';
  if (upper.includes('PARTICIP') && (upper.includes('PROGRAMA') || upper.includes('COMUNIT'))) {
    return 'Participacion en programas comunitarios';
  }
  if (upper.includes('REPAR') || upper.includes('DANO') || upper.includes('DAÃ‘O')) {
    return 'Reparacion por danos a la convivencia';
  }
  if (upper.includes('DESTRU') || upper.includes('BIEN')) {
    return 'Medidas sobre bienes relacionados con convivencia';
  }
  return clean;
};

const publicFacingText = (text = '') => publicMeasureName(text)
  .replace(/MULTA\s+GENERAL\s+TIPO\s+4/gi, 'Comparendos con multa de mayor cuantia')
  .replace(/MULTA\s+GENERAL\s+TIPO\s+3/gi, 'Comparendos con multa de cuantia alta')
  .replace(/MULTA\s+GENERAL\s+TIPO\s+2/gi, 'Comparendos con multa de cuantia media')
  .replace(/MULTA\s+GENERAL\s+TIPO\s+1/gi, 'Comparendos con multa de menor cuantia')
  .replace(/PROHIBICI[OÃ“]N DE INGRESO A ACTIVIDAD QUE INVOLUCRA AGLOMERACIONES DE PUBLICO COMPLEJAS O NO COMPLEJAS/gi, 'Restricciones de ingreso a eventos publicos')
  .replace(/MULTA\s+GENERAL/gi, 'Comparendos por convivencia ciudadana');

const indicatorDisplayName = (indicator = {}) => publicMeasureName(indicator.indicator_name || indicator.title || '');
const isPublicIndicator = (indicator = {}) => Boolean(indicatorDisplayName(indicator));

const indicatorPublicDetail = (indicator = {}) => {
  if (indicator.metadata?.public_detail) return indicator.metadata.public_detail;
  const technical = indicator.metadata?.technical_name || indicator.indicator_name || indicator.title || '';
  const upper = String(technical).toUpperCase();
  if (!upper || ['NAN', 'NONE', 'NULL', 'SIN ESPECIFICAR'].includes(upper)) {
    return '';
  }
  if (upper.includes('PROHIBICION DE INGRESO') || upper.includes('PROHIBICIÃ“N DE INGRESO')) {
    return 'Medida aplicada para limitar el ingreso a actividades o eventos con publico.';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL') && upper.includes('TIPO 4')) {
    return 'La fuente informa la categoria de la multa, no el comportamiento especifico.';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL') && upper.includes('TIPO 3')) {
    return 'La fuente informa la categoria de la multa, no el comportamiento especifico.';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL') && upper.includes('TIPO 2')) {
    return 'La fuente informa la categoria de la multa, no el comportamiento especifico.';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL') && upper.includes('TIPO 1')) {
    return 'La fuente informa la categoria de la multa, no el comportamiento especifico.';
  }
  if (upper.includes('MULTA') && upper.includes('GENERAL')) {
    return 'La fuente reporta el tipo de multa; para saber el comportamiento se requiere articulo o numeral.';
  }
  return '';
};

const indicatorSourceLabel = (indicator = {}) => {
  const source = String(indicator.source || '').toUpperCase();
  if (source.includes('COMISARIAS')) return 'Comisarias de Familia';
  if (source.includes('INSPECCIONES') || source.includes('RNMC')) return 'Inspecciones de Policia';
  if (source.includes('POLICIA')) return 'Policia Nacional';
  return indicator.source || '';
};

const comparisonLabel = (publication) => publication?.comparison_label || 'mismo periodo del ano anterior';
const comparisonShortLabel = (publication) => {
  const label = comparisonLabel(publication).toLowerCase();
  if (label.includes('ano anterior')) return 'mismo periodo AA';
  if (label.includes('periodo anterior')) return 'periodo anterior';
  return label;
};
const normalizeComparisonText = (text = '', label = 'mismo periodo del ano anterior') => String(text)
  .replace(/frente al periodo anterior/gi, `frente al ${label}`)
  .replace(/frente al mismo periodo del ano anterior/gi, `frente al ${label}`)
  .replace(/vs periodo anterior/gi, `vs ${label}`)
  .replace(/vs mismo periodo AA/gi, `vs ${label}`);

const publicInsightText = (text = '', label = 'mismo periodo del ano anterior') =>
  publicFacingText(normalizeComparisonText(text, label));

const editionLabel = (publication) => {
  const type = publication?.edition_type;
  if (type === 'monthly') return 'BOLETIN MENSUAL';
  if (type === 'semester') return 'BOLETIN SEMESTRAL';
  if (type === 'annual') return 'BOLETIN ANUAL';
  if (type === 'security') return 'SEGURIDAD';
  if (type === 'convivencia') return 'CONVIVENCIA';
  if (type === 'territory') return 'TERRITORIO';
  return 'BOLETIN SEMANAL';
};

const slideNumberLabel = (slide, publication) => {
  const slides = publication?.slides || [];
  const index = Math.max(0, slides.findIndex((item) => item.title === slide.title));
  return `${String(index + 1).padStart(2, '0')} / ${String(slides.length || 5).padStart(2, '0')}`;
};

const visualSceneSvg = (title, color) => {
  if (title === 'SISC EN CIFRAS') {
    return `
      <g opacity="0.95">
        <circle cx="720" cy="190" r="46" fill="#FFE000" opacity="0.82"/>
        <path d="M590 276 C648 218 694 226 738 274 C786 218 848 224 910 286 Z" fill="#FFFFFF" opacity="0.16"/>
        <path d="M612 295 H968 V330 H612 Z" fill="#FFFFFF" opacity="0.12"/>
        <rect x="648" y="244" width="44" height="86" rx="8" fill="#FFFFFF" opacity="0.22"/>
        <rect x="704" y="220" width="58" height="110" rx="10" fill="#FFFFFF" opacity="0.18"/>
        <rect x="776" y="254" width="52" height="76" rx="8" fill="#FFFFFF" opacity="0.20"/>
        <rect x="842" y="232" width="66" height="98" rx="10" fill="#FFFFFF" opacity="0.16"/>
        <path d="M604 330 C690 300 794 304 982 334" fill="none" stroke="#FFE000" stroke-width="8" opacity="0.44"/>
      </g>
    `;
  }
  if (title === 'SEGURIDAD') {
    return `
      <g opacity="0.96">
        <circle cx="836" cy="210" r="112" fill="#FFFFFF" opacity="0.10"/>
        <path d="M835 112 L920 144 V214 C920 278 878 318 835 340 C792 318 750 278 750 214 V144 Z" fill="#FFFFFF" opacity="0.18"/>
        <path d="M835 142 L890 164 V215 C890 254 866 282 835 300 C804 282 780 254 780 215 V164 Z" fill="#FFE000" opacity="0.72"/>
        <path d="M800 222 L826 248 L872 194" fill="none" stroke="#281FD0" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>
      </g>
    `;
  }
  if (title === 'CONVIVENCIA') {
    return `
      <g opacity="0.96">
        <circle cx="846" cy="214" r="118" fill="#FFFFFF" opacity="0.10"/>
        <circle cx="805" cy="198" r="34" fill="#FFE000" opacity="0.78"/>
        <circle cx="885" cy="198" r="34" fill="#FFFFFF" opacity="0.72"/>
        <path d="M742 292 C774 246 832 238 846 292" fill="none" stroke="#FFFFFF" stroke-width="26" stroke-linecap="round" opacity="0.38"/>
        <path d="M846 292 C860 238 918 246 950 292" fill="none" stroke="#FFE000" stroke-width="26" stroke-linecap="round" opacity="0.46"/>
        <path d="M768 144 H928" stroke="#FFFFFF" stroke-width="10" stroke-linecap="round" opacity="0.24"/>
        <path d="M792 326 H904" stroke="#FFE000" stroke-width="10" stroke-linecap="round" opacity="0.48"/>
      </g>
    `;
  }
  if (title === 'TERRITORIO') {
    return `
      <g opacity="0.95">
        <path d="M760 114 L946 168 L910 336 L704 292 Z" fill="#FFFFFF" opacity="0.17"/>
        <path d="M760 114 L704 292 M830 134 L778 306 M896 154 L850 322 M722 228 L926 286 M738 174 L940 230" stroke="#FFFFFF" stroke-width="5" opacity="0.20"/>
        <circle cx="820" cy="228" r="26" fill="#FFE000" opacity="0.86"/>
        <path d="M820 188 C786 188 762 212 762 244 C762 290 820 334 820 334 C820 334 878 290 878 244 C878 212 854 188 820 188 Z" fill="#FFE000" opacity="0.42"/>
        <circle cx="820" cy="244" r="17" fill="#281FD0" opacity="0.88"/>
      </g>
    `;
  }
  return `
    <g opacity="0.95">
      <circle cx="842" cy="214" r="112" fill="#FFFFFF" opacity="0.10"/>
      <path d="M756 280 H936" stroke="#FFFFFF" stroke-width="12" stroke-linecap="round" opacity="0.24"/>
      <path d="M790 236 L840 186 L890 236" fill="none" stroke="#FFE000" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" opacity="0.82"/>
      <path d="M790 274 L840 324 L890 274" fill="none" stroke="#FFFFFF" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" opacity="0.72"/>
      <rect x="746" y="152" width="188" height="188" rx="38" fill="#FFFFFF" opacity="0.08" stroke="#FFFFFF" stroke-width="4"/>
    </g>
  `;
};

const slideToSvg = (slide, publication, assets = {}) => {
  const color = DOMAIN_COLORS[slide.title] || '#281FD0';
  const secondary = slide.title === 'CONVIVENCIA' ? '#3A30F1' : slide.title === 'TERRITORIO' ? '#606175' : '#281FD0';
  const period = `${publication?.period?.start || ''} - ${publication?.period?.end || ''}`;
  const subtitle = slide.subtitle || period;
  const subtitleLine = subtitle.toLowerCase().startsWith('jamundi') ? subtitle : `Jamundi | ${subtitle}`;
  const rows = (slide.indicators || []).filter((row) => isPublicIndicator(row)
    && (slide.title !== 'TERRITORIO' || isPublicTerritoryName(row.geography || row.indicator_name)));
  const insights = slide.insights || [];
  const blocks = slide.blocks || [];
  const escudo = assets.escudoDataUrl;
  const edition = editionLabel(publication);
  const slideNumber = slideNumberLabel(slide, publication);
  const trendText = (value) => {
    if (value === null || value === undefined) return 'Sin comparativo';
    if (Math.abs(Number(value)) < 0.05) return 'Sin variacion';
    return `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}% vs ${comparisonShortLabel(publication)}`;
  };

  const statIcon = (domain, x, y) => {
    const iconColor = DOMAIN_COLORS[domain] || secondary;
    if (domain === 'SEGURIDAD') {
      return `<path d="M${x + 34} ${y + 10} L${x + 70} ${y + 24} V${y + 54} C${x + 70} ${y + 80} ${x + 52} ${y + 98} ${x + 34} ${y + 106} C${x + 16} ${y + 98} ${x - 2} ${y + 80} ${x - 2} ${y + 54} V${y + 24} Z" fill="${iconColor}" opacity="0.14"/><path d="M${x + 34} ${y + 22} L${x + 58} ${y + 31} V${y + 55} C${x + 58} ${y + 70} ${x + 48} ${y + 82} ${x + 34} ${y + 89} C${x + 20} ${y + 82} ${x + 10} ${y + 70} ${x + 10} ${y + 55} V${y + 31} Z" fill="${iconColor}"/>`;
    }
    if (domain === 'CONVIVENCIA') {
      return `<circle cx="${x + 34}" cy="${y + 44}" r="31" fill="${iconColor}" opacity="0.14"/><path d="M${x + 15} ${y + 52} C${x + 28} ${y + 38} ${x + 40} ${y + 38} ${x + 53} ${y + 52}" stroke="${iconColor}" stroke-width="10" stroke-linecap="round" fill="none"/><circle cx="${x + 22}" cy="${y + 31}" r="11" fill="${iconColor}"/><circle cx="${x + 47}" cy="${y + 31}" r="11" fill="${iconColor}"/>`;
    }
    return `<path d="M${x + 10} ${y + 72} L${x + 34} ${y + 26} L${x + 58} ${y + 72} Z" fill="${iconColor}" opacity="0.14"/><path d="M${x + 6} ${y + 74} H${x + 64} M${x + 18} ${y + 74} V${y + 50} M${x + 34} ${y + 74} V${y + 36} M${x + 50} ${y + 74} V${y + 50}" stroke="${iconColor}" stroke-width="8" stroke-linecap="round"/>`;
  };

  const compactCover = slide.type === 'cover' && blocks.length >= 3;
  const blockSvg = blocks.slice(0, compactCover ? 3 : 4).map((b, idx) => {
    const x = compactCover ? 76 + idx * 309 : (idx % 2 === 0 ? 76 : 552);
    const y = compactCover ? 408 : 408 + Math.floor(idx / 2) * 218;
    const width = compactCover ? 286 : 452;
    const titleSize = compactCover ? 20 : 24;
    const valueSize = compactCover ? 46 : 52;
    const unitSize = compactCover ? 18 : 23;
    const iconX = compactCover ? x + 196 : x + 326;
    const c = DOMAIN_COLORS[b.domain] || secondary;
    return `
      <rect x="${x}" y="${y}" width="${width}" height="184" rx="28" fill="#FFFFFF" stroke="#D9E2F0" stroke-width="2"/>
      <rect x="${x}" y="${y}" width="${width}" height="12" rx="6" fill="${c}"/>
      ${statIcon(b.domain, iconX, y + 42)}
      ${svgTextBlock(b.domain, x + 30, y + 54, { size: titleSize, fill: c, weight: 900, maxChars: compactCover ? 16 : 19, maxLines: 1 })}
      <text x="${x + 30}" y="${y + 111}" font-size="${valueSize}" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">${fmt(b.value)}</text>
      ${svgTextBlock(b.unit, x + 30, y + 144, { size: unitSize, fill: '#334155', weight: 800, maxChars: compactCover ? 19 : 24, maxLines: 1 })}
      <text x="${x + 30}" y="${y + 168}" font-size="17" font-weight="800" fill="#64748B" font-family="Calibri, Arial, sans-serif">Corte ${escapeSvg(b.cutoff_date || 'sin corte')} | ${escapeSvg(b.quality_status)}</text>
    `;
  }).join('');

  const indicatorSvg = rows.slice(0, 6).map((row, idx) => {
    const y = 420 + idx * 106;
    const width = Math.min(690, 90 + Number(row.value || 0) * 16);
    const displayName = indicatorDisplayName(row);
    const publicDetail = indicatorPublicDetail(row);
    const technicalName = row.metadata?.technical_name && row.metadata.technical_name !== row.indicator_name
      ? row.metadata.technical_name
      : displayName !== row.indicator_name
        ? row.indicator_name
      : '';
    const sourceLabel = indicatorSourceLabel(row);
    const unitLabel = row.unit || '';
    const helperLine = [sourceLabel, publicDetail || unitLabel].filter(Boolean).join(' | ')
      || (technicalName ? `Clasificacion interna: ${technicalName}` : '');
    const barY = helperLine ? y + 20 : y + 6;
    return `
      <rect x="76" y="${y - 48}" width="928" height="84" rx="22" fill="#FFFFFF" stroke="#D9E2F0" stroke-width="2"/>
      ${svgTextBlock(displayName, 108, y - 14, { size: 24, fill: '#172033', weight: 900, maxChars: 39, maxLines: 1 })}
      ${helperLine ? svgTextBlock(helperLine, 108, y + 8, { size: 13, fill: '#64748B', weight: 800, maxChars: 62, maxLines: 1 }) : ''}
      <rect x="108" y="${barY}" width="690" height="14" rx="7" fill="#E2E8F0"/>
      <rect x="108" y="${barY}" width="${width}" height="14" rx="7" fill="${secondary}"/>
      <text x="856" y="${y + 12}" font-size="34" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">${fmt(row.value)}</text>
    `;
  }).join('');

  const emptyIndicatorSvg = `
    <rect x="76" y="430" width="928" height="196" rx="30" fill="#F8FAFC" stroke="#D9E2F0" stroke-width="2"/>
    <circle cx="138" cy="528" r="34" fill="${secondary}" opacity="0.12"/>
    <text x="138" y="539" text-anchor="middle" font-size="30" font-weight="900" fill="${secondary}" font-family="Calibri, Arial, sans-serif">i</text>
    <text x="196" y="500" font-size="28" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">Sin datos territoriales publicables</text>
    ${svgTextBlock('No se encontraron barrios, comunas o zonas con nombre validado y volumen suficiente para destacar en este periodo.', 196, 544, { size: 22, fill: '#64748B', weight: 800, maxChars: 58, maxLines: 2, lineHeight: 30 })}
  `;

  const changesSvg = insights.slice(0, 4).map((insight, idx) => {
    const y = 408 + idx * 118;
    const domainColor = DOMAIN_COLORS[insight.domain] || secondary;
    const detail = publicInsightText(insight.detail, comparisonLabel(publication));
    const title = publicFacingText(insight.title);
    return `
      <rect x="76" y="${y - 36}" width="928" height="96" rx="24" fill="#FFFFFF" stroke="#D9E2F0" stroke-width="2"/>
      <circle cx="124" cy="${y + 12}" r="26" fill="${domainColor}" opacity="0.12"/>
      <text x="124" y="${y + 21}" text-anchor="middle" font-size="22" font-weight="900" fill="${domainColor}" font-family="Calibri, Arial, sans-serif">${idx + 1}</text>
      <text x="166" y="${y - 2}" font-size="16" font-weight="900" fill="${domainColor}" font-family="Calibri, Arial, sans-serif" letter-spacing="2">${escapeSvg(insight.domain)}</text>
      ${svgTextBlock(title, 166, y + 30, { size: 25, fill: '#3A3A44', weight: 900, maxChars: 30, maxLines: 1 })}
      ${svgTextBlock(detail, 520, y + 12, { size: 21, fill: '#475569', weight: 800, maxChars: 40, maxLines: 2, lineHeight: 28 })}
    `;
  }).join('');

  const emptyChangesSvg = `
    <rect x="76" y="430" width="928" height="176" rx="30" fill="#F8FAFC" stroke="#D9E2F0" stroke-width="2"/>
    <text x="112" y="492" font-size="28" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">Sin cambios publicables</text>
    <text x="112" y="534" font-size="22" font-weight="800" fill="#64748B" font-family="Calibri, Arial, sans-serif">No se encontraron variaciones relevantes con calidad suficiente.</text>
  `;

  const insightText = publicInsightText(
    slide.featured || insights[0]?.detail || 'Boletin generado para revision institucional.',
    comparisonLabel(publication)
  );
  const lecturaSvg = slide.type === 'cover' ? `
    <rect x="76" y="650" width="928" height="176" rx="30" fill="#F8FAFC" stroke="#D9E2F0" stroke-width="2"/>
    <text x="112" y="700" font-size="25" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">Lectura del periodo</text>
    <rect x="112" y="724" width="214" height="52" rx="26" fill="#281FD0" opacity="0.10"/>
    <text x="219" y="758" text-anchor="middle" font-size="20" font-weight="900" fill="#281FD0" font-family="Calibri, Arial, sans-serif">${blocks.length} dominios</text>
    <rect x="350" y="724" width="250" height="52" rx="26" fill="#3A30F1" opacity="0.10"/>
    <text x="475" y="758" text-anchor="middle" font-size="20" font-weight="900" fill="#3A30F1" font-family="Calibri, Arial, sans-serif">${(publication?.sources || []).length} fuentes revisadas</text>
    <rect x="624" y="724" width="300" height="52" rx="26" fill="#FFE000" opacity="0.36"/>
    <text x="774" y="758" text-anchor="middle" font-size="20" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">cortes independientes</text>
    ${svgTextBlock(insightText, 112, 808, { size: 22, fill: '#475569', weight: 800, maxChars: 72, maxLines: 1 })}
  ` : '';
  const insightSvg = svgTextBlock(insightText, 112, 978, {
    size: 30,
    fill: '#FFFFFF',
    weight: 900,
    maxChars: 46,
    maxLines: 3,
    lineHeight: 38,
  });
  const topVariation = blocks.find((b) => b.variation !== undefined && b.variation !== null)?.variation
    ?? rows.find((row) => row.variation_percentage !== undefined && row.variation_percentage !== null)?.variation_percentage;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
    <defs>
      <linearGradient id="hero" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#281FD0"/>
        <stop offset="65%" stop-color="${secondary}"/>
        <stop offset="100%" stop-color="#000000"/>
      </linearGradient>
      <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#3A3A44" flood-opacity="0.16"/>
      </filter>
    </defs>
    <rect width="1080" height="1350" fill="#F4F7FB"/>
    <path d="M0 1120 C120 1088 220 1130 354 1102 C520 1068 642 1126 790 1094 C932 1064 1008 1082 1080 1058 V1350 H0 Z" fill="#EAF1F8"/>
    <path d="M0 0 H1080 V336 C850 296 760 368 578 330 C386 289 258 317 0 360 Z" fill="url(#hero)"/>
    <rect width="1080" height="24" fill="#FFE000"/>
    <circle cx="930" cy="70" r="230" fill="#FFFFFF" opacity="0.08"/>
    <circle cx="870" cy="250" r="118" fill="#FFE000" opacity="0.16"/>
    <path d="M68 300 C178 240 250 244 338 286 C431 331 520 286 604 260 C722 224 834 239 1008 310" fill="none" stroke="#FFFFFF" stroke-width="5" opacity="0.16"/>
    ${visualSceneSvg(slide.title || 'SISC EN CIFRAS', secondary)}
    ${escudo ? `<image href="${escudo}" x="812" y="54" width="170" height="170" opacity="0.96"/>` : ''}
    <text x="76" y="86" font-size="24" font-weight="900" fill="#FFE000" font-family="Calibri, Arial, sans-serif" letter-spacing="4">ALCALDIA DE JAMUNDI</text>
    ${svgTextBlock(slide.title || 'SISC EN CIFRAS', 76, 168, { size: 64, fill: '#FFFFFF', weight: 900, maxChars: 20, maxLines: 2, lineHeight: 68 })}
    <text x="80" y="244" font-size="31" font-weight="900" fill="#FFFFFF" opacity="0.92" font-family="Calibri, Arial, sans-serif">${escapeSvg(subtitleLine)}</text>
    <rect x="76" y="266" width="218" height="38" rx="19" fill="#FFFFFF" opacity="0.16"/>
    <text x="100" y="291" font-size="15" font-weight="900" fill="#FFFFFF" font-family="Calibri, Arial, sans-serif" letter-spacing="2">${escapeSvg(edition)}</text>
    <rect x="318" y="266" width="92" height="38" rx="19" fill="#FFE000" opacity="0.92"/>
    <text x="364" y="291" text-anchor="middle" font-size="15" font-weight="900" fill="#000000" font-family="Calibri, Arial, sans-serif">${escapeSvg(slideNumber)}</text>
    <rect x="76" y="314" width="430" height="34" rx="17" fill="#FFFFFF" opacity="0.16"/>
    <text x="100" y="337" font-size="16" font-weight="900" fill="#FFFFFF" font-family="Calibri, Arial, sans-serif">${escapeSvg(trendText(topVariation))}</text>
    <rect x="52" y="360" width="976" height="818" rx="36" fill="#FFFFFF" opacity="0.74" filter="url(#shadow)"/>
    <rect x="52" y="360" width="976" height="818" rx="36" fill="#FFFFFF" opacity="0.72"/>
    ${slide.type === 'cover' ? blockSvg : slide.type === 'changes' ? (changesSvg || emptyChangesSvg) : (indicatorSvg || emptyIndicatorSvg)}
    ${lecturaSvg}
    <rect x="76" y="902" width="928" height="196" rx="30" fill="#3A3A44"/>
    <rect x="76" y="902" width="12" height="196" rx="6" fill="#FFE000"/>
    <text x="112" y="944" font-size="22" font-weight="900" fill="#FFE000" font-family="Calibri, Arial, sans-serif" letter-spacing="3">DATO DESTACADO</text>
    ${insightSvg}
    <rect x="76" y="1128" width="928" height="94" rx="26" fill="#FFFFFF" stroke="#D9E2F0" stroke-width="2"/>
    ${escudo ? `<image href="${escudo}" x="96" y="1144" width="58" height="58"/>` : ''}
    <text x="${escudo ? 172 : 96}" y="1172" font-size="24" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">Fuente: SISC | Secretaria de Seguridad y Convivencia</text>
    <text x="${escudo ? 172 : 96}" y="1204" font-size="18" font-weight="800" fill="#64748B" font-family="Calibri, Arial, sans-serif">Revision humana obligatoria antes de publicar. No contiene datos personales.</text>
    <text x="76" y="1286" font-size="20" font-weight="900" fill="#64748B" font-family="Calibri, Arial, sans-serif">SISC EN CIFRAS | Serie visual ${escapeSvg(edition.toLowerCase())}</text>
    <text x="1004" y="1286" text-anchor="end" font-size="18" font-weight="900" fill="#64748B" font-family="Calibri, Arial, sans-serif">${escapeSvg(slideNumber)}</text>
  </svg>`;
};

const summaryToSvg = (publication, assets = {}) => {
  const width = 1080;
  const height = 1920;
  const escudo = assets.escudoDataUrl;
  const cover = publication?.slides?.find((slide) => slide.type === 'cover') || publication?.slides?.[0] || {};
  const blocks = (cover.blocks || []).slice(0, 3);
  const insights = (publication?.insights || []).slice(0, 3);
  const label = comparisonLabel(publication);
  const period = publication?.period ? `${publication.period.start} - ${publication.period.end}` : 'periodo seleccionado';
  const featured = publicInsightText(
    cover.featured || insights[0]?.detail || 'Boletin generado para revision institucional.',
    label
  );

  const kpiCards = blocks.map((block, idx) => {
    const y = 392 + idx * 172;
    const color = DOMAIN_COLORS[block.domain] || '#281FD0';
    return `
      <rect x="76" y="${y}" width="928" height="136" rx="28" fill="#FFFFFF" stroke="#D9E2F0" stroke-width="2"/>
      <rect x="76" y="${y}" width="12" height="136" rx="6" fill="${color}"/>
      <text x="112" y="${y + 42}" font-size="23" font-weight="900" fill="${color}" font-family="Calibri, Arial, sans-serif">${escapeSvg(block.domain)}</text>
      <text x="112" y="${y + 100}" font-size="54" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">${fmt(block.value)}</text>
      ${svgTextBlock(block.unit, 270, y + 88, { size: 25, fill: '#334155', weight: 900, maxChars: 28, maxLines: 1 })}
      <text x="812" y="${y + 56}" font-size="18" font-weight="900" fill="#64748B" font-family="Calibri, Arial, sans-serif">Corte ${escapeSvg(block.cutoff_date || 'sin corte')}</text>
      <text x="812" y="${y + 92}" font-size="18" font-weight="900" fill="#64748B" font-family="Calibri, Arial, sans-serif">${escapeSvg(block.quality_status || '')}</text>
    `;
  }).join('');

  const changeCards = insights.map((insight, idx) => {
    const y = 1180 + idx * 150;
    const color = DOMAIN_COLORS[insight.domain] || '#281FD0';
    const detail = publicInsightText(insight.detail, label);
    return `
      <rect x="76" y="${y}" width="928" height="120" rx="26" fill="#FFFFFF" stroke="#D9E2F0" stroke-width="2"/>
      <circle cx="126" cy="${y + 60}" r="28" fill="${color}" opacity="0.12"/>
      <text x="126" y="${y + 70}" text-anchor="middle" font-size="24" font-weight="900" fill="${color}" font-family="Calibri, Arial, sans-serif">${idx + 1}</text>
      <text x="174" y="${y + 44}" font-size="17" font-weight="900" fill="${color}" font-family="Calibri, Arial, sans-serif" letter-spacing="2">${escapeSvg(insight.domain)}</text>
      ${svgTextBlock(detail, 174, y + 82, { size: 25, fill: '#3A3A44', weight: 900, maxChars: 50, maxLines: 2, lineHeight: 31 })}
    `;
  }).join('');

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <defs>
      <linearGradient id="summaryHero" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#281FD0"/>
        <stop offset="64%" stop-color="#3A30F1"/>
        <stop offset="100%" stop-color="#000000"/>
      </linearGradient>
      <filter id="summaryShadow" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#3A3A44" flood-opacity="0.14"/>
      </filter>
    </defs>
    <rect width="${width}" height="${height}" fill="#F4F7FB"/>
    <rect width="${width}" height="24" fill="#FFE000"/>
    <path d="M0 0 H1080 V334 C858 292 760 362 574 326 C390 290 252 320 0 356 Z" fill="url(#summaryHero)"/>
    <circle cx="908" cy="112" r="220" fill="#FFFFFF" opacity="0.08"/>
    <circle cx="860" cy="260" r="118" fill="#FFE000" opacity="0.16"/>
    <path d="M68 300 C178 240 250 244 338 286 C431 331 520 286 604 260 C722 224 834 239 1008 310" fill="none" stroke="#FFFFFF" stroke-width="5" opacity="0.16"/>
    ${escudo ? `<image href="${escudo}" x="830" y="58" width="142" height="142" opacity="0.96"/>` : ''}
    <text x="76" y="86" font-size="24" font-weight="900" fill="#FFE000" font-family="Calibri, Arial, sans-serif" letter-spacing="4">ALCALDIA DE JAMUNDI</text>
    <text x="76" y="168" font-size="66" font-weight="900" fill="#FFFFFF" font-family="Calibri, Arial, sans-serif">SISC EN CIFRAS</text>
    <text x="80" y="230" font-size="29" font-weight="900" fill="#FFFFFF" opacity="0.94" font-family="Calibri, Arial, sans-serif">Jamundi | ${escapeSvg(period)}</text>
    <rect x="76" y="262" width="540" height="46" rx="23" fill="#FFFFFF" opacity="0.16"/>
    <text x="100" y="292" font-size="18" font-weight="900" fill="#FFFFFF" font-family="Calibri, Arial, sans-serif">Comparacion: ${escapeSvg(label)}</text>

    <rect x="52" y="350" width="976" height="1410" rx="38" fill="#FFFFFF" opacity="0.78" filter="url(#summaryShadow)"/>
    <rect x="52" y="350" width="976" height="1410" rx="38" fill="#FFFFFF" opacity="0.76"/>
    <text x="76" y="348" font-size="1" fill="transparent">.</text>

    <text x="76" y="382" font-size="26" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">Resumen rapido</text>
    ${kpiCards}

    <rect x="76" y="930" width="928" height="196" rx="30" fill="#3A3A44"/>
    <rect x="76" y="930" width="12" height="196" rx="6" fill="#FFE000"/>
    <text x="112" y="972" font-size="22" font-weight="900" fill="#FFE000" font-family="Calibri, Arial, sans-serif" letter-spacing="3">DATO DESTACADO</text>
    ${svgTextBlock(featured, 112, 1014, { size: 34, fill: '#FFFFFF', weight: 900, maxChars: 45, maxLines: 3, lineHeight: 42 })}

    <text x="76" y="1160" font-size="26" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">Que cambio</text>
    ${changeCards || `
      <rect x="76" y="1180" width="928" height="132" rx="26" fill="#F8FAFC" stroke="#D9E2F0" stroke-width="2"/>
      <text x="112" y="1254" font-size="26" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">Sin cambios publicables para destacar</text>
    `}

    <rect x="76" y="1644" width="928" height="94" rx="26" fill="#FFFFFF" stroke="#D9E2F0" stroke-width="2"/>
    ${escudo ? `<image href="${escudo}" x="96" y="1660" width="58" height="58"/>` : ''}
    <text x="${escudo ? 172 : 96}" y="1688" font-size="24" font-weight="900" fill="#3A3A44" font-family="Calibri, Arial, sans-serif">Fuente: SISC | Secretaria de Seguridad y Convivencia</text>
    <text x="${escudo ? 172 : 96}" y="1720" font-size="18" font-weight="800" fill="#64748B" font-family="Calibri, Arial, sans-serif">Revision humana obligatoria antes de publicar. No contiene datos personales.</text>
    <text x="76" y="1838" font-size="22" font-weight="900" fill="#64748B" font-family="Calibri, Arial, sans-serif">SISC EN CIFRAS | Imagen resumen para chat</text>
  </svg>`;
};

const SlidePreview = ({ slide, publication }) => {
  const color = DOMAIN_COLORS[slide.title] || '#281FD0';
  const featured = publicInsightText(
    slide.featured || slide.insights?.[0]?.detail || 'Boletin generado para revision institucional.',
    comparisonLabel(publication)
  );
  const edition = editionLabel(publication);
  const slideNumber = slideNumberLabel(slide, publication);
  const previewIndicators = (slide.indicators || []).filter((indicator) => isPublicIndicator(indicator)
    && (slide.title !== 'TERRITORIO' || isPublicTerritoryName(indicator.geography || indicator.indicator_name)));
  return (
    <div className="aspect-[4/5] w-full max-w-[520px] overflow-hidden rounded-lg border border-slate-200 bg-[#f4f7fb] shadow-lg">
      <div className="h-2 bg-[#FFE000]" />
      <div className="relative overflow-hidden px-8 pb-14 pt-7 text-white" style={{ background: `linear-gradient(135deg, #281FD0, ${color}, #000000)` }}>
        <div className="absolute -right-10 -top-16 h-48 w-48 rounded-full bg-white/10" />
        <div className="absolute right-10 top-20 h-28 w-28 rounded-full bg-[#FFE000]/20" />
        <div className="absolute right-16 bottom-8 h-24 w-44 rounded-full border-8 border-white/15" />
        <img src="/assets/escudo-limpio.png" alt="Escudo Jamundi" className="absolute right-8 top-8 h-20 w-20 object-contain drop-shadow-md" />
        <p className="text-[9px] font-black uppercase tracking-[0.28em] text-[#FFE000]">Alcaldia de Jamundi</p>
        <div className="mt-3 flex items-center gap-2">
          <span className="rounded-full bg-white/15 px-3 py-1 text-[8px] font-black uppercase tracking-widest text-white">{edition}</span>
          <span className="rounded-full bg-[#FFE000] px-3 py-1 text-[8px] font-black text-slate-950">{slideNumber}</span>
        </div>
        <h2 className="mt-3 max-w-[330px] text-4xl font-black uppercase leading-none tracking-tight">{slide.title}</h2>
        <p className="mt-3 text-sm font-bold text-white/90">{slide.subtitle || `${publication?.period?.start} - ${publication?.period?.end}`}</p>
      </div>
      <div className="-mt-8 space-y-4 p-6">
        <div className="rounded-3xl bg-white/90 p-4 shadow-xl ring-1 ring-slate-200">
          <div className="grid grid-cols-2 gap-3">
            {slide.blocks?.map((block) => (
              <div key={block.domain} className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-[9px] font-black uppercase tracking-widest" style={{ color: DOMAIN_COLORS[block.domain] || color }}>{block.domain}</p>
                <p className="mt-2 text-3xl font-black text-slate-950">{fmt(block.value)}</p>
                <p className="text-xs font-bold text-slate-500">{block.unit}</p>
                <p className="mt-2 text-[10px] font-bold text-slate-400">Corte: {block.cutoff_date || 'sin corte'}</p>
              </div>
            ))}
          </div>
          {previewIndicators.slice(0, 5).map((indicator) => (
            <div key={indicator.id} className="mt-3 rounded-2xl border border-slate-200 bg-white p-3">
              <div className="mb-1 flex items-center justify-between gap-3">
                <p className="truncate text-xs font-black uppercase text-slate-600">{indicatorDisplayName(indicator)}</p>
                <p className="text-sm font-black text-slate-900">{fmt(indicator.value)}</p>
              </div>
              {(indicatorSourceLabel(indicator) || indicatorPublicDetail(indicator) || (indicator.metadata?.technical_name && indicator.metadata.technical_name !== indicator.indicator_name) || indicatorDisplayName(indicator) !== indicator.indicator_name) && (
                <p className="mb-2 truncate text-[10px] font-bold text-slate-400">{[indicatorSourceLabel(indicator), indicatorPublicDetail(indicator) || indicator.unit].filter(Boolean).join(' | ') || `Clasificacion interna: ${indicator.metadata?.technical_name || indicator.indicator_name}`}</p>
              )}
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, 18 + Number(indicator.value || 0) * 6)}%`, backgroundColor: color }} />
              </div>
            </div>
          ))}
          {slide.title === 'TERRITORIO' && previewIndicators.length === 0 && (
            <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-black uppercase text-slate-700">Sin datos territoriales publicables</p>
              <p className="mt-1 text-xs font-bold text-slate-500">No hay nombres validados con volumen suficiente para destacar.</p>
            </div>
          )}
          <div className="mt-4 rounded-2xl bg-slate-950 p-4 text-white">
            <p className="text-[9px] font-black uppercase tracking-[0.24em] text-[#FFE000]">Dato destacado</p>
            <p className="mt-2 text-sm font-black leading-snug">{featured}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-2xl bg-white p-3 shadow-sm ring-1 ring-slate-200">
          <img src="/assets/escudo-limpio.png" alt="Escudo" className="h-9 w-9 object-contain" />
          <div>
            <p className="text-[11px] font-black text-slate-900">Fuente: SISC | Secretaria de Seguridad y Convivencia</p>
            <p className="text-[10px] font-bold text-slate-500">Revision humana obligatoria. Sin datos personales.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

const SiscCifras = ({ publicMode = false }) => {
  const [edition, setEdition] = useState('weekly');
  const [comparisonMode, setComparisonMode] = useState('auto');
  const [periodStart, setPeriodStart] = useState(sevenDaysAgoIso());
  const [periodEnd, setPeriodEnd] = useState(todayIso());
  const [sources, setSources] = useState([]);
  const [selectedSources, setSelectedSources] = useState(DEFAULT_SOURCES);
  const [publication, setPublication] = useState(null);
  const [activeSlide, setActiveSlide] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [shareStatus, setShareStatus] = useState(null);
  const [periodSuggested, setPeriodSuggested] = useState(false);
  const [institutionalPeriod, setInstitutionalPeriod] = useState('');

  const publicSources = useMemo(
    () => sources.filter((source) => source.publication_level === 'PUBLICO'),
    [sources]
  );

  const institutionalPeriods = useMemo(
    () => institutionalSiscCifrasPeriods(sources),
    [sources]
  );

  const fetchSources = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/sisc-cifras/sources`, { headers: authHeaders() });
      if (!response.ok) throw new Error(await responseError(response, 'No se pudo consultar el registro de fuentes.'));
      setSources(await response.json());
    } catch (err) {
      setError(err.message);
    }
  };

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/sisc-cifras/generate`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          edition_type: edition,
          period_start: periodStart,
          period_end: periodEnd,
          comparison_mode: comparisonMode,
          source_codes: selectedSources,
          max_insights: 5,
          save_history: !publicMode,
        }),
      });
      if (!response.ok) throw new Error(await responseError(response, 'No se pudo generar SISC en cifras.'));
      const data = await response.json();
      setPublication(data);
      setActiveSlide(0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleSource = (code) => {
    setSelectedSources((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code]
    );
  };

  const applySuggestedPeriod = (nextEdition = edition) => {
    const suggested = suggestedSiscCifrasPeriod(sources, nextEdition);
    setPeriodStart(suggested.start);
    setPeriodEnd(suggested.end);
  };

  const applyInstitutionalPeriod = (periodId) => {
    const selected = institutionalPeriods.find((item) => item.id === periodId);
    setInstitutionalPeriod(periodId);
    if (!selected) return;
    setEdition(selected.edition);
    setPeriodStart(selected.start);
    setPeriodEnd(selected.end);
  };

  const downloadJson = () => {
    if (!publication) return;
    downloadBlob(JSON.stringify(publication, null, 2), `sisc-en-cifras-${publication.id}.json`, 'application/json');
  };

  const downloadSvg = async () => {
    if (!publication?.slides?.length) return;
    const slide = publication.slides[activeSlide];
    const escudoDataUrl = await getEscudoDataUrl();
    downloadBlob(slideToSvg(slide, publication, { escudoDataUrl }), slideFilename(activeSlide, slide, 'svg'), 'image/svg+xml');
  };

  const downloadPngCarousel = async () => {
    if (!publication?.slides?.length) return;
    setShareStatus(null);
    try {
      const escudoDataUrl = await getEscudoDataUrl();
      const files = [];
      for (const [idx, slide] of publication.slides.entries()) {
        const blob = await svgToPngBlob(slideToSvg(slide, publication, { escudoDataUrl }));
        files.push({ name: slideFilename(idx, slide), blob });
      }
      const zip = await createZipBlob(files);
      downloadBlob(zip, `sisc-en-cifras-carrusel-${publication.id}.zip`, 'application/zip');
      setShareStatus(`${publication.slides.length} PNG guardados en un ZIP. Extraelo y adjunta las imagenes en orden en WhatsApp.`);
    } catch (err) {
      setShareStatus(err.message);
    }
  };

  const downloadSummaryImage = async () => {
    if (!publication) return;
    setShareStatus(null);
    try {
      const escudoDataUrl = await getEscudoDataUrl();
      const blob = await svgToPngBlob(summaryToSvg(publication, { escudoDataUrl }), 1080, 1920);
      downloadBlob(blob, `sisc-en-cifras-resumen-${publication.id}.png`, 'image/png');
      setShareStatus('Imagen resumen lista para enviar en un chat de WhatsApp.');
    } catch (err) {
      setShareStatus(err.message);
    }
  };

  const copyWhatsappText = async () => {
    if (!publication) return;
    setShareStatus(null);
    const text = buildWhatsappText(publication);
    try {
      await navigator.clipboard.writeText(text);
      setShareStatus('Texto copiado. Ya puedes pegarlo en WhatsApp.');
    } catch (_) {
      setShareStatus('No se pudo copiar automaticamente. Selecciona el texto de la caja de WhatsApp.');
    }
  };

  const shareWhatsappCarousel = async () => {
    if (!publication?.slides?.length) return;
    setShareStatus(null);
    try {
      const escudoDataUrl = await getEscudoDataUrl();
      const files = [];
      for (const [idx, slide] of publication.slides.entries()) {
        const blob = await svgToPngBlob(slideToSvg(slide, publication, { escudoDataUrl }));
        files.push(blobToFile(blob, slideFilename(idx, slide)));
      }
      const text = buildWhatsappText(publication);
      if (navigator.canShare?.({ files }) && navigator.share) {
        await navigator.share({ title: 'SISC en cifras', text, files });
        setShareStatus('Carrusel listo para compartir.');
      } else if (navigator.share) {
        await navigator.share({ title: 'SISC en cifras', text });
        setShareStatus('Texto compartido. Descarga el ZIP del carrusel para adjuntar las imagenes.');
      } else {
        const zip = await createZipBlob(files.map((file) => ({ name: file.name, blob: file })));
        downloadBlob(zip, `sisc-en-cifras-carrusel-${publication.id}.zip`, 'application/zip');
        await navigator.clipboard?.writeText(text);
        setShareStatus('Tu navegador no permite compartir directo. Descargue el ZIP y copie el texto.');
      }
    } catch (err) {
      if (err.name !== 'AbortError') setShareStatus(err.message || 'No se pudo compartir directamente.');
    }
  };

  useEffect(() => {
    fetchSources();
  }, []);

  useEffect(() => {
    if (!sources.length) return;
    const publicDefaults = DEFAULT_SOURCES.filter((code) =>
      sources.some((source) => source.code === code && source.publication_level === 'PUBLICO')
    );
    setSelectedSources((current) => {
      const next = [...current];
      publicDefaults.forEach((code) => {
        if (!next.includes(code)) next.push(code);
      });
      return next;
    });
  }, [sources]);

  useEffect(() => {
    if (!sources.length || periodSuggested) return;
    applySuggestedPeriod(edition);
    setPeriodSuggested(true);
  }, [sources, periodSuggested, edition]);

  const recommendedPeriod = useMemo(
    () => suggestedSiscCifrasPeriod(sources, edition),
    [sources, edition]
  );

  return (
    <div className="min-h-screen bg-[#F2F4F7]">
      <div className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#281FD0]">Redaccion estadistica automatizada</p>
            <h1 className="mt-1 text-3xl font-black uppercase tracking-tight text-slate-900">SISC en cifras</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={fetchSources} className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-black uppercase text-slate-600 hover:bg-slate-50">
              <RefreshCw size={15} /> Fuentes
            </button>
            <button onClick={downloadJson} disabled={!publication} className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-black uppercase text-slate-600 hover:bg-slate-50 disabled:opacity-40">
              <FileJson size={15} /> JSON
            </button>
            <button onClick={downloadSvg} disabled={!publication} className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-black uppercase text-slate-600 hover:bg-slate-50 disabled:opacity-40">
              <Download size={15} /> SVG
            </button>
            <button onClick={downloadPngCarousel} disabled={!publication} className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-black uppercase text-slate-600 hover:bg-slate-50 disabled:opacity-40">
              <ImageDown size={15} /> ZIP carrusel
            </button>
            <button onClick={downloadSummaryImage} disabled={!publication} className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-black uppercase text-slate-600 hover:bg-slate-50 disabled:opacity-40">
              <ImageDown size={15} /> Imagen resumen
            </button>
            <button onClick={copyWhatsappText} disabled={!publication} className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-black uppercase text-slate-600 hover:bg-slate-50 disabled:opacity-40">
              <Copy size={15} /> Copiar texto
            </button>
            <button onClick={shareWhatsappCarousel} disabled={!publication} className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-xs font-black uppercase text-white hover:bg-emerald-700 disabled:opacity-40">
              <MessageCircle size={15} /> Compartir
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-6 p-6 xl:grid-cols-[360px_1fr]">
        <aside className="space-y-5">
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2 text-slate-900">
              <CalendarDays size={18} />
              <h2 className="text-sm font-black uppercase tracking-wide">Modo rapido</h2>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_EDITIONS.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setEdition(item.id);
                    setInstitutionalPeriod('');
                    applySuggestedPeriod(item.id);
                  }}
                  className={`rounded-md px-3 py-2 text-xs font-black uppercase transition ${edition === item.id ? 'bg-[#281FD0] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="mt-3">
              <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Enfoque</p>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {FOCUS_EDITIONS.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      setEdition(item.id);
                      setInstitutionalPeriod('');
                      applySuggestedPeriod(item.id);
                    }}
                    className={`rounded-md px-2 py-2 text-[10px] font-black uppercase transition ${edition === item.id ? 'bg-[#281FD0] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
            <label className="mt-4 block text-[10px] font-black uppercase tracking-widest text-slate-500">
              Cierre institucional
              <select
                aria-label="Cierre institucional"
                value={institutionalPeriod}
                onChange={(event) => applyInstitutionalPeriod(event.target.value)}
                className="mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold normal-case tracking-normal text-slate-800 outline-none focus:border-[#281FD0]"
              >
                <option value="">Seleccionar periodo cerrado</option>
                {institutionalPeriods.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                Inicio
                <input type="date" value={periodStart} max={recommendedPeriod.end} onChange={(e) => setPeriodStart(e.target.value)} className="mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-800 outline-none focus:border-[#281FD0]" />
              </label>
              <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                Corte
                <input type="date" value={periodEnd} max={recommendedPeriod.end} onChange={(e) => setPeriodEnd(e.target.value)} className="mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-800 outline-none focus:border-[#281FD0]" />
              </label>
            </div>
            <button onClick={() => applySuggestedPeriod()} className="mt-3 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-[#281FD0]/30 bg-[#281FD0]/5 px-3 text-xs font-black text-[#281FD0] hover:bg-[#281FD0]/10">
              <CalendarDays size={15} /> Usar ultimo corte disponible
            </button>
            <div className="mt-5">
              <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Comparacion</p>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {COMPARISON_MODES.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setComparisonMode(item.id)}
                    className={`rounded-md px-2 py-2 text-[10px] font-black uppercase transition ${comparisonMode === item.id ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={generate}
              disabled={loading || selectedSources.length === 0}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-md bg-[#FFE000] px-4 py-3 text-sm font-black uppercase tracking-wide text-slate-950 shadow-sm hover:bg-[#FFB600] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="animate-spin" size={18} /> : <Sparkles size={18} />}
              Generar SISC en cifras
            </button>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2 text-slate-900">
              <Layers size={18} />
              <h2 className="text-sm font-black uppercase tracking-wide">Fuentes publicables</h2>
            </div>
            <div className="space-y-3">
              {publicSources.map((source) => {
                const selected = selectedSources.includes(source.code);
                return (
                  <button key={source.code} onClick={() => toggleSource(source.code)} className="w-full rounded-md border border-slate-200 p-3 text-left transition hover:bg-slate-50">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-black uppercase text-slate-800">{source.name}</p>
                        <p className="mt-1 text-[11px] font-bold text-slate-500">Corte: {source.last_cutoff_date || 'sin datos'} | {source.available_records} registros</p>
                      </div>
                      {selected ? <ToggleRight className="text-[#281FD0]" /> : <ToggleLeft className="text-slate-300" />}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </aside>

        <main className="space-y-6">
          {error && <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">{error}</div>}

          {!publication ? (
            <section className="flex min-h-[560px] items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white">
              <div className="max-w-md text-center">
                <BarChart3 className="mx-auto text-[#281FD0]" size={52} />
                <h2 className="mt-4 text-xl font-black uppercase text-slate-900">Semanal para seguimiento / Mensual para balance</h2>
                <p className="mt-2 text-sm font-semibold text-slate-500">Genera 5 laminas publicables para WhatsApp con comparacion automatica, trazabilidad de fuentes y revision institucional previa.</p>
              </div>
            </section>
          ) : (
            <>
              <section className="grid gap-4 lg:grid-cols-4">
                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Hallazgos</p>
                  <p className="mt-2 text-3xl font-black text-slate-900">{publication.insights?.length || 0}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Laminas</p>
                  <p className="mt-2 text-3xl font-black text-slate-900">{publication.slides?.length || 0}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Indicadores</p>
                  <p className="mt-2 text-3xl font-black text-slate-900">{publication.indicators?.length || 0}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Estado</p>
                  <p className="mt-2 flex items-center gap-2 text-lg font-black text-emerald-700"><CheckCircle2 size={20} /> {publication.governance?.history_saved ? 'Borrador guardado' : 'Vista previa'}</p>
                </div>
              </section>

              <section className="grid gap-6 xl:grid-cols-[560px_1fr]">
                <div>
                  <div className="mb-3 flex flex-wrap gap-2">
                    {publication.slides?.map((slide, idx) => (
                      <button key={`${slide.title}-${idx}`} onClick={() => setActiveSlide(idx)} className={`rounded-md px-3 py-2 text-xs font-black uppercase ${activeSlide === idx ? 'bg-[#281FD0] text-white' : 'bg-white text-slate-600 hover:bg-slate-100'}`}>
                        {idx + 1}. {slide.title}
                      </button>
                    ))}
                  </div>
                  <SlidePreview slide={publication.slides?.[activeSlide]} publication={publication} />
                </div>

                <div className="space-y-4">
                  <section className="rounded-lg border border-slate-200 bg-white p-5">
                    <div className="mb-4 flex items-center gap-2">
                      <MessageCircle size={18} className="text-emerald-600" />
                      <h2 className="text-sm font-black uppercase tracking-wide text-slate-900">Publicacion para WhatsApp</h2>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-4">
                      <button onClick={downloadPngCarousel} className="inline-flex items-center justify-center gap-2 rounded-md bg-slate-900 px-3 py-3 text-xs font-black uppercase text-white hover:bg-slate-700">
                        <ImageDown size={15} /> ZIP carrusel
                      </button>
                      <button onClick={downloadSummaryImage} className="inline-flex items-center justify-center gap-2 rounded-md bg-[#281FD0] px-3 py-3 text-xs font-black uppercase text-white hover:bg-[#1f18a8]">
                        <ImageDown size={15} /> Imagen resumen
                      </button>
                      <button onClick={copyWhatsappText} className="inline-flex items-center justify-center gap-2 rounded-md bg-slate-100 px-3 py-3 text-xs font-black uppercase text-slate-700 hover:bg-slate-200">
                        <Copy size={15} /> Copiar texto
                      </button>
                      <button onClick={shareWhatsappCarousel} className="inline-flex items-center justify-center gap-2 rounded-md bg-emerald-600 px-3 py-3 text-xs font-black uppercase text-white hover:bg-emerald-700">
                        <MessageCircle size={15} /> Compartir
                      </button>
                    </div>
                    {shareStatus && (
                      <p className="mt-3 rounded-md bg-emerald-50 p-3 text-xs font-bold text-emerald-800">{shareStatus}</p>
                    )}
                    <textarea
                      readOnly
                      value={buildWhatsappText(publication)}
                      className="mt-4 h-44 w-full resize-none rounded-md border border-slate-200 bg-slate-50 p-3 text-xs font-semibold leading-relaxed text-slate-700 outline-none"
                    />
                  </section>

                  <section className="rounded-lg border border-slate-200 bg-white p-5">
                    <div className="mb-4 flex items-center gap-2">
                      <ShieldCheck size={18} className="text-[#281FD0]" />
                      <h2 className="text-sm font-black uppercase tracking-wide text-slate-900">Hallazgos seleccionados</h2>
                    </div>
                    <div className="space-y-3">
                      {publication.insights?.map((insight) => (
                        <div key={insight.id} className="rounded-md bg-slate-50 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <p className="text-sm font-black uppercase text-slate-900">{publicFacingText(insight.title)}</p>
                            <span className="rounded bg-white px-2 py-1 text-[10px] font-black text-slate-500">score {insight.relevance_score}</span>
                          </div>
                          <p className="mt-2 text-sm font-semibold text-slate-600">{publicInsightText(insight.detail, comparisonLabel(publication))}</p>
                          <p className="mt-2 text-[11px] font-bold text-slate-400">{insight.domain} | {insight.source} | Corte {insight.cutoff_date || 'sin corte'}</p>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-lg border border-slate-200 bg-white p-5">
                    <h2 className="text-sm font-black uppercase tracking-wide text-slate-900">Trazabilidad y gobierno</h2>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      {publication.sources?.map((source) => (
                        <div key={source.code} className="rounded-md border border-slate-200 p-3">
                          <p className="text-xs font-black uppercase text-slate-800">{source.name}</p>
                          <p className="mt-1 text-[11px] font-bold text-slate-500">Corte: {source.last_cutoff_date || 'sin datos'}</p>
                          <p className="text-[11px] font-bold text-slate-500">Calidad: {source.quality_status}</p>
                        </div>
                      ))}
                    </div>
                    <p className="mt-4 rounded-md bg-amber-50 p-3 text-xs font-bold text-amber-800">
                      Revision humana obligatoria antes de publicar. Esta vista conserva fuentes, cortes y trazabilidad; las laminas y el resumen usan lenguaje ciudadano.
                    </p>
                  </section>
                </div>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
};

export default SiscCifras;


