import { accentuate } from './accentuate.js';

// Valores vacíos de la fuente ("NAN", "SIN ESPECIFICAR") no se publican.
const EMPTY_VALUES = ['NAN', 'NONE', 'NULL', 'SIN ESPECIFICAR'];

export const publicFacingText = (text = '') => {
  const clean = String(text || '').trim().replace(/\s+/g, ' ');
  return EMPTY_VALUES.includes(clean.toUpperCase()) ? '' : clean
  .replace(/MULTA\s+GENERAL\s+TIPO\s+4/gi, 'Comparendos con multa de mayor cuantía')
  .replace(/MULTA\s+GENERAL\s+TIPO\s+3/gi, 'Comparendos con multa de cuantía alta')
  .replace(/MULTA\s+GENERAL\s+TIPO\s+2/gi, 'Comparendos con multa de cuantía media')
  .replace(/MULTA\s+GENERAL\s+TIPO\s+1/gi, 'Comparendos con multa de menor cuantía')
  .replace(/PROHIBICI[OÃ“]N DE INGRESO A ACTIVIDAD QUE INVOLUCRA AGLOMERACIONES DE PUBLICO COMPLEJAS O NO COMPLEJAS/gi, 'Restricciones de ingreso a eventos públicos')
  .replace(/MULTA\s+GENERAL/gi, 'Comparendos por convivencia ciudadana');
};

const normalizeComparisonText = (text = '', label = 'mismo periodo del ano anterior') => String(text)
  .replace(/frente al periodo anterior/gi, `frente al ${label}`)
  .replace(/frente al mismo periodo del a[nñ]o anterior/gi, `frente al ${label}`)
  .replace(/vs periodo anterior/gi, `vs ${label}`)
  .replace(/vs mismo periodo AA/gi, `vs ${label}`);

export const publicInsightText = (text = '', label = 'mismo periodo del año anterior') =>
  accentuate(publicFacingText(normalizeComparisonText(text, label)));

const comparisonLabel = (publication) => accentuate(publication?.comparison_label || 'mismo periodo del ano anterior');

export const buildWhatsappText = (publication, bulletinUrl) => {
  if (!publication) return '';
  const period = publication.period ? `${publication.period.start} al ${publication.period.end}` : 'periodo seleccionado';
  const label = comparisonLabel(publication);
  const insightLines = (publication.insights || [])
    .filter((insight) => publicFacingText(insight.title || insight.detail))
    .slice(0, 3)
    .map((insight) => {
      const title = publicFacingText(insight.title || '');
      const detail = publicInsightText(insight.detail, label);
      return `- ${title && !detail.toLowerCase().startsWith(title.toLowerCase()) ? `${title}: ` : ''}${detail}`;
    });
  const sourceLines = (publication.sources || [])
    .filter((source) => source.publication_level === 'PUBLICO' && source.included !== false && source.in_bulletin !== false)
    .map((source) => `${source.name}: corte ${source.last_cutoff_date || 'sin corte'}`);
  const body = insightLines.length
    ? insightLines.join('\n')
    : '- Boletín generado sin hallazgos publicables. Revise disponibilidad y calidad de datos.';

  return [
    'SISC EN CIFRAS',
    `Jamundí | ${period}`,
    publication.status === 'PUBLISHED' ? 'Edición oficial publicada.' : publication.governance?.history_saved ? 'Borrador pendiente de aprobación.' : 'Consulta personalizada; no es una edición oficial.',
    `Comparado con: ${label}${publication.comparison_period ? ` (${publication.comparison_period.start} al ${publication.comparison_period.end})` : ''}`,
    '',
    body,
    '',
    `Fuentes: ${sourceLines.join(' | ') || 'SISC'}`,
    'Secretaría de Seguridad y Convivencia',
    'Cifras agregadas para información ciudadana.',
    '',
    `Consultar boletines oficiales: ${bulletinUrl}`,
  ].join('\n');
};

