import React, { useEffect, useMemo, useState } from 'react';
import {
    ArrowDownRight,
    ArrowLeft,
    ArrowUpRight,
    BarChart3,
    CalendarClock,
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
    TrendingUp
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
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { API_BASE_URL } from '../utils/apiConfig';

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

const KpiTile = ({ icon: Icon, label, value, helper, tone = 'blue' }) => {
    const toneClasses = {
        blue: 'bg-[#281FD0]/10 text-[#281FD0]',
        amber: 'bg-amber-100 text-amber-700',
        slate: 'bg-slate-100 text-slate-700',
        red: 'bg-red-100 text-red-700',
    };
    return (
        <div className="bg-white border border-slate-200 p-5 min-h-[148px] flex flex-col justify-between">
            <div className="flex items-start justify-between gap-3">
                <p className="text-[11px] font-black uppercase tracking-[0.12em] text-slate-500 leading-snug">{label}</p>
                <span className={`p-2.5 ${toneClasses[tone] || toneClasses.blue}`}><Icon size={20} /></span>
            </div>
            <div>
                <p className="text-3xl font-black text-slate-900 tracking-tight">{value}</p>
                <p className="text-xs font-semibold text-slate-500 mt-1">{helper}</p>
            </div>
        </div>
    );
};

const ChartShell = ({ title, subtitle, children }) => (
    <section className="bg-white border border-slate-200 p-5 min-h-[360px] flex flex-col">
        <div className="mb-4">
            <h2 className="text-base font-black text-slate-900 uppercase tracking-tight">{title}</h2>
            {subtitle && <p className="text-xs text-slate-500 mt-1 font-medium">{subtitle}</p>}
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

const AggregatedMap = ({ points = [], suppressed = 0, minCount = 3 }) => {
    const maxTotal = Math.max(1, ...points.map((point) => point.total || 0));
    return (
        <div className="h-[470px] border border-slate-200 bg-white">
            <div className="h-full relative">
                <MapContainer center={[3.2606, -76.5364]} zoom={12} zoomControl={false} preferCanvas style={{ height: '100%', width: '100%' }}>
                    <TileLayer attribution='&copy; CARTO' url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" />
                    {points.map((point) => {
                        const radius = 8 + ((point.total || 0) / maxTotal) * 26;
                        return (
                            <CircleMarker
                                key={point.name}
                                center={[point.lat, point.lng]}
                                radius={radius}
                                pathOptions={{ color: '#281FD0', fillColor: '#FFB600', fillOpacity: 0.45, weight: 2 }}
                            >
                                <Popup>
                                    <div className="text-sm">
                                        <p className="font-black text-slate-900">{point.name}</p>
                                        <p className="text-slate-600">{numberFmt.format(point.total)} hechos agregados</p>
                                        <p className="text-[11px] text-slate-500 mt-2">Centroide territorial aproximado.</p>
                                    </div>
                                </Popup>
                            </CircleMarker>
                        );
                    })}
                </MapContainer>
                <div className="absolute left-4 bottom-4 z-[1000] bg-white/95 border border-slate-200 p-3 max-w-xs shadow-sm">
                    <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Mapa agregado</p>
                    <p className="text-xs text-slate-700 mt-1">Centroides por barrio, vereda o corregimiento. Se ocultan territorios con menos de {minCount} hechos.</p>
                    {suppressed > 0 && <p className="text-xs font-bold text-amber-700 mt-2">{numberFmt.format(suppressed)} hechos en territorios de baja frecuencia fueron suprimidos.</p>}
                </div>
            </div>
        </div>
    );
};

const PublicDashboard = ({ onLoginClick, onBack }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const loadDashboard = async () => {
        setLoading(true);
        setError('');
        try {
            const response = await fetch(`${API_BASE_URL}/analitica/public/dashboard`, { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error(`Servicio no disponible (${response.status})`);
            setData(await response.json());
        } catch (requestError) {
            setData(null);
            setError(requestError.message || 'No fue posible cargar el tablero ciudadano.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadDashboard(); }, []);

    const csvRows = useMemo(() => {
        if (!data) return [];
        return [
            ['Indicador', 'Valor'],
            ['Hechos unicos', data.kpis.total_hechos],
            ['Registros validados', data.kpis.total_registros],
            ['Homicidios', data.kpis.homicidios],
            ['Tasa de homicidios por 100.000 habitantes', data.kpis.tasa_homicidios],
            ['Variacion interanual total', variationLabel(data.kpis.variation_pct)],
        ];
    }, [data]);

    const downloadCsv = () => {
        const body = csvRows.map((row) => row.map((cell) => `"${String(cell ?? '').replaceAll('"', '""')}"`).join(';')).join('\n');
        const blob = new Blob([`\uFEFF${body}`], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `sisc_dashboard_ciudadano_${new Date().toISOString().slice(0, 10)}.csv`;
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
                    <div className="max-w-7xl mx-auto px-4 md:px-6 py-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                            <button onClick={onBack} className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-500 hover:text-[#281FD0] mb-3">
                                <ArrowLeft size={16} /> Portal ciudadano
                            </button>
                            <div className="flex items-center gap-3">
                                <div className="p-3 bg-[#281FD0] text-white"><Globe size={22} /></div>
                                <div>
                                    <h1 className="text-2xl md:text-3xl font-black tracking-tight">Dashboard ciudadano SISC Jamundi</h1>
                                    <p className="text-sm text-slate-600 mt-1">Informacion agregada y anonimizada sobre seguridad y convivencia.</p>
                                </div>
                            </div>
                        </div>
                        <button onClick={loadDashboard} className="inline-flex items-center gap-2 border border-slate-300 bg-white px-4 py-3 text-xs font-black uppercase tracking-widest hover:border-[#281FD0] hover:text-[#281FD0]">
                            <RefreshCcw size={16} /> Reintentar
                        </button>
                    </div>
                </header>
                <main className="max-w-3xl mx-auto px-4 py-12">
                    <div className="border-l-4 border-red-600 bg-red-50 p-5 text-red-800">
                        <h2 className="font-black text-lg">No fue posible cargar los datos publicos</h2>
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

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <header className="bg-white border-b border-slate-200">
                <div className="max-w-7xl mx-auto px-4 md:px-6 py-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <button onClick={onBack} className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-500 hover:text-[#281FD0] mb-3">
                            <ArrowLeft size={16} /> Portal ciudadano
                        </button>
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-[#281FD0] text-white"><Globe size={22} /></div>
                            <div>
                                <h1 className="text-2xl md:text-3xl font-black tracking-tight">Dashboard ciudadano SISC Jamundi</h1>
                                <p className="text-sm text-slate-600 mt-1">Informacion agregada y anonimizada sobre seguridad y convivencia.</p>
                            </div>
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button onClick={loadDashboard} className="inline-flex items-center gap-2 border border-slate-300 bg-white px-4 py-3 text-xs font-black uppercase tracking-widest hover:border-[#281FD0] hover:text-[#281FD0]">
                            <RefreshCcw size={16} /> Actualizar
                        </button>
                        <button onClick={downloadCsv} disabled={!csvRows.length} className="inline-flex items-center gap-2 border border-[#281FD0] text-[#281FD0] px-4 py-3 text-xs font-black uppercase tracking-widest disabled:opacity-40">
                            <Download size={16} /> CSV
                        </button>
                        {bulletin && (
                            <a href={buildDownloadUrl(bulletin.url)} className="inline-flex items-center gap-2 bg-[#281FD0] text-white px-4 py-3 text-xs font-black uppercase tracking-widest">
                                <FileText size={16} /> Boletin PDF
                            </a>
                        )}
                        <button onClick={onLoginClick} className="inline-flex items-center gap-2 bg-slate-900 text-white px-4 py-3 text-xs font-black uppercase tracking-widest">
                            <Lock size={16} /> Institucional
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 md:px-6 py-6 space-y-6">
                <section className="grid gap-px bg-slate-200 border border-slate-200 md:grid-cols-4">
                    <div className="bg-white p-4"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Periodo publicado</p><p className="font-black text-slate-900 mt-1">{formatDate(meta.period_start)} a {formatDate(meta.period_end)}</p></div>
                    <div className="bg-white p-4"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Fecha de corte</p><p className="font-black text-slate-900 mt-1">{formatDate(meta.latest_event_date)}</p></div>
                    <div className="bg-white p-4"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Fuente</p><p className="font-black text-slate-900 mt-1">{meta.source || 'SABANA oficial'}</p></div>
                    <div className="bg-white p-4"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Ultima carga</p><p className="font-black text-slate-900 mt-1">{formatDateTime(meta.last_ingestion?.loaded_at)}</p></div>
                </section>

                <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                    <KpiTile icon={BarChart3} label="Hechos unicos" value={numberFmt.format(data.kpis?.total_hechos || 0)} helper="Conteo deduplicado por hecho" />
                    <KpiTile icon={Database} label="Registros validados" value={numberFmt.format(data.kpis?.total_registros || 0)} helper="Filas validas de la sabana" tone="slate" />
                    <KpiTile icon={TrendingUp} label="Comparacion interanual" value={variationLabel(variation)} helper={`${data.interannual?.current?.year || ''} frente a ${data.interannual?.previous?.year || ''}`} tone={variationIsUp ? 'red' : 'blue'} />
                    <KpiTile icon={ShieldCheck} label="Homicidios" value={numberFmt.format(data.kpis?.homicidios || 0)} helper={`${data.kpis?.tasa_homicidios || 0} por 100.000 hab.`} tone="red" />
                    <KpiTile icon={Layers} label="Territorios visibles" value={numberFmt.format(data.territories?.length || 0)} helper={`Minimo ${data.map?.min_location_count || 3} hechos para publicar`} tone="amber" />
                </section>

                <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
                    <ChartShell title="Tendencia mensual" subtitle="Hechos unicos por mes dentro del periodo publicado">
                        {data.monthly_trend?.length ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={data.monthly_trend} margin={{ top: 10, right: 20, left: -18, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" /><XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} /><YAxis tick={{ fontSize: 11, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} /><Tooltip content={<CustomTooltip />} /><Area type="monotone" dataKey="total" name="Hechos" stroke="#281FD0" fill="#281FD0" fillOpacity={0.16} strokeWidth={3} /></AreaChart></ResponsiveContainer> : <EmptyState />}
                    </ChartShell>
                    <ChartShell title="Comparacion interanual" subtitle="Mismo rango calendario frente al ano anterior">
                        <ResponsiveContainer width="100%" height="100%"><BarChart data={[data.interannual.previous, data.interannual.current]} margin={{ top: 10, right: 20, left: -18, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" /><XAxis dataKey="year" tick={{ fontSize: 12, fill: '#64748b', fontWeight: 800 }} tickLine={false} axisLine={false} /><YAxis tick={{ fontSize: 11, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} /><Tooltip content={<CustomTooltip />} /><Bar dataKey="total" name="Hechos" fill="#281FD0" /></BarChart></ResponsiveContainer>
                        <div className={`mt-3 inline-flex items-center gap-2 text-sm font-black ${variationIsUp ? 'text-red-700' : 'text-emerald-700'}`}>{variationIsUp ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}Variacion: {variationLabel(variation)}</div>
                    </ChartShell>
                </section>

                <section className="grid gap-6 lg:grid-cols-3">
                    <ChartShell title="Conductas" subtitle="Principales conductas agregadas">
                        {data.conductas?.length ? <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data.conductas} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={92} innerRadius={54} paddingAngle={2}>{data.conductas.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}</Pie><Tooltip content={<CustomTooltip />} /></PieChart></ResponsiveContainer> : <EmptyState />}
                    </ChartShell>
                    <ChartShell title="Zona urbana/rural" subtitle="Distribucion declarada en la fuente">
                        {data.zones?.length ? <div className="space-y-3">{data.zones.map((zone, index) => { const max = Math.max(...data.zones.map((item) => item.value || 0), 1); return <div key={zone.name}><div className="flex justify-between text-xs font-black uppercase text-slate-600 mb-1"><span>{zone.name}</span><span>{numberFmt.format(zone.value)}</span></div><div className="h-3 bg-slate-100"><div className="h-3" style={{ width: `${(zone.value / max) * 100}%`, backgroundColor: COLORS[index % COLORS.length] }} /></div></div>; })}</div> : <EmptyState />}
                    </ChartShell>
                    <ChartShell title="Tendencia semanal" subtitle="Lectura operativa por semana del ano">
                        {data.weekly_trend?.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={data.weekly_trend} margin={{ top: 10, right: 10, left: -24, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" /><XAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} interval="preserveStartEnd" /><YAxis tick={{ fontSize: 10, fill: '#64748b', fontWeight: 700 }} tickLine={false} axisLine={false} /><Tooltip content={<CustomTooltip />} /><Bar dataKey="total" name="Hechos" fill="#FFB600" /></BarChart></ResponsiveContainer> : <EmptyState />}
                    </ChartShell>
                </section>

                <section className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
                    <div className="bg-white border border-slate-200 p-5"><div className="flex items-center gap-2 mb-4"><MapPinned size={20} className="text-[#281FD0]" /><h2 className="text-base font-black uppercase tracking-tight">Barrios y corregimientos</h2></div><div className="divide-y divide-slate-100 border-y border-slate-100">{(data.territories || []).slice(0, 12).map((territory, index) => <div key={territory.name} className="py-3 flex items-center justify-between gap-4"><div className="flex items-center gap-3 min-w-0"><span className="w-7 h-7 bg-slate-100 text-slate-700 text-xs font-black flex items-center justify-center shrink-0">{index + 1}</span><span className="font-bold text-slate-800 truncate">{territory.name}</span></div><span className="font-black text-slate-900">{numberFmt.format(territory.total)}</span></div>)}</div></div>
                    <AggregatedMap points={data.map?.points || []} suppressed={data.map?.suppressed_count || 0} minCount={data.map?.min_location_count || 3} />
                </section>

                <section className="grid gap-6 lg:grid-cols-2">
                    <div className="bg-white border border-slate-200 p-5"><div className="flex items-center gap-2 mb-3"><Info size={20} className="text-[#281FD0]" /><h2 className="font-black uppercase">Metodologia</h2></div><p className="text-sm leading-6 text-slate-700 font-medium">{meta.methodology}</p><p className="text-sm leading-6 text-slate-700 font-medium mt-3">{meta.privacy}</p></div>
                    <div className="bg-white border border-slate-200 p-5"><div className="flex items-center gap-2 mb-3"><CalendarClock size={20} className="text-[#281FD0]" /><h2 className="font-black uppercase">Trazabilidad de carga</h2></div><dl className="grid grid-cols-2 gap-px bg-slate-200 border border-slate-200 text-sm"><div className="bg-white p-3"><dt className="text-[10px] font-black uppercase text-slate-500">Archivo</dt><dd className="font-bold break-words">{meta.last_ingestion?.filename || 'No disponible'}</dd></div><div className="bg-white p-3"><dt className="text-[10px] font-black uppercase text-slate-500">Aprobadas</dt><dd className="font-bold">{numberFmt.format(meta.last_ingestion?.approved || 0)}</dd></div><div className="bg-white p-3"><dt className="text-[10px] font-black uppercase text-slate-500">Rechazadas</dt><dd className="font-bold">{numberFmt.format(meta.last_ingestion?.rejected || 0)}</dd></div><div className="bg-white p-3"><dt className="text-[10px] font-black uppercase text-slate-500">Duplicadas</dt><dd className="font-bold">{numberFmt.format(meta.last_ingestion?.duplicates || 0)}</dd></div></dl></div>
                </section>
            </main>

            <footer className="border-t border-slate-200 bg-white px-4 py-8 text-center"><button onClick={onBack} className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-500 hover:text-[#281FD0]"><Home size={15} /> Volver al inicio del portal</button><p className="text-[11px] text-slate-400 font-bold uppercase tracking-widest mt-4">SISC Jamundi - Publicacion ciudadana agregada</p></footer>
        </div>
    );
};

export default PublicDashboard;