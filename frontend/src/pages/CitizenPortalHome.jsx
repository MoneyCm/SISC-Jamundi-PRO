import React, { useEffect, useMemo, useState } from 'react';
import {
    ArrowRight, BarChart3, CalendarClock, CheckCircle2, ChevronRight, Database,
    Download, FileText, Gavel, HeartPulse, Info, MapPinned, MessageCircle,
    PhoneCall, RefreshCw, Share2, ShieldAlert, TrendingDown, TrendingUp, Users,
} from 'lucide-react';
import CitizenFilterBar from '../components/public/CitizenFilterBar';
import PublicPortalHeader from '../components/public/PublicPortalHeader';
import {
    buildCitizenInsights, DEFAULT_PUBLIC_FILTERS, filtersToSearchParams,
    formatNumber, formatVariation, parsePublicFilters, variationTone,
} from '../utils/citizenInsights';
import { getCachedPublicDashboard, loadPublicDashboard } from '../utils/publicDashboardCache';

const formatDate = (value) => {
    if (!value) return 'Sin corte disponible';
    return new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'long', year: 'numeric' })
        .format(new Date(`${value}T12:00:00`));
};

const comparisonHelper = (data) => {
    const meta = data?.metadata || {};
    if (!meta.comparison_start || !meta.comparison_end) return 'Consulta sin periodo de comparación';
    return `${meta.comparison_label}: ${formatDate(meta.comparison_start)} a ${formatDate(meta.comparison_end)}`;
};

const KpiCard = ({ icon: Icon, label, value, helper, tone = 'blue' }) => {
    const tones = {
        blue: { border: 'border-t-[#281FD0]', icon: 'bg-[#281FD0]/10 text-[#281FD0]' },
        amber: { border: 'border-t-[#FFB600]', icon: 'bg-amber-50 text-amber-700' },
        red: { border: 'border-t-red-600', icon: 'bg-red-50 text-red-700' },
        green: { border: 'border-t-emerald-600', icon: 'bg-emerald-50 text-emerald-700' },
        slate: { border: 'border-t-slate-500', icon: 'bg-slate-100 text-slate-700' },
    };
    const style = tones[tone] || tones.blue;
    return (
        <article className={`min-h-[176px] border border-t-4 border-slate-200 bg-white p-5 shadow-sm ${style.border}`}>
            <div className="flex items-start justify-between gap-3">
                <p className="text-[11px] font-black uppercase tracking-[0.1em] text-slate-500">{label}</p>
                <span className={`inline-flex h-9 w-9 items-center justify-center ${style.icon}`}><Icon size={19} /></span>
            </div>
            <p className="mt-5 text-3xl font-black leading-none text-slate-950">{value}</p>
            <p className="mt-3 text-xs font-semibold leading-5 text-slate-600">{helper}</p>
        </article>
    );
};

const DataSkeleton = () => (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" aria-label="Cargando indicadores">
        {[0, 1, 2, 3, 4].map((item) => <div key={item} className="h-44 animate-pulse border border-slate-200 bg-white p-5"><div className="h-3 w-24 bg-slate-200" /><div className="mt-10 h-8 w-20 bg-slate-200" /><div className="mt-4 h-3 w-full bg-slate-100" /></div>)}
    </div>
);

const ServiceLink = ({ icon: Icon, title, description, onClick }) => (
    <button onClick={onClick} className="group flex min-h-32 items-start gap-4 border border-slate-200 bg-white p-5 text-left transition hover:border-[#281FD0] hover:shadow-sm">
        <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center bg-slate-100 text-[#281FD0] group-hover:bg-[#281FD0] group-hover:text-white"><Icon size={22} /></span>
        <span className="min-w-0">
            <strong className="block text-base font-black text-slate-900">{title}</strong>
            <span className="mt-1 block text-sm leading-5 text-slate-600">{description}</span>
            <span className="mt-3 inline-flex items-center gap-1 text-xs font-black text-[#281FD0]">Consultar <ChevronRight size={15} /></span>
        </span>
    </button>
);

const CitizenPortalHome = ({ onNavigate, onLoginClick }) => {
    const initialFilters = useMemo(() => parsePublicFilters(window.location.search), []);
    const initialOptions = { ...initialFilters, includeMap: false, minLocationCount: 3 };
    const [draftFilters, setDraftFilters] = useState(initialFilters);
    const [appliedFilters, setAppliedFilters] = useState(initialFilters);
    const [data, setData] = useState(() => getCachedPublicDashboard(initialOptions));
    const [loading, setLoading] = useState(() => !getCachedPublicDashboard(initialOptions));
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');
    const [selectedNeighborhood, setSelectedNeighborhood] = useState(initialFilters.territorio || '');
    const [profileData, setProfileData] = useState(null);
    const [profileLoading, setProfileLoading] = useState(false);
    const [shareStatus, setShareStatus] = useState('');

    const loadOverview = async (filters, force = false) => {
        if (data) setRefreshing(true);
        else setLoading(true);
        setError('');
        try {
            setData(await loadPublicDashboard({ ...filters, includeMap: false, minLocationCount: 3, force }));
        } catch (requestError) {
            setError(requestError.message || 'No fue posible consultar los datos públicos.');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        loadOverview(appliedFilters, Boolean(data));
        // appliedFilters changes only when the user submits the form.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [appliedFilters]);

    useEffect(() => {
        const restoreFilters = () => {
            const restored = parsePublicFilters(window.location.search);
            setDraftFilters(restored);
            setAppliedFilters(restored);
            setSelectedNeighborhood(restored.territorio || '');
        };
        window.addEventListener('popstate', restoreFilters);
        return () => window.removeEventListener('popstate', restoreFilters);
    }, []);

    useEffect(() => {
        if (!selectedNeighborhood) {
            setProfileData(null);
            return;
        }
        if (appliedFilters.territorio === selectedNeighborhood && data) {
            setProfileData(data);
            return;
        }
        let active = true;
        setProfileLoading(true);
        loadPublicDashboard({ ...appliedFilters, territorio: selectedNeighborhood, includeMap: false, minLocationCount: 3 })
            .then((result) => { if (active) setProfileData(result); })
            .catch(() => { if (active) setProfileData(null); })
            .finally(() => { if (active) setProfileLoading(false); });
        return () => { active = false; };
    }, [selectedNeighborhood, appliedFilters, data]);

    const updateUrl = (filters) => {
        const query = filtersToSearchParams(filters, 'hub').toString();
        window.history.pushState({ page: 'hub' }, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
    };

    const applyFilters = () => {
        setAppliedFilters({ ...draftFilters });
        setSelectedNeighborhood(draftFilters.territorio || '');
        updateUrl(draftFilters);
    };

    const clearFilters = () => {
        const cleared = { ...DEFAULT_PUBLIC_FILTERS };
        setDraftFilters(cleared);
        setAppliedFilters(cleared);
        setSelectedNeighborhood('');
        updateUrl(cleared);
    };

    const insights = useMemo(() => buildCitizenInsights(data, 4), [data]);
    const topConducta = data?.conductas?.[0];
    const topTerritory = data?.territories?.[0];
    const variation = data?.kpis?.variation_pct;
    const maxConducta = Math.max(1, ...(data?.conductas || []).slice(0, 5).map((item) => Number(item.value || 0)));
    const filterOptions = data?.filters?.available || {};

    const shareNeighborhood = async () => {
        if (!selectedNeighborhood) return;
        const params = filtersToSearchParams({ ...appliedFilters, territorio: selectedNeighborhood }, 'hub');
        const url = `${window.location.origin}${window.location.pathname}?${params}#mi-barrio`;
        try {
            if (navigator.share) {
                await navigator.share({ title: `SISC Jamundí: ${selectedNeighborhood}`, text: 'Consulta agregada y protegida del territorio.', url });
                setShareStatus('Consulta compartida.');
            } else {
                await navigator.clipboard.writeText(url);
                setShareStatus('Enlace copiado.');
            }
        } catch (shareError) {
            if (shareError.name !== 'AbortError') setShareStatus('No fue posible compartir el enlace.');
        }
    };

    const services = [
        { id: 'public-inspections', title: 'Gestión de Inspecciones', description: 'Actuaciones, trámites y servicios agregados de las Inspecciones de Policía.', icon: Gavel },
        { id: 'public-family-protection', title: 'Protección familiar', description: 'Atenciones y medidas de protección de las Comisarías de Familia.', icon: HeartPulse },
        { id: 'reporting', title: 'Reporte seguro', description: 'Canal institucional para informar delitos o riesgos.', icon: ShieldAlert },
        { id: 'participation', title: 'Participación ciudadana', description: 'Información y canales de colaboración comunitaria.', icon: Users },
    ];

    return (
        <div className="public-portal min-h-screen bg-[#F2F4F7] text-slate-900">
            <a href="#contenido-principal" className="skip-link">Saltar al contenido principal</a>
            <PublicPortalHeader currentPage="hub" onNavigate={onNavigate} onLoginClick={onLoginClick} />

            <main id="contenido-principal">
                <section className="relative overflow-hidden bg-[#281FD0] text-white">
                    <div className="h-1.5 bg-[#FFE000]" />
                    <div className="mx-auto grid min-h-[390px] max-w-[1320px] items-center gap-10 px-4 py-12 md:px-6 lg:grid-cols-[1fr_280px] lg:py-14">
                        <div className="max-w-4xl">
                            <div className="mb-5 flex items-center gap-4">
                                <img src="/assets/escudo-limpio.png" alt="Escudo de la Alcaldía de Jamundí" className="h-[82px] w-[66px] object-contain drop-shadow-lg md:h-[96px] md:w-[78px]" />
                                <div className="border-l border-white/30 pl-4">
                                    <p className="text-xs font-black uppercase tracking-[0.18em] text-[#FFE000]">Alcaldía de Jamundí</p>
                                    <p className="mt-1 text-sm font-bold text-white/75">Sistema de Información para la Seguridad y Convivencia</p>
                                </div>
                            </div>
                            <h1 className="max-w-4xl text-4xl font-black leading-[1.05] tracking-normal md:text-6xl">Seguridad y convivencia en Jamundí</h1>
                            <p className="mt-5 max-w-3xl text-lg font-semibold leading-7 text-white/85 md:text-xl">Consulta datos públicos, comparables y protegidos para comprender lo que ocurre en el municipio.</p>
                            <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm font-bold text-white/85">
                                <span className="inline-flex items-center gap-2"><CalendarClock size={18} className="text-[#FFE000]" /> Corte: {formatDate(data?.metadata?.latest_event_date)}</span>
                                <span className="inline-flex items-center gap-2"><CheckCircle2 size={18} className="text-[#FFE000]" /> Datos agregados, sin información personal</span>
                            </div>
                            <div className="mt-8 flex flex-wrap gap-3">
                                <button onClick={() => onNavigate?.('transparency')} className="inline-flex min-h-12 items-center gap-2 bg-[#FFE000] px-5 font-black text-[#1b176f] hover:bg-white"><BarChart3 size={19} /> Explorar datos</button>
                                <button onClick={() => document.getElementById('mi-barrio')?.scrollIntoView({ behavior: 'smooth' })} className="inline-flex min-h-12 items-center gap-2 border border-white/50 px-5 font-black text-white hover:bg-white hover:text-[#281FD0]"><MapPinned size={19} /> Consultar mi barrio</button>
                            </div>
                        </div>
                        <aside className="hidden border-l border-white/25 pl-8 lg:block">
                            <p className="text-xs font-black uppercase tracking-[0.16em] text-[#FFE000]">Atención inmediata</p>
                            <a href="tel:123" className="mt-4 inline-flex min-h-12 items-center gap-3 bg-red-600 px-5 font-black text-white hover:bg-red-700"><PhoneCall size={20} /> Emergencias 123</a>
                            <button onClick={() => onNavigate?.('pqr')} className="mt-3 inline-flex min-h-11 items-center gap-2 text-sm font-bold text-white/85 hover:text-white"><MessageCircle size={18} /> Ventanilla única PQR <ArrowRight size={16} /></button>
                        </aside>
                    </div>
                </section>

                <div className="mx-auto max-w-[1320px] space-y-10 px-4 py-8 md:px-6 md:py-10">
                    <CitizenFilterBar filters={draftFilters} options={filterOptions} onChange={setDraftFilters} onApply={applyFilters} onClear={clearFilters} busy={refreshing} />

                    {error && (
                        <section className="flex flex-col gap-4 border-l-4 border-red-600 bg-red-50 p-5 text-red-900 sm:flex-row sm:items-center sm:justify-between" role="alert">
                            <div><h2 className="font-black">No fue posible actualizar los datos</h2><p className="mt-1 text-sm font-semibold">{error}</p></div>
                            <button onClick={() => loadOverview(appliedFilters, true)} className="inline-flex min-h-11 items-center justify-center gap-2 border border-red-700 px-4 text-sm font-black"><RefreshCw size={17} /> Reintentar</button>
                        </section>
                    )}

                    <section aria-labelledby="jamundi-hoy-title">
                        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                            <div><p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Panorama público</p><h2 id="jamundi-hoy-title" className="mt-1 text-3xl font-black tracking-normal text-slate-950">Jamundí hoy</h2></div>
                            {data && <p className="max-w-xl text-right text-xs font-semibold leading-5 text-slate-500">Periodo: {formatDate(data.metadata?.period_start)} a {formatDate(data.metadata?.period_end)}. Fuente: SIEDCO / Policía Nacional.</p>}
                        </div>
                        {loading && !data ? <DataSkeleton /> : data ? (
                            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                                <KpiCard icon={Database} label="Casos agregados" value={formatNumber(data.kpis?.total_hechos)} helper="Casos únicos registrados en el periodo consultado." />
                                <KpiCard icon={variationTone(variation) === 'down' ? TrendingDown : TrendingUp} label="Cambio del periodo" value={formatVariation(variation)} helper={comparisonHelper(data)} tone={variationTone(variation) === 'up' ? 'red' : variationTone(variation) === 'down' ? 'green' : 'slate'} />
                                <KpiCard icon={ShieldAlert} label="Homicidios" value={formatNumber(data.kpis?.homicidios)} helper={`${data.kpis?.tasa_homicidios || 0} por cada 100.000 habitantes en el periodo.`} tone="red" />
                                <KpiCard icon={BarChart3} label="Conducta más registrada" value={formatNumber(topConducta?.value)} helper={topConducta?.name || 'Sin conducta publicable'} tone="amber" />
                                <KpiCard icon={MapPinned} label="Mayor concentración" value={formatNumber(topTerritory?.total)} helper={topTerritory ? `${topTerritory.name}. Registros agregados, no nivel de riesgo.` : 'Sin territorio publicable'} tone="slate" />
                            </div>
                        ) : null}
                    </section>

                    {data && (
                        <section aria-labelledby="changes-title" className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Lectura rápida</p>
                                <h2 id="changes-title" className="mt-1 text-3xl font-black tracking-normal text-slate-950">¿Qué cambió?</h2>
                                <p className="mt-3 max-w-xl text-sm font-semibold leading-6 text-slate-600">Comparaciones calculadas sobre el periodo seleccionado. Un aumento de registros no prueba por sí solo un aumento del riesgo.</p>
                                <div className="mt-5 border-l-4 border-[#FFB600] bg-white p-4 text-sm leading-6 text-slate-700"><strong className="block text-slate-950">Base de comparación</strong>{comparisonHelper(data)}</div>
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                {insights.map((insight) => (
                                    <article key={insight.id} className="border border-slate-200 bg-white p-5 shadow-sm">
                                        <p className="text-[10px] font-black uppercase tracking-[0.14em] text-[#281FD0]">{insight.eyebrow}</p>
                                        <h3 className="mt-2 text-lg font-black leading-6 text-slate-950">{insight.title}</h3>
                                        <p className="mt-2 text-sm font-semibold leading-6 text-slate-600">{insight.summary}</p>
                                    </article>
                                ))}
                            </div>
                        </section>
                    )}

                    {data?.conductas?.length ? (
                        <section className="grid gap-6 border-y border-slate-200 py-8 lg:grid-cols-[0.7fr_1.3fr]" aria-labelledby="conductas-title">
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Conductas registradas</p>
                                <h2 id="conductas-title" className="mt-1 text-2xl font-black text-slate-950">¿Qué se reportó más?</h2>
                                <p className="mt-3 text-sm font-semibold leading-6 text-slate-600">Casos únicos agrupados con nombres ciudadanos. Las variantes técnicas de la fuente se consolidan en una sola categoría.</p>
                                <button onClick={() => onNavigate?.('transparency')} className="mt-5 inline-flex min-h-11 items-center gap-2 font-black text-[#281FD0]">Ver todas las tendencias <ArrowRight size={17} /></button>
                            </div>
                            <div className="space-y-4">
                                {data.conductas.slice(0, 5).map((item) => (
                                    <div key={item.code || item.name}>
                                        <div className="mb-1.5 flex items-end justify-between gap-4 text-sm"><span className="font-black text-slate-800">{item.name}</span><span className="font-black text-slate-950">{formatNumber(item.value)}</span></div>
                                        <div className="h-3 bg-slate-200"><div className="h-3 bg-[#384CF5]" style={{ width: `${Math.max(4, (Number(item.value || 0) / maxConducta) * 100)}%` }} /></div>
                                        <p className="mt-1 text-[11px] font-semibold text-slate-500">{formatVariation(item.variation_pct)} frente a la comparación</p>
                                    </div>
                                ))}
                            </div>
                        </section>
                    ) : null}

                    <section id="mi-barrio" className="scroll-mt-24 border border-slate-200 bg-white" aria-labelledby="neighborhood-title">
                        <div className="grid lg:grid-cols-[0.72fr_1.28fr]">
                            <div className="bg-slate-950 p-6 text-white md:p-8">
                                <p className="text-xs font-black uppercase tracking-[0.16em] text-[#FFE000]">Consulta territorial</p>
                                <h2 id="neighborhood-title" className="mt-2 text-3xl font-black">Mi barrio, vereda o sector</h2>
                                <p className="mt-3 text-sm font-semibold leading-6 text-white/70">La publicación muestra totales agregados y oculta ubicaciones de baja frecuencia.</p>
                                <label className="mt-6 grid gap-2 text-xs font-black uppercase tracking-wide text-white/80">Seleccionar territorio
                                    <select value={selectedNeighborhood} onChange={(event) => { setSelectedNeighborhood(event.target.value); setShareStatus(''); }} className="min-h-12 w-full bg-white px-3 text-sm font-bold text-slate-900 outline-none focus:ring-2 focus:ring-[#FFE000]">
                                        <option value="">Elige un territorio</option>
                                        {(filterOptions.territories || []).map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
                                    </select>
                                </label>
                                <div className="mt-5 flex flex-wrap gap-3">
                                    <button onClick={shareNeighborhood} disabled={!selectedNeighborhood || profileLoading} className="inline-flex min-h-11 items-center gap-2 bg-[#FFE000] px-4 text-sm font-black text-[#1b176f] disabled:opacity-40"><Share2 size={17} /> Compartir consulta</button>
                                    <button onClick={() => onNavigate?.('transparency', { hash: 'mapa' })} className="inline-flex min-h-11 items-center gap-2 text-sm font-black text-white"><MapPinned size={17} /> Abrir mapa</button>
                                </div>
                                {shareStatus && <p className="mt-3 text-xs font-bold text-white/75" role="status">{shareStatus}</p>}
                            </div>
                            <div className="p-6 md:p-8">
                                {profileLoading ? <div className="flex min-h-56 items-center justify-center text-sm font-bold text-slate-500"><RefreshCw className="mr-2 animate-spin" size={18} /> Consultando territorio</div> : profileData && selectedNeighborhood ? (
                                    <div>
                                        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
                                            <div><p className="text-xs font-black uppercase tracking-wide text-[#281FD0]">Perfil territorial agregado</p><h3 className="mt-1 text-2xl font-black text-slate-950">{selectedNeighborhood}</h3><p className="mt-1 text-sm font-semibold text-slate-500">{profileData.zones?.[0]?.name || 'Zona sin clasificar'}</p></div>
                                            <div className="text-right"><p className="text-4xl font-black text-slate-950">{formatNumber(profileData.kpis?.total_hechos)}</p><p className="text-xs font-bold text-slate-500">casos en el periodo</p></div>
                                        </div>
                                        <div className="mt-5 grid gap-4 sm:grid-cols-2">
                                            <div className="border-l-4 border-[#281FD0] pl-4"><p className="text-xs font-bold text-slate-500">Cambio comparado</p><p className="mt-1 text-2xl font-black text-slate-950">{formatVariation(profileData.kpis?.variation_pct)}</p><p className="mt-1 text-xs font-semibold text-slate-500">{comparisonHelper(profileData)}</p></div>
                                            <div><p className="text-xs font-black uppercase tracking-wide text-slate-500">Conductas más registradas</p><ol className="mt-2 space-y-2">{profileData.conductas?.slice(0, 3).map((item, index) => <li key={item.code || item.name} className="flex justify-between gap-4 text-sm"><span className="font-bold text-slate-700">{index + 1}. {item.name}</span><strong>{formatNumber(item.value)}</strong></li>)}</ol></div>
                                        </div>
                                        <p className="mt-6 inline-flex items-start gap-2 bg-slate-50 p-3 text-xs font-semibold leading-5 text-slate-600"><Info size={16} className="mt-0.5 shrink-0 text-[#281FD0]" /> El perfil no contiene direcciones, coordenadas puntuales, personas ni expedientes.</p>
                                    </div>
                                ) : (
                                    <div className="flex min-h-56 items-center justify-center text-center"><div><MapPinned size={34} className="mx-auto text-slate-300" /><p className="mt-3 font-black text-slate-800">Selecciona un territorio</p><p className="mt-1 text-sm font-semibold text-slate-500">Verás el total, la comparación y las conductas principales.</p></div></div>
                                )}
                            </div>
                        </div>
                    </section>

                    {data?.territories?.length ? (
                        <section className="grid gap-6 lg:grid-cols-[0.78fr_1.22fr]" aria-labelledby="territory-title">
                            <div><p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Distribución municipal</p><h2 id="territory-title" className="mt-1 text-3xl font-black text-slate-950">¿Dónde se concentran los registros?</h2><p className="mt-3 text-sm font-semibold leading-6 text-slate-600">La lista indica volumen agregado en el periodo; no es una clasificación de barrios “buenos” o “malos”.</p></div>
                            <ol className="divide-y divide-slate-200 border-y border-slate-200 bg-white">
                                {data.territories.slice(0, 5).map((item, index) => <li key={item.name} className="flex min-h-14 items-center gap-4 px-4"><span className="inline-flex h-8 w-8 items-center justify-center bg-slate-100 text-xs font-black text-[#281FD0]">{index + 1}</span><span className="min-w-0 flex-1 truncate text-sm font-black text-slate-800">{item.name}</span><span className="font-black text-slate-950">{formatNumber(item.total)}</span></li>)}
                            </ol>
                        </section>
                    ) : null}

                    <section className="border-y border-slate-200 py-8" aria-labelledby="publish-title">
                        <div className="mb-6 max-w-3xl"><p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Información para compartir</p><h2 id="publish-title" className="mt-1 text-3xl font-black text-slate-950">SISC en cifras y boletines</h2><p className="mt-3 text-sm font-semibold leading-6 text-slate-600">Piezas visuales y documentos públicos con su periodo, fuente y fecha de corte.</p></div>
                        <div className="grid gap-3 md:grid-cols-3">
                            <button onClick={() => onNavigate?.('sisc-cifras')} className="flex min-h-32 items-center gap-4 bg-[#281FD0] p-5 text-left text-white"><MessageCircle size={28} className="shrink-0 text-[#FFE000]" /><span><strong className="block text-lg font-black">SISC en cifras</strong><span className="mt-1 block text-sm font-semibold text-white/75">Resumen y carrusel para WhatsApp.</span></span><ArrowRight className="ml-auto shrink-0" /></button>
                            <button onClick={() => onNavigate?.('technical-bulletins')} className="flex min-h-32 items-center gap-4 border border-slate-200 bg-white p-5 text-left"><FileText size={28} className="shrink-0 text-[#281FD0]" /><span><strong className="block text-lg font-black">Boletines</strong><span className="mt-1 block text-sm font-semibold text-slate-600">Archivo técnico por fecha y periodo.</span></span><ArrowRight className="ml-auto shrink-0 text-[#281FD0]" /></button>
                            <button onClick={() => onNavigate?.('open-data')} className="flex min-h-32 items-center gap-4 border border-slate-200 bg-white p-5 text-left"><Download size={28} className="shrink-0 text-[#281FD0]" /><span><strong className="block text-lg font-black">Datos abiertos</strong><span className="mt-1 block text-sm font-semibold text-slate-600">Descargas agregadas y diccionario.</span></span><ArrowRight className="ml-auto shrink-0 text-[#281FD0]" /></button>
                        </div>
                    </section>

                    <section aria-labelledby="services-title">
                        <div className="mb-5"><p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Servicios públicos</p><h2 id="services-title" className="mt-1 text-2xl font-black text-slate-950">Atención, protección y participación</h2></div>
                        <div className="grid gap-3 md:grid-cols-2">{services.map((service) => <ServiceLink key={service.id} {...service} onClick={() => onNavigate?.(service.id)} />)}</div>
                    </section>
                </div>
            </main>

            <footer className="border-t-4 border-[#FFE000] bg-slate-950 text-white">
                <div className="mx-auto grid max-w-[1320px] gap-8 px-4 py-10 md:grid-cols-[1.2fr_0.8fr_0.8fr] md:px-6">
                    <div className="flex items-start gap-4"><img src="/assets/escudo-limpio.png" alt="" className="h-16 w-12 object-contain" /><div><p className="text-xl font-black">SISC Jamundí</p><p className="mt-2 max-w-md text-sm font-semibold leading-6 text-white/60">Sistema de Información para la Seguridad y Convivencia. Publicación agregada de la Alcaldía de Jamundí.</p></div></div>
                    <div><p className="text-xs font-black uppercase tracking-wide text-[#FFE000]">Transparencia</p><div className="mt-3 grid gap-2 text-sm font-bold text-white/70"><button onClick={() => onNavigate?.('transparency-info')} className="min-h-8 text-left hover:text-white">Metodología y fuentes</button><button onClick={() => onNavigate?.('open-data')} className="min-h-8 text-left hover:text-white">Datos abiertos</button><button onClick={() => onNavigate?.('technical-bulletins')} className="min-h-8 text-left hover:text-white">Boletines técnicos</button></div></div>
                    <div><p className="text-xs font-black uppercase tracking-wide text-[#FFE000]">Contacto</p><a href="tel:123" className="mt-3 inline-flex min-h-10 items-center gap-2 font-black"><PhoneCall size={18} /> Emergencias 123</a><p className="mt-2 text-sm font-semibold text-white/60">Centro de Mando: (602) 519 22 22</p></div>
                </div>
            </footer>
        </div>
    );
};

export default CitizenPortalHome;
