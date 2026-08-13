import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Activity,
    AlertTriangle,
    Brain,
    Car,
    ChevronDown,
    Database,
    Download,
    FileSpreadsheet,
    FileText,
    Home,
    Layers,
    LoaderCircle,
    MapPinned,
    PhoneForwarded,
    RefreshCw,
    Shield,
    Skull,
    UserMinus,
    Users,
} from 'lucide-react';
import DashboardFilters from '../components/DashboardFiltersV2';
import InstitutionalManagementSummary from '../components/InstitutionalManagementSummary';
import MapComponent from '../components/Map/MapComponent';
import {
    AIAnalysisPanel,
    AlertsPanel,
    DistributionChart,
    EmptyInstitutionalPanel,
    MetricCard,
    RecentRecords,
    TrendChart,
} from '../components/OperationalDashboardWidgets';
import { apiFetch, apiJson, readApiError } from '../utils/apiClient';

const METRIC_DEFINITIONS = [
    { key: 'homicidios', label: 'Homicidios', icon: Skull },
    { key: 'hurto_personas', label: 'Hurto a personas', icon: UserMinus },
    { key: 'hurto_vehiculos', label: 'Hurto de vehículos', icon: Car },
    { key: 'extorsion', label: 'Extorsión', icon: PhoneForwarded },
    { key: 'vif', label: 'Violencia intrafamiliar', icon: Home },
    { key: 'lesiones', label: 'Lesiones personales', icon: Activity },
];

const parseIso = (value) => new Date(`${value}T00:00:00`);
const toIso = (value) => value.toISOString().slice(0, 10);
const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

const monthRangeFromCutoff = (value) => {
    const cutoff = parseIso(value);
    return {
        start: toIso(new Date(cutoff.getFullYear(), cutoff.getMonth(), 1)),
        end: toIso(new Date(cutoff.getFullYear(), cutoff.getMonth() + 1, 0)),
    };
};

const shiftYear = (value) => {
    const source = parseIso(value);
    const shifted = new Date(source);
    shifted.setFullYear(source.getFullYear() - 1);
    if (shifted.getMonth() !== source.getMonth()) shifted.setDate(0);
    return toIso(shifted);
};

const getReferenceRange = (range, mode) => {
    if (mode === 'previous_year') return { start: shiftYear(range.start), end: shiftYear(range.end) };
    const start = parseIso(range.start);
    const end = parseIso(range.end);
    const days = Math.round((end - start) / 86400000) + 1;
    const previousEnd = new Date(start);
    previousEnd.setDate(previousEnd.getDate() - 1);
    const previousStart = new Date(previousEnd);
    previousStart.setDate(previousStart.getDate() - days + 1);
    return { start: toIso(previousStart), end: toIso(previousEnd) };
};

const metricComparison = (current, previous) => {
    const currentValue = Number(current || 0);
    const previousValue = Number(previous || 0);
    if (previousValue === 0) return { changeText: currentValue === 0 ? 'Sin variación' : 'Sin base comparable', trend: 'neutral' };
    const percent = ((currentValue - previousValue) / previousValue) * 100;
    return {
        changeText: `${percent > 0 ? '+' : ''}${percent.toFixed(1)}%`,
        trend: percent > 0 ? 'negative' : percent < 0 ? 'positive' : 'neutral',
    };
};

const formatDate = (value, includeTime = false) => {
    if (!value) return 'No disponible';
    const date = value instanceof Date ? value : new Date(value.length === 10 ? `${value}T00:00:00` : value);
    return new Intl.DateTimeFormat('es-CO', includeTime
        ? { dateStyle: 'medium', timeStyle: 'short' }
        : { day: 'numeric', month: 'short', year: 'numeric' }).format(date);
};

const downloadResponse = async (response, filename) => {
    if (!response.ok) throw new Error(await readApiError(response, 'No fue posible generar el archivo.'));
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
};

const Dashboard = ({ userRoles = [], dataLevel = 1, onNavigate }) => {
    const isInstitutional = dataLevel >= 2;
    const [sourceStatus, setSourceStatus] = useState(null);
    const [range, setRange] = useState(null);
    const [comparisonMode, setComparisonMode] = useState('previous_year');
    const [currentKpis, setCurrentKpis] = useState({});
    const [previousKpis, setPreviousKpis] = useState({});
    const [trend, setTrend] = useState([]);
    const [distribution, setDistribution] = useState([]);
    const [recent, setRecent] = useState([]);
    const [mapData, setMapData] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [alertsUpdatedAt, setAlertsUpdatedAt] = useState(null);
    const [aiInsight, setAiInsight] = useState('');
    const [aiProvider, setAiProvider] = useState('');
    const [inbox, setInbox] = useState(null);
    const [managementSummary, setManagementSummary] = useState(null);
    const [managementLoading, setManagementLoading] = useState(true);
    const [managementError, setManagementError] = useState('');
    const [loading, setLoading] = useState(true);
    const [extrasLoading, setExtrasLoading] = useState(true);
    const [error, setError] = useState('');
    const [exportOpen, setExportOpen] = useState(false);
    const [exporting, setExporting] = useState('');
    const requestIdRef = useRef(0);
    const managementRequestIdRef = useRef(0);

    useEffect(() => {
        let cancelled = false;
        const initialize = async () => {
            try {
                const status = await apiJson('/analitica/estadisticas/ultima-actualizacion');
                if (cancelled) return;
                const referenceDate = parseIso(status.ultima_fecha);
                setSourceStatus(status);
                setRange({
                    start: toIso(new Date(referenceDate.getFullYear(), referenceDate.getMonth(), 1)),
                    end: status.ultima_fecha,
                });
            } catch (requestError) {
                if (!cancelled) {
                    setError(requestError.message || 'No fue posible consultar el corte disponible.');
                    setLoading(false);
                }
            }
        };
        initialize();
        return () => { cancelled = true; };
    }, []);

    const loadDashboard = useCallback(async (selectedRange, mode) => {
        if (!selectedRange?.start || !selectedRange?.end) return;
        const requestId = ++requestIdRef.current;
        setLoading(true);
        setError('');
        const referenceRange = getReferenceRange(selectedRange, mode);
        const query = `start_date=${selectedRange.start}&end_date=${selectedRange.end}`;
        const referenceQuery = `start_date=${referenceRange.start}&end_date=${referenceRange.end}`;
        try {
            const baseRequests = [
                apiJson(`/analitica/estadisticas/kpis?${query}`),
                apiJson(`/analitica/estadisticas/kpis?${referenceQuery}`),
                apiJson(`/analitica/estadisticas/tendencia?${query}`),
                apiJson(`/analitica/estadisticas/distribucion?${query}`),
            ];
            if (isInstitutional) {
                baseRequests.push(
                    apiJson(`/analitica/estadisticas/resumen?${query}`),
                    apiJson(`/analitica/eventos/geojson?${query}`),
                );
            }
            const [current, previous, trendRows, distributionRows, recentRows = [], geoJson = {}] = await Promise.all(baseRequests);
            if (requestId !== requestIdRef.current) return;
            if (current?.error_fallback) throw new Error('La fuente respondió sin indicadores válidos.');
            setCurrentKpis(current || {});
            setPreviousKpis(previous || {});
            setTrend(Array.isArray(trendRows) ? trendRows : []);
            setDistribution(Array.isArray(distributionRows) ? distributionRows : []);
            setRecent(Array.isArray(recentRows) ? recentRows.slice(0, 8).map((item) => ({ id: item.id, type: item.tipo, location: item.barrio, time: item.fecha })) : []);
            setMapData(Array.isArray(geoJson?.features) ? geoJson.features : []);
        } catch (requestError) {
            if (requestId === requestIdRef.current) setError(requestError.message || 'No fue posible actualizar el tablero.');
        } finally {
            if (requestId === requestIdRef.current) setLoading(false);
        }
    }, [isInstitutional]);

    useEffect(() => { loadDashboard(range, comparisonMode); }, [range, comparisonMode, loadDashboard]);

    const loadManagementSummary = useCallback(async (selectedRange, mode) => {
        if (!isInstitutional || !selectedRange?.start || !selectedRange?.end) return;
        const requestId = ++managementRequestIdRef.current;
        setManagementLoading(true);
        setManagementError('');
        try {
            const query = new URLSearchParams({
                period_start: selectedRange.start,
                period_end: selectedRange.end,
                comparison_mode: mode,
            });
            const endpoint = `/sisc-cifras/operational-summary?${query.toString()}`;
            let summary;
            let lastError;
            for (let attempt = 0; attempt < 3; attempt += 1) {
                try {
                    summary = await apiJson(endpoint);
                    break;
                } catch (requestError) {
                    lastError = requestError;
                    const serviceIsUpdating = [404, 502, 503, 504].includes(requestError.status);
                    if (!serviceIsUpdating || attempt === 2) throw requestError;
                    await wait(1800 * (attempt + 1));
                    if (requestId !== managementRequestIdRef.current) return;
                }
            }
            if (!summary) throw lastError || new Error('La fuente no entregó una respuesta válida.');
            if (requestId === managementRequestIdRef.current) setManagementSummary(summary);
        } catch (requestError) {
            if (requestId === managementRequestIdRef.current) {
                const serviceIsUpdating = [404, 502, 503, 504].includes(requestError.status);
                setManagementError(serviceIsUpdating
                    ? 'El servicio de fuentes se está actualizando. Reintente en unos segundos.'
                    : requestError.message || 'No fue posible consultar Inspecciones y Comisarías.');
            }
        } finally {
            if (requestId === managementRequestIdRef.current) setManagementLoading(false);
        }
    }, [isInstitutional]);

    useEffect(() => {
        loadManagementSummary(range, comparisonMode);
    }, [range, comparisonMode, loadManagementSummary]);

    useEffect(() => {
        if (!isInstitutional || !range) {
            setExtrasLoading(false);
            return undefined;
        }
        let cancelled = false;
        const loadExtras = async () => {
            setExtrasLoading(true);
            const query = `start_date=${range.start}&end_date=${range.end}`;
            const results = await Promise.allSettled([
                apiJson(`/ia/insights?${query}`),
                apiJson('/ia/alertas'),
                apiJson('/participacion/admin/bandeja'),
            ]);
            if (cancelled) return;
            if (results[0].status === 'fulfilled') {
                setAiInsight(results[0].value.insight || '');
                setAiProvider(results[0].value.provider || 'IA');
            }
            if (results[1].status === 'fulfilled') {
                setAlerts(results[1].value.alertas || []);
                setAlertsUpdatedAt(results[1].value.timestamp || null);
            }
            if (results[2].status === 'fulfilled') setInbox(results[2].value.items || []);
            setExtrasLoading(false);
        };
        loadExtras();
        return () => { cancelled = true; };
    }, [isInstitutional, range]);

    const referenceRange = useMemo(() => range ? getReferenceRange(range, comparisonMode) : null, [range, comparisonMode]);
    const metrics = useMemo(() => METRIC_DEFINITIONS.map((definition) => ({
        ...definition,
        value: currentKpis[definition.key] || 0,
        previous: previousKpis[definition.key] || 0,
        ...metricComparison(currentKpis[definition.key], previousKpis[definition.key]),
    })), [currentKpis, previousKpis]);

    const comparisonLabel = comparisonMode === 'previous_year'
        ? 'mismo periodo del año anterior'
        : 'periodo inmediatamente anterior';

    const exportCsv = () => {
        const rows = [
            ['Indicador', 'Periodo actual', 'Periodo de referencia', 'Comparación'],
            ...metrics.map((metric) => [metric.label, metric.value, metric.previous, metric.changeText]),
        ];
        const csv = `\uFEFF${rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\r\n')}`;
        const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = `Resumen_SISC_${range.end}.csv`;
        link.click();
        URL.revokeObjectURL(url);
        setExportOpen(false);
    };

    const exportPdf = async (executive = false) => {
        setExporting(executive ? 'executive' : 'detail');
        setError('');
        try {
            const endpoint = executive
                ? `/reportes/generar-boletin-ejecutivo?fecha_inicio=${range.start}&fecha_fin=${range.end}`
                : `/reportes/generar-boletin?fuente=POLICIA_SEMANAL&fecha_inicio=${range.start}&fecha_fin=${range.end}`;
            const response = await apiFetch(endpoint);
            await downloadResponse(response, `${executive ? 'Boletin_Ejecutivo' : 'Resumen_Detallado'}_SISC_${range.end}.pdf`);
            setExportOpen(false);
        } catch (requestError) {
            setError(requestError.message || 'No fue posible generar el archivo.');
        } finally {
            setExporting('');
        }
    };

    if (!range && loading) {
        return <div className="min-h-[55vh] flex items-center justify-center text-slate-600"><LoaderCircle size={24} className="animate-spin mr-3 text-primary" />Cargando corte institucional...</div>;
    }

    return (
        <div className="max-w-[1600px] mx-auto space-y-5 pb-12">
            <header className="flex flex-col 2xl:flex-row 2xl:items-end justify-between gap-4">
                <div>
                    <p className="text-xs font-bold uppercase text-primary">Secretaría de Seguridad y Convivencia</p>
                    <h2 className="text-2xl md:text-3xl font-black text-slate-900 mt-1">Resumen operativo</h2>
                    <p className="text-sm text-slate-500 mt-1">Indicadores consolidados para seguimiento y toma de decisiones.</p>
                </div>
                <div className="flex flex-col lg:flex-row lg:items-center gap-3">
                    <DashboardFilters range={range} referenceDate={sourceStatus?.ultima_fecha ? parseIso(sourceStatus.ultima_fecha) : new Date()} comparisonMode={comparisonMode} onRangeChange={setRange} onComparisonChange={setComparisonMode} />
                    <div className="relative">
                        <button onClick={() => setExportOpen(!exportOpen)} className="w-full lg:w-auto inline-flex items-center justify-center gap-2 bg-primary text-white rounded-lg px-4 py-2.5 text-sm font-bold"><Download size={17} />Exportar<ChevronDown size={15} /></button>
                        {exportOpen && <><button aria-label="Cerrar exportación" onClick={() => setExportOpen(false)} className="fixed inset-0 z-40 cursor-default" /><div className="absolute right-0 top-full mt-2 z-50 w-64 bg-white border border-slate-200 rounded-lg shadow-xl p-2"><button onClick={() => exportPdf(true)} disabled={Boolean(exporting)} className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 text-left disabled:opacity-50"><Brain size={17} className="text-primary" /><span><span className="block text-sm font-bold">Boletín ejecutivo</span><span className="block text-[10px] text-slate-500">PDF con lectura asistida</span></span></button><button onClick={() => exportPdf(false)} disabled={Boolean(exporting)} className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 text-left disabled:opacity-50"><FileText size={17} className="text-slate-600" /><span><span className="block text-sm font-bold">Resumen detallado</span><span className="block text-[10px] text-slate-500">PDF comparativo</span></span></button><button onClick={exportCsv} className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 text-left"><FileSpreadsheet size={17} className="text-emerald-700" /><span><span className="block text-sm font-bold">Indicadores CSV</span><span className="block text-[10px] text-slate-500">Datos de esta vista</span></span></button></div></>}
                    </div>
                </div>
            </header>

            <section className="grid sm:grid-cols-2 xl:grid-cols-4 bg-white border border-slate-200 rounded-lg divide-y sm:divide-y-0 sm:divide-x divide-slate-200" aria-label="Estado de la fuente">
                <div className="p-3.5 flex items-center gap-3"><Database size={18} className="text-primary" /><div><p className="text-[10px] uppercase font-bold text-slate-500">Fuente principal</p><p className="text-sm font-bold text-slate-900">Sábana SIEDCO · Policía</p></div></div>
                <div className="p-3.5 flex items-center gap-3"><RefreshCw size={18} className="text-emerald-700" /><div><p className="text-[10px] uppercase font-bold text-slate-500">Corte disponible</p><p className="text-sm font-bold text-slate-900">{formatDate(sourceStatus?.ultima_fecha)}</p></div></div>
                <div className="p-3.5 flex items-center gap-3"><Shield size={18} className="text-amber-700" /><div><p className="text-[10px] uppercase font-bold text-slate-500">Base de conteo</p><p className="text-sm font-bold text-slate-900">Registros únicos consolidados</p></div></div>
                <div className="p-3.5 flex items-center gap-3"><Layers size={18} className="text-slate-600" /><div><p className="text-[10px] uppercase font-bold text-slate-500">Última carga</p><p className="text-sm font-bold text-slate-900">{formatDate(sourceStatus?.fecha_carga, true)}</p></div></div>
            </section>

            {error && <div className="bg-red-50 border border-red-100 rounded-lg p-4 text-sm text-red-800 flex items-start gap-3"><AlertTriangle size={18} className="shrink-0" /><span className="flex-1">{error}</span><button onClick={() => loadDashboard(range, comparisonMode)} className="font-bold inline-flex items-center gap-1"><RefreshCw size={14} />Reintentar</button></div>}

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-2"><div><h3 className="text-lg font-black text-slate-900">Indicadores prioritarios</h3><p className="text-xs text-slate-500">Comparación con el {comparisonLabel}: {referenceRange ? `${formatDate(referenceRange.start)} – ${formatDate(referenceRange.end)}` : ''}.</p></div>{loading && <span className="text-xs font-bold text-primary inline-flex items-center gap-2"><LoaderCircle size={15} className="animate-spin" />Actualizando</span>}</div>
            <section className="grid grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6 gap-3">{metrics.map((metric) => <MetricCard key={metric.key} metric={metric} />)}</section>

            {isInstitutional && (
                <InstitutionalManagementSummary
                    summary={managementSummary}
                    loading={managementLoading}
                    error={managementError}
                    onRetry={() => loadManagementSummary(range, comparisonMode)}
                    onNavigate={onNavigate}
                    onUseCutoff={(cutoff) => setRange(monthRangeFromCutoff(cutoff))}
                />
            )}

            {isInstitutional ? (
                <section className="grid xl:grid-cols-2 gap-4">
                    <AlertsPanel alerts={alerts} updatedAt={alertsUpdatedAt} onOpen={() => onNavigate?.('alerts')} />
                    <AIAnalysisPanel insight={aiInsight} provider={aiProvider} loading={extrasLoading} onOpen={() => onNavigate?.('intelligence')} onDownload={() => exportPdf(false)} />
                </section>
            ) : <EmptyInstitutionalPanel />}

            <section className="grid xl:grid-cols-5 gap-4">
                <div className="xl:col-span-3"><TrendChart data={trend} /></div>
                <div className="xl:col-span-2"><DistributionChart data={distribution} /></div>
            </section>

            {isInstitutional && (
                <section className="grid xl:grid-cols-3 gap-4">
                    <article className="xl:col-span-2 bg-white border border-slate-200 rounded-lg overflow-hidden h-[480px] flex flex-col">
                        <div className="px-5 py-4 border-b border-slate-200 flex items-start justify-between gap-3"><div><h3 className="font-black text-slate-900">Mapa de registros georreferenciados</h3><p className="text-xs text-slate-500">Ubicaciones disponibles para el periodo seleccionado.</p></div><MapPinned size={20} className="text-primary" /></div>
                        <div className="flex-1 min-h-0"><MapComponent incidents={mapData} /></div>
                    </article>
                    <RecentRecords data={recent} onOpen={() => onNavigate?.('data')} />
                </section>
            )}

            <section className="grid xl:grid-cols-3 gap-4">
                {Array.isArray(inbox) && (
                    <article className="xl:col-span-2 bg-white border border-slate-200 rounded-lg p-5">
                        <div className="flex items-start justify-between gap-3 mb-4"><div><h3 className="font-black text-slate-900">Participación ciudadana</h3><p className="text-xs text-slate-500">Solicitudes pendientes recibidas por los canales públicos.</p></div><Users size={20} className="text-emerald-700" /></div>
                        {inbox.length === 0 ? <p className="text-sm text-slate-500 py-6 text-center">No hay solicitudes pendientes.</p> : <div className="grid md:grid-cols-2 gap-3">{inbox.slice(0, 4).map((item) => <div key={item.id} className="border border-slate-200 rounded-lg p-3"><div className="flex justify-between gap-2"><span className="text-[10px] font-bold text-primary uppercase">{item.tipo}</span><span className="text-[10px] text-slate-500">{formatDate(item.fecha)}</span></div><p className="text-sm font-bold text-slate-900 mt-2">{item.titulo}</p><p className="text-xs text-slate-500 mt-1 line-clamp-2">{item.subtitulo || item.descripcion}</p></div>)}</div>}
                    </article>
                )}
                <article className="bg-slate-900 text-white rounded-lg p-5">
                    <h3 className="font-black">Accesos de trabajo</h3><p className="text-xs text-slate-400 mt-1 mb-4">Herramientas relacionadas con este resumen.</p>
                    <div className="space-y-2"><button onClick={() => onNavigate?.('sources')} className="w-full flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-bold"><Database size={17} className="text-emerald-400" />Centro de fuentes</button><button onClick={() => onNavigate?.('reports')} className="w-full flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-bold"><FileText size={17} className="text-yellow-300" />Reportes técnicos</button><button onClick={() => onNavigate?.('sisc_cifras')} className="w-full flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-bold"><FileSpreadsheet size={17} className="text-blue-300" />SISC en cifras</button></div>
                </article>
            </section>
        </div>
    );
};

export default Dashboard;
