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
