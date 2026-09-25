// El backend y los boletines ya guardados escriben muchos textos sin tildes ("ano anterior",
// "Policia Nacional"). Se corrigen al mostrarlos, sin cambiar los datos guardados ni los
// textos que el sistema compara internamente.
export const ACCENT_FIXES = [
  [/\bano anterior\b/gi, (m) => (m[0] === 'A' ? 'Año anterior' : 'año anterior')],
  [/\bboletin\b/g, 'boletín'], [/\bBoletin\b/g, 'Boletín'],
  [/\bultimos\b/g, 'últimos'], [/\bultimo\b/g, 'último'], [/\bUltimo\b/g, 'Último'],
  [/\bdias\b/g, 'días'], [/\bvariacion\b/g, 'variación'], [/\bcomparacion\b/g, 'comparación'],
  [/\bpequenas\b/g, 'pequeñas'], [/\btardios\b/g, 'tardíos'], [/\bdisminuyo\b/g, 'disminuyó'],
  [/\baumento (\d)/g, 'aumentó $1'], [/\b(\d+) mas\b/g, '$1 más'], [/\bpublicos\b/g, 'públicos'],
  [/\bcuantia\b/g, 'cuantía'], [/\bPROTECCION\b/g, 'PROTECCIÓN'], [/\bProteccion\b/g, 'Protección'],
  [/\bParticipacion\b/g, 'Participación'], [/\binformacion\b/g, 'información'],
  [/\bPolicia\b/g, 'Policía'], [/\bComisarias\b/g, 'Comisarías'], [/\bInspeccion\b/g, 'Inspección'],
  [/\brevision\b/g, 'revisión'],
];

export const accentuate = (text = '') =>
  ACCENT_FIXES.reduce((value, [pattern, replacement]) => value.replace(pattern, replacement), String(text));
