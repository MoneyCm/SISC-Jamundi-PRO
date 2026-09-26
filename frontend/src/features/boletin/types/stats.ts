/**
 * Tipos compartidos para el Generador de Boletines de Seguridad.
 * Centraliza las estructuras de datos que se intercambian entre
 * el parseo del Excel, el cálculo de estadísticas (Dashboard) y
 * la vista previa del boletín (NewsletterPreview).
 */

/** Tipo de periodo temporal seleccionable en el filtro. */
export type PeriodType = 'semanal' | 'mensual' | 'semestral' | 'anual';

/** Métricas operativas extraídas del PDF de resultados. */
export interface OperationsData {
  capturas: number;
  armasIncautadas: number;
  estupefacientes: number;
  motosRecuperadas: number;
}

/** Fila normalizada tras leer el Excel SIEDCO/PONAL. */
export interface CrimeRow {
  AÑO: number;
  MES: string;
  NoSEMANA: number;
  CONDUCTA: string;
  CONDUCTA_ORIGINAL?: string;
  BARRIO: string;
  ARMA: string;
  DIA: string;
  HECHOS_ID?: string;
  FECHA_HECHO?: string;
  GENERO?: string;
  EDAD?: string;
  GESTION_ESTATAL?: string;
  SOURCE_ROW_KEY?: string;
}

/** Elemento de los "top N" (delitos, barrios, armas más frecuentes). */
export interface TopItem {
  name: string;
  count: number;
}

/** Punto de la serie temporal para los gráficos (actual vs año previo). */
export interface ChartPoint {
  name: string;
  current: number;
  prev: number;
}

/** Fila de la tabla comparativa del periodo puntual. */
export interface PeriodTableRow {
  name: string;
  current: number;
  prev: number;
  varPct: string;
  prevImmediate?: number;
  diffYoY: number;
  diffWoW: number;
}

/** Fila de la tabla comparativa acumulada (YTD). */
export interface YtdTableRow {
  name: string;
  current: number;
  prev: number;
  varPct: string;
  diffAbs: number;
}

export type SiscCoverageStatus = 'aligned' | 'partial' | 'stale' | 'missing' | 'context' | 'not_applicable';

export interface SiscSourceStatus {
  code: string;
  name: string;
  domain: string;
  periodicity: string;
  last_cutoff_date?: string | null;
  reported_cutoff_date?: string | null;
  quality_status: string;
  coverage_status: SiscCoverageStatus;
  period_records: number;
  comparison_records: number;
  future_records?: number;
  excluded_test_records?: number;
  exclusion_note?: string | null;
  included: boolean;
  comparable: boolean;
  publishable: boolean;
  status_note?: string | null;
  reporting_basis?: string[];
  reporting_entities?: string[];
}

export type SiscCoverageType = 'EXACT' | 'CONTEXT';

export interface SiscIndicator {
  id: string;
  source: string;
  source_code: string;
  domain: string;
  category: string;
  indicator_code: string;
  indicator_name: string;
  value: number | null;
  unit: string;
  period_start: string;
  period_end: string;
  comparison_value: number | null;
  variation_absolute: number | null;
  variation_percentage: number | null;
  quality_status: string;
  cutoff_date: string | null;
  metadata: Record<string, unknown>;
  coverage_type?: SiscCoverageType;
  source_period?: string | null;
  context_label?: string | null;
  reporting_entity?: string | null;
  reporting_basis?: string | null;
}

export interface SiscPublication {
  id: string;
  title: string;
  edition_type: string;
  period: { start: string; end: string };
  comparison_period: { start: string; end: string };
  comparison_label: string;
  comparison_mode: string;
  generated_at: string;
  sources: SiscSourceStatus[];
  indicators: SiscIndicator[];
  governance: {
    public_only: boolean;
    human_review_required: boolean;
    publication_ready?: boolean;
    review_blockers?: string[];
    privacy_note: string;
    aggregation_note?: string;
  };
}

/** Resultado completo del cálculo de estadísticas del Dashboard. */
export interface StatsResult {
  currentPeriodCount: number;
  prevPeriodCount: number;
  currentYTDCount: number;
  prevYTDCount: number;
  prevImmediatePeriodCount: number;
  last4WeeksAvg: number;
  baseYear: number;
  prevYear: number;
  periodName: string;
  topConductas: TopItem[];
  topBarrios: TopItem[];
  topArmas: TopItem[];
  generatedAnalysis: string;
  selectedConducta: string;
  chartData: ChartPoint[];
  periodTableData: PeriodTableRow[];
  ytdTableData: YtdTableRow[];
  periodType: PeriodType;
  
  // Nuevos campos para trazabilidad, fechas y conciliación
  fechaCorteInicio?: string;
  fechaCorteFin?: string;
  fechaExtraccion?: string;
  nombreArchivo?: string;
  hashArchivo?: string;
  totalesPorConductaSemana?: Record<string, number>;
  totalesPorConductaYTD?: Record<string, number>;
  conciliacion?: BulletinConciliation;
  versionBoletin?: string;
  pisccTracking?: import('../lib/pisccGoals').PisccTrackingResult;
}

export type BulletinState = 'vigente' | 'sustituida' | 'anulada' | 'antecedente';

export interface BulletinConciliation {
  boletinComparadoId: string | null;
  semanaComparada: number | null;
  totalSemanaPublicado: number;
  totalSemanaRecalculado: number;
  diferenciaSemana: number;
  totalYTDPublicado: number;
  totalYTDRecalculado: number;
  diferenciaYTD: number;
  ajusteSemanasPrevias: number;
  cambiosPorConducta: Array<{
    conducta: string;
    publicado: number;
    recalculado: number;
    diferencia: number;
  }>;
  tipoAjuste: 'sin_cambios' | 'incremento_neto' | 'reduccion_neta' | 'reclasificacion_neta' | 'indeterminado';
  precision: 'registro_individual' | 'semanal' | 'agregada' | 'indeterminada';
  notaGenerada: string;
}

export interface BulletinRecord {
  id: string;
  anio: number;
  semana: number;
  periodType?: PeriodType;
  version: string;
  estado: BulletinState;
  fechaCorteInicio: string;
  fechaCorteFin: string;
  fechaExtraccion: string;
  fechaPublicacion: string;
  totalSemana: number;
  totalYTD: number;
  fuente: string;
  nombreArchivo: string;
  hashArchivo: string;
  origenRegistro: 'generado' | 'importado_excel' | 'manual';
  versionAnteriorId: string | null;
  motivoRevision: string;
  creadoEn: string;
  totalesPorConductaSemana: Record<string, number>;
  totalesPorConductaYTD: Record<string, number>;
  conciliacion?: BulletinConciliation;
  siscPublication?: SiscPublication;
}
