import type { CrimeRow, PeriodType } from '../types/stats';
import { withinBulletinCutoff } from './bulletinPeriod';

export interface PisccGoalDefinition {
  id: string;
  indicador: string;
  unidad: 'Número' | 'Tasa';
  lineaBase2023: number;
  meta2027: number;
  conductaNormalizada?: string;
  fuenteRequerida: 'SIEDCO' | 'COMISARIAS' | 'RNMC' | 'GAULA_FISCALIA';
  fuenteDescripcion: string;
}

export const PISCC_INDICADORES_TABLA_16: PisccGoalDefinition[] = [
  {
    id: 'homicidios',
    indicador: 'Número de homicidios',
    unidad: 'Número',
    lineaBase2023: 115,
    meta2027: 105,
    conductaNormalizada: 'Homicidio',
    fuenteRequerida: 'SIEDCO',
    fuenteDescripcion: 'Policía Nacional (SIEDCO) - Víctimas',
  },
  {
    id: 'secuestro',
    indicador: 'Secuestro',
    unidad: 'Número',
    lineaBase2023: 4,
    meta2027: 3,
    fuenteRequerida: 'GAULA_FISCALIA',
    fuenteDescripcion: 'Policía Nacional / Fiscalía General de la Nación',
  },
  {
    id: 'extorsion',
    indicador: 'Extorsión',
    unidad: 'Número',
    lineaBase2023: 58,
    meta2027: 55,
    fuenteRequerida: 'GAULA_FISCALIA',
    fuenteDescripcion: 'GAULA Policía / CTI Fiscalía',
  },
  {
    id: 'vif',
    indicador: 'Violencia intrafamiliar',
    unidad: 'Número',
    lineaBase2023: 187,
    meta2027: 180,
    fuenteRequerida: 'COMISARIAS',
    fuenteDescripcion: 'Comisarías de Familia / Fiscalía',
  },
  {
    id: 'motos',
    indicador: 'Hurto a motocicletas',
    unidad: 'Número',
    lineaBase2023: 200,
    meta2027: 180,
    conductaNormalizada: 'Hurto de motocicletas',
    fuenteRequerida: 'SIEDCO',
    fuenteDescripcion: 'Policía Nacional (SIEDCO) - Hechos',
  },
  {
    id: 'lesiones',
    indicador: 'Lesiones personales',
    unidad: 'Número',
    lineaBase2023: 453,
    meta2027: 430,
    conductaNormalizada: 'Lesiones personales',
    fuenteRequerida: 'SIEDCO',
    fuenteDescripcion: 'Policía Nacional (SIEDCO) - Víctimas',
  },
  {
    id: 'convivencia',
    indicador: 'Comportamientos Contrarios a la Convivencia',
    unidad: 'Número',
    lineaBase2023: 4798,
    meta2027: 4000,
    fuenteRequerida: 'RNMC',
    fuenteDescripcion: 'RNMC / Inspecciones de Policía (Medidas correctivas)',
  },
];

export type PisccStatusType = 'favorable' | 'alerta' | 'critico' | 'requiere_fuente';

export interface PisccIndicatorTracking {
  id: string;
  indicador: string;
  unidad: string;
  lineaBase2023: number;
  meta2027: number;
  countPrev: number | null;
  countBase: number | null;
  diferenciaAbs: number | null;
  variacionPct: number | null;
  variacionStr: string;
  proyeccionAnual: number | null;
  status: PisccStatusType;
  observacionTecnica: string;
  fuenteDescripcion: string;
  disponibleEnSabana: boolean;
  /** Fuente que aportó los datos reales (distinta de sábana policial) */
  fuenteExterna?: string;
  /** Fecha de corte de la fuente externa */
  fechaCorteExterno?: string;
}

/**
 * Datos de fuentes externas (MinDefensa, SIEDCO, etc.) para enriquecer
 * los indicadores que no están en la sábana policial ordinaria.
 */
export interface ExternalPisccSource {
  id: string;
  indicador: string;
  countPrev: number;
  countBase: number;
  diferenciaAbs: number;
  variacionPct: number | null;
  variacionStr: string;
  proyeccionAnual: number;
  status: 'favorable' | 'alerta' | 'critico';
  observacionTecnica: string;
  fuenteNombre: string;
  fechaCorte: string;
}

export interface PisccTrackingResult {
  baseYear: number;
  prevYear: number;
  cutoffDescription: string;
  semanasTranscurridas: number;
  indicadores: PisccIndicatorTracking[];
  resumenEjecutivo: string;
  totalDirectosDisponibles: number;
}

const normalizeString = (str?: string): string => {
  if (!str) return '';
  return str
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toUpperCase();
};

const matchesConducta = (rowConducta: string, targetConducta?: string): boolean => {
  if (!targetConducta) return false;
  const c1 = normalizeString(rowConducta);
  const c2 = normalizeString(targetConducta);
  
  if (c1 === c2) return true;
  if (c2.includes('HOMICIDIO') && c1.includes('HOMICIDIO')) return true;
  if (c2.includes('MOTO') && (c1.includes('MOTO') || c1.includes('MOTOCICLETA'))) return true;
  if (c2.includes('LESION') && c1.includes('LESION')) return true;
  return false;
};

export function computePisccTracking(
  crimeRows: CrimeRow[],
  baseYear: number,
  prevYear: number,
  periodType: PeriodType,
  periodValue: string | number,
  /** Datos de fuentes externas: MinDefensa, Fiscalía, SIEDCO, SISC-Inspecciones */
  externalSources?: Record<string, ExternalPisccSource>
): PisccTrackingResult {
  let semanasTranscurridas = 36; // Fallback por defecto si no es calculable
  let cutoffDescription = '';

  if (periodType === 'semanal') {
    semanasTranscurridas = Math.max(1, Math.min(52, Number(periodValue) || 1));
    cutoffDescription = `Semana ${semanasTranscurridas}`;
  } else if (periodType === 'mensual') {
    const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const idx = months.indexOf(String(periodValue).toLowerCase().substring(0, 3));
    const monthNum = idx >= 0 ? idx + 1 : 1;
    semanasTranscurridas = Math.max(1, Math.round((monthNum / 12) * 52));
    cutoffDescription = `Mes de ${periodValue}`;
  } else if (periodType === 'semestral') {
    const sem = String(periodValue) === '2' ? 2 : 1;
    semanasTranscurridas = sem === 1 ? 26 : 52;
    cutoffDescription = `Semestre ${sem}`;
  } else {
    semanasTranscurridas = 52;
    cutoffDescription = `Año completo`;
  }

  // Si es semanal filtramos por NoSEMANA <= semanasTranscurridas
  // Si es mensual filtramos por mes o acumulado
  const indicadores: PisccIndicatorTracking[] = PISCC_INDICADORES_TABLA_16.map(def => {
    if (!def.conductaNormalizada) {
      // Intentar enriquecer con fuente externa si está disponible
      const ext = externalSources?.[def.id];
      if (ext) {
        return {
          id: def.id,
          indicador: def.indicador,
          unidad: def.unidad,
          lineaBase2023: def.lineaBase2023,
          meta2027: def.meta2027,
          countPrev: ext.countPrev,
          countBase: ext.countBase,
          diferenciaAbs: ext.diferenciaAbs,
          variacionPct: ext.variacionPct,
          variacionStr: ext.variacionStr,
          proyeccionAnual: ext.proyeccionAnual,
          status: ext.status,
          observacionTecnica: ext.observacionTecnica,
          fuenteDescripcion: ext.fuenteNombre,
          disponibleEnSabana: false,
          fuenteExterna: ext.fuenteNombre,
          fechaCorteExterno: ext.fechaCorte,
        };
      }
      return {
        id: def.id,
        indicador: def.indicador,
        unidad: def.unidad,
        lineaBase2023: def.lineaBase2023,
        meta2027: def.meta2027,
        countPrev: null,
        countBase: null,
        diferenciaAbs: null,
        variacionPct: null,
        variacionStr: '—',
        proyeccionAnual: null,
        status: 'requiere_fuente',
        observacionTecnica: `Requiere fuente específica (${def.fuenteDescripcion}). No disponible en sábana policial ordinaria.`,
        fuenteDescripcion: def.fuenteDescripcion,
        disponibleEnSabana: false,
      };
    }

    // Filtrar filas para el año base y previo acumulado al corte
    let baseRows = 0;
    let prevRows = 0;

    crimeRows.forEach(row => {
      if (!matchesConducta(row.CONDUCTA, def.conductaNormalizada)) return;

      const isCutoffMet = withinBulletinCutoff(row, periodType, periodValue);

      if (isCutoffMet) {
        if (row.AÑO === baseYear) baseRows++;
        if (row.AÑO === prevYear) prevRows++;
      }
    });

    const diffAbs = baseRows - prevRows;
    let varPct: number | null = null;
    let varStr = '0,0 %';

    if (prevRows > 0) {
      varPct = ((baseRows - prevRows) / prevRows) * 100;
      const sign = varPct > 0 ? '+' : '';
      varStr = `${sign}${varPct.toFixed(1).replace('.', ',')} %`;
    } else if (baseRows > 0) {
      varStr = 'Sin base comparable';
    }

    // Proyección lineal simple al cierre de año (52 semanas)
    const proyeccion = Math.round((baseRows / semanasTranscurridas) * 52);

    let status: PisccStatusType = 'favorable';
    let observacionTecnica = '';

    if (def.id === 'homicidios') {
      if (proyeccion > def.meta2027) {
        status = 'alerta';
        observacionTecnica = diffAbs <= 0
          ? `Mejora interanual (${varStr}). Atención: proyección lineal anual es ≈${proyeccion} (meta: ${def.meta2027}).`
          : `Alerta: incremento de ${diffAbs} casos frente a ${prevYear}. Proyección lineal anual es ≈${proyeccion} (meta: ${def.meta2027}).`;
      } else {
        status = 'favorable';
        observacionTecnica = `Evolución favorable: proyección anual ≈${proyeccion}, en trayectoria a cumplir meta (${def.meta2027}).`;
      }
    } else if (def.id === 'motos') {
      if (diffAbs > 0 || proyeccion > def.meta2027) {
        status = 'critico';
        observacionTecnica = `Indicador prioritario de atención: ${diffAbs > 0 ? `+${diffAbs}` : diffAbs} casos frente a ${prevYear}. Proyección lineal ≈${proyeccion} (meta: ${def.meta2027}).`;
      } else {
        status = 'favorable';
        observacionTecnica = `Comportamiento controlado: reducción de ${Math.abs(diffAbs)} casos. Proyección anual ≈${proyeccion} (meta: ${def.meta2027}).`;
      }
    } else if (def.id === 'lesiones') {
      if (proyeccion <= def.meta2027) {
        status = 'favorable';
        observacionTecnica = `Evolución favorable: reducción de ${Math.abs(diffAbs)} casos (${varStr}). Proyección anual ≈${proyeccion}, inferior a la meta (${def.meta2027}).`;
      } else {
        status = 'alerta';
        observacionTecnica = `Seguimiento requerido: proyección anual ≈${proyeccion} supera meta de ${def.meta2027}.`;
      }
    }

    return {
      id: def.id,
      indicador: def.indicador,
      unidad: def.unidad,
      lineaBase2023: def.lineaBase2023,
      meta2027: def.meta2027,
      countPrev: prevRows,
      countBase: baseRows,
      diferenciaAbs: diffAbs,
      variacionPct: varPct,
      variacionStr: varStr,
      proyeccionAnual: proyeccion,
      status,
      observacionTecnica,
      fuenteDescripcion: def.fuenteDescripcion,
      disponibleEnSabana: true,
    };
  });

  const directos = indicadores.filter(i => i.disponibleEnSabana);
  const homicidios = directos.find(i => i.id === 'homicidios');
  const lesiones = directos.find(i => i.id === 'lesiones');
  const motos = directos.find(i => i.id === 'motos');

  const resumenEjecutivo = `Acumulado al corte de ${cutoffDescription} de ${baseYear}. ` +
    [homicidios, lesiones, motos].filter(Boolean).map(ind =>
      `${ind!.indicador}: ${ind!.countBase} registros frente a ${ind!.countPrev} en ${prevYear} (${ind!.variacionStr}); proyección anual ≈${ind!.proyeccionAnual}, meta ${ind!.meta2027}.`
    ).join(' ') + ' Las fuentes externas conservan el corte indicado en cada fila; no se suman como si tuvieran la misma cobertura.';

  return {
    baseYear,
    prevYear,
    cutoffDescription,
    semanasTranscurridas,
    indicadores,
    resumenEjecutivo,
    totalDirectosDisponibles: directos.length,
  };
}
