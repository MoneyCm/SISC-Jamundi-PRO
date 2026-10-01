/**
 * Página PISCC del boletín (tabla 16). No calcula nada: presenta las metas que el servidor
 * mide con la regla oficial (MinDefensa hasta el último mes publicado, la misma fuente y unidad
 * de la meta; RNMC para convivencia), la misma que usa el Centro de análisis.
 */

export type PisccStatusType = 'favorable' | 'alerta' | 'critico' | 'preliminar' | 'requiere_fuente';

/** Fila de la tabla 16 tal como la entrega `/sisc-cifras/piscc-sources` en `goals`. */
export interface BackendPisccGoal {
  id: string;
  label: string;
  baseline_2023: number;
  goal_2027: number;
  status: 'EN_META' | 'DESVIACION' | 'SUPERADA' | 'PRELIMINAR' | 'SIN_DATOS';
  status_label: string;
  detail: string;
  count?: number;
  previous?: number | null;
  projection?: number | null;
  compares?: 'acumulado' | 'proyeccion';
  cutoff?: string;
  days_elapsed?: number;
  source?: string;
  stale?: boolean;
  previous_status?: BackendPisccGoal['status'];
  /** Cifra más reciente de la sábana (hechos), cuando MinDefensa va hasta un mes anterior. */
  reciente?: { count: number; cutoff: string; source?: string; since?: number; since_start?: string } | null;
  closed_years?: { anio: number; total: number | null; completo: boolean; semaforo: 'VERDE' | 'AMARILLO' | 'ROJO' | null; semaforo_label?: string }[];
}

export interface BackendPisccGoals {
  as_of: string;
  indicators: BackendPisccGoal[];
  off_track: string[];
  note: string;
}

export interface PisccIndicatorTracking {
  id: string;
  indicador: string;
  unidad: string;
  lineaBase2023: number;
  meta2027: number;
  countPrev: number | null;
  /** Cómo iba el mismo tramo del año anterior frente a la meta (mismo criterio que el año en curso). */
  statusPrev: PisccStatusType | null;
  /** Años cerrados (enero a diciembre) con su semáforo frente a la línea base y la meta. */
  aniosCerrados: { anio: number; total: number | null; completo: boolean; semaforo: string | null; etiqueta: string }[];
  countBase: number | null;
  /** Dato más reciente de la sábana policial (hechos): se muestra aparte, no se compara con la meta. */
  reciente: { since: number; desde: string; hasta: string } | null;
  diferenciaAbs: number | null;
  variacionPct: number | null;
  variacionStr: string;
  proyeccionAnual: number | null;
  status: PisccStatusType;
  observacionTecnica: string;
  fuenteDescripcion: string;
  fechaCorte?: string;
  corteAtrasado: boolean;
}

export interface PisccTrackingResult {
  baseYear: number;
  prevYear: number;
  cutoffDescription: string;
  semanasTranscurridas: number;
  indicadores: PisccIndicatorTracking[];
  resumenEjecutivo: string;
  fueraDeTrayectoria: string[];
  nota: string;
}

const STATUS: Record<BackendPisccGoal['status'], PisccStatusType> = {
  EN_META: 'favorable',
  DESVIACION: 'alerta',
  SUPERADA: 'critico',
  PRELIMINAR: 'preliminar',
  SIN_DATOS: 'requiere_fuente',
};

const SMALL_BASE = 30; // igual que el resto del boletín: con menos, la variación va en casos

export function variationText(count: number, previous: number | null | undefined): { pct: number | null; text: string } {
  if (previous === null || previous === undefined) return { pct: null, text: 'Sin año anterior' };
  const diff = count - previous;
  if (previous < SMALL_BASE) return { pct: null, text: diff ? `${diff > 0 ? '+' : ''}${diff} casos` : 'Igual' };
  const pct = (diff / previous) * 100;
  return { pct, text: `${pct > 0 ? '+' : ''}${pct.toFixed(1).replace('.', ',')} %` };
}

export function toPisccTracking(
  goals: BackendPisccGoals,
  baseYear: number,
  prevYear: number,
  cutoffDescription: string,
): PisccTrackingResult {
  const indicadores = goals.indicators.map((goal): PisccIndicatorTracking => {
    const measured = goal.count !== undefined;
    const variation = measured ? variationText(goal.count!, goal.previous) : { pct: null, text: '—' };
    return {
      id: goal.id,
      indicador: goal.label,
      unidad: 'Número',
      lineaBase2023: goal.baseline_2023,
      meta2027: goal.goal_2027,
      countPrev: measured ? goal.previous ?? null : null,
      statusPrev: measured && goal.previous_status ? STATUS[goal.previous_status] : null,
      aniosCerrados: (goal.closed_years || []).map(year => ({
        anio: year.anio, total: year.total, completo: year.completo, semaforo: year.semaforo,
        etiqueta: year.semaforo_label || (year.completo ? '' : 'Año incompleto'),
      })),
      countBase: measured ? goal.count! : null,
      reciente: measured && goal.reciente && goal.reciente.since !== undefined && goal.reciente.since_start
        ? { since: goal.reciente.since, desde: goal.reciente.since_start, hasta: goal.reciente.cutoff } : null,
      diferenciaAbs: measured && goal.previous !== null && goal.previous !== undefined ? goal.count! - goal.previous : null,
      variacionPct: variation.pct,
      variacionStr: variation.text,
      proyeccionAnual: goal.projection ?? null,
      status: STATUS[goal.status],
      observacionTecnica: goal.detail,
      fuenteDescripcion: goal.source || 'Sin fuente disponible',
      fechaCorte: goal.cutoff,
      corteAtrasado: Boolean(goal.stale),
    };
  });
  const police = goals.indicators.find(goal => goal.id === 'homicidios' && goal.days_elapsed);
  const offTrack = indicadores.filter(item => goals.off_track.includes(item.id));
  const resumenEjecutivo = offTrack.length
    ? `Al corte, ${offTrack.length === 1 ? 'un indicador se aparta' : `${offTrack.length} indicadores se apartan`} de la meta 2027: ` +
      offTrack.map(item => `${item.indicador}: ${item.observacionTecnica.charAt(0).toLowerCase()}${item.observacionTecnica.slice(1).replace(/\.$/, '')}`).join('; ') + '.'
    : 'Al corte, ningún indicador medido se aparta de la meta 2027.';
  return {
    baseYear,
    prevYear,
    cutoffDescription,
    semanasTranscurridas: police ? Math.max(1, Math.round(police.days_elapsed! / 7)) : 0,
    indicadores,
    resumenEjecutivo: `${resumenEjecutivo} Cada fuente conserva su propio corte; no se suman como si tuvieran la misma cobertura.`,
    fueraDeTrayectoria: offTrack.map(item => item.indicador),
    nota: goals.note,
  };
}
