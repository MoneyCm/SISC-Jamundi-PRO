import { bulletinFetch as fetch } from '../lib/bulletinApi';
"use client";

import React, { useEffect, useState, useMemo } from 'react';
import * as XLSX from 'xlsx';
import { AlertTriangle, CalendarClock, CheckCircle2, Clock3, Database, ExternalLink, Megaphone, Printer, RefreshCw, XCircle } from 'lucide-react';
import NewsletterPreview from './NewsletterPreview';
import type {
  ChartPoint,
  CrimeRow,
  OperationsData,
  PeriodTableRow,
  PeriodType,
  StatsResult,
  TopItem,
  YtdTableRow,
  BulletinRecord,
  BulletinConciliation,
  SiscPublication,
  SiscSourceStatus
} from '../types/stats';
import { deduplicateCrimeRows, sourceRowRecordKey } from '../lib/sabanaHistory';
import { computePisccTracking, type ExternalPisccSource } from '../lib/pisccGoals';
import { withinBulletinCutoff } from '../lib/bulletinPeriod';
import OfficialQueryPanel from './OfficialQueryPanel';
import CentralHistoryPanel from './CentralHistoryPanel';
import SabanaUploadFlow from './SabanaUploadFlow';
import type { OfficialResult } from '../hooks/useOfficialIndicator';

export const NOMBRES_CONDUCTAS_DICT: Record<string, string> = {
  "H.PERSONAS": "Hurto a personas",
  "H PERSONAS": "Hurto a personas",
  "HURTO PERSONAS": "Hurto a personas",
  "HURTO A PERSONAS": "Hurto a personas",
  "H.MOTOS": "Hurto de motocicletas",
  "H.MOTOCICLETAS": "Hurto de motocicletas",
  "HURTO MOTOS": "Hurto de motocicletas",
  "HURTO DE MOTOCICLETAS": "Hurto de motocicletas",
  "H.RESIDENCIAS": "Hurto a residencias",
  "H.RESIDENCIA": "Hurto a residencias",
  "HURTO RESIDENCIAS": "Hurto a residencias",
  "HURTO A RESIDENCIAS": "Hurto a residencias",
  "H.COMERCIO": "Hurto a comercio",
  "HURTO COMERCIO": "Hurto a comercio",
  "HURTO A ESTABLECIMIENTO": "Hurto a comercio",
  "H.AUTOMOTORES": "Hurto de automotores",
  "HURTO AUTOMOTORES": "Hurto de automotores",
  "LESIONES": "Lesiones personales",
  "LESIONES PERSONALES": "Lesiones personales",
  "HOMICIDIO": "Homicidio"
};

export const normalizarConducta = (raw: string): string => {
  if (!raw) return 'Sin Dato';
  const normalizedKey = raw.trim().toUpperCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  
  // Buscar coincidencia exacta
  for (const [key, label] of Object.entries(NOMBRES_CONDUCTAS_DICT)) {
    const cleanKey = key.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    if (normalizedKey === cleanKey) {
      return label;
    }
  }
  
  // Buscar coincidencia parcial
  for (const [key, label] of Object.entries(NOMBRES_CONDUCTAS_DICT)) {
    const cleanKey = key.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    if (normalizedKey.includes(cleanKey) || cleanKey.includes(normalizedKey)) {
      return label;
    }
  }

  // Fallback capitalizando
  return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
};

export const generateQuickHash = (str: string): string => {
  let hash = 0;
  for (let i = 0; i < Math.min(str.length, 100000); i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(16);
};

export const getDatesForWeek = (year: number, weekNum: number) => {
  const jan1 = new Date(year, 0, 1);
  const jan1Day = jan1.getDay();
  const firstSunday = new Date(jan1);
  firstSunday.setDate(jan1.getDate() - jan1Day);

  const startDate = new Date(firstSunday);
  startDate.setDate(firstSunday.getDate() + (weekNum - 1) * 7);
  
  const endDate = new Date(startDate);
  endDate.setDate(startDate.getDate() + 6);
  
  return { start: startDate, end: endDate };
};

const MONTH_LABELS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const DEFAULT_PERIOD_DATE = new Date();
DEFAULT_PERIOD_DATE.setDate(1);
DEFAULT_PERIOD_DATE.setMonth(DEFAULT_PERIOD_DATE.getMonth() - 1);
const DEFAULT_PERIOD_YEAR = DEFAULT_PERIOD_DATE.getFullYear();
const DEFAULT_PERIOD_MONTH = MONTH_LABELS[DEFAULT_PERIOD_DATE.getMonth()];

const toIsoDate = (value: Date): string => {
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

export const getPeriodDateRange = (
  year: number,
  periodType: PeriodType,
  periodValue: string,
): { start: string; end: string } => {
  if (periodType === 'semanal') {
    const range = getDatesForWeek(year, Number(periodValue));
    return { start: toIsoDate(range.start), end: toIsoDate(range.end) };
  }

  if (periodType === 'mensual') {
    const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const monthIndex = Math.max(0, months.indexOf(periodValue.toLowerCase().slice(0, 3)));
    return {
      start: toIsoDate(new Date(year, monthIndex, 1)),
      end: toIsoDate(new Date(year, monthIndex + 1, 0)),
    };
  }

  if (periodType === 'semestral') {
    const firstSemester = periodValue === '1';
    return {
      start: toIsoDate(new Date(year, firstSemester ? 0 : 6, 1)),
      end: toIsoDate(new Date(year, firstSemester ? 6 : 12, 0)),
    };
  }

  return {
    start: toIsoDate(new Date(year, 0, 1)),
    end: toIsoDate(new Date(year, 12, 0)),
  };
};

const SOURCE_STATUS_LABELS: Record<SiscSourceStatus['coverage_status'], string> = {
  aligned: 'Mismo periodo',
  partial: 'Corte parcial',
  stale: 'Desactualizada',
  missing: 'Sin datos',
  not_applicable: 'Solo mensual',
};

const SOURCE_STATUS_STYLES: Record<SiscSourceStatus['coverage_status'], string> = {
  aligned: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
  partial: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
  stale: 'border-orange-400/30 bg-orange-400/10 text-orange-200',
  missing: 'border-red-400/30 bg-red-400/10 text-red-200',
  not_applicable: 'border-slate-400/20 bg-slate-400/10 text-slate-300',
};

const normalizeComparableLabel = (value: string): string => value
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .trim()
  .toUpperCase();

const fetchSiscPublication = async (
  periodType: PeriodType,
  periodStart: string,
  periodEnd: string,
  signal?: AbortSignal,
  publish = false,
  sourceVersionId?: string,
): Promise<SiscPublication> => {
  const editionMap: Record<PeriodType, string> = {
    semanal: 'weekly',
    mensual: 'monthly',
    semestral: 'semester',
    anual: 'annual',
  };
  const response = await fetch('/api/sisc-publication', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      edition_type: editionMap[periodType],
      period_start: periodStart,
      period_end: periodEnd,
      comparison_mode: 'auto',
      publish,
      source_version_id: sourceVersionId,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'El SISC no pudo preparar las fuentes institucionales.');
  }
  return data as SiscPublication;
};

const createBulletinId = (): string => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 9)}`;
};

export const excelSerialToDateString = (serialVal: unknown): string => {
  if (!serialVal) return '';
  if (serialVal instanceof Date) {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${serialVal.getFullYear()}-${pad(serialVal.getMonth() + 1)}-${pad(serialVal.getDate())}`;
  }
  const serial = Number(serialVal);
  if (isNaN(serial) || serial <= 0) return String(serialVal);
  
  const offset = serial > 59 ? 25569 + 1 : 25569;
  const dateVal = new Date((serial - offset) * 86400 * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${dateVal.getFullYear()}-${pad(dateVal.getMonth() + 1)}-${pad(dateVal.getDate())}`;
};

export default function Dashboard({ onOpenArchive }: { onOpenArchive: () => void }) {
  const [loading, setLoading] = useState(false);

  // Data State
  const [rawExcelData, setRawExcelData] = useState<CrimeRow[]>([]);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [uploadedFileName, setUploadedFileName] = useState<string>('');
  const [uploadedFileHash, setUploadedFileHash] = useState<string>('');
  const [uploadSummary, setUploadSummary] = useState<{
    totalRows: number;
    uniqueRows: number;
    duplicateRows: number;
  } | null>(null);

  // Historial local: SOLO borrador/preferencia, nunca fuente oficial.
  // La fuente oficial es el historial central del servidor (CentralHistoryPanel).
  const [history, setHistory] = useState<BulletinRecord[]>([]);
  const [officialResult, setOfficialResult] = useState<OfficialResult | null>(null);
  const [loadedDelivery, setLoadedDelivery] = useState('');
  const [officialPending, setOfficialPending] = useState(false);
  const [officialError, setOfficialError] = useState<string | null>(null);
  const [officialSelection, setOfficialSelection] = useState<{ sourceVersionId: string; indicator: string }>({ sourceVersionId: '', indicator: 'SEGURIDAD_TOTAL' });

  React.useEffect(() => {
    const saved = window.localStorage.getItem('sisc_replica_boletines_historial');
    if (!saved) return;

    try {
      const parsed = JSON.parse(saved);
      const storedHistory = Array.isArray(parsed)
        ? parsed
        : parsed && Array.isArray(parsed.boletines)
          ? parsed.boletines
          : null;

      if (storedHistory) {
        window.setTimeout(() => setHistory(storedHistory), 0);
      }
    } catch (error) {
      console.error("Error cargando historial de boletines:", error);
    }
  }, []);

  const saveHistoryToStorage = (updatedHistory: BulletinRecord[]) => {
    setHistory(updatedHistory);
    localStorage.setItem('sisc_replica_boletines_historial', JSON.stringify(updatedHistory));
  };

  // Modales de historial
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showAntecedentModal, setShowAntecedentModal] = useState(false);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState<BulletinRecord | null>(null);

  // Formulario del modal de publicación
  const [revisionMotive, setRevisionMotive] = useState('');
  const [customVersion, setCustomVersion] = useState('1.0');
  const [publishDate, setPublishDate] = useState(new Date().toISOString().split('T')[0]);

  // Formulario de antecedente manual
  const [antYear, setAntYear] = useState<number>(new Date().getFullYear());
  const [antWeek, setAntWeek] = useState<number>(1);
  const [antVersion, setAntVersion] = useState('1.0');
  const [antTotalSemana, setAntTotalSemana] = useState<number>(0);
  const [antTotalYTD, setAntTotalYTD] = useState<number>(0);
  const [antFileName, setAntFileName] = useState('');
  const [antMotive, setAntMotive] = useState('Registro manual antecedente');
  const [antConductasSemanaText, setAntConductasSemanaText] = useState('{}'); 
  const [antConductasYTDText, setAntConductasYTDText] = useState('{}');

  const handleRegisterPublish = async () => {
    if (!stats) return;
    // La cifra publicada es la oficial del servidor, no el conteo Excel; exige correspondencia exacta.
    if (!publicationCanBeRegistered || !officialResult) {
      alert('Para publicar, consulte primero la cifra oficial (SEGURIDAD_TOTAL) con la entrega fijada para este período.');
      return;
    }
    setPublishing(true);
    let centralPublication: SiscPublication;
    try {
      centralPublication = await fetchSiscPublication(
        periodType,
        stats.fechaCorteInicio || getPeriodDateRange(selectedYear, periodType, selectedPeriodValue).start,
        stats.fechaCorteFin || getPeriodDateRange(selectedYear, periodType, selectedPeriodValue).end,
        undefined,
        true,
        officialResult.source_version_id || undefined,
      );
    } catch (error: unknown) {
      alert(error instanceof Error ? error.message : 'No fue posible publicar el boletín en el repositorio central.');
      setPublishing(false);
      return;
    }
    const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const targetWeek = periodType === 'semanal' ? Number(selectedPeriodValue) :
                       periodType === 'mensual' ? months.indexOf(String(selectedPeriodValue).toLowerCase().substring(0,3)) + 1 :
                       periodType === 'semestral' ? Number(selectedPeriodValue) : 1;
    const baseYear = Number(selectedYear);
    const id = createBulletinId();
    
    const existingIndex = history.findIndex(b => 
      b.anio === baseYear && 
      b.semana === targetWeek && 
      (b.periodType || 'semanal') === periodType && 
      b.estado === 'vigente'
    );
    const updatedHistory = [...history];
    let versionToSave = customVersion;
    let prevId: string | null = null;

    if (existingIndex > -1) {
      const existing = history[existingIndex];
      prevId = existing.id;
      updatedHistory[existingIndex] = {
        ...existing,
        estado: 'sustituida'
      };
      const currentVer = parseFloat(existing.version) || 1.0;
      versionToSave = (currentVer + 0.1).toFixed(1);
    }

    const record: BulletinRecord = {
      id,
      anio: baseYear,
      semana: targetWeek,
      periodType,
      version: versionToSave,
      estado: 'vigente',
      fechaCorteInicio: officialResult.period.start,
      fechaCorteFin: officialResult.period.end,
      fechaExtraccion: stats.fechaExtraccion || '',
      fechaPublicacion: publishDate,
      totalSemana: officialResult.value,
      totalYTD: officialResult.value,
      fuente: `OFICIAL backend ${officialResult.indicator} · ${officialResult.unit} · entrega ${officialResult.source_version_id} · met ${officialResult.methodology_version} · qh ${officialResult.query_hash.slice(0, 12)}`,
      nombreArchivo: stats.nombreArchivo || 'SABANAS MANUALES.xlsx',
      hashArchivo: stats.hashArchivo || 'hash_manual',
      origenRegistro: 'generado',
      versionAnteriorId: prevId,
      motivoRevision: revisionMotive || (prevId ? 'Actualización retroactiva' : 'Publicación inicial'),
      creadoEn: new Date().toISOString(),
      totalesPorConductaSemana: stats.totalesPorConductaSemana || {},
      totalesPorConductaYTD: stats.totalesPorConductaYTD || {},
      conciliacion: stats.conciliacion,
      siscPublication: centralPublication,
    };

    updatedHistory.push(record);
    saveHistoryToStorage(updatedHistory);
    alert(`Boletín público generado con éxito.\nVersión: ${versionToSave}\nPeriodo: ${stats.periodName}`);
    setShowPublishModal(false);
    setRevisionMotive('');
    setPublishing(false);
  };

  const handleRegisterAntecedent = () => {
    const id = createBulletinId();
    
    let condSemana: Record<string, number> = {};
    let condYTD: Record<string, number> = {};
    try {
      condSemana = JSON.parse(antConductasSemanaText);
    } catch {
      alert("Error parseando JSON de conductas de la semana. Se usará un objeto vacío.");
    }
    try {
      condYTD = JSON.parse(antConductasYTDText);
    } catch {
      alert("Error parseando JSON de conductas YTD. Se usará un objeto vacío.");
    }

    const { start, end } = getDatesForWeek(antYear, antWeek);
    const pad = (n: number) => String(n).padStart(2, '0');
    const startStr = `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`;
    const endStr = `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}`;

    const record: BulletinRecord = {
      id,
      anio: antYear,
      semana: antWeek,
      version: antVersion || '1.0',
      estado: 'antecedente',
      fechaCorteInicio: startStr,
      fechaCorteFin: endStr,
      fechaExtraccion: new Date().toLocaleDateString('es-CO'),
      fechaPublicacion: new Date().toISOString().split('T')[0],
      totalSemana: antTotalSemana,
      totalYTD: antTotalYTD,
      fuente: 'SIEDCO - Policía Nacional',
      nombreArchivo: antFileName || 'REGISTRO_MANUAL.xlsx',
      hashArchivo: 'hash_manual_antecedente',
      origenRegistro: 'manual',
      versionAnteriorId: null,
      motivoRevision: antMotive || 'Registro manual antecedente',
      creadoEn: new Date().toISOString(),
      totalesPorConductaSemana: condSemana,
      totalesPorConductaYTD: condYTD
    };

    const duplicate = history.some(b => b.anio === antYear && b.semana === antWeek && b.version === antVersion);
    if (duplicate) {
      alert(`Advertencia: Ya existe un registro para el Año ${antYear}, Semana ${antWeek}, Versión ${antVersion}. Cancele o use una versión distinta.`);
      return;
    }

    const updatedHistory = [...history, record];
    saveHistoryToStorage(updatedHistory);
    alert(`Antecedente registrado con éxito.\nSemana: ${antWeek}`);
    setShowAntecedentModal(false);
  };

  const handleExportHistory = () => {
    const dataStr = JSON.stringify({
      schemaVersion: "2.0",
      appVersion: "2.0.0",
      origin: "SISC_BULLETIN_STUDIO",
      sourceSystem: "SISC",
      exportadoEn: new Date().toISOString(),
      cantidadRegistros: history.length,
      boletines: history
    }, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', 'historial_boletines.json');
    linkElement.click();
  };

  const handleImportHistory = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileReader = new FileReader();
    const file = e.target.files?.[0];
    if (!file) return;

    fileReader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        let importedBoletines: BulletinRecord[] = [];
        if (Array.isArray(parsed)) {
          importedBoletines = parsed;
        } else if (parsed && Array.isArray(parsed.boletines)) {
          importedBoletines = parsed.boletines;
        }

        if (importedBoletines.length === 0) {
          alert("El archivo no contiene boletines válidos.");
          return;
        }

        if (confirm(`¿Deseas importar ${importedBoletines.length} registros históricos? Esto combinará o reemplazará el historial actual.`)) {
          const overwrite = confirm("¿Deseas sobrescribir el historial actual por completo? Cancelar mantendrá los registros actuales y solo agregará los nuevos.");
          if (overwrite) {
            saveHistoryToStorage(importedBoletines);
          } else {
            const existingIds = new Set(history.map(b => b.id));
            const newItems = importedBoletines.filter(b => b.id && !existingIds.has(b.id));
            saveHistoryToStorage([...history, ...newItems]);
          }
          alert("¡Historial importado con éxito!");
        }
      } catch (err) {
        alert("Error al importar el archivo JSON.");
        console.error(err);
      }
    };
    fileReader.readAsText(file);
  };

  const handleAnnulRecord = (id: string) => {
    if (confirm("¿Estás seguro de que deseas anular esta publicación? Su estado cambiará a 'anulada' pero se conservará en la serie para trazabilidad.")) {
      const updated = history.map(b => {
        if (b.id === id) {
          return { ...b, estado: 'anulada' as const };
        }
        return b;
      });
      saveHistoryToStorage(updated);
    }
  };

  const handleDeleteRecord = (id: string) => {
    const record = history.find(b => b.id === id);
    if (!record) return;
    if (record.estado !== 'anulada' && record.estado !== 'antecedente') {
      alert("Solo se pueden eliminar definitivamente registros anulados o antecedentes.");
      return;
    }
    if (confirm("¿Estás seguro de eliminar permanentemente este registro del historial?")) {
      const updated = history.filter(b => b.id !== id);
      saveHistoryToStorage(updated);
      if (selectedHistoryItem?.id === id) setSelectedHistoryItem(null);
    }
  };

  // Filter State
  const [selectedYear, setSelectedYear] = useState<number>(DEFAULT_PERIOD_YEAR);
  const [periodType, setPeriodType] = useState<PeriodType>('mensual');
  const [selectedPeriodValue, setSelectedPeriodValue] = useState<string>(DEFAULT_PERIOD_MONTH);

  const [availableConductas, setAvailableConductas] = useState<string[]>([]);
  const [selectedConducta, setSelectedConducta] = useState<string>('Todos');
  const [includePisccPage, setIncludePisccPage] = useState<boolean>(true);

  // External Operations (PDF)
  const [operations, setOperations] = useState<OperationsData>({
    capturas: 0,
    armasIncautadas: 0,
    estupefacientes: 0,
    motosRecuperadas: 0
  });
  const [siscPublication, setSiscPublication] = useState<SiscPublication | null>(null);
  const [siscLoading, setSiscLoading] = useState(false);
  const [siscError, setSiscError] = useState<string | null>(null);
  const [externalPisccSources, setExternalPisccSources] = useState<Record<string, ExternalPisccSource>>({});
  const [pisccSourceNotice, setPisccSourceNotice] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setExternalPisccSources({});
    setPisccSourceNotice('Consultando fuentes externas del PISCC…');
    const cutoff = getPeriodDateRange(selectedYear, periodType, selectedPeriodValue).end;
    fetch(`/api/piscc-sources?cutoff=${encodeURIComponent(cutoff)}`, { signal: controller.signal })
      .then(async res => { const data = await res.json(); if (!res.ok) throw new Error(data.error || 'No se pudieron consultar las fuentes PISCC.'); return data; })
      .then(data => {
        if (controller.signal.aborted) return;
        if (data?.sources) setExternalPisccSources(data.sources as Record<string, ExternalPisccSource>);
        setPisccSourceNotice((data.notices || []).join(' '));
      })
      .catch(error => { if (!controller.signal.aborted) setPisccSourceNotice(error.message || 'Fuentes PISCC no disponibles.'); });
    return () => controller.abort();
  }, [selectedYear, periodType, selectedPeriodValue]);

  const handleExcelUpload = (file: File) => {

    setLoading(true);
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const bstr = evt.target?.result;
        if (typeof bstr !== 'string') {
          setLoading(false);
          return;
        }

        const fileHash = generateQuickHash(bstr);
        setUploadedFileName(file.name);
        setUploadedFileHash(fileHash);

        const wb = XLSX.read(bstr, { type: 'binary', cellDates: true, ...(/\.csv$/i.test(file.name) ? { codepage: 65001 } : {}) });
        const normalizeHeader = (value: unknown) => String(value ?? '')
          .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
          .toUpperCase().replace(/[._\-/]+/g, ' ').replace(/\s+/g, ' ').trim();
        const headerKey = (value: unknown) => normalizeHeader(value).replace(/\s+/g, '');
        const isMunicipioHeader = (value: string) => /MUNICIPIO|MUNI|CIUDAD|MUNICIPALIDAD/.test(headerKey(value));
        const isConductaHeader = (value: string) => /CONDUCTA|DELITO|INFRACCION|COMPORTAMIENTO/.test(headerKey(value));

        // La entrega puede traer primero hojas de resumen o tablas dinámicas.
        // Elegimos la primera hoja que realmente contenga la tabla detallada.
        const sheetData = wb.SheetNames.map((name) => ({
          name,
          rows: XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets[name], { header: 1, raw: true }),
        }));
        const selectedSheet = sheetData.find(({ rows }) => rows.some((row) => {
          if (!row) return false;
          const normalized = row.map(normalizeHeader);
          return normalized.some(isMunicipioHeader) && normalized.some(isConductaHeader);
        }));
        const rawData = selectedSheet?.rows ?? [];

        let headerIdx = -1;
        const columns: Record<string, number> = {};
        // Algunas entregas oficiales traen títulos, logos o notas antes de la tabla.
        for (let i = 0; i < Math.min(100, rawData.length); i++) {
            const row = rawData[i];
            if (!row) continue;
            const normalized = row.map(normalizeHeader);
            if (normalized.some(isMunicipioHeader) && normalized.some(isConductaHeader)) {
                headerIdx = i;
                normalized.forEach((h: string, idx: number) => { if(h) columns[h] = idx; });
                break;
            }
        }

        if (headerIdx > -1) {
            const parsedData: CrimeRow[] = [];

            const muniIdx = Object.keys(columns).find(isMunicipioHeader);
            const anioIdx = Object.keys(columns).find(k => /\bANO\b|\bAO\b|\bANIO\b|\bYEAR\b/i.test(k));
            const mesIdx = Object.keys(columns).find(k => /^MES$|^MONTH$/i.test(k));
            const semanaIdx = Object.keys(columns).find(k => /\b(NO\s*)?SEMANA\b|\bSEM\b|\bNRO\s*SEMANA\b|\bNUM\s*SEMANA\b/i.test(k));
            const conductaIdx = Object.keys(columns).find(isConductaHeader);
            const barrioIdx = Object.keys(columns).find(k => /BARRIOS HECHO|\bBARRIO\b|\bSECTOR\b/i.test(k));
            const armaIdx = Object.keys(columns).find(k => /ARMAS MEDIOS|\bARMA\b|\bMEDIO\b/i.test(k));
            const diaIdx = Object.keys(columns).find(k => /DIA|DÍA/i.test(k));
            const hechosIdIdx = Object.keys(columns).find(k => /HECHOS_ID|ID_HECHO|IDENTIFICADOR/i.test(k));
            const fechaIdx = Object.keys(columns).find(k => /FECHA_HECHO|FECHA/i.test(k));
            const generoIdx = Object.keys(columns).find(k => /GENERO|GÉNERO|SEXO/i.test(k));
            const edadIdx = Object.keys(columns).find(k => /EDAD|EDADES/i.test(k));
            const gestionEstatalIdx = Object.keys(columns).find(k => /GESTION_ESTATAL|FUENTE/i.test(k));

            if (muniIdx === undefined || anioIdx === undefined || semanaIdx === undefined || conductaIdx === undefined) {
                const missing = [];
                if (muniIdx === undefined) missing.push("Municipio");
                if (anioIdx === undefined) missing.push("Año");
                if (semanaIdx === undefined) missing.push("No. Semana");
                if (conductaIdx === undefined) missing.push("Conducta / Delito");
                alert("Error de importación: No se encontraron las columnas necesarias:\n" + missing.join(", ") + "\n\nColumnas detectadas: " + Object.keys(columns).join(", "));
                setLoading(false);
                return;
            }

            for(let i = headerIdx + 1; i < rawData.length; i++) {
                const row = rawData[i];
                if (!row) continue;

                const muni = String(row[columns[muniIdx]] ?? '').toUpperCase();
                if (muni.includes('JAMUNDI') || muni.includes('JAMUNDÍ')) {
                    const y = parseInt(String(row[columns[anioIdx]]));
                    if(!isNaN(y)) {
                        const rawConducta = String(row[columns[conductaIdx]] ?? '').trim();
                        const normalizedConducta = normalizarConducta(rawConducta);
                        
                        parsedData.push({
                            AÑO: y,
                            MES: mesIdx ? String(row[columns[mesIdx]] ?? '').toLowerCase() : '',
                            NoSEMANA: Number.parseInt(String(row[columns[semanaIdx]]).replace(/[^0-9-]/g, ''), 10) || 0,
                            CONDUCTA: normalizedConducta,
                            CONDUCTA_ORIGINAL: rawConducta,
                            BARRIO: barrioIdx ? String(row[columns[barrioIdx]] ?? '').trim().toUpperCase() : 'SIN DATO',
                            ARMA: armaIdx ? String(row[columns[armaIdx]] ?? '').trim().toUpperCase() : 'SIN DATO',
                            DIA: diaIdx ? String(row[columns[diaIdx]] ?? '').trim().toUpperCase() : 'SIN DATO',
                            HECHOS_ID: hechosIdIdx ? String(row[columns[hechosIdIdx]] ?? '').trim() : undefined,
                            FECHA_HECHO: fechaIdx ? excelSerialToDateString(row[columns[fechaIdx]]) : undefined,
                            GENERO: generoIdx ? String(row[columns[generoIdx]] ?? '').trim().toUpperCase() : undefined,
                            EDAD: edadIdx ? String(row[columns[edadIdx]] ?? '').trim() : undefined,
                            GESTION_ESTATAL: gestionEstatalIdx ? String(row[columns[gestionEstatalIdx]] ?? '').trim() : undefined,
                            SOURCE_ROW_KEY: sourceRowRecordKey(row),
                        });
                    }
                }
            }

            const deduplicated = deduplicateCrimeRows(parsedData);
            const uniqueYears = Array.from(new Set(deduplicated.rows.map(row => row.AÑO))).sort((a,b)=>b-a);
            setAvailableYears(uniqueYears);
            if(uniqueYears.length > 0) setSelectedYear(uniqueYears[0]); // Select max year

            // Extract unique conductas
            const conductas = new Set<string>();
            deduplicated.rows.forEach(row => {
               const val = row.CONDUCTA.trim();
               if (val && val !== 'Sin Dato' && val !== 'No reportada') conductas.add(val);
            });
            setAvailableConductas(Array.from(conductas).sort());
            setSelectedConducta('Todos');
            setUploadSummary({
              totalRows: deduplicated.totalRows,
              uniqueRows: deduplicated.rows.length,
              duplicateRows: deduplicated.duplicateRows,
            });
            setRawExcelData(deduplicated.rows);
        } else {
            alert("No se pudo detectar la fila de cabecera con las columnas de Municipio y Conducta/Delito.");
        }
      } catch (err) {
        console.error(err);
        alert("Error procesando el archivo Excel.");
      } finally {
        setLoading(false);
      }
    };
    reader.readAsBinaryString(file);
  };

  const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch('/api/parse-pdf', { method: 'POST', body: formData });
        const json = await res.json();
        if (json.success) {
            setOperations(json.data as OperationsData);
            alert("¡PDF Analizado con éxito!\nCapturas: " + json.data.capturas);
        } else {
            console.error("PDF Error", json);
            alert("Error analizando PDF");
        }
    } catch (err) {
        console.error(err);
    } finally {
        setLoading(false);
    }
  };

  // Stats Calculation Logic
  /* eslint-disable react-hooks/preserve-manual-memoization */
  const stats = useMemo<StatsResult | null>(() => {
    if (!rawExcelData || rawExcelData.length === 0) return null;

    let currentPeriodCount = 0;
    let prevPeriodCount = 0;
    let currentYTDCount = 0;
    let prevYTDCount = 0;
    
    let prevImmediatePeriodCount = 0;
    let last4WeeksCount = 0;
    
    const currentPeriodRows: CrimeRow[] = [];

    const baseYear = Number(selectedYear);
    const prevYear = baseYear - 1;

    const tableCountsYTD: Record<string, { current: number, prev: number }> = {};
    const tableCountsPeriod: Record<string, { current: number, prev: number, prevImmediate?: number }> = {};
    const tableGroupingKey: keyof CrimeRow = selectedConducta === 'Todos' ? 'CONDUCTA' : 'BARRIO';

    rawExcelData.forEach(row => {
      // Conducta Filter
      if (selectedConducta !== 'Todos' && row.CONDUCTA.trim().toUpperCase() !== selectedConducta.toUpperCase()) {
          return; // Skip if it doesn't match the selected crime
      }

      const year = row.AÑO;
      const month = row.MES;
      const week = row.NoSEMANA;
      
      let inCurrentPeriod = false;
      let inPrevPeriod = false;
      let inCurrentYTD = false;
      let inPrevYTD = false;
      
      let inPrevImmediatePeriod = false;
      let inLast4Weeks = false;

      if (periodType === 'semanal') {
        const targetWeek = Number(selectedPeriodValue);
        if (week === targetWeek) {
            if (year === baseYear) inCurrentPeriod = true;
            if (year === prevYear) inPrevPeriod = true;
        }
        if (week === targetWeek - 1 && year === baseYear) {
            inPrevImmediatePeriod = true;
        }
        if (week > targetWeek - 4 && week <= targetWeek && year === baseYear) {
            inLast4Weeks = true;
        }
        if (week <= targetWeek) {
            if (year === baseYear) inCurrentYTD = true;
            if (year === prevYear) inPrevYTD = true;
        }
      } else if (periodType === 'mensual') {
        const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
        const targetMonthIdx = months.indexOf(String(selectedPeriodValue).toLowerCase().substring(0,3));
        const rowMonthIdx = months.indexOf(month.substring(0,3));
        
        if (rowMonthIdx === targetMonthIdx) {
            if (year === baseYear) inCurrentPeriod = true;
            if (year === prevYear) inPrevPeriod = true;
        }
        if (rowMonthIdx === targetMonthIdx - 1 && year === baseYear) {
            inPrevImmediatePeriod = true;
        }
        if (rowMonthIdx <= targetMonthIdx && rowMonthIdx !== -1) {
            if (year === baseYear) inCurrentYTD = true;
            if (year === prevYear) inPrevYTD = true;
        }
      } else if (periodType === 'semestral') {
        const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
        const rowMonthIdx = months.indexOf(month.substring(0,3));
        const s1 = rowMonthIdx >= 0 && rowMonthIdx <= 5;
        const s2 = rowMonthIdx >= 6 && rowMonthIdx <= 11;
        const isTargetS1 = String(selectedPeriodValue) === '1';

        if ((isTargetS1 && s1) || (!isTargetS1 && s2)) {
            if (year === baseYear) inCurrentPeriod = true;
            if (year === prevYear) inPrevPeriod = true;
        }
        // Periodo inmediatamente anterior:
        //  - Si el target es S2 (2do semestre) del año base -> el inmediato anterior es S1 del año base.
        //  - Si el target es S1 (1er semestre) del año base -> el inmediato anterior es S2 del año anterior.
        if (!isTargetS1 && s1 && year === baseYear) {
            inPrevImmediatePeriod = true;
        }
        if (isTargetS1 && s2 && year === prevYear) {
            inPrevImmediatePeriod = true;
        }

        if (isTargetS1) {
            if (s1) {
                if (year === baseYear) inCurrentYTD = true;
                if (year === prevYear) inPrevYTD = true;
            }
        } else {
            if (s1 || s2) {
                if (year === baseYear) inCurrentYTD = true;
                if (year === prevYear) inPrevYTD = true;
            }
        }
      } else if (periodType === 'anual') {
        if (year === baseYear) {
            inCurrentPeriod = true;
            inCurrentYTD = true;
        }
        if (year === prevYear) {
            inPrevPeriod = true;
            inPrevYTD = true;
            inPrevImmediatePeriod = true;
        }
      }

      if (inCurrentPeriod) {
          currentPeriodCount++;
          currentPeriodRows.push(row);
      }
      if (inPrevPeriod) prevPeriodCount++;
      if (inCurrentYTD) currentYTDCount++;
      if (inPrevYTD) prevYTDCount++;
      if (inPrevImmediatePeriod) prevImmediatePeriodCount++;
      if (inLast4Weeks) last4WeeksCount++;

      // Table Aggregations
      const keyVal = String(row[tableGroupingKey] || '').trim().toUpperCase();
      if (keyVal && keyVal !== 'SIN DATO' && keyVal !== '-' && keyVal !== 'UNDEFINED') {
          // Period Table (also track prevImmediate)
          if (inCurrentPeriod || inPrevPeriod || inPrevImmediatePeriod) {
              if (!tableCountsPeriod[keyVal]) tableCountsPeriod[keyVal] = { current: 0, prev: 0, prevImmediate: 0 };
              if (inCurrentPeriod) tableCountsPeriod[keyVal].current++;
              if (inPrevPeriod) tableCountsPeriod[keyVal].prev++;
              if (inPrevImmediatePeriod) tableCountsPeriod[keyVal].prevImmediate = (tableCountsPeriod[keyVal].prevImmediate || 0) + 1;
          }
          // YTD Table
          if (inCurrentYTD || inPrevYTD) {
              if (!tableCountsYTD[keyVal]) tableCountsYTD[keyVal] = { current: 0, prev: 0 };
              if (inCurrentYTD) tableCountsYTD[keyVal].current++;
              if (inPrevYTD) tableCountsYTD[keyVal].prev++;
          }
      }
    });

    const getTop = (arr: CrimeRow[], key: keyof CrimeRow, n: number): TopItem[] => {
        const counts: Record<string, number> = {};
        arr.forEach(item => {
            const raw = item[key];
            if (raw === undefined) return;
            const val = String(raw).trim().toUpperCase();
            if(val && val !== 'UNDEFINED' && val !== 'SIN DATO' && val !== '-' && val !== 'NO REPORTADA' && val !== 'NO REPORTADO') {
                counts[val] = (counts[val] || 0) + 1;
            }
        });
        return Object.entries(counts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, n)
            .map(x => ({ name: x[0], count: x[1] }));
    };

    const topConductas = getTop(currentPeriodRows, 'CONDUCTA', 3);
    const topBarrios = getTop(currentPeriodRows, 'BARRIO', 5);
    const topArmas = getTop(currentPeriodRows, 'ARMA', 5);

    // Chart Data (Time Series by Month or Week)
    let chartData: ChartPoint[] = [];
    const isWeeklyChart = periodType === 'semanal';
    const targetWeek = Number(selectedPeriodValue) || 1;

    if (isWeeklyChart) {
        for (let i = 1; i <= targetWeek; i++) {
            chartData.push({ name: `S${i}`, current: 0, prev: 0 });
        }
    } else {
        const monthsKeys = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
        chartData = monthsKeys.map(m => ({ name: m, current: 0, prev: 0 }));
    }

    rawExcelData.forEach(row => {
        if (selectedConducta !== 'Todos' && row.CONDUCTA.trim().toUpperCase() !== selectedConducta) return;
        const y = row.AÑO;
        const mStr = row.MES?.substring(0,3).toLowerCase();
        const mIdx = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'].indexOf(mStr);
        const w = row.NoSEMANA;

        let inYTD = false;
        if (periodType === 'semanal' && w <= targetWeek) inYTD = true;
        if (periodType === 'mensual' && mIdx !== -1 && mIdx <= ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'].indexOf(String(selectedPeriodValue).toLowerCase().substring(0,3))) inYTD = true;
        if (periodType === 'semestral') {
            const isTargetS1 = String(selectedPeriodValue) === '1';
            if (isTargetS1 && mIdx >= 0 && mIdx <= 5) inYTD = true;
            if (!isTargetS1 && mIdx >= 0 && mIdx <= 11) inYTD = true;
        }
        if (periodType === 'anual') inYTD = true;

        if (isWeeklyChart) {
            if (w >= 1 && w <= targetWeek) {
                if (y === baseYear) chartData[w - 1].current++;
                if (y === prevYear) chartData[w - 1].prev++;
            }
        } else {
            if (mIdx >= 0 && mIdx < 12) {
                if (inYTD) {
                    if (y === baseYear) chartData[mIdx].current++;
                    if (y === prevYear) chartData[mIdx].prev++;
                }
            }
        }
    });

    const formatTablePeriod = (countsMap: Record<string, { current: number, prev: number, prevImmediate?: number }>): PeriodTableRow[] => {
        return Object.entries(countsMap)
            .sort((a, b) => b[1].current - a[1].current)
            .slice(0, 5) // TOP 5
            .map(([name, counts]) => {
                let varPct = '0%';
                if (counts.prev === 0) varPct = counts.current > 0 ? '+100%' : '0%';
                else {
                    const diff = ((counts.current - counts.prev) / counts.prev) * 100;
                    varPct = `${diff > 0 ? '+' : ''}${diff.toFixed(0)}%`;
                }
                const diffYoY = counts.current - counts.prev;
                const diffWoW = counts.prevImmediate !== undefined ? counts.current - counts.prevImmediate : 0;
                return { name, current: counts.current, prev: counts.prev, varPct, prevImmediate: counts.prevImmediate, diffYoY, diffWoW };
            });
    };

    const formatTableYTD = (countsMap: Record<string, { current: number, prev: number }>): YtdTableRow[] => {
        return Object.entries(countsMap)
            .sort((a, b) => b[1].current - a[1].current)
            .slice(0, 10) // YTD Table can be longer if needed, or 5
            .map(([name, counts]) => {
                let varPct = '0%';
                if (counts.prev === 0) varPct = counts.current > 0 ? '+100%' : '0%';
                else {
                    const diff = ((counts.current - counts.prev) / counts.prev) * 100;
                    varPct = `${diff > 0 ? '+' : ''}${diff.toFixed(0)}%`;
                }
                const diffAbs = counts.current - counts.prev;
                return { name, current: counts.current, prev: counts.prev, varPct, diffAbs };
            });
    };

    const totalesPorConductaSemana: Record<string, number> = {};
    const totalesPorConductaYTD: Record<string, number> = {};

    rawExcelData.forEach(row => {
      const year = row.AÑO;
      const week = row.NoSEMANA;
      const month = row.MES;
      const c = row.CONDUCTA;

      if (year === baseYear) {
        if (periodType === 'semanal') {
          const targetWeek = Number(selectedPeriodValue);
          if (week === targetWeek) {
            totalesPorConductaSemana[c] = (totalesPorConductaSemana[c] || 0) + 1;
          }
          if (week <= targetWeek) {
            totalesPorConductaYTD[c] = (totalesPorConductaYTD[c] || 0) + 1;
          }
        } else if (periodType === 'mensual') {
          const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
          const targetMonthIdx = months.indexOf(String(selectedPeriodValue).toLowerCase().substring(0,3));
          const rowMonthIdx = months.indexOf(month.substring(0,3));
          if (rowMonthIdx === targetMonthIdx) {
            totalesPorConductaSemana[c] = (totalesPorConductaSemana[c] || 0) + 1;
          }
          if (rowMonthIdx <= targetMonthIdx && rowMonthIdx !== -1) {
            totalesPorConductaYTD[c] = (totalesPorConductaYTD[c] || 0) + 1;
          }
        } else if (periodType === 'semestral') {
          const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
          const rowMonthIdx = months.indexOf(month.substring(0,3));
          const s1 = rowMonthIdx >= 0 && rowMonthIdx <= 5;
          const s2 = rowMonthIdx >= 6 && rowMonthIdx <= 11;
          const isTargetS1 = String(selectedPeriodValue) === '1';
          if ((isTargetS1 && s1) || (!isTargetS1 && s2)) {
            totalesPorConductaSemana[c] = (totalesPorConductaSemana[c] || 0) + 1;
          }
          if (isTargetS1 ? s1 : (s1 || s2)) {
            totalesPorConductaYTD[c] = (totalesPorConductaYTD[c] || 0) + 1;
          }
        } else if (periodType === 'anual') {
          totalesPorConductaSemana[c] = (totalesPorConductaSemana[c] || 0) + 1;
          totalesPorConductaYTD[c] = (totalesPorConductaYTD[c] || 0) + 1;
        }
      }
    });

    const periodRange = getPeriodDateRange(baseYear, periodType, selectedPeriodValue);
    const fechaCorteInicio = periodRange.start;
    const fechaCorteFin = periodRange.end;

    // MOTOR DE CONCILIACIÓN
    let conciliacion: BulletinConciliation | undefined = undefined;

    if (periodType === 'semanal') {
      const targetWeek = Number(selectedPeriodValue);
      let prevBulletin = history.find(b => b.estado === 'vigente' && b.anio === baseYear && b.semana === targetWeek - 1 && (b.periodType || 'semanal') === 'semanal');
      let warningMessage = '';

      if (!prevBulletin && targetWeek > 1) {
        const previousBulletins = history
          .filter(b => b.estado === 'vigente' && b.anio === baseYear && b.semana < targetWeek && (b.periodType || 'semanal') === 'semanal')
          .sort((a, b) => b.semana - a.semana);
        if (previousBulletins.length > 0) {
          prevBulletin = previousBulletins[0];
          warningMessage = `No se encontró un boletín histórico vigente para la semana ${targetWeek - 1}. La conciliación se realizó contra la semana ${prevBulletin.semana} y puede no identificar todos los ajustes intermedios.`;
        } else {
          warningMessage = 'No se encontró un boletín histórico vigente para comparar. La validación se omitirá hasta registrar publicaciones previas.';
        }
      }

      if (prevBulletin) {
        const compWeek = prevBulletin.semana;
        const hasImmediateBaseline = compWeek === targetWeek - 1;
        let totalSemanaRecalculado = 0;
        let totalYTDRecalculado = 0;
        const newTotalesSemanaComp: Record<string, number> = {};
        const newTotalesYTDComp: Record<string, number> = {};

        rawExcelData.forEach(row => {
          const year = row.AÑO;
          const week = row.NoSEMANA;
          const c = row.CONDUCTA;

          if (year === baseYear) {
            if (week === compWeek) {
              totalSemanaRecalculado++;
              newTotalesSemanaComp[c] = (newTotalesSemanaComp[c] || 0) + 1;
            }
            if (week <= compWeek) {
              totalYTDRecalculado++;
              newTotalesYTDComp[c] = (newTotalesYTDComp[c] || 0) + 1;
            }
          }
        });

        const totalSemanaPublicado = prevBulletin.totalSemana;
        const totalYTDPublicado = prevBulletin.totalYTD;

        const diferenciaSemana = totalSemanaRecalculado - totalSemanaPublicado;
        const diferenciaYTD = totalYTDRecalculado - totalYTDPublicado;
        const ajusteSemanasPrevias = diferenciaYTD - diferenciaSemana;

        const cambiosPorConducta: Array<{ conducta: string; publicado: number; recalculado: number; diferencia: number }> = [];
        const allConductasKeys = new Set([
          ...Object.keys(prevBulletin.totalesPorConductaYTD || {}),
          ...Object.keys(newTotalesYTDComp)
        ]);

        allConductasKeys.forEach(cKey => {
          const pubVal = prevBulletin?.totalesPorConductaYTD?.[cKey] || 0;
          const recalcVal = newTotalesYTDComp[cKey] || 0;
          const diff = recalcVal - pubVal;
          if (diff !== 0) {
            cambiosPorConducta.push({
              conducta: cKey,
              publicado: pubVal,
              recalculado: recalcVal,
              diferencia: diff
            });
          }
        });

        let tipoAjuste: BulletinConciliation['tipoAjuste'] = 'sin_cambios';
        if (diferenciaYTD > 0) tipoAjuste = 'incremento_neto';
        else if (diferenciaYTD < 0) tipoAjuste = 'reduccion_neta';
        else if (diferenciaYTD === 0 && cambiosPorConducta.length > 0) tipoAjuste = 'reclasificacion_neta';

        const esAltoImpacto = hasImmediateBaseline && Math.abs(diferenciaYTD) > 15;
        let notaGenerada = '';
        
        if (esAltoImpacto) {
          notaGenerada = `Inconsistencia histórica de alto impacto: el valor recalculado (${totalYTDRecalculado}) difiere significativamente del boletín publicado (${totalYTDPublicado}) en la semana ${compWeek}. Se requiere revisión del archivo utilizado, los filtros aplicados o la metodología de conteo antes de generar una nota automática.`;
        } else if (tipoAjuste === 'incremento_neto') {
          const hechoSemanaWord = Math.abs(diferenciaSemana) === 1 ? 'hecho corresponde' : 'hechos corresponden';
          const hechoPrevWord = Math.abs(ajusteSemanasPrevias) === 1 ? 'hecho a semanas previas' : 'hechos a semanas previas';
          
          if (diferenciaSemana !== 0 && ajusteSemanasPrevias !== 0) {
            notaGenerada = `Ajuste de la serie: la nueva entrega de la fuente oficial presenta una variación neta positiva de ${diferenciaYTD} hechos correspondientes a periodos anteriores. De esta diferencia, ${Math.abs(diferenciaSemana)} ${hechoSemanaWord} a la semana ${compWeek} y ${Math.abs(ajusteSemanasPrevias)} ${hechoPrevWord}. Las cifras acumuladas fueron actualizadas y pueden diferir de boletines previamente publicados.`;
          } else if (diferenciaSemana !== 0) {
            notaGenerada = `Ajuste de la serie: la nueva entrega de la fuente oficial presenta una variación neta de ${diferenciaYTD} hechos adicionales correspondientes a la semana ${compWeek}. Las cifras acumuladas fueron actualizadas y pueden diferir de boletines previamente publicados.`;
          } else {
            notaGenerada = `Ajuste de la serie: la nueva entrega de la fuente oficial presenta una variación neta positiva de ${diferenciaYTD} hechos correspondientes a periodos anteriores (semanas previas a la semana ${compWeek}). Las cifras acumuladas fueron actualizadas y pueden diferir de boletines previamente publicados.`;
          }
        } else if (tipoAjuste === 'reduccion_neta') {
          const hechoSemanaWord = Math.abs(diferenciaSemana) === 1 ? 'hecho corresponde' : 'hechos corresponden';
          const hechoPrevWord = Math.abs(ajusteSemanasPrevias) === 1 ? 'hecho' : 'hechos';
          
          if (diferenciaSemana !== 0 && ajusteSemanasPrevias !== 0) {
            notaGenerada = `Ajuste de la serie: la nueva entrega de la fuente oficial presenta una reducción neta de ${Math.abs(diferenciaYTD)} hechos correspondientes a periodos anteriores. De esta diferencia, ${Math.abs(diferenciaSemana)} ${hechoSemanaWord} a la semana ${compWeek} y ${Math.abs(ajusteSemanasPrevias)} ${hechoPrevWord} a semanas previas. Las cifras acumuladas fueron actualizadas.`;
          } else if (diferenciaSemana !== 0) {
            notaGenerada = `Ajuste de la serie: la nueva entrega presenta una reducción neta de ${Math.abs(diferenciaYTD)} hechos correspondientes a la semana ${compWeek}, por depuraciones de la fuente oficial.`;
          } else {
            notaGenerada = `Ajuste de la serie: la nueva entrega presenta una reducción neta de ${Math.abs(diferenciaYTD)} hechos en semanas anteriores a la semana ${compWeek}, derivada de ajustes realizados por la fuente oficial.`;
          }
        } else if (tipoAjuste === 'reclasificacion_neta') {
          notaGenerada = `Ajuste de la serie: aunque el total acumulado no presenta variación neta, se identificaron reclasificaciones entre conductas respecto del boletín previamente publicado por actualización de la fuente oficial.`;
        }

        conciliacion = {
          boletinComparadoId: prevBulletin.id,
          semanaComparada: compWeek,
          totalSemanaPublicado,
          totalSemanaRecalculado,
          diferenciaSemana,
          totalYTDPublicado,
          totalYTDRecalculado,
          diferenciaYTD,
          ajusteSemanasPrevias,
          cambiosPorConducta,
          tipoAjuste,
          precision: warningMessage ? 'indeterminada' : 'semanal',
          notaGenerada: warningMessage ? `${warningMessage}\n\n${notaGenerada}` : notaGenerada
        };
      }
    }

    const periodTableData = formatTablePeriod(tableCountsPeriod);
    const ytdTableData = formatTableYTD(tableCountsYTD);

    const periodName = periodType === 'semanal' ? `Semana ${selectedPeriodValue}` : 
                       periodType === 'mensual' ? `Mes ${String(selectedPeriodValue).toUpperCase()}` : 
                       periodType === 'semestral' ? `Semestre ${selectedPeriodValue}` : `Anual`;

    // 1. Balance General
    const diffYTD = currentYTDCount - prevYTDCount;
    const signYTD = diffYTD > 0 ? 'un incremento' : 'una reducción';
    const signYTD2 = diffYTD > 0 ? 'un aumento' : 'una disminución';
    const absDiffYTD = Math.abs(diffYTD);
    const pctYTD = prevYTDCount > 0 ? Math.abs((diffYTD / prevYTDCount) * 100).toFixed(1) : '0';
    const balanceText = `El balance general del acumulado de delitos priorizados al corte de la ${periodName.toLowerCase()} registra ${signYTD} de ${absDiffYTD} ${absDiffYTD === 1 ? 'hecho' : 'hechos'} frente al mismo periodo de ${prevYear}, equivalente a ${signYTD2} del ${pctYTD}%.`;

    // 2. Conductas que explican el resultado
    const totalesPorConductaYTDPrev: Record<string, number> = {};
    rawExcelData.forEach(row => {
      const year = row.AÑO;
      const week = row.NoSEMANA;
      const month = row.MES;
      const c = row.CONDUCTA;
      if (year === prevYear) {
        if (periodType === 'semanal') {
          const targetWeek = Number(selectedPeriodValue);
          if (week <= targetWeek) {
            totalesPorConductaYTDPrev[c] = (totalesPorConductaYTDPrev[c] || 0) + 1;
          }
        } else if (periodType === 'mensual') {
          const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
          const targetMonthIdx = months.indexOf(String(selectedPeriodValue).toLowerCase().substring(0,3));
          const rowMonthIdx = months.indexOf(month.substring(0,3));
          if (rowMonthIdx <= targetMonthIdx && rowMonthIdx !== -1) {
            totalesPorConductaYTDPrev[c] = (totalesPorConductaYTDPrev[c] || 0) + 1;
          }
        } else if (periodType === 'semestral') {
          const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
          const rowMonthIdx = months.indexOf(month.substring(0,3));
          const s1 = rowMonthIdx >= 0 && rowMonthIdx <= 5;
          const s2 = rowMonthIdx >= 6 && rowMonthIdx <= 11;
          const isTargetS1 = String(selectedPeriodValue) === '1';
          if (isTargetS1 ? s1 : (s1 || s2)) {
            totalesPorConductaYTDPrev[c] = (totalesPorConductaYTDPrev[c] || 0) + 1;
          }
        } else if (periodType === 'anual') {
          totalesPorConductaYTDPrev[c] = (totalesPorConductaYTDPrev[c] || 0) + 1;
        }
      }
    });

    const aportesConductas: Array<{ conducta: string; diff: number }> = [];
    const todasLasConductas = new Set([...Object.keys(totalesPorConductaYTD), ...Object.keys(totalesPorConductaYTDPrev)]);
    todasLasConductas.forEach(c => {
      const currVal = totalesPorConductaYTD[c] || 0;
      const prevVal = totalesPorConductaYTDPrev[c] || 0;
      aportesConductas.push({ conducta: c, diff: currVal - prevVal });
    });

    let conductasExplicativas = '';
    if (diffYTD < 0) {
      const reducciones = [...aportesConductas].sort((a, b) => a.diff - b.diff).filter(x => x.diff < 0);
      if (reducciones.length >= 2) {
        conductasExplicativas = `Esta reducción está explicada principalmente por el ${reducciones[0].conducta.toLowerCase()}, con ${Math.abs(reducciones[0].diff)} ${Math.abs(reducciones[0].diff) === 1 ? 'caso menos' : 'casos menos'}, y el ${reducciones[1].conducta.toLowerCase()}, con ${Math.abs(reducciones[1].diff)} ${Math.abs(reducciones[1].diff) === 1 ? 'caso menos' : 'casos menos'}.`;
      } else if (reducciones.length === 1) {
        conductasExplicativas = `Esta reducción está explicada principalmente por el ${reducciones[0].conducta.toLowerCase()}, con ${Math.abs(reducciones[0].diff)} ${Math.abs(reducciones[0].diff) === 1 ? 'caso menos' : 'casos menos'}.`;
      } else {
        conductasExplicativas = 'Esta variación presenta un comportamiento estable entre las distintas conductas delictivas.';
      }
    } else {
      const incrementos = [...aportesConductas].sort((a, b) => b.diff - a.diff).filter(x => x.diff > 0);
      if (incrementos.length >= 2) {
        conductasExplicativas = `Este incremento está explicado principalmente por el ${incrementos[0].conducta.toLowerCase()}, con ${incrementos[0].diff} ${incrementos[0].diff === 1 ? 'caso más' : 'casos más'}, y el ${incrementos[1].conducta.toLowerCase()}, con ${incrementos[1].diff} ${incrementos[1].diff === 1 ? 'caso más' : 'casos más'}.`;
      } else if (incrementos.length === 1) {
        conductasExplicativas = `Este incremento está explicado principalmente por el ${incrementos[0].conducta.toLowerCase()}, con ${incrementos[0].diff} ${incrementos[0].diff === 1 ? 'caso más' : 'casos más'}.`;
      } else {
        conductasExplicativas = 'Esta variación presenta un comportamiento de estabilidad o baja fluctuación en las distintas conductas.';
      }
    }

    // 3. Alertas de seguimiento
    const alertas: string[] = [];
    aportesConductas.forEach(item => {
      if (item.diff > 0) {
        const currVal = totalesPorConductaYTD[item.conducta] || 0;
        const prevVal = totalesPorConductaYTDPrev[item.conducta] || 0;
        const pctDiff = prevVal > 0 ? (item.diff / prevVal) * 100 : 100;
        const participacion = currentYTDCount > 0 ? (currVal / currentYTDCount) * 100 : 0;

        const condUpper = item.conducta.toUpperCase();
        const esDelitoCritico = condUpper.includes("HOMICIDIO") || condUpper.includes("MOTOCICLETAS") || condUpper.includes("MOTOS") || condUpper.includes("MOTOR");

        const cumpleCriterio1 = item.diff >= 3;
        const cumpleCriterio2 = participacion > 10;
        const cumpleCriterio3 = esDelitoCritico && pctDiff > 5;

        if (cumpleCriterio1 || cumpleCriterio2 || cumpleCriterio3) {
          alertas.push(`${item.conducta.toLowerCase()} (con incremento de ${item.diff} ${item.diff === 1 ? 'hecho' : 'hechos'}, equivalente a +${pctDiff.toFixed(1)}%)`);
        }
      }
    });

    let alertasText = '';
    if (alertas.length > 0) {
      alertasText = `El balance general continúa siendo favorable; sin embargo, se mantienen alertas focalizadas en: ${alertas.join(', ')}.`;
    } else {
      alertasText = `El balance general continúa siendo favorable, manteniéndose la estabilidad en las principales conductas de impacto.`;
    }

    const generatedAnalysis = `ANÁLISIS DE HALLAZGOS EJECUTIVOS\n\n1. BALANCE GENERAL\n${balanceText}\n\n2. CONDUCTAS QUE EXPLICAN EL RESULTADO\n${conductasExplicativas}\n\n3. ALERTAS DE SEGUIMIENTO\n${alertasText}`;

    const activeRecord = history.find(b => b.anio === baseYear && b.semana === (periodType === 'semanal' ? Number(selectedPeriodValue) : 0) && b.estado === 'vigente');
    const versionBoletin = activeRecord ? `v${activeRecord.version}` : 'v1.0 (Borrador)';

    const fechaHoy = new Date();
    const pad2 = (n: number) => String(n).padStart(2, '0');
    const fechaExtraccionStr = `${pad2(fechaHoy.getDate())}/${pad2(fechaHoy.getMonth() + 1)}/${fechaHoy.getFullYear()}`;

    return {
      currentPeriodCount,
      prevPeriodCount,
      currentYTDCount,
      prevYTDCount,
      prevImmediatePeriodCount,
      last4WeeksAvg: last4WeeksCount / 4,
      baseYear,
      prevYear,
      periodName,
      topConductas,
      topBarrios,
      topArmas,
      generatedAnalysis,
      selectedConducta,
      chartData,
      periodTableData,
      ytdTableData,
      periodType,
      fechaCorteInicio,
      fechaCorteFin,
      fechaExtraccion: fechaExtraccionStr,
      nombreArchivo: uploadedFileName || 'SABANAS MANUALES.xlsx',
      hashArchivo: uploadedFileHash || 'hash_manual',
      totalesPorConductaSemana,
      totalesPorConductaYTD,
      conciliacion,
      versionBoletin,
      pisccTracking: computePisccTracking(rawExcelData, baseYear, prevYear, periodType, selectedPeriodValue, externalPisccSources)
    };
  }, [rawExcelData, selectedYear, periodType, selectedPeriodValue, selectedConducta, history, uploadedFileName, uploadedFileHash, externalPisccSources]);
  /* eslint-enable react-hooks/preserve-manual-memoization */

  const selectedPeriodRange = getPeriodDateRange(selectedYear, periodType, selectedPeriodValue);
  const requestedPeriodRange = {
    start: stats?.fechaCorteInicio || selectedPeriodRange.start,
    end: stats?.fechaCorteFin || selectedPeriodRange.end,
  };

  const syncSiscPublication = async (signal?: AbortSignal) => {
    setSiscLoading(true);
    setSiscError(null);
    setSiscPublication(null);
    try {
      const publication = await fetchSiscPublication(
        periodType,
        requestedPeriodRange.start,
        requestedPeriodRange.end,
        signal,
      );
      setSiscPublication(publication);
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      setSiscPublication(null);
      setSiscError(error instanceof Error ? error.message : 'No fue posible conectar con el SISC.');
    } finally {
      if (!signal?.aborted) setSiscLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSiscLoading(true);
      setSiscError(null);
      setSiscPublication(null);
      try {
        const publication = await fetchSiscPublication(
          periodType,
          requestedPeriodRange.start,
          requestedPeriodRange.end,
          controller.signal,
        );
        if (!controller.signal.aborted) setSiscPublication(publication);
      } catch (error: unknown) {
        if (controller.signal.aborted) return;
        setSiscPublication(null);
        setSiscError(error instanceof Error ? error.message : 'No fue posible conectar con el SISC.');
      } finally {
        if (!controller.signal.aborted) setSiscLoading(false);
      }
    }, 150);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [periodType, requestedPeriodRange.start, requestedPeriodRange.end]);

  const selectSourceLastCutoff = (cutoff?: string | null) => {
    if (!cutoff) return;
    const [year, month] = cutoff.split('-').map(Number);
    if (!year || !month) return;
    setSelectedYear(year);
    setPeriodType('mensual');
    setSelectedPeriodValue(MONTH_LABELS[month - 1]);
  };

  const securityReconciliation = (() => {
    if (!stats || !siscPublication) return null;
    const targetLabel = normalizeComparableLabel(selectedConducta);
    const officialIndicator = siscPublication.indicators.find(indicator => {
      if (indicator.source_code !== 'POLICIA_SEMANAL') return false;
      if (selectedConducta === 'Todos') return indicator.indicator_code === 'seguridad.total';
      return indicator.category === 'Conducta'
        && normalizeComparableLabel(indicator.indicator_name) === targetLabel;
    });
    if (!officialIndicator) {
      return {
        matches: false,
        message: `SISC no devolvió un indicador comparable para ${selectedConducta === 'Todos' ? 'el total de Seguridad' : selectedConducta}.`,
      };
    }

    const officialValue = Number(officialIndicator.value);
    const matches = officialValue === stats.currentPeriodCount;
    return {
      matches,
      message: matches
        ? `La sábana cargada coincide con SISC: ${officialValue} ${officialValue === 1 ? 'hecho' : 'hechos'} en el periodo.`
        : `La sábana cargada no coincide: archivo local ${stats.currentPeriodCount}; SISC ${officialValue}.`,
    };
  })();

  const publicationForPreview: SiscPublication | null = (() => {
    if (!siscPublication) return null;
    if (securityReconciliation?.matches !== false) return siscPublication;
    return {
      ...siscPublication,
      governance: {
        ...siscPublication.governance,
        publication_ready: false,
        review_blockers: [
          ...(siscPublication.governance.review_blockers || []),
          securityReconciliation.message,
        ],
      },
    };
  })();

  // Las fuentes, cortes y diferencias se muestran como advertencias de
  // trazabilidad. No requieren una aprobación administrativa adicional porque
  // el boletín contiene únicamente información pública agregada y anonimizada.
  // Publicación deshabilitada mientras haya consulta oficial pendiente o fallida,
  // o sin cifra oficial vigente (ningún conteo local alimenta cifras oficiales).
  // La cifra oficial debe corresponder a la consulta actual: mismo período,
  // indicador SEGURIDAD_TOTAL, entrega SELECCIONADA actualmente (no solo existente),
  // territorio JAMUNDI y metodología 1. Restricción explícita de este flujo:
  // solo se publica JAMUNDI + SEGURIDAD_TOTAL; otros territorios/indicadores
  // requieren un flujo de publicación propio.
  const officialMatchesCurrentQuery = Boolean(
    officialResult
    && officialResult.indicator === 'SEGURIDAD_TOTAL'
    && officialSelection.indicator === 'SEGURIDAD_TOTAL'
    && officialResult.period.start === requestedPeriodRange.start
    && officialResult.period.end === requestedPeriodRange.end
    && officialResult.territory === 'JAMUNDI'
    && officialResult.methodology_version === '1'
    && officialResult.source_version_id
    && officialSelection.sourceVersionId
    && officialResult.source_version_id === officialSelection.sourceVersionId,
  );
  const publicationCanBeRegistered = Boolean(stats) && officialMatchesCurrentQuery && !officialPending && !officialError
    && securityReconciliation?.matches === true && !siscLoading && !siscError;

  const currentYear = new Date().getFullYear();
  const periodYearOptions = Array.from(new Set([
    selectedYear,
    currentYear,
    currentYear - 1,
    currentYear - 2,
    ...availableYears,
  ])).sort((a, b) => b - a);

  // Dynamic dropdown options
  const getPeriodOptions = () => {
    if (periodType === 'semanal') {
        return Array.from({length: 53}, (_, i) => (<option key={i+1} value={i+1}>Semana {i+1}</option>));
    }
    if (periodType === 'mensual') {
        return MONTH_LABELS.map((m) => (<option key={m} value={m}>{m}</option>));
    }
    if (periodType === 'semestral') {
        return [
            <option key="1" value="1">Semestre 1 (Ene-Jun)</option>,
            <option key="2" value="2">Semestre 2 (Jul-Dic)</option>
        ];
    }
    return <option value="1">Todo el año</option>;
  };

  return (
    <main className="app-container">
      <aside className="control-panel overflow-y-auto">
        <div className="p-6 border-b border-ui-border">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
            <h1 className="text-xl font-bold tracking-wide text-white">Generador Institucional</h1>
            <p className="text-sm text-ui-text-secondary mt-1">Secretaría de Seguridad y Convivencia</p>
            </div>
            <button type="button" onClick={onOpenArchive} className="flex shrink-0 items-center gap-1.5 border border-ui-border bg-white/5 px-3 py-2 text-xs font-bold text-white hover:bg-white/10">
              Boletines <ExternalLink size={13} />
            </button>
          </div>
        </div>

        <div className="p-6 flex flex-col gap-6">
          <section className="order-3 bg-ui-card-bg p-5 rounded-lg border border-ui-border">
            <h2 className="text-lg font-semibold text-ui-text-primary mb-3 flex items-center gap-2">
              📂 Cargar Datos
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-ui-text-secondary mb-1">Archivo SABANAS (Excel, carga local rápida)</label>
                <input
                  type="file" accept=".xlsx, .xls, .csv"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleExcelUpload(f); }}
                  onClick={(e: React.MouseEvent<HTMLInputElement>) => { e.currentTarget.value = ''; }}
                  className="block w-full text-sm text-ui-text-secondary file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-ui-accent file:text-white hover:file:bg-blue-600 cursor-pointer bg-black/20 rounded-md border border-ui-border"
                />
                <p className="mt-1 text-[11px] text-ui-text-secondary">Previsualización inmediata en este navegador. Para cifra oficial y publicación use la carga validada al servidor.</p>
              </div>
              <SabanaUploadFlow
                onStart={() => { setLoadedDelivery(''); setOfficialResult(null); setRawExcelData([]); setUploadSummary(null); setSiscPublication(null); }}
                onReady={(file, run) => {
                  setLoadedDelivery(run.id);
                  handleExcelUpload(file);
                  const end = run.resumen?.snapshot?.coverage?.max_date;
                  if (end) {
                    const year = Number(end.slice(0, 4));
                    const week = run.resumen?.snapshot?.coverage?.max_week_by_year?.[String(year)];
                    setSelectedYear(year);
                    if (week) { setPeriodType('semanal'); setSelectedPeriodValue(String(week)); }
                    else { setPeriodType('mensual'); setSelectedPeriodValue(MONTH_LABELS[Number(end.slice(5, 7)) - 1]); }
                  }
                }}
              />
              
              <div>
                <label className="block text-sm font-medium text-ui-text-secondary mb-1">Resultados Operativos (PDF)</label>
                <input 
                  type="file" accept=".pdf" onChange={handlePdfUpload} onClick={(e: React.MouseEvent<HTMLInputElement>) => { e.currentTarget.value = ''; }}
                  className="block w-full text-sm text-ui-text-secondary file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-police-green file:text-white hover:file:bg-green-600 cursor-pointer bg-black/20 rounded-md border border-ui-border"
                />
              </div>
              
              {loading && <div className="text-ui-accent text-sm font-bold animate-pulse">Procesando archivo...</div>}
              {uploadSummary && !loading && (
                <div className="border border-ui-border bg-black/20 p-3 text-xs text-ui-text-secondary">
                  <div className="font-semibold text-ui-text-primary">Previsualización de carga — registros, no oficial</div>
                  <div>{uploadSummary.uniqueRows} filas únicas de {uploadSummary.totalRows} leídas.</div>
                  <div>{uploadSummary.duplicateRows} filas idénticas excluidas del análisis.</div>
                </div>
              )}
              <OfficialQueryPanel
                sourceVersionId={loadedDelivery}
                periodStart={requestedPeriodRange.start}
                periodEnd={requestedPeriodRange.end}
                onOfficialChange={setOfficialResult}
                onPendingChange={(p, e) => { setOfficialPending(p); setOfficialError(e); }}
                onSelectionChange={setOfficialSelection}
              />
              <details className="text-sm text-ui-text-secondary"><summary>Historial y herramientas de conciliación</summary><CentralHistoryPanel localDrafts={history.map((h) => ({ id: h.id, anio: h.anio, semana: h.semana, totalYTD: h.totalYTD, totalSemana: h.totalSemana, nombreArchivo: h.nombreArchivo, hashArchivo: h.hashArchivo }))} /></details>
            </div>
          </section>

          <section className="order-1 bg-ui-card-bg p-5 rounded-lg border border-ui-border">
              <h2 className="text-md font-semibold text-white mb-3 flex items-center gap-2">
                <CalendarClock size={17} aria-hidden="true" /> Periodo de consulta
              </h2>
              <div className="space-y-3">
                 <div>
                    <label className="block text-xs text-ui-text-secondary mb-1">Año Base</label>
                    <select value={selectedYear} onChange={e => setSelectedYear(Number(e.target.value))} className="w-full bg-black/30 border border-ui-border rounded p-2 text-white text-sm">
                        {periodYearOptions.map(y => <option key={y} value={y}>{y}</option>)}
                    </select>
                 </div>
                 {rawExcelData.length > 0 && <div>
                    <label className="block text-xs text-ui-text-secondary mb-1">Delito a Analizar</label>
                    <select value={selectedConducta} onChange={e => setSelectedConducta(e.target.value)} className="w-full bg-black/30 border border-ui-border rounded p-2 text-white text-sm font-semibold text-police-accent">
                        <option value="Todos">⚠️ Todos los Delitos</option>
                        {availableConductas.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                 </div>}
                 <div className="grid grid-cols-2 gap-2">
                    <div>
                        <label className="block text-xs text-ui-text-secondary mb-1">Tipo de Periodo</label>
                        <select value={periodType} onChange={e => {
                            setPeriodType(e.target.value as PeriodType);
                            if (e.target.value === 'semanal') setSelectedPeriodValue('1');
                            if (e.target.value === 'mensual') setSelectedPeriodValue(DEFAULT_PERIOD_MONTH);
                            if (e.target.value === 'semestral') setSelectedPeriodValue('1');
                            if (e.target.value === 'anual') setSelectedPeriodValue('1');
                        }} className="w-full bg-black/30 border border-ui-border rounded p-2 text-white text-sm">
                            <option value="semanal">Semanal</option>
                            <option value="mensual">Mensual</option>
                            <option value="semestral">Semestral</option>
                            <option value="anual">Anual</option>
                        </select>
                    </div>
                    <div>
                        <label className="block text-xs text-ui-text-secondary mb-1">Periodo Exacto</label>
                        <select value={selectedPeriodValue} onChange={e => setSelectedPeriodValue(e.target.value)} disabled={periodType === 'anual'} className="w-full bg-black/30 border border-ui-border rounded p-2 text-white text-sm disabled:opacity-50">
                            {getPeriodOptions()}
                        </select>
                    </div>
                 </div>
                 <div className="border-l-2 border-ui-accent pl-3 text-[11px] leading-relaxed text-ui-text-secondary">
                   {rawExcelData.length > 0
                     ? `Sábana cargada. Las cifras se conciliarán con SISC para ${requestedPeriodRange.start} a ${requestedPeriodRange.end}.`
                     : `Consulta institucional para ${requestedPeriodRange.start} a ${requestedPeriodRange.end}. El PDF permanece pendiente hasta cargar la sábana.`}
                 </div>
              </div>
            </section>

          <section className="order-2 bg-ui-card-bg p-5 rounded-lg border border-ui-border">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <h2 className="text-md font-semibold text-white flex items-center gap-2">
                    <Database size={17} aria-hidden="true" /> Fuentes SISC
                  </h2>
                  <p className="text-[11px] text-ui-text-secondary mt-1">
                    Policía, Inspecciones y Comisarías | {requestedPeriodRange.start} al {requestedPeriodRange.end}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void syncSiscPublication()}
                  disabled={siscLoading}
                  title="Actualizar fuentes del SISC"
                  className="h-8 px-2.5 border border-ui-border bg-black/20 hover:bg-black/40 disabled:opacity-50 text-white flex items-center gap-1.5 text-xs font-semibold"
                >
                  <RefreshCw size={14} className={siscLoading ? 'animate-spin' : ''} aria-hidden="true" />
                  Actualizar
                </button>
              </div>

              {siscError && (
                <div className="flex gap-2 border-l-2 border-red-400 pl-3 py-1 text-xs text-red-200">
                  <XCircle size={15} className="shrink-0 mt-0.5" aria-hidden="true" />
                  <span>{siscError} El boletin local sigue disponible.</span>
                </div>
              )}

              {!siscError && siscLoading && !siscPublication && (
                <div className="text-xs text-ui-text-secondary flex items-center gap-2">
                  <RefreshCw size={14} className="animate-spin" aria-hidden="true" /> Consultando cortes aprobados...
                </div>
              )}

              {!siscError && !siscLoading && !siscPublication && (
                <div className="text-xs text-ui-text-secondary">
                  Presione Actualizar para consultar las fuentes institucionales.
                </div>
              )}

              {siscPublication && (
                <div className="border-y border-ui-border">
                  <div className="divide-y divide-ui-border">
                    {siscPublication.sources.map((source) => {
                      const coverage = source.coverage_status || 'missing';
                      const ready = coverage === 'aligned' && source.quality_status === 'VALIDADO';
                      const StatusIcon = ready ? CheckCircle2 : coverage === 'not_applicable' ? Clock3 : AlertTriangle;
                      const sourceIndicators = siscPublication.indicators.filter(indicator => (
                        indicator.source_code === source.code && indicator.domain !== 'TERRITORIO'
                      ));
                      const visibleIndicators = source.code === 'INSPECCIONES_RNMC'
                        ? sourceIndicators.filter(indicator => (
                            indicator.indicator_code === 'convivencia.actuaciones' || indicator.category === 'Medida'
                          )).slice(0, 4)
                        : sourceIndicators.slice(0, 4);
                      return (
                        <div key={source.code} className="py-3">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0 flex items-center gap-2 text-xs font-semibold text-white">
                              <StatusIcon size={14} className={ready ? 'text-emerald-300' : 'text-amber-200'} aria-hidden="true" />
                              <span>{source.name}</span>
                            </div>
                            <span className={`shrink-0 border px-2 py-0.5 text-[10px] font-bold ${SOURCE_STATUS_STYLES[coverage]}`}>
                              {SOURCE_STATUS_LABELS[coverage]}
                            </span>
                          </div>
                          <div className="mt-1 pl-[22px] text-[10px] leading-relaxed text-ui-text-secondary">
                            {source.included
                              ? `${source.period_records} ${source.code === 'COMISARIAS_FAMILIA' ? 'indicadores' : 'registros'} publicables | ${coverage === 'partial' ? 'cobertura hasta' : 'fuente actualizada al'} ${source.last_cutoff_date || 'sin fecha'}`
                              : source.status_note || 'Sin información publicable para este periodo.'}
                          </div>
                          {source.future_records ? (
                            <div className="mt-1 pl-[22px] text-[10px] text-amber-200">
                              {source.future_records} fechas futuras excluidas; requiere corrección de la fuente.
                            </div>
                          ) : null}
                          {source.exclusion_note ? (
                            <div className="mt-1 pl-[22px] text-[10px] text-ui-text-secondary">
                              {source.exclusion_note}
                            </div>
                          ) : null}
                          {visibleIndicators.length > 0 && (
                            <div className="mt-2 ml-[22px] border-y border-ui-border divide-y divide-ui-border">
                              {visibleIndicators.map(indicator => (
                                <div key={indicator.id} className="flex items-start justify-between gap-3 py-1.5 text-[10px]">
                                  <span className="leading-snug text-ui-text-secondary">
                                    {indicator.indicator_name}
                                    {indicator.metadata?.coverage_type === 'CONTEXT' && (
                                      <span className="ml-1 text-[9px] text-amber-400">(contexto)</span>
                                    )}
                                  </span>
                                  <strong className="shrink-0 text-white">
                                    {indicator.value != null
                                      ? new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 }).format(indicator.value)
                                      : '|||'}
                                  </strong>
                                </div>
                              ))}
                            </div>
                          )}
                          {!source.included && source.last_cutoff_date && source.code !== 'POLICIA_SEMANAL' && (
                            <button
                              type="button"
                              onClick={() => selectSourceLastCutoff(source.last_cutoff_date)}
                              className="mt-2 ml-[22px] inline-flex items-center gap-1.5 border border-ui-border px-2 py-1 text-[10px] font-semibold text-white hover:bg-black/30"
                              title={`Consultar el mes del último corte de ${source.name}`}
                            >
                              <CalendarClock size={12} aria-hidden="true" />
                              Ver último corte
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {securityReconciliation && (
                    <div className={`mt-2 border-l-2 px-3 py-2 text-[10px] leading-relaxed ${securityReconciliation.matches ? 'border-emerald-400 text-emerald-200' : 'border-red-400 text-red-200'}`}>
                      <strong>Conciliación de Seguridad:</strong> {securityReconciliation.message}
                    </div>
                  )}
                </div>
              )}
            </section>

          {stats && (
            <section className="order-4 bg-ui-card-bg p-5 rounded-lg border border-ui-border">
              <h2 className="text-md font-semibold text-white mb-2">📊 Datos Calculados</h2>
              <div className="text-sm text-ui-text-secondary mb-2">Se analizaron <strong>{rawExcelData.length}</strong> registros en memoria para extraer el comparativo.</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                 <div className="bg-black/30 p-2 rounded">
                    <span className="block text-gray-400">Actual ({stats.periodName})</span>
                    <strong className="text-white text-base">{stats.currentPeriodCount}</strong>
                 </div>
                 <div className="bg-black/30 p-2 rounded">
                    <span className="block text-gray-400">Anterior ({stats.prevYear})</span>
                    <strong className="text-white text-base">{stats.prevPeriodCount}</strong>
                 </div>
                 <div className="bg-black/30 p-2 rounded">
                    <span className="block text-gray-400">Acumulado {stats.baseYear}</span>
                    <strong className="text-white text-base">{stats.currentYTDCount}</strong>
                 </div>
                 <div className="bg-black/30 p-2 rounded">
                    <span className="block text-gray-400">Acumulado {stats.prevYear}</span>
                    <strong className="text-white text-base">{stats.prevYTDCount}</strong>
                 </div>
              </div>
              <button 
                onClick={() => window.print()}
                className="mt-4 w-full bg-ui-accent hover:bg-blue-600 text-white font-bold py-2 px-4 rounded transition-colors flex items-center justify-center gap-2"
              >
                <Printer size={16} aria-hidden="true" />
                <span>Descargar PDF / Imprimir</span>
              </button>
              <div className="mt-3 pt-3 border-t border-ui-border">
                <label className="flex items-center gap-2 text-xs text-ui-text-secondary cursor-pointer hover:text-white transition-colors">
                  <input
                    type="checkbox"
                    checked={includePisccPage}
                    onChange={e => setIncludePisccPage(e.target.checked)}
                    className="rounded border-ui-border text-police-accent focus:ring-0 focus:ring-offset-0 bg-black/40"
                  />
                  <span>Incluir Seguimiento PISCC 2024–2027 (Tabla 16)</span>
                </label>
                {includePisccPage && pisccSourceNotice && (
                  <p className="mt-2 text-[10px] leading-relaxed text-amber-200">{pisccSourceNotice}</p>
                )}
              </div>
            </section>
          )}

          {/* Sección de Historial */}
          <section className="order-5 bg-ui-card-bg p-5 rounded-lg border border-ui-border">
            <h2 className="text-md font-semibold text-white mb-3">📂 Boletines públicos</h2>
            <div className="space-y-3 text-xs">
              {stats && (
                <button
                  onClick={() => {
                    const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
                    const targetWeek = periodType === 'semanal' ? Number(selectedPeriodValue) :
                                       periodType === 'mensual' ? months.indexOf(String(selectedPeriodValue).toLowerCase().substring(0,3)) + 1 :
                                       periodType === 'semestral' ? Number(selectedPeriodValue) : 1;
                    const baseYear = Number(selectedYear);
                    const existing = history.find(b => 
                      b.anio === baseYear && 
                      b.semana === targetWeek && 
                      (b.periodType || 'semanal') === periodType && 
                      b.estado === 'vigente'
                    );
                    if (existing) {
                      const currentVer = parseFloat(existing.version) || 1.0;
                      setCustomVersion((currentVer + 0.1).toFixed(1));
                      setRevisionMotive('Actualización de cifras por retroactividad');
                    } else {
                      setCustomVersion('1.0');
                      setRevisionMotive('Publicación inicial');
                    }
                    setShowPublishModal(true);
                  }}
                  disabled={siscLoading || publishing || !publicationCanBeRegistered || officialPending}
                  title={publicationCanBeRegistered
                    ? `Generar boletín con cifra oficial ${officialResult ? `${officialResult.value} ${officialResult.unit} (${officialResult.indicator})` : ''}`
                    : officialPending
                      ? 'Consulta oficial en curso…'
                      : officialError
                        ? `Backend: ${officialError}`
                        : 'La entrega y el borrador deben coincidir antes de publicar'}
                  className="w-full bg-police-green hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white font-bold py-2 px-3 rounded transition-colors flex items-center justify-center gap-2"
                >
                  <Megaphone size={15} aria-hidden="true" />
                  <span>{publishing ? 'Publicando…' : 'Generar boletín público'}</span>
                </button>
              )}
              <button
                onClick={() => setShowHistoryModal(true)}
                className="w-full bg-black/40 hover:bg-black/60 border border-ui-border text-white py-2 px-3 rounded transition-colors flex items-center justify-center gap-2"
              >
                <span>👁️ Ver historial ({history.length})</span>
              </button>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={handleExportHistory}
                  className="bg-black/20 hover:bg-black/30 border border-ui-border text-gray-300 py-1.5 px-2 rounded transition-colors flex items-center justify-center gap-1"
                >
                  <span>📥 Exportar</span>
                </button>
                <label className="bg-black/20 hover:bg-black/30 border border-ui-border text-gray-300 py-1.5 px-2 rounded transition-colors flex items-center justify-center gap-1 cursor-pointer text-center">
                  <span>📤 Importar</span>
                  <input type="file" accept=".json" onChange={handleImportHistory} className="hidden" />
                </label>
              </div>
              <button
                onClick={() => {
                  setAntYear(Number(selectedYear));
                  setAntWeek(Number(selectedPeriodValue) || 1);
                  setAntVersion('1.0');
                  setAntTotalSemana(stats ? stats.currentPeriodCount : 0);
                  setAntTotalYTD(stats ? stats.currentYTDCount : 0);
                  setAntFileName(stats ? stats.nombreArchivo || '' : '');
                  setAntMotive('Carga de antecedente manual');
                  setAntConductasSemanaText(JSON.stringify(stats ? stats.totalesPorConductaSemana : {}, null, 2));
                  setAntConductasYTDText(JSON.stringify(stats ? stats.totalesPorConductaYTD : {}, null, 2));
                  setShowAntecedentModal(true);
                }}
                className="w-full text-center text-gray-400 hover:text-white py-1 transition-colors text-[11px] underline"
              >
                ➕ Agregar antecedente manual
              </button>
            </div>
          </section>

        </div>
      </aside>

      <section className="app-preview flex-1 bg-black/10 overflow-y-auto p-10 flex justify-center">
          <div className={`newsletter-document-container w-full max-w-4xl ${stats ? 'has-document' : ''}`}>
           {stats && !publicationCanBeRegistered && <p role="status" className="mb-4 rounded border border-amber-400/40 bg-amber-950 p-4 text-sm text-amber-100 print:hidden hide-on-print">Borrador no publicable todavía. {securityReconciliation?.matches === false ? 'Las cifras del borrador y de la entrega no coinciden. Revise la conciliación antes de publicar oficialmente.' : 'Esperando la comprobación de cifras y fuentes para el período seleccionado.'}</p>}
           <NewsletterPreview
             key={stats?.generatedAnalysis ?? 'empty-preview'}
             stats={stats}
             operations={operations}
             siscPublication={publicationForPreview}
              includePisccPage={includePisccPage}
           />
        </div>
      </section>

      {/* Modal 1: Generar boletín público */}
      {showPublishModal && stats && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1a1a24] border border-ui-border rounded-xl max-w-md w-full p-6 text-white shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-2">📢 Generar boletín público</h3>
            <p className="text-xs text-ui-text-secondary mb-4">
              La información es agregada y anonimizada. Las alertas de cobertura y conciliación se conservarán en el boletín como trazabilidad, sin requerir aprobación de un administrador.
            </p>
            
            <div className="bg-black/30 p-3 rounded-lg text-xs space-y-2 mb-4 border border-ui-border/50">
              <div>
                <strong className="text-gray-400">Año / Período:</strong> {selectedYear} / {
                  periodType === 'semanal' ? `Semana ${selectedPeriodValue}` :
                  periodType === 'mensual' ? `Mes ${selectedPeriodValue}` :
                  periodType === 'semestral' ? `Semestre ${selectedPeriodValue}` : 'Anual'
                }
              </div>
              <div>
                <strong className="text-gray-400">Total del Período:</strong> {stats.currentPeriodCount} hechos
              </div>
              <div><strong className="text-gray-400">Acumulado YTD:</strong> {stats.currentYTDCount} hechos</div>
              <div><strong className="text-gray-400">Archivo:</strong> <span className="font-mono text-police-accent">{stats.nombreArchivo}</span></div>
            </div>

            <div className="space-y-3 text-xs mb-6">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-ui-text-secondary mb-1">Versión del boletín</label>
                  <input 
                    type="text" 
                    value={customVersion} 
                    onChange={e => setCustomVersion(e.target.value)} 
                    className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                  />
                </div>
                <div>
                  <label className="block text-ui-text-secondary mb-1">Fecha de publicación</label>
                  <input 
                    type="date" 
                    value={publishDate} 
                    onChange={e => setPublishDate(e.target.value)} 
                    className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                  />
                </div>
              </div>
              <div>
                <label className="block text-ui-text-secondary mb-1">Motivo de la versión / Nota de revisión *</label>
                <textarea 
                  required
                  rows={3}
                  placeholder="Ej: Publicación inicial, o Corrección de 2 delitos por reclasificación retroactiva de la fuente."
                  value={revisionMotive} 
                  onChange={e => setRevisionMotive(e.target.value)} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white resize-none"
                />
              </div>
            </div>

            <div className="flex gap-3 justify-end text-xs font-bold">
              <button 
                onClick={() => setShowPublishModal(false)}
                className="bg-black/30 hover:bg-black/40 border border-ui-border text-white px-4 py-2 rounded transition-colors"
              >
                Cancelar
              </button>
              <button 
                onClick={handleRegisterPublish}
                disabled={publishing}
                className="bg-ui-accent hover:bg-blue-600 disabled:bg-gray-600 disabled:cursor-wait text-white px-4 py-2 rounded transition-colors"
              >
                {publishing ? 'Publicando…' : 'Generar y guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 2: Ver Historial */}
      {showHistoryModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1a1a24] border border-ui-border rounded-xl max-w-4xl w-full max-h-[85vh] flex flex-col text-white shadow-2xl overflow-hidden">
            
            <div className="p-6 border-b border-ui-border flex justify-between items-center">
              <div>
                <h3 className="text-lg font-bold text-white">📚 Historial de Boletines Publicados</h3>
                <p className="text-xs text-ui-text-secondary">Registro inmutable de publicaciones del Observatorio del Delito de Jamundí</p>
              </div>
              <button 
                onClick={() => setShowHistoryModal(false)}
                className="text-gray-400 hover:text-white font-bold text-lg"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 flex gap-6">
              <div className="flex-1 overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-black/40 border-b border-ui-border text-gray-400">
                      <th className="py-2 px-3 font-semibold">Año/Sem</th>
                      <th className="py-2 px-3 font-semibold">Versión</th>
                      <th className="py-2 px-3 font-semibold">Estado</th>
                      <th className="py-2 px-3 font-semibold text-center">Total</th>
                      <th className="py-2 px-3 font-semibold text-center">Acum.</th>
                      <th className="py-2 px-3 font-semibold text-center">Ajuste</th>
                      <th className="py-2 px-3 font-semibold">Publicación</th>
                      <th className="py-2 px-3 font-semibold">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ui-border/30">
                    {history.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-gray-500">No hay boletines registrados en este navegador.</td>
                      </tr>
                    ) : (
                      [...history].sort((a,b) => b.anio - a.anio || b.semana - a.semana || parseFloat(b.version) - parseFloat(a.version)).map((record) => {
                        const hasAjuste = record.conciliacion && record.conciliacion.tipoAjuste !== 'sin_cambios';
                        const statusColors: Record<string, string> = {
                          vigente: 'bg-green-500/20 text-green-400 border border-green-500/30',
                          sustituida: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
                          anulada: 'bg-red-500/20 text-red-400 border border-red-500/30',
                          antecedente: 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        };
                        return (
                          <tr 
                            key={record.id} 
                            className={`hover:bg-white/5 cursor-pointer ${selectedHistoryItem?.id === record.id ? 'bg-white/10' : ''}`}
                            onClick={() => setSelectedHistoryItem(record)}
                          >
                            <td className="py-2.5 px-3 font-medium">{record.anio} / S{record.semana}</td>
                            <td className="py-2.5 px-3">{record.version}</td>
                            <td className="py-2.5 px-3">
                              <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${statusColors[record.estado] || 'bg-gray-500'}`}>
                                {record.estado}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-center font-bold">{record.totalSemana}</td>
                            <td className="py-2.5 px-3 text-center">{record.totalYTD}</td>
                            <td className="py-2.5 px-3 text-center">
                              {hasAjuste ? <span className="text-yellow-400">⚠️ Sí</span> : <span className="text-gray-500">No</span>}
                            </td>
                            <td className="py-2.5 px-3 text-gray-400">{record.fechaPublicacion}</td>
                            <td className="py-2.5 px-3 space-x-2" onClick={e => e.stopPropagation()}>
                              <button 
                                onClick={() => setSelectedHistoryItem(record)}
                                className="text-police-accent hover:underline text-[11px]"
                              >
                                Detalle
                              </button>
                              {record.estado === 'vigente' && (
                                <button 
                                  onClick={() => handleAnnulRecord(record.id)}
                                  className="text-red-400 hover:underline text-[11px]"
                                >
                                  Anular
                                </button>
                              )}
                              {(record.estado === 'anulada' || record.estado === 'antecedente') && (
                                <button 
                                  onClick={() => handleDeleteRecord(record.id)}
                                  className="text-gray-400 hover:text-white hover:underline text-[11px]"
                                >
                                  Eliminar
                                </button>
                              )}
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {selectedHistoryItem && (
                <div className="w-80 bg-black/30 border border-ui-border rounded-lg p-4 text-xs space-y-4 overflow-y-auto max-h-[60vh] border-l-[4px] border-l-police-accent">
                  <div className="flex justify-between items-center border-b border-ui-border/50 pb-2">
                    <h4 className="font-bold text-white text-sm">Detalles del Registro</h4>
                    <button onClick={() => setSelectedHistoryItem(null)} className="text-gray-400 hover:text-white font-bold">✕</button>
                  </div>
                  
                  <div className="space-y-2">
                    <div><strong className="text-gray-400">ID:</strong> <span className="font-mono text-gray-500">{selectedHistoryItem.id.substring(0,8)}...</span></div>
                    <div><strong className="text-gray-400">Año / Semana:</strong> {selectedHistoryItem.anio} / S{selectedHistoryItem.semana}</div>
                    <div><strong className="text-gray-400">Versión:</strong> {selectedHistoryItem.version} ({selectedHistoryItem.estado})</div>
                    <div><strong className="text-gray-400">Origen:</strong> {selectedHistoryItem.origenRegistro}</div>
                    <div><strong className="text-gray-400">Motivo:</strong> {selectedHistoryItem.motivoRevision}</div>
                    <div><strong className="text-gray-400">Publicado:</strong> {selectedHistoryItem.fechaPublicacion}</div>
                    <div><strong className="text-gray-400">Archivo:</strong> <span className="font-mono text-police-accent block break-all">{selectedHistoryItem.nombreArchivo}</span></div>
                  </div>

                  {selectedHistoryItem.conciliacion && (
                    <div className="border-t border-ui-border/50 pt-3 space-y-2">
                      <h5 className="font-bold text-white text-[11px]">Conciliación</h5>
                      <div><strong className="text-gray-400">Dif. Semana:</strong> {selectedHistoryItem.conciliacion.diferenciaSemana > 0 ? '+' : ''}{selectedHistoryItem.conciliacion.diferenciaSemana}</div>
                      <div><strong className="text-gray-400">Dif. YTD:</strong> {selectedHistoryItem.conciliacion.diferenciaYTD > 0 ? '+' : ''}{selectedHistoryItem.conciliacion.diferenciaYTD}</div>
                      {selectedHistoryItem.conciliacion.cambiosPorConducta && selectedHistoryItem.conciliacion.cambiosPorConducta.length > 0 && (
                        <div>
                          <strong className="text-gray-400">Por Conducta YTD:</strong>
                          <ul className="list-disc list-inside mt-1 space-y-0.5 text-gray-400 text-[10px]">
                            {selectedHistoryItem.conciliacion.cambiosPorConducta.map((c, i) => (
                              <li key={i}>{c.conducta}: {c.diferencia > 0 ? '+' : ''}{c.diferencia}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="p-6 border-t border-ui-border flex justify-end">
              <button 
                onClick={() => setShowHistoryModal(false)}
                className="bg-ui-accent hover:bg-blue-600 text-white font-bold py-2 px-6 rounded transition-colors text-xs"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 3: Agregar Antecedente */}
      {showAntecedentModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1a1a24] border border-ui-border rounded-xl max-w-lg w-full p-6 text-white shadow-2xl overflow-y-auto max-h-[90vh]">
            <h3 className="text-lg font-bold text-white mb-2">➕ Agregar Antecedente Manual</h3>
            <p className="text-xs text-ui-text-secondary mb-4">
              Registrar un boletín histórico de forma manual para alimentar la base de conciliación.
            </p>

            <div className="grid grid-cols-3 gap-2 text-xs mb-3">
              <div>
                <label className="block text-ui-text-secondary mb-1">Año</label>
                <input 
                  type="number" 
                  value={antYear} 
                  onChange={e => setAntYear(Number(e.target.value))} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                />
              </div>
              <div>
                <label className="block text-ui-text-secondary mb-1">Semana</label>
                <input 
                  type="number" 
                  value={antWeek} 
                  onChange={e => setAntWeek(Number(e.target.value))} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                />
              </div>
              <div>
                <label className="block text-ui-text-secondary mb-1">Versión</label>
                <input 
                  type="text" 
                  value={antVersion} 
                  onChange={e => setAntVersion(e.target.value)} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs mb-3">
              <div>
                <label className="block text-ui-text-secondary mb-1">Total Semana</label>
                <input 
                  type="number" 
                  value={antTotalSemana} 
                  onChange={e => setAntTotalSemana(Number(e.target.value))} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                />
              </div>
              <div>
                <label className="block text-ui-text-secondary mb-1">Total YTD Acumulado</label>
                <input 
                  type="number" 
                  value={antTotalYTD} 
                  onChange={e => setAntTotalYTD(Number(e.target.value))} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                />
              </div>
            </div>

            <div className="space-y-3 text-xs mb-4">
              <div>
                <label className="block text-ui-text-secondary mb-1">Nombre del Archivo Excel Original</label>
                <input 
                  type="text" 
                  placeholder="SABANAS SEM X 2026.xlsx"
                  value={antFileName} 
                  onChange={e => setAntFileName(e.target.value)} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                />
              </div>
              <div>
                <label className="block text-ui-text-secondary mb-1">Observaciones / Motivo de carga</label>
                <input 
                  type="text" 
                  value={antMotive} 
                  onChange={e => setAntMotive(e.target.value)} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white"
                />
              </div>
              <div>
                <label className="block text-ui-text-secondary mb-1">Totales por Conducta Semana (JSON)</label>
                <textarea 
                  rows={2}
                  value={antConductasSemanaText} 
                  onChange={e => setAntConductasSemanaText(e.target.value)} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white font-mono text-[10px]"
                />
              </div>
              <div>
                <label className="block text-ui-text-secondary mb-1">Totales por Conducta YTD (JSON)</label>
                <textarea 
                  rows={2}
                  value={antConductasYTDText} 
                  onChange={e => setAntConductasYTDText(e.target.value)} 
                  className="w-full bg-black/40 border border-ui-border rounded p-2 text-white font-mono text-[10px]"
                />
              </div>
            </div>

            <div className="flex gap-3 justify-end text-xs font-bold">
              <button 
                onClick={() => setShowAntecedentModal(false)}
                className="bg-black/30 hover:bg-black/40 border border-ui-border text-white px-4 py-2 rounded transition-colors"
              >
                Cancelar
              </button>
              <button 
                onClick={handleRegisterAntecedent}
                className="bg-ui-accent hover:bg-blue-600 text-white px-4 py-2 rounded transition-colors"
              >
                Guardar Antecedente
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
