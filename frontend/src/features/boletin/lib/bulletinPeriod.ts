import type { CrimeRow, PeriodType } from '../types/stats';

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

/** Shared YTD boundary for the comparative table and PISCC. */
export function withinBulletinCutoff(row: CrimeRow, type: PeriodType, value: string | number) {
  if (type === 'anual') return true;
  if (type === 'semanal') return row.NoSEMANA >= 1 && row.NoSEMANA <= Number(value);
  const month = MONTHS.indexOf(String(row.MES).trim().toLowerCase().slice(0, 3));
  const cutoff = type === 'semestral' ? (String(value) === '1' ? 5 : 11)
    : MONTHS.indexOf(String(value).trim().toLowerCase().slice(0, 3));
  return month >= 0 && cutoff >= 0 && month <= cutoff;
}
