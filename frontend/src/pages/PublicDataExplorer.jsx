import React, { useEffect, useMemo, useState } from 'react';
import {
    ArrowLeft, Download, FileJson2, FileSpreadsheet, FileText, Info,
    RefreshCw, Share2, ShieldCheck,
} from 'lucide-react';
import {
    Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
    Tooltip, XAxis, YAxis,
} from 'recharts';
import { GeoJSON, MapContainer, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import CitizenFilterBar from '../components/public/CitizenFilterBar';
import PublicPortalHeader from '../components/public/PublicPortalHeader';
import { API_BASE_URL } from '../utils/apiConfig';
import {
    buildCitizenInsights, DEFAULT_PUBLIC_FILTERS, filtersToSearchParams,
    formatNumber, formatVariation, parsePublicFilters, variationTone,
} from '../utils/citizenInsights';
import { getCachedPublicDashboard, loadPublicDashboard } from '../utils/publicDashboardCache';
import { downloadCsvFile, downloadJsonFile, downloadXlsxFile } from '../utils/publicDataDownloads';

const PUBLIC_DATA_DICTIONARY = [
    { field: 'dataset', description: 'Grupo de información publicado.' },
    { field: 'category', description: 'Nombre ciudadano del indicador, conducta, zona o territorio.' },
    { field: 'current_value', description: 'Valor agregado del periodo seleccionado.' },
    { field: 'comparison_value', description: 'Valor agregado del periodo usado como comparación.' },
    { field: 'period_start', description: 'Fecha inicial del periodo consultado, formato AAAA-MM-DD.' },
    { field: 'period_end', description: 'Fecha final del periodo consultado, formato AAAA-MM-DD.' },
    { field: 'cutoff_date', description: 'Fecha del último registro disponible en la fuente.' },
    { field: 'source', description: 'Fuente institucional de la información.' },
];

const buildOpenDataRows = (data) => {
    const meta = data?.metadata || {};
    const rows = [];
    const push = (dataset, category, currentValue, comparisonValue = '') => rows.push({
        dataset,
        category,
        current_value: currentValue ?? '',
        comparison_value: comparisonValue ?? '',
        period_start: meta.period_start || '',
        period_end: meta.period_end || '',
        cutoff_date: meta.latest_event_date || '',
        source: meta.source || '',
    });

    push('indicadores', 'Casos agregados', data?.kpis?.total_hechos, data?.kpis?.previous_total);
    push('indicadores', 'Homicidios', data?.kpis?.homicidios);
    (data?.conductas || []).forEach((item) => push('conductas', item.name, item.value, item.previous_value));
    (data?.zones || []).forEach((item) => push('zonas', item.name, item.value, item.previous_value));
    (data?.territories || []).forEach((item) => push('territorios', item.name, item.total, item.previous_value));
    return rows;
};

const formatDate = (value) => {
    if (!value) return 'No disponible';
    return new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })
        .format(new Date(`${value}T12:00:00`));
};

const downloadUrl = (url) => {
    if (!url) return '#';
    if (url.startsWith('http')) return url;
    return `${API_BASE_URL.replace(/\/api\/?$/, '')}${url}`;
};

const chartTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return <div className="border border-slate-200 bg-white p-3 shadow-lg"><p className="text-xs font-black text-slate-900">{label}</p>{payload.map((entry) => <p key={entry.dataKey} className="mt-1 text-xs font-bold" style={{ color: entry.color }}>{entry.name}: {formatNumber(entry.value)}</p>)}</div>;
};

const ChartPanel = ({ title, subtitle, children }) => (
    <section className="min-h-[360px] border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-black text-slate-950">{title}</h2>
        <p className="mt-1 text-sm font-semibold text-slate-500">{subtitle}</p>
        <div className="mt-5 h-[270px]">{children}</div>
    </section>
);

const LoadingPage = () => (
    <div className="min-h-[70vh] bg-[#F2F4F7] px-4 py-14" role="status">
        <div className="mx-auto max-w-[1320px]"><div className="h-36 animate-pulse bg-white" /><div className="mt-4 grid gap-3 md:grid-cols-4">{[0, 1, 2, 3].map((item) => <div key={item} className="h-36 animate-pulse bg-white" />)}</div></div>
    </div>
);

const Metric = ({ label, value, helper, tone = 'blue' }) => {
    const color = tone === 'red' ? 'text-red-700' : tone === 'green' ? 'text-emerald-700' : 'text-[#281FD0]';
    return <article className="border border-slate-200 bg-white p-5 shadow-sm"><p className="text-[11px] font-black uppercase tracking-wide text-slate-500">{label}</p><p className={`mt-4 text-3xl font-black ${color}`}>{value}</p><p className="mt-2 text-xs font-semibold leading-5 text-slate-600">{helper}</p></article>;
};

const AggregatedMap = ({ map, onSelect }) => {
    const points = map?.points || [];
    const max = Math.max(1, ...points.map((point) => Number(point.total || 0)));
    if (!points.length) return <div className="flex h-[420px] items-center justify-center bg-slate-100 px-6 text-center text-sm font-bold text-slate-500">No hay territorios con polígono oficial para los filtros seleccionados.</div>;
    return (
        <div className="h-[420px] md:h-[520px]">
            <MapContainer center={[3.2606, -76.5364]} zoom={12} preferCanvas style={{ height: '100%', width: '100%' }}>
                <TileLayer attribution="&copy; OpenStreetMap contributors &copy; CARTO" url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" maxZoom={19} />
                {points.map((point) => {
                    const ratio = Number(point.total || 0) / max;
                    return <GeoJSON key={point.name} data={point.geometry} eventHandlers={{ click: () => onSelect?.(point.name) }} style={{ color: '#281FD0', fillColor: ratio > 0.66 ? '#FFB600' : '#384CF5', fillOpacity: 0.25 + ratio * 0.45, weight: 2 }}><Popup><div className="min-w-44"><strong>{point.name}</strong><p className="mt-1">{formatNumber(point.total)} casos agregados</p><p className="mt-2 text-xs text-slate-600">{point.conductas?.slice(0, 3).join(', ')}</p></div></Popup></GeoJSON>;
                })}
            </MapContainer>
        </div>
    );
};

const PublicDataExplorer = ({ onBack, onNavigate, onLoginClick }) => {
    const initialFilters = useMemo(() => parsePublicFilters(window.location.search), []);
    const initialOptions = { ...initialFilters, includeMap: true, minLocationCount: 3 };
    const [draftFilters, setDraftFilters] = useState(initialFilters);
    const [appliedFilters, setAppliedFilters] = useState(initialFilters);
    const [data, setData] = useState(() => getCachedPublicDashboard(initialOptions));
    const [loading, setLoading] = useState(() => !getCachedPublicDashboard(initialOptions));
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');
    const [shareStatus, setShareStatus] = useState('');
    const [exportingXlsx, setExportingXlsx] = useState(false);

    const fetchData = async (filters, force = false) => {
        if (data) setRefreshing(true);
        else setLoading(true);
        setError('');
        try {
            setData(await loadPublicDashboard({ ...filters, includeMap: true, minLocationCount: 3, force }));
        } catch (requestError) {
            setError(requestError.message || 'No fue posible consultar el tablero ciudadano.');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchData(appliedFilters, Boolean(data));
        // appliedFilters changes only on form submission.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [appliedFilters]);

    useEffect(() => {
        if (!loading && window.location.hash) {
            window.setTimeout(() => document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: 'start' }), 0);
        }
    }, [loading]);

    useEffect(() => {
        const restoreFilters = () => {
            const restored = parsePublicFilters(window.location.search);
            setDraftFilters(restored);
            setAppliedFilters(restored);
        };
        window.addEventListener('popstate', restoreFilters);
        return () => window.removeEventListener('popstate', restoreFilters);
    }, []);

    const syncUrl = (filters) => {
        const params = filtersToSearchParams(filters, 'transparency');
        window.history.pushState({ page: 'transparency' }, '', `${window.location.pathname}?${params}`);
    };

    const applyFilters = () => {
        setAppliedFilters({ ...draftFilters });
        syncUrl(draftFilters);
    };

    const clearFilters = () => {
        const cleared = { ...DEFAULT_PUBLIC_FILTERS };
        setDraftFilters(cleared);
        setAppliedFilters(cleared);
        syncUrl(cleared);
    };

    const trendData = useMemo(() => {
        const current = data?.monthly_trend || [];
        const previous = data?.comparison_monthly_trend || [];
        return current.map((item, index) => ({ label: item.name.slice(5), actual: item.total, comparacion: previous[index]?.total ?? null }));
    }, [data]);
    const conductData = useMemo(() => (data?.conductas || []).slice(0, 7).map((item) => ({ name: item.name, actual: item.value, comparacion: item.previous_value })), [data]);
    const insights = useMemo(() => buildCitizenInsights(data, 3), [data]);
    const openDataRows = useMemo(() => buildOpenDataRows(data), [data]);

    const downloadCsv = () => {
        if (!data) return;
        const headers = Object.keys(openDataRows[0] || {});
        downloadCsvFile(
            `sisc-jamundi-datos-agregados-${data.metadata?.period_end || 'corte'}.csv`,
            headers,
            openDataRows.map((row) => headers.map((header) => row[header]))
        );
    };

    const buildOpenDataPackage = () => ({
        metadata: data?.metadata || {},
        selected_filters: data?.filters?.selected || appliedFilters,
        privacy: {
            minimum_territory_count: data?.map?.min_location_count || 3,
            note: data?.metadata?.privacy || '',
        },
        data_dictionary: PUBLIC_DATA_DICTIONARY,
        records: openDataRows,
    });

    const downloadJson = () => {
        if (!data) return;
        downloadJsonFile(
            `sisc-jamundi-datos-agregados-${data.metadata?.period_end || 'corte'}.json`,
            buildOpenDataPackage()
        );
    };

    const downloadXlsx = async () => {
        if (!data || exportingXlsx) return;
        setExportingXlsx(true);
        try {
            await downloadXlsxFile(
                `sisc-jamundi-datos-agregados-${data.metadata?.period_end || 'corte'}.xlsx`,
                [
                    { name: 'Datos agregados', rows: openDataRows },
                    { name: 'Diccionario', rows: PUBLIC_DATA_DICTIONARY },
                    { name: 'Metadatos', rows: Object.entries(data.metadata || {}).filter(([, value]) => typeof value !== 'object').map(([field, value]) => ({ field, value })) },
                ]
            );
            setShareStatus('Archivo XLSX generado.');
        } catch {
            setShareStatus('No fue posible generar el archivo XLSX.');
        } finally {
            setExportingXlsx(false);
        }
    };

    const shareView = async () => {
        const url = window.location.href;
        try {
            if (navigator.share) await navigator.share({ title: 'Datos públicos SISC Jamundí', url });
            else await navigator.clipboard.writeText(url);
            setShareStatus(navigator.share ? 'Consulta compartida.' : 'Enlace copiado.');
        } catch (shareError) {
            if (shareError.name !== 'AbortError') setShareStatus('No fue posible compartir la consulta.');
        }
    };

    if (loading && !data) return <><PublicPortalHeader currentPage="transparency" onNavigate={onNavigate} onLoginClick={onLoginClick} /><LoadingPage /></>;

    if (!data) return (
        <div className="min-h-screen bg-[#F2F4F7]"><PublicPortalHeader currentPage="transparency" onNavigate={onNavigate} onLoginClick={onLoginClick} /><main className="mx-auto max-w-3xl px-4 py-14"><button onClick={onBack} className="mb-6 inline-flex min-h-11 items-center gap-2 font-black text-[#281FD0]"><ArrowLeft size={18} /> Volver al portal</button><div className="border-l-4 border-red-600 bg-red-50 p-6"><h1 className="text-xl font-black text-red-900">No fue posible cargar los datos públicos</h1><p className="mt-2 text-sm font-semibold text-red-800">{error || 'El servicio no respondió.'}</p><button onClick={() => fetchData(appliedFilters, true)} className="mt-5 inline-flex min-h-11 items-center gap-2 border border-red-700 px-4 font-black text-red-800"><RefreshCw size={17} /> Reintentar</button></div></main></div>
    );

    const meta = data.metadata || {};
    const variation = data.kpis?.variation_pct;
    const tone = variationTone(variation);
    const bulletin = meta.downloads?.[0];
    const filterOptions = data.filters?.available || {};

    return (
        <div className="public-portal min-h-screen bg-[#F2F4F7] text-slate-900">
            <a href="#explorer-main" className="skip-link">Saltar al contenido principal</a>
            <PublicPortalHeader currentPage="transparency" onNavigate={onNavigate} onLoginClick={onLoginClick} />
            <main id="explorer-main" className="mx-auto max-w-[1320px] space-y-7 px-4 py-7 md:px-6">
                <header className="border-t-4 border-[#FFE000] bg-[#281FD0] p-6 text-white md:p-8">
                    <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                        <div><button onClick={onBack} className="mb-4 inline-flex min-h-10 items-center gap-2 text-sm font-bold text-white/75 hover:text-white"><ArrowLeft size={17} /> Portal ciudadano</button><p className="text-xs font-black uppercase tracking-[0.16em] text-[#FFE000]">Explorador de datos públicos</p><h1 className="mt-2 text-3xl font-black tracking-normal md:text-5xl">Seguridad y convivencia</h1><p className="mt-3 max-w-3xl text-base font-semibold leading-7 text-white/80">Tendencias, comparaciones y distribución territorial con información agregada.</p></div>
                        <div className="grid gap-2 text-sm font-bold text-white/80 sm:grid-cols-2 lg:text-right"><p><span className="block text-[10px] uppercase tracking-wide text-[#FFE000]">Periodo</span>{formatDate(meta.period_start)} a {formatDate(meta.period_end)}</p><p><span className="block text-[10px] uppercase tracking-wide text-[#FFE000]">Fecha de corte</span>{formatDate(meta.latest_event_date)}</p></div>
                    </div>
                </header>

                <CitizenFilterBar filters={draftFilters} options={filterOptions} onChange={setDraftFilters} onApply={applyFilters} onClear={clearFilters} busy={refreshing} compact />

                <div className="flex flex-wrap items-center gap-2">
                    <button onClick={() => fetchData(appliedFilters, true)} disabled={refreshing} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 bg-white px-4 text-sm font-black text-slate-700 disabled:opacity-60"><RefreshCw size={17} className={refreshing ? 'animate-spin' : ''} /> Actualizar</button>
                    <button onClick={shareView} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 bg-white px-4 text-sm font-black text-slate-700"><Share2 size={17} /> Compartir vista</button>
                    <button onClick={downloadCsv} className="inline-flex min-h-11 items-center gap-2 border border-[#281FD0] bg-white px-4 text-sm font-black text-[#281FD0]"><Download size={17} /> Descargar CSV</button>
                    <button onClick={downloadJson} className="inline-flex min-h-11 items-center gap-2 border border-[#281FD0] bg-white px-4 text-sm font-black text-[#281FD0]"><FileJson2 size={17} /> JSON</button>
                    <button onClick={downloadXlsx} disabled={exportingXlsx} className="inline-flex min-h-11 items-center gap-2 border border-[#281FD0] bg-white px-4 text-sm font-black text-[#281FD0] disabled:opacity-60"><FileSpreadsheet size={17} /> {exportingXlsx ? 'Generando' : 'XLSX'}</button>
                    {bulletin && <a href={downloadUrl(bulletin.url)} className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white"><FileText size={17} /> Boletín PDF</a>}
                    {shareStatus && <span className="text-xs font-bold text-slate-600" role="status">{shareStatus}</span>}
                </div>

                {error && <div className="border-l-4 border-amber-500 bg-amber-50 p-4 text-sm font-bold text-amber-900" role="alert">Se conservan los últimos datos disponibles. {error}</div>}

                <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Indicadores principales">
                    <Metric label="Casos agregados" value={formatNumber(data.kpis?.total_hechos)} helper="Casos únicos en el periodo seleccionado." />
                    <Metric label="Cambio comparado" value={formatVariation(variation)} helper={meta.comparison_label || 'Sin comparación'} tone={tone === 'up' ? 'red' : tone === 'down' ? 'green' : 'blue'} />
                    <Metric label="Homicidios" value={formatNumber(data.kpis?.homicidios)} helper={`${data.kpis?.tasa_homicidios || 0} por cada 100.000 habitantes.`} tone="red" />
                    <Metric label="Territorios visibles" value={formatNumber(data.territories?.length)} helper={`Solo volúmenes de ${data.map?.min_location_count || 3} casos o más.`} />
                </section>

                <section className="grid gap-3 md:grid-cols-3" aria-labelledby="quick-reading-title">
                    <h2 id="quick-reading-title" className="sr-only">Lectura rápida del periodo</h2>
                    {insights.map((item) => <article key={item.id} className="border border-slate-200 bg-white p-5"><p className="text-[10px] font-black uppercase tracking-wide text-[#281FD0]">{item.eyebrow}</p><h3 className="mt-2 text-lg font-black text-slate-950">{item.title}</h3><p className="mt-2 text-sm font-semibold leading-6 text-slate-600">{item.summary}</p></article>)}
                </section>

                <section className="grid gap-5 lg:grid-cols-2">
                    <ChartPanel title="Evolución mensual" subtitle={`${meta.comparison_label || 'Periodo consultado'}; los meses se alinean por posición dentro de cada rango.`}>
                        {trendData.length ? <><ResponsiveContainer width="100%" height="100%"><LineChart data={trendData} margin={{ top: 5, right: 15, left: -16, bottom: 5 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#dbe2ea" /><XAxis dataKey="label" tick={{ fontSize: 11, fill: '#475569' }} /><YAxis tick={{ fontSize: 11, fill: '#475569' }} /><Tooltip content={chartTooltip} /><Legend /><Line type="monotone" dataKey="actual" name="Periodo actual" stroke="#281FD0" strokeWidth={3} dot={{ r: 3 }} /><Line type="monotone" dataKey="comparacion" name="Comparación" stroke="#64748b" strokeWidth={2} strokeDasharray="5 4" dot={false} /></LineChart></ResponsiveContainer><table className="sr-only"><caption>Evolución mensual en valores</caption><tbody>{trendData.map((item) => <tr key={item.label}><th>{item.label}</th><td>{item.actual}</td><td>{item.comparacion}</td></tr>)}</tbody></table></> : <p className="flex h-full items-center justify-center text-sm font-bold text-slate-500">Sin tendencia para el filtro seleccionado.</p>}
                    </ChartPanel>
                    <ChartPanel title="Conductas más registradas" subtitle="Comparación del mismo conjunto de categorías ciudadanas.">
                        {conductData.length ? <><ResponsiveContainer width="100%" height="100%"><BarChart data={conductData} layout="vertical" margin={{ top: 0, right: 15, left: 24, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#dbe2ea" /><XAxis type="number" tick={{ fontSize: 10, fill: '#475569' }} /><YAxis type="category" dataKey="name" width={112} tick={{ fontSize: 10, fill: '#334155', fontWeight: 700 }} /><Tooltip content={chartTooltip} /><Legend /><Bar dataKey="actual" name="Periodo actual" fill="#281FD0" /><Bar dataKey="comparacion" name="Comparación" fill="#FFB600" /></BarChart></ResponsiveContainer><table className="sr-only"><caption>Conductas en valores</caption><tbody>{conductData.map((item) => <tr key={item.name}><th>{item.name}</th><td>{item.actual}</td><td>{item.comparacion}</td></tr>)}</tbody></table></> : <p className="flex h-full items-center justify-center text-sm font-bold text-slate-500">Sin conductas para el filtro seleccionado.</p>}
                    </ChartPanel>
                </section>

                <section id="mapa" className="scroll-mt-24 border border-slate-200 bg-white" aria-labelledby="map-title">
                    <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs font-black uppercase tracking-wide text-[#281FD0]">Mapa agregado</p><h2 id="map-title" className="mt-1 text-2xl font-black text-slate-950">Distribución por territorio oficial</h2><p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-600">Los colores representan volumen agregado. No se muestran hechos puntuales, direcciones ni ubicaciones personales.</p></div><span className="text-xs font-bold text-slate-500">{formatNumber(data.map?.points?.length)} territorios con geometría verificada</span></div>
                    <AggregatedMap map={data.map} onSelect={(name) => setDraftFilters((current) => ({ ...current, territorio: name }))} />
                    <div className="grid gap-3 border-t border-slate-200 bg-slate-50 p-4 text-xs font-semibold leading-5 text-slate-600 md:grid-cols-3"><p><strong className="text-slate-900">Privacidad:</strong> mínimo {data.map?.min_location_count || 3} casos por territorio.</p><p><strong className="text-slate-900">Omitidos por baja frecuencia:</strong> {formatNumber(data.map?.suppressed_count)} registros.</p><p><strong className="text-slate-900">Valores administrativos excluidos:</strong> {formatNumber(data.map?.excluded_non_territorial_count)} registros.</p></div>
                </section>

                <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
                    <div className="border border-slate-200 bg-white p-5"><h2 className="text-xl font-black text-slate-950">Territorios con mayor volumen agregado</h2><div className="mt-4 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead className="bg-slate-100 text-xs uppercase text-slate-600"><tr><th className="p-3">Territorio</th><th className="p-3 text-right">Actual</th><th className="p-3 text-right">Comparación</th><th className="p-3 text-right">Cambio</th></tr></thead><tbody className="divide-y divide-slate-200">{(data.territories || []).slice(0, 12).map((item) => <tr key={item.name}><th className="p-3 font-black text-slate-800">{item.name}</th><td className="p-3 text-right font-bold">{formatNumber(item.total)}</td><td className="p-3 text-right text-slate-600">{formatNumber(item.previous_value)}</td><td className="p-3 text-right font-bold">{formatVariation(item.variation_pct)}</td></tr>)}</tbody></table></div></div>
                    <aside className="space-y-4"><div className="border border-slate-200 bg-white p-5"><div className="flex items-center gap-2"><ShieldCheck className="text-[#281FD0]" size={20} /><h2 className="font-black text-slate-950">Protección de datos</h2></div><p className="mt-3 text-sm font-semibold leading-6 text-slate-600">{meta.privacy}</p></div><div className="border border-slate-200 bg-white p-5"><div className="flex items-center gap-2"><Info className="text-[#281FD0]" size={20} /><h2 className="font-black text-slate-950">Fuente y método</h2></div><p className="mt-3 text-sm font-semibold leading-6 text-slate-600">{meta.methodology}</p><button onClick={() => onNavigate?.('transparency-info')} className="mt-4 inline-flex min-h-10 items-center gap-2 font-black text-[#281FD0]">Ver metodología completa <ArrowLeft className="rotate-180" size={16} /></button></div></aside>
                </section>
            </main>
            <footer className="mt-10 border-t-4 border-[#FFE000] bg-slate-950 px-4 py-8 text-center text-sm font-bold text-white/65">SISC Jamundí · Publicación ciudadana agregada · Fuente y corte visibles en cada consulta</footer>
        </div>
    );
};

export default PublicDataExplorer;
