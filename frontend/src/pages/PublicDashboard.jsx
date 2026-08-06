import React, { useEffect, useMemo, useState } from 'react';
import {
    ArrowDownRight,
    ArrowLeft,
    ArrowUpRight,
    BarChart3,
    CalendarClock,
    CheckCircle2,
    Database,
    Download,
    FileText,
    Globe,
    Home,
    Info,
    Layers,
    Loader,
    Lock,
    MapPinned,
    RefreshCcw,
    ShieldCheck,
    TrendingUp,
    Users
} from 'lucide-react';
import {
    Area,
    AreaChart,
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from 'recharts';
import { MapContainer, TileLayer, GeoJSON, Popup, Tooltip as MapTooltip, CircleMarker } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { API_BASE_URL } from '../utils/apiConfig';
import { getCachedPublicDashboard, loadPublicDashboard } from '../utils/publicDashboardCache';

const COLORS = ['#281FD0', '#384CF5', '#FFB600', '#3A3A44', '#0f766e', '#b91c1c', '#7c3aed', '#475569'];
const numberFmt = new Intl.NumberFormat('es-CO');
const pctFmt = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

const formatDate = (value) => {
    if (!value) return 'Sin corte';
    return new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`));
};

const formatDateTime = (value) => {
    if (!value) return 'Sin registro';
    return new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
};

const buildDownloadUrl = (url) => {
    if (!url) return '#';
    if (url.startsWith('http')) return url;
    if (API_BASE_URL.startsWith('http') && url.startsWith('/api')) {
        return `${API_BASE_URL.replace(/\/api\/?$/, '')}${url}`;
    }
    return url;
};

const variationLabel = (value) => {
    if (value === null || value === undefined) return 'Sin base previa';
    return `${value > 0 ? '+' : ''}${pctFmt.format(value)}%`;
};

const googleMapsUrl = (lat, lng) => 'https://www.google.com/maps/search/?api=1&query=' + lat + ',' + lng;

const KpiTile = ({ icon: Icon, label, value, helper, tone = 'blue' }) => {
    const toneClasses = {
        blue: 'bg-[#281FD0]/10 text-[#281FD0] ring-[#281FD0]/10',
        amber: 'bg-amber-100 text-amber-700 ring-amber-200/70',
        slate: 'bg-slate-100 text-slate-700 ring-slate-200',
        red: 'bg-red-100 text-red-700 ring-red-200/70',
        green: 'bg-emerald-100 text-emerald-700 ring-emerald-200/70',
    };
    return (
        <div className="bg-white border border-slate-200 rounded-md p-5 min-h-[158px] flex flex-col justify-between shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between gap-3">
                <p className="text-[11px] font-black uppercase tracking-[0.12em] text-slate-500 leading-snug">{label}</p>
                <span className={`p-2.5 rounded-md ring-1 ${toneClasses[tone] || toneClasses.blue}`}><Icon size={20} /></span>
            </div>
            <div>
                <p className="text-4xl font-black text-slate-950 tracking-tight leading-none">{value}</p>
                <p className="text-xs font-semibold text-slate-500 mt-2 leading-snug">{helper}</p>
            </div>
        </div>
    );
};

const ChartShell = ({ title, subtitle, children, action }) => (
    <section className="bg-white border border-slate-200 rounded-md p-5 min-h-[360px] flex flex-col shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
            <div>
                <h2 className="text-base font-black text-slate-950 uppercase tracking-tight">{title}</h2>
                {subtitle && <p className="text-xs text-slate-500 mt-1 font-medium">{subtitle}</p>}
            </div>
            {action}
        </div>
        <div className="flex-1 min-h-[260px]">{children}</div>
    </section>
);

const EmptyState = ({ label = 'Sin datos disponibles' }) => (
    <div className="h-full min-h-[220px] flex items-center justify-center text-center text-slate-400">
        <div>
            <Database size={30} className="mx-auto mb-2 text-slate-300" />
            <p className="text-xs font-black uppercase tracking-widest">{label}</p>
        </div>
    </div>
);

const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
        <div className="bg-white border border-slate-200 shadow-lg p-3 text-sm">
            <p className="font-black text-slate-900 mb-2">{label}</p>
            {payload.map((entry) => (
                <p key={entry.dataKey || entry.name} className="font-semibold text-slate-600">
                    {entry.name}: <span className="text-slate-900">{numberFmt.format(entry.value || 0)}</span>
                </p>
            ))}
        </div>
    );
};

const TerritoryPopup = ({ point }) => (
    <div className="text-sm min-w-[190px]">
        <p className="font-black text-slate-900">{point.name}</p>
        <p className="text-slate-600">{numberFmt.format(point.total)} casos agregados</p>
        {point.zones?.length ? <p className="text-[11px] text-slate-500 mt-2">Zona: {point.zones.join(', ')}</p> : null}
        {point.conductas?.length ? <p className="text-[11px] text-slate-500 mt-1">Conductas: {point.conductas.slice(0, 3).join(', ')}</p> : null}
        {point.source && <p className="text-[11px] text-slate-500 mt-1">Fuente: {point.source}</p>}
        <a className="mt-2 inline-flex text-[11px] font-bold text-[#281FD0] underline" href={googleMapsUrl(point.lat, point.lng)} target="_blank" rel="noreferrer">Abrir en Google Maps</a>
    </div>
);

const AggregatedMap = ({ points = [], suppressed = 0, unmapped = 0, minCount = 1, zoneFilter = '', conductaFilter = '', showBubbles = false, onZoneFilter, onConductaFilter, onToggleBubbles, onSelectTerritory }) => {
    const zones = [...new Set(points.flatMap((point) => point.zones || []))].sort();
    const conductas = [...new Set(points.flatMap((point) => point.conductas || []))].sort();
    const visiblePoints = points.filter((point) => point.geometry && (!zoneFilter || point.zones?.includes(zoneFilter)) && (!conductaFilter || point.conductas?.includes(conductaFilter)));
    const maxTotal = Math.max(1, ...visiblePoints.map((point) => point.total || 0));
    const labelledTerritories = new Set([...visiblePoints].sort((a, b) => (b.total || 0) - (a.total || 0)).slice(0, 3).map((point) => point.name));
    return (
        <div className="border border-slate-200 rounded-md bg-white overflow-hidden shadow-sm">
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
                <select value={zoneFilter} onChange={(event) => onZoneFilter?.(event.target.value)} className="border border-slate-300 bg-white px-2 py-1.5 text-[11px] font-bold text-slate-700" aria-label="Filtrar por zona"><option value="">Todas las zonas</option>{zones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}</select>
                <select value={conductaFilter} onChange={(event) => onConductaFilter?.(event.target.value)} className="border border-slate-300 bg-white px-2 py-1.5 text-[11px] font-bold text-slate-700" aria-label="Filtrar por conducta"><option value="">Todas las conductas</option>{conductas.map((conducta) => <option key={conducta} value={conducta}>{conducta}</option>)}</select>
                <label className="inline-flex items-center gap-2 px-2 py-1.5 text-[11px] font-bold text-slate-700"><input type="checkbox" checked={showBubbles} onChange={(event) => onToggleBubbles?.(event.target.checked)} /> Ver burbujas</label>
                <span className="ml-auto text-[11px] font-bold text-slate-500">{visiblePoints.length} barrios en mapa</span>
            </div>
            <div className="h-[500px] relative">
                <MapContainer center={[3.2606, -76.5364]} zoom={12} zoomControl={false} preferCanvas style={{ height: '100%', width: '100%' }}>
                    <TileLayer attribution='&copy; OpenStreetMap contributors &copy; CARTO' url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" maxZoom={19} />
                    {visiblePoints.map((point) => { const intensity = (point.total || 0) / maxTotal; return <GeoJSON key={point.name} data={point.geometry} eventHandlers={{ click: () => onSelectTerritory?.(point) }} style={{ color: '#281FD0', fillColor: intensity >= 0.7 ? '#FFB600' : '#384CF5', fillOpacity: 0.28 + intensity * 0.38, weight: 2 }}>{labelledTerritories.has(point.name) && <MapTooltip permanent direction="center" className="sisc-map-label">{point.name}</MapTooltip>}<Popup><TerritoryPopup point={point} /></Popup></GeoJSON>; })}
                    {showBubbles && visiblePoints.map((point) => <CircleMarker key={`bubble-${point.name}`} center={[point.lat, point.lng]} radius={Math.max(5, Math.min(20, 5 + Math.sqrt(point.total || 0) * 1.2))} pathOptions={{ color: '#FFB600', fillColor: '#FFB600', fillOpacity: 0.24, weight: 1 }} eventHandlers={{ click: () => onSelectTerritory?.(point) }}><Popup><TerritoryPopup point={point} /></Popup></CircleMarker>)}
                </MapContainer>
            </div>
            <details className="border-t border-slate-200"><summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2 text-xs font-black uppercase tracking-wide text-slate-600"><Info size={14} className="text-[#281FD0]" /> Resumen del mapa</summary><div className="grid gap-2 border-t border-slate-100 px-4 py-3 text-xs text-slate-600 sm:grid-cols-2"><p>Solo aparecen barrios o sectores con polígono oficial verificado.</p><p>{numberFmt.format(unmapped)} barrios aún no se ubican en el mapa porque falta validación cartográfica.</p><p>No se muestran barrios con menos de {minCount} casos para proteger la privacidad de personas y comunidades. Registros omitidos: {numberFmt.format(suppressed)}.</p><p>Fuentes cartográficas: Gobernación del Valle y cartografía oficial de Jamundí.</p></div></details>
        </div>
    );
};

const DecisionCard = ({ territory }) => (
    <section className="border border-[#281FD0]/20 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-black uppercase tracking-widest text-[#281FD0]">Ficha de decisión</p><h2 className="mt-1 text-xl font-black text-slate-950">Foco territorial: {territory.name}</h2></div><a className="inline-flex items-center gap-2 border border-[#281FD0] px-3 py-2 text-[11px] font-black uppercase tracking-wide text-[#281FD0]" href={googleMapsUrl(territory.lat, territory.lng)} target="_blank" rel="noreferrer"><MapPinned size={14} /> Ver ubicación</a></div><div className="mt-4 grid gap-4 md:grid-cols-3"><div><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Resumen</p><p className="mt-1 text-sm font-bold text-slate-800">{numberFmt.format(territory.total)} casos agregados</p><p className="text-xs text-slate-500">{territory.zones?.join(', ') || 'Zona no clasificada'}</p></div><div><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Decisión sugerida</p><p className="mt-1 text-sm font-bold text-slate-800">Mantener vigilancia focalizada y revisar la tendencia en el próximo corte.</p></div><div><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Seguimiento</p><p className="mt-1 text-sm font-bold text-slate-800">Comparar casos, conducta y zona antes de mover o cerrar el foco.</p><p className="text-xs text-slate-500 mt-1">Fuente: {territory.source || 'SABANA SIEDCO/PONAL'}</p></div></div></section>
);
const PendingTerritories = ({ items = [] }) => {
    if (!items.length) return null;
    return (
        <section className="border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3"><div><p className="text-[10px] font-black uppercase tracking-widest text-amber-700">Calidad cartográfica</p><h2 className="mt-1 text-lg font-black text-slate-950">Territorios pendientes de ubicación</h2></div><span className="text-xs font-black text-slate-500">{items.length} registrados</span></div>
            <div className="mt-4 grid gap-2 md:grid-cols-2 lg:grid-cols-3">{items.slice(0, 12).map((item) => <div key={item.name} className="border border-slate-200 px-3 py-2"><div className="flex items-start justify-between gap-2"><p className="truncate text-xs font-black text-slate-800" title={item.name}>{item.name}</p><span className="shrink-0 text-xs font-black text-slate-900">{numberFmt.format(item.total)}</span></div><p className="mt-1 text-[11px] font-semibold text-amber-700">{item.reason || 'pendiente de verificación de barrio'}</p></div>)}</div>
            {items.length > 12 && <p className="mt-3 text-xs font-semibold text-slate-500">Se muestran los primeros 12; el total completo queda disponible en la respuesta técnica del tablero.</p>}
        </section>
    );
};
const PublicDashboard = ({ onLoginClick, onBack }) => {
    const [minLocationCount] = useState(1);
    const [data, setData] = useState(() => getCachedPublicDashboard(1));
    const [loading, setLoading] = useState(() => !getCachedPublicDashboard(1));
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');
    const [zoneFilter, setZoneFilter] = useState('');
    const [conductaFilter, setConductaFilter] = useState('');
    const [showBubbles, setShowBubbles] = useState(false);
    const [selectedTerritory, setSelectedTerritory] = useState(null);

    const loadDashboard = async ({ force = false } = {}) => {
        const hasVisibleData = Boolean(data);
        if (hasVisibleData) setRefreshing(true);
        else setLoading(true);
        setError('');
        try {
            setData(await loadPublicDashboard({ force, minLocationCount }));
        } catch (requestError) {
            if (!hasVisibleData) setData(null);
            setError(requestError.message || 'No fue posible cargar el tablero ciudadano.');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        loadDashboard({ force: Boolean(data) });
    }, []);

    const csvRows = useMemo(() => {
        if (!data) return [];
        const metadata = data.metadata || {};
        const source = data.kpis?.fuente || 'SABANA SIEDCO/PONAL';
        const cutoff = metadata.latest_event_date || '';
        const periodStart = metadata.period_start || '';
        const periodEnd = metadata.period_end || '';
        const privacyRule = `Solo datos agregados; barrios publicados con mínimo ${data.map?.min_location_count || 1} casos y ubicación oficial verificada.`;
        const rows = [['conjunto', 'dimension_1', 'dimension_2', 'valor', 'periodo_inicio', 'periodo_fin', 'fecha_corte', 'fuente', 'regla_privacidad']];
        const add = (set, dimension1, dimension2, value) => rows.push([set, dimension1, dimension2, value ?? 0, periodStart, periodEnd, cutoff, source, privacyRule]);

        add('indicadores', 'casos_unicos', '', data.kpis?.total_hechos);
        add('indicadores', 'registros_validados', '', data.kpis?.total_registros);
        add('indicadores', 'homicidios', '', data.kpis?.homicidios);
        add('indicadores', 'tasa_homicidios_por_100000_habitantes', '', data.kpis?.tasa_homicidios);
        add('indicadores', 'variacion_interanual_porcentaje', '', data.kpis?.variation_pct);
        (data.conductas || []).forEach((item) => add('conductas', item.name, '', item.value));
        (data.zones || []).forEach((item) => add('zonas', item.name, '', item.value));
        (data.monthly_trend || []).forEach((item) => add('tendencia_mensual', item.name, '', item.total));
        (data.weekly_trend || []).forEach((item) => add('tendencia_semanal', item.name, '', item.total));
        [data.interannual?.previous, data.interannual?.current].filter(Boolean).forEach((item) => add('comparacion_interanual', item.year, '', item.total));
        (data.territories || []).forEach((item) => add('barrios_visibles', item.name, (item.zones || []).join(' | '), item.total));
        return rows;
    }, [data]);

    const downloadCsv = () => {
        const body = csvRows.map((row) => row.map((cell) => `"${String(cell ?? '').replaceAll('"', '""')}"`).join(';')).join('\n');
        const blob = new Blob([`\uFEFF${body}`], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `sisc_datos_abiertos_agregados_${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6">
                <div className="text-center">
                    <Loader className="w-10 h-10 text-[#281FD0] animate-spin mx-auto mb-4" />
                    <p className="text-sm font-black uppercase tracking-widest text-slate-500">Cargando tablero ciudadano</p>
                </div>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="min-h-screen bg-slate-50 text-slate-900">
                <header className="bg-white border-b border-slate-200">
                    <div className="max-w-[1500px] mx-auto px-4 md:px-6 py-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                            <button onClick={onBack} className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-500 hover:text-[#281FD0] mb-3">
                                <ArrowLeft size={16} /> Portal ciudadano
                            </button>
                            <div className="flex items-center gap-3">
                                <div className="p-3 bg-[#281FD0] text-white"><Globe size={22} /></div>
                                <div>
                                    <h1 className="text-2xl md:text-3xl font-black tracking-tight">Tablero ciudadano SISC Jamundí</h1>
                                    <p className="text-sm text-slate-600 mt-1">Información agregada y anonimizada sobre seguridad y convivencia.</p>
                                </div>
                            </div>
                        </div>
                        <button onClick={() => loadDashboard({ force: true })} className="inline-flex items-center gap-2 border border-slate-300 bg-white px-4 py-3 text-xs font-black uppercase tracking-widest hover:border-[#281FD0] hover:text-[#281FD0]">
                            <RefreshCcw size={16} /> Reintentar
                        </button>
                    </div>
                </header>
                <main className="max-w-3xl mx-auto px-4 py-12">
                    <div className="border-l-4 border-red-600 bg-red-50 p-5 text-red-800">
                        <h2 className="font-black text-lg">No fue posible cargar los datos públicos</h2>
                        <p className="text-sm font-semibold mt-2">{error || 'El servicio de datos no respondio.'}</p>
                    </div>
                </main>
            </div>
        );
    }

    const meta = data.metadata || {};
    const variation = data.kpis?.variation_pct;
    const variationIsUp = variation > 0;
    const bulletin = meta.downloads?.[0];
    const topConductas = (data.conductas || []).slice(0, 6);
    const topTerritory = data.territories?.[0];
    const mainZone = data.zones?.[0];
    const currentYear = data.interannual?.current?.year || meta.year || '';
    const previousYear = data.interannual?.previous?.year || (currentYear ? currentYear - 1 : '');
    const periodText = `${formatDate(meta.period_start)} a ${formatDate(meta.period_end)}`;
    const comparisonText = `${formatDate(meta.comparison_start || data.interannual?.current?.start)} a ${formatDate(meta.comparison_end || data.interannual?.current?.end)}`;
    const coverageText = `${formatDate(meta.first_available_date)} a ${formatDate(meta.latest_event_date)}`;

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <header className="bg-white border-b border-slate-200">
                <div className="max-w-[1500px] mx-auto px-4 md:px-6 py-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <button onClick={onBack} className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-500 hover:text-[#281FD0] mb-3">
                            <ArrowLeft size={16} /> Portal ciudadano
                        </button>
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-[#281FD0] text-white"><Globe size={22} /></div>
                            <div>
                                <h1 className="text-2xl md:text-3xl font-black tracking-tight">Tablero ciudadano SISC Jamundí</h1>
                                <p className="text-sm text-slate-600 mt-1">Información agregada y anonimizada sobre seguridad y convivencia.</p>
                            </div>
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button onClick={() => loadDashboard({ force: true })} disabled={refreshing} className="inline-flex items-center gap-2 border border-slate-300 bg-white px-4 py-3 text-xs font-black uppercase tracking-widest hover:border-[#281FD0] hover:text-[#281FD0] disabled:opacity-60">
                            <RefreshCcw size={16} className={refreshing ? 'animate-spin' : ''} /> {refreshing ? 'Actualizando' : 'Actualizar'}
                        </button>
                        <button onClick={downloadCsv} disabled={!csvRows.length} className="inline-flex items-center gap-2 border border-[#281FD0] text-[#281FD0] px-4 py-3 text-xs font-black uppercase tracking-widest disabled:opacity-40">
                            <Download size={16} /> Datos abiertos CSV
                        </button>
                        {bulletin && (
                            <a href={buildDownloadUrl(bulletin.url)} className="inline-flex items-center gap-2 bg-[#281FD0] text-white px-4 py-3 text-xs font-black uppercase tracking-widest">
                                <FileText size={16} /> Resumen ciudadano PDF
                            </a>
                        )}
                        <button onClick={onLoginClick} className="inline-flex items-center gap-2 bg-slate-900 text-white px-4 py-3 text-xs font-black uppercase tracking-widest">
                            <Lock size={16} /> Institucional
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-[1320px] mx-auto px-4 md:px-6 py-6 space-y-6">
                <section className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
                    <div className="bg-white border border-slate-200 rounded-md shadow-sm overflow-hidden">
                        <div className="h-2 bg-[#FFB600]" />
                        <div className="p-6 md:p-7">
                            <div className="flex flex-wrap items-center gap-2 mb-5">
                                <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-black uppercase tracking-widest text-emerald-700"><CheckCircle2 size={14} /> Datos públicos y protegidos</span>
                                <span className="inline-flex items-center gap-2 rounded-full bg-[#281FD0]/10 px-3 py-1.5 text-xs font-black uppercase tracking-widest text-[#281FD0]"><CalendarClock size={14} /> Corte: {formatDate(meta.latest_event_date)}</span>
                            </div>
                            <h2 className="text-3xl md:text-5xl font-black tracking-tight text-slate-950 leading-tight">Panorama ciudadano de seguridad</h2>
                            <p className="mt-3 max-w-3xl text-base md:text-lg font-semibold leading-7 text-slate-600">Consulta datos agregados del SISC para entender tendencias, conductas, zonas y barrios con información pública. No se publican registros individuales ni direcciones exactas.</p>
                            <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                                <div className="border border-slate-200 rounded-md p-4"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Periodo mostrado</p><p className="mt-1 font-black text-slate-950">{periodText}</p></div>
                                <div className="border border-slate-200 rounded-md p-4"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Cobertura histórica</p><p className="mt-1 font-black text-slate-950">{coverageText}</p></div>
                                <div className="border border-slate-200 rounded-md p-4"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Fuente</p><p className="mt-1 font-black text-slate-950">SABANA SIEDCO/PONAL</p></div>
                                <div className="border border-slate-200 rounded-md p-4"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Última carga</p><p className="mt-1 font-black text-slate-950">{formatDateTime(meta.last_ingestion?.loaded_at)}</p></div>
                            </div>
                        </div>
                    </div>
                    <aside className="bg-slate-950 text-white rounded-md p-6 shadow-sm flex flex-col justify-between gap-5">
                        <div>
                            <p className="text-xs font-black uppercase tracking-widest text-[#FFB600]">Como leer este tablero</p>
                            <div className="mt-5 space-y-4">
                                <div className="flex items-start gap-3"><TrendingUp className="mt-0.5 text-[#FFB600]" size={20} /><p className="text-sm font-semibold leading-6"><span className="font-black">{variationLabel(variation)}</span> frente a {previousYear} en {comparisonText}.</p></div>
                                <div className="flex items-start gap-3"><MapPinned className="mt-0.5 text-[#FFB600]" size={20} /><p className="text-sm font-semibold leading-6">Top barrio visible: <span className="font-black">{topTerritory?.name || 'sin dato'}</span>{topTerritory ? ` (${numberFmt.format(topTerritory.total)} casos)` : ''}.</p></div>
                                <div className="flex items-start gap-3"><Users className="mt-0.5 text-[#FFB600]" size={20} /><p className="text-sm font-semibold leading-6">Zona con mas registros: <span className="font-black">{mainZone?.name || 'sin dato'}</span>{mainZone ? ` (${numberFmt.format(mainZone.value)})` : ''}.</p></div>
                            </div>
                        </div>
                        <div className="rounded-md bg-white/10 p-4 ring-1 ring-white/10">
                            <p className="text-[11px] font-black uppercase tracking-widest text-white/60">Privacidad</p>
                            <p className="mt-2 text-sm font-semibold leading-6 text-white/90">Este panel muestra información territorial agregada; para proteger la privacidad, se ocultan barrios de bajo volumen.</p>
                        </div>
                    </aside>
                </section>

                <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                    <KpiTile icon={BarChart3} label={`Casos únicos ${currentYear}`} value={numberFmt.format(data.kpis?.total_hechos || 0)} helper="Se cuentan solo casos únicos (sin registros repetidos)." />
                    <KpiTile icon={Database} label={`Registros validados ${currentYear}`} value={numberFmt.format(data.kpis?.total_registros || 0)} helper="Filas válidas de la SABANA" tone="slate" />
                    <KpiTile icon={TrendingUp} label="Comparación interanual" value={variationLabel(variation)} helper={`${data.interannual?.current?.year || ''} frente a ${data.interannual?.previous?.year || ''}`} tone={variationIsUp ? 'red' : 'blue'} />
                    <KpiTile icon={ShieldCheck} label={`Homicidios ${currentYear}`} value={numberFmt.format(data.kpis?.homicidios || 0)} helper={`Tasa acumulada al corte: ${data.kpis?.tasa_homicidios || 0} por 100.000 hab.`} tone="red" />
                    <KpiTile icon={Layers} label="Barrios visibles" value={numberFmt.format(data.territories?.length || 0)} helper={`Mínimo ${data.map?.min_location_count || 1} casos para publicar`} tone="amber" />
                </section>

                <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
                    <ChartShell title="Tendencia mensual" subtitle={`Casos únicos por mes de ${currentYear} hasta el corte`}>
                        {data.monthly_trend?.length ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={data.monthly_trend} margin={{ top: 10, right: 20, left: -18, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" /><XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} /><YAxis tick={{ fontSize: 11, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} /><Tooltip content={<CustomTooltip />} /><Area type="monotone" dataKey="total" name="Casos" stroke="#281FD0" fill="#281FD0" fillOpacity={0.16} strokeWidth={3} /></AreaChart></ResponsiveContainer> : <EmptyState />}
                    </ChartShell>
                    <ChartShell title="Comparación interanual" subtitle="Mismo rango calendario frente al año anterior">
                        <ResponsiveContainer width="100%" height="100%"><BarChart data={[data.interannual.previous, data.interannual.current]} margin={{ top: 10, right: 20, left: -18, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" /><XAxis dataKey="year" tick={{ fontSize: 12, fill: '#64748b', fontWeight: 800 }} tickLine={false} axisLine={false} /><YAxis tick={{ fontSize: 11, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} /><Tooltip content={<CustomTooltip />} /><Bar dataKey="total" name="Casos" fill="#281FD0" /></BarChart></ResponsiveContainer>
                        <div className={`mt-3 inline-flex items-center gap-2 text-sm font-black ${variationIsUp ? 'text-red-700' : 'text-emerald-700'}`}>{variationIsUp ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}Variacion: {variationLabel(variation)}</div>
                    </ChartShell>
                </section>

                <section className="grid gap-4 lg:grid-cols-3">
                    <ChartShell title="Conductas" subtitle="Principales conductas agregadas" action={<span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-slate-600">Top {topConductas.length}</span>}>
                        {data.conductas?.length ? (
                            <div className="grid h-full gap-4 md:grid-cols-[0.9fr_1.1fr]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie data={topConductas} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={88} innerRadius={52} paddingAngle={2}>
                                            {topConductas.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}
                                        </Pie>
                                        <Tooltip content={<CustomTooltip />} />
                                    </PieChart>
                                </ResponsiveContainer>
                                <div className="space-y-3 self-center">
                                    {topConductas.map((item, index) => {
                                        const max = Math.max(...topConductas.map((entry) => entry.value || 0), 1);
                                        return (
                                            <div key={item.name}>
                                                <div className="mb-1 flex items-center justify-between gap-3 text-xs font-black uppercase text-slate-600">
                                                    <span className="flex min-w-0 items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} /> <span className="truncate">{item.name}</span></span>
                                                    <span>{numberFmt.format(item.value)}</span>
                                                </div>
                                                <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full" style={{ width: `${(item.value / max) * 100}%`, backgroundColor: COLORS[index % COLORS.length] }} /></div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ) : <EmptyState />}
                    </ChartShell>
                    <ChartShell title="Zona urbana/rural" subtitle="Distribución declarada en la fuente">
                        {data.zones?.length ? <div className="space-y-3">{data.zones.map((zone, index) => { const max = Math.max(...data.zones.map((item) => item.value || 0), 1); return <div key={zone.name}><div className="flex justify-between text-xs font-black uppercase text-slate-600 mb-1"><span>{zone.name}</span><span>{numberFmt.format(zone.value)}</span></div><div className="h-3 bg-slate-100"><div className="h-3" style={{ width: `${(zone.value / max) * 100}%`, backgroundColor: COLORS[index % COLORS.length] }} /></div></div>; })}</div> : <EmptyState />}
                    </ChartShell>
                    <ChartShell title="Tendencia semanal" subtitle={`Evolución semanal de ${currentYear} hasta el corte`}>
                        {data.weekly_trend?.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={data.weekly_trend} margin={{ top: 10, right: 10, left: -24, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" /><XAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} interval="preserveStartEnd" /><YAxis tick={{ fontSize: 10, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} /><Tooltip content={<CustomTooltip />} /><Bar dataKey="total" name="Casos" fill="#FFB600" /></BarChart></ResponsiveContainer> : <EmptyState />}
                    </ChartShell>
                </section>

                                <section className="grid gap-3 xl:grid-cols-2 items-start">
                    {selectedTerritory && <DecisionCard territory={selectedTerritory} />}

                    <details className="border border-slate-200 bg-white rounded-md" open>
                        <summary className="px-4 py-3 text-xs font-black uppercase tracking-widest text-slate-700 flex items-center gap-2">Top barrios</summary>
                        <div className="border-t border-slate-200 p-4">
                            <div className="space-y-2">
                                <div className="flex items-center gap-2"><MapPinned size={18} className="text-[#281FD0]" /><h2 className="text-sm font-black uppercase tracking-tight">Top barrios visibles</h2></div>
                                <div className="divide-y divide-slate-100 border-y border-slate-100">{(data.territories || []).slice(0, 12).map((territory, index) => <div key={territory.name} className="py-2 flex items-center justify-between gap-4"><div className="flex items-center gap-2 min-w-0"><span className="w-6 h-6 bg-slate-100 text-slate-700 text-[10px] font-black flex items-center justify-center shrink-0">{index + 1}</span><span className="font-bold text-slate-800 text-sm truncate">{territory.name}</span></div><span className="font-black text-slate-900 text-sm">{numberFmt.format(territory.total)}</span></div>)}</div>
                            </div>
                        </div>
                    </details>

                    <details className="border border-slate-200 bg-white rounded-md" open>
                        <summary className="px-4 py-3 text-xs font-black uppercase tracking-widest text-slate-700 flex items-center gap-2">Mapa territorial</summary>
                        <div className="border-t border-slate-200">
                            <AggregatedMap points={data.map?.points || []} suppressed={data.map?.suppressed_count || 0} unmapped={data.map?.unmapped_count || 0} minCount={data.map?.min_location_count || 1} zoneFilter={zoneFilter} conductaFilter={conductaFilter} showBubbles={showBubbles} onZoneFilter={setZoneFilter} onConductaFilter={setConductaFilter} onToggleBubbles={setShowBubbles} onSelectTerritory={setSelectedTerritory} />
                        </div>
                    </details>

                    {data.map?.unmapped_names?.length ? (
                        <details className="border border-slate-200 bg-white rounded-md xl:col-span-2" open>
                            <summary className="px-4 py-3 text-xs font-black uppercase tracking-widest text-slate-700 flex items-center gap-2">Calidad cartográfica</summary>
                            <div className="border-t border-slate-200 p-4">
                                <PendingTerritories items={data.map?.unmapped_names || []} />
                            </div>
                        </details>
                    ) : null}
                </section>
                <section className="grid gap-6 lg:grid-cols-2">
                    <div className="bg-white border border-slate-200 p-5"><div className="flex items-center gap-2 mb-3"><Info size={20} className="text-[#281FD0]" /><h2 className="font-black uppercase">Metodología</h2></div><p className="text-sm leading-6 text-slate-700 font-medium">{meta.methodology}</p><p className="text-sm leading-6 text-slate-700 font-medium mt-3">{meta.privacy}</p></div>
                    <div className="bg-white border border-slate-200 p-5"><div className="flex items-center gap-2 mb-3"><CalendarClock size={20} className="text-[#281FD0]" /><h2 className="font-black uppercase">Ultima actualizacion de la base</h2></div><dl className="grid grid-cols-2 gap-px bg-slate-200 border border-slate-200 text-sm"><div className="bg-white p-3"><dt className="text-[10px] font-black uppercase text-slate-500">Archivo</dt><dd className="font-bold break-words">{meta.last_ingestion?.filename || 'No disponible'}</dd></div><div className="bg-white p-3"><dt className="text-[10px] font-black uppercase text-slate-500">Aprobadas</dt><dd className="font-bold">{numberFmt.format(meta.last_ingestion?.approved || 0)}</dd></div><div className="bg-white p-3"><dt className="text-[10px] font-black uppercase text-slate-500">Rechazadas</dt><dd className="font-bold">{numberFmt.format(meta.last_ingestion?.rejected || 0)}</dd></div><div className="bg-white p-3"><dt className="text-[10px] font-black uppercase text-slate-500">Sin cambios</dt><dd className="font-bold">{numberFmt.format(meta.last_ingestion?.duplicates || 0)}</dd></div></dl></div>
                </section>
            </main>

            <footer className="border-t border-slate-200 bg-white px-4 py-8 text-center"><button onClick={onBack} className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-500 hover:text-[#281FD0]"><Home size={15} /> Volver al inicio del portal</button><p className="text-[11px] text-slate-400 font-bold uppercase tracking-widest mt-4">SISC Jamundí - Publicación ciudadana agregada</p></footer>
        </div>
    );
};

export default PublicDashboard;




















