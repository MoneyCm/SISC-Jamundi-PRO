import type { CrimeRow } from '../types/stats';

export interface SabanaDeduplicationResult {
  rows: CrimeRow[];
  totalRows: number;
  duplicateRows: number;
}

const normalizeSourceCell = (value: unknown): string => {
  if (value instanceof Date) return value.toISOString();
  return String(value ?? '');
};

export const sourceRowRecordKey = (row: readonly unknown[]): string =>
  JSON.stringify(row.map(normalizeSourceCell));

export const crimeRowRecordKey = (row: CrimeRow): string | null =>
  row.SOURCE_ROW_KEY || null;

/** Identidad del hecho: HECHOS_ID de la Policía; sin él, la fila completa. */
export const crimeEventKey = (row: CrimeRow): string =>
  String(row.HECHOS_ID ?? '').trim() || `FILA:${row.SOURCE_ROW_KEY ?? JSON.stringify(row)}`;

/** Conductas que se cuentan por víctima, como las publica la Policía (metodología v2 del SISC). */
const CONDUCTAS_POR_VICTIMA = new Set(['HOMICIDIO', 'HOMICIDIO INTENCIONAL', 'HOMICIDIO DOLOSO']);

export const esConteoPorVictima = (conducta: string | undefined): boolean =>
  CONDUCTAS_POR_VICTIMA.has(String(conducta ?? '').trim().toUpperCase());

const victimaIds = new WeakMap<CrimeRow, number>();
let siguienteVictima = 0;

/** Clave de conteo: cada víctima de homicidio por separado; el resto, por hecho (crimeEventKey). */
export const crimeCountKey = (row: CrimeRow): string => {
  if (!esConteoPorVictima(row.CONDUCTA)) return crimeEventKey(row);
  if (row.SOURCE_ROW_KEY) return `V:${row.SOURCE_ROW_KEY}`;
  let id = victimaIds.get(row);
  if (id === undefined) { id = siguienteVictima++; victimaIds.set(row, id); }
  return `V#${id}`;
};

/**
 * La sábana trae una fila por víctima: un hecho con dos víctimas aparece dos veces. Las cifras
 * del boletín cuentan hechos únicos, salvo homicidio, que cuenta víctimas como la Policía; es la
 * misma regla del cálculo oficial del SISC (backend/services/hechos_metrics.py).
 * - byConduct=false: una fila por hecho (totales, series, barrios); cada víctima de homicidio suma.
 * - byConduct=true: una fila por hecho y conducta; un hecho con un homicidio y un lesionado
 *   cuenta en las dos conductas, como hace el servidor al contar por delito.
 */
export const uniqueCrimeEvents = (rows: CrimeRow[], byConduct = false): CrimeRow[] => {
  const seen = new Set<string>();
  return rows.filter((row) => {
    if (esConteoPorVictima(row.CONDUCTA)) return true; // cada fila de homicidio es una víctima
    const key = byConduct ? `${crimeEventKey(row)}|${row.CONDUCTA.trim().toUpperCase()}` : crimeEventKey(row);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export const deduplicateCrimeRows = (rows: CrimeRow[]): SabanaDeduplicationResult => {
  const seen = new Set<string>();
  const uniqueRows: CrimeRow[] = [];

  for (const row of rows) {
    const key = crimeRowRecordKey(row);
    if (!key) {
      uniqueRows.push(row);
      continue;
    }
    if (seen.has(key)) continue;
    seen.add(key);
    uniqueRows.push(row);
  }

  return {
    rows: uniqueRows,
    totalRows: rows.length,
    duplicateRows: rows.length - uniqueRows.length,
  };
};
