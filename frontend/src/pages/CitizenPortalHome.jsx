import React, { useEffect, useMemo, useState } from 'react';
import {
    ArrowRight, BarChart3, CalendarClock, CheckCircle2, ChevronRight, Database,
    Download, FileText, Gavel, HeartPulse, MapPinned, MessageCircle,
    LifeBuoy, PhoneCall, RefreshCw, Share2, ShieldAlert, TrendingDown, TrendingUp, Users,
} from 'lucide-react';
import CitizenFilterBar from '../components/public/CitizenFilterBar';
import PublicPortalHeader from '../components/public/PublicPortalHeader';
import NeighborhoodStory from '../components/public/NeighborhoodStory';
import MetasPiscc from '../components/public/MetasPiscc';
import ComparacionMunicipios from '../components/public/ComparacionMunicipios';
import {
    buildCitizenInsights, DEFAULT_PUBLIC_FILTERS, filtersToSearchParams,
    formatNumber, formatVariation, parsePublicFilters, PERIOD_OPTIONS, variationTone,
} from '../utils/citizenInsights';
import { getCachedPublicDashboard, loadPublicDashboard } from '../utils/publicDashboardCache';
import { mesesIncompletos, motivoSinTasa, textoCobertura } from '../utils/cobertura';
import { HIDDEN_PUBLIC_PAGES } from '../utils/publicBuild';

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
            <p className="mt-5 text-3xl font-black leading-none tabular-nums text-slate-950">{value}</p>
            <p className="mt-3 text-xs font-semibold leading-5 text-slate-600">{helper}</p>
        </article>
    );
};

const DataSkeleton = () => (
    <div className="grid gap-3 sm:grid-cols-3" aria-label="Cargando indicadores">
        {[0, 1, 2].map((item) => <div key={item} className="h-44 animate-pulse border border-slate-200 bg-white p-5"><div className="h-3 w-24 bg-slate-200" /><div className="mt-10 h-8 w-20 bg-slate-200" /><div className="mt-4 h-3 w-full bg-slate-100" /></div>)}
    </div>
);

const ServiceLink = ({ icon: Icon, title, description, onClick }) => (
    <button onClick={onClick} className="group flex min-h-32 items-start gap-4 border border-slate-200 bg-white p-5 text-left transition-colors hover:border-[#281FD0] hover:shadow-sm">
        <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center bg-slate-100 text-[#281FD0] transition-colors group-hover:bg-[#281FD0] group-hover:text-white"><Icon size={22} /></span>
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

    // El balance general ya está en las tarjetas de arriba y la concentración territorial en "Mi barrio":
    // aquí solo va lo que no se repite.
    const insights = useMemo(() => buildCitizenInsights(data, 4)
        .filter((item) => !['overall-change', 'top-territory'].includes(item.id)), [data]);
    const filtersChanged = Object.keys(DEFAULT_PUBLIC_FILTERS).some((key) => appliedFilters[key] !== DEFAULT_PUBLIC_FILTERS[key]);
    const filterSummary = [
        PERIOD_OPTIONS.find((option) => option.value === appliedFilters.periodMode)?.label,
        appliedFilters.territorio || appliedFilters.zona || 'todo Jamundí',
    ].filter(Boolean).join(' · ');
    const variation = data?.kpis?.variation_pct;
    const maxConducta = Math.max(1, ...(data?.conductas || []).slice(0, 5).map((item) => Number(item.value || 0)));
    const filterOptions = data?.filters?.available || {};

    const neighborhoodUrl = selectedNeighborhood
        ? `${window.location.origin}${window.location.pathname}?${filtersToSearchParams({ ...appliedFilters, territorio: selectedNeighborhood }, 'hub')}#mi-barrio`
        : '';
    // El porcentaje del municipio solo es válido si el tablero general no está filtrado por territorio.
    const municipalTotal = !appliedFilters.territorio ? Number(data?.kpis?.total_hechos || 0) : null;

    const shareNeighborhood = async () => {
        if (!selectedNeighborhood) return;
        const url = neighborhoodUrl;
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

    // Las rutas de atención y el reporte seguro van arriba, en la franja de ayuda.
    const services = [
        { id: 'public-inspections', title: 'Gestión de Inspecciones', description: 'Actuaciones, trámites y servicios agregados de las Inspecciones de Policía.', icon: Gavel },
        { id: 'public-family-protection', title: 'Protección familiar', description: 'Atenciones y medidas de protección de las Comisarías de Familia.', icon: HeartPulse },
        { id: 'participation', title: 'Participación ciudadana', description: 'Información y canales de colaboración comunitaria.', icon: Users },
        { id: 'open-data', title: 'Datos abiertos', description: 'Descargas agregadas y diccionario, con fuente y fecha de corte.', icon: Download },
        { id: 'sisc-cifras', title: 'SISC en cifras', description: 'Resumen y carrusel para WhatsApp.', icon: MessageCircle },
        { id: 'technical-bulletins', title: 'Boletines', description: 'Archivo técnico por fecha y periodo.', icon: FileText },
    ].filter((item) => !HIDDEN_PUBLIC_PAGES.includes(item.id));


    return (
        <div className="public-portal min-h-screen bg-[#F2F4F7] text-slate-900">
            <a href="#contenido-principal" className="skip-link">Saltar al contenido principal</a>
            <PublicPortalHeader currentPage="hub" onNavigate={onNavigate} onLoginClick={onLoginClick} />

            <main id="contenido-principal">
                <section className="relative overflow-hidden bg-[#281FD0] text-white">
                    <div className="h-1.5 bg-[#FFE000]" />
                    <div className="mx-auto grid min-h-[320px] max-w-[1320px] items-center gap-10 px-4 py-10 md:px-6 lg:grid-cols-[1fr_280px] lg:py-12">
                        <div className="max-w-4xl">
                            <div className="mb-5 flex items-center gap-4">
                                <img src="/assets/escudo-limpio.png" alt="Escudo de la Alcaldía de Jamundí" className="h-[82px] w-[66px] object-contain drop-shadow-lg md:h-[96px] md:w-[78px]" />
                                <div className="border-l border-white/30 pl-4">
                                    <p className="text-xs font-black uppercase tracking-[0.18em] text-[#FFE000]">Alcaldía de Jamundí</p>
                                    <p className="mt-1 text-sm font-bold text-white/75">Sistema de Información para la Seguridad y Convivencia</p>
                                </div>
                            </div>
                            <h1 className="max-w-4xl text-4xl font-black leading-[1.05] tracking-normal md:text-6xl">Seguridad y convivencia en Jamundí</h1>
                            <p className="mt-5 max-w-3xl text-lg font-semibold leading-7 text-white/85 md:text-xl">Consulta datos públicos y comparables, sin información personal, para comprender lo que ocurre en el municipio.</p>
                            <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm font-bold text-white/85">
                                <span className="inline-flex items-center gap-2"><CalendarClock size={18} className="text-[#FFE000]" /> Corte de la Policía: {formatDate(data?.metadata?.latest_event_date)} · cada indicador muestra el suyo</span>
                                <span className="inline-flex items-center gap-2"><CheckCircle2 size={18} className="text-[#FFE000]" /> Datos agregados, sin información personal</span>
                            </div>
                            <div className="mt-8 flex flex-wrap gap-3">
                                <button onClick={() => onNavigate?.('transparency')} className="inline-flex min-h-12 items-center gap-2 bg-[#FFE000] px-5 font-black text-[#281FD0] transition-colors hover:bg-white"><BarChart3 size={19} /> Explorar datos</button>
                                <button onClick={() => document.getElementById('mi-barrio')?.scrollIntoView({ behavior: 'smooth' })} className="inline-flex min-h-12 items-center gap-2 border border-white/50 px-5 font-black text-white transition-colors hover:bg-white hover:text-[#281FD0]"><MapPinned size={19} /> Consultar mi barrio</button>
                            </div>
                            <div className="mt-4 lg:hidden">
                                <a href="tel:123" className="inline-flex min-h-12 items-center gap-3 bg-red-600 px-5 font-black text-white transition-colors hover:bg-red-700"><PhoneCall size={20} /> Emergencias 123</a>
                            </div>
                        </div>
                        <aside className="hidden border-l border-white/25 pl-8 lg:block">
                            <p className="text-xs font-black uppercase tracking-[0.16em] text-[#FFE000]">Atención inmediata</p>
                            <a href="tel:123" className="mt-4 inline-flex min-h-12 items-center gap-3 bg-red-600 px-5 font-black text-white transition-colors hover:bg-red-700"><PhoneCall size={20} /> Emergencias 123</a>
                            <button onClick={() => onNavigate?.('pqr')} className="mt-3 inline-flex min-h-11 items-center gap-2 text-sm font-bold text-white/85 transition-colors hover:text-white"><MessageCircle size={18} /> Ventanilla única PQR <ArrowRight size={16} /></button>
                        </aside>
                    </div>
                </section>

                <section aria-label="Ayuda y atención" className="border-b border-slate-200 bg-white">
                    <div className="mx-auto flex max-w-[1320px] flex-col gap-2 px-4 py-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3 md:px-6">
                        <p className="text-sm font-black text-slate-900 sm:mr-2">¿Necesitas ayuda?</p>
                        <button onClick={() => onNavigate?.('victim-support')} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 px-4 text-left text-sm font-black text-[#281FD0] transition-colors hover:border-[#281FD0]"><LifeBuoy size={18} className="shrink-0" /> Rutas de atención a víctimas <ChevronRight size={16} className="ml-auto shrink-0" /></button>
                        <button onClick={() => onNavigate?.('reporting')} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 px-4 text-left text-sm font-black text-[#281FD0] transition-colors hover:border-[#281FD0]"><ShieldAlert size={18} className="shrink-0" /> Reporte seguro <ChevronRight size={16} className="ml-auto shrink-0" /></button>
                    </div>
                </section>

                <div className="mx-auto max-w-[1320px] space-y-10 px-4 py-8 md:px-6 md:py-10">
                    {error && (
                        <section className="flex flex-col gap-4 border-l-4 border-red-600 bg-red-50 p-5 text-red-900 sm:flex-row sm:items-center sm:justify-between" role="alert">
                            <div><h2 className="font-black">No fue posible actualizar los datos</h2><p className="mt-1 text-sm font-semibold">{error}</p></div>
                            <button onClick={() => loadOverview(appliedFilters, true)} className="inline-flex min-h-11 items-center justify-center gap-2 border border-red-700 px-4 text-sm font-black"><RefreshCw size={17} /> Reintentar</button>
                        </section>
                    )}

                    <section aria-labelledby="jamundi-hoy-title">
                        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                            <div><p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Panorama público</p><h2 id="jamundi-hoy-title" className="mt-1 text-3xl font-black tracking-normal text-slate-950">Jamundí hoy</h2></div>
                            {data && <p className="max-w-xl text-xs font-semibold leading-5 text-slate-500 sm:text-right">Periodo: {formatDate(data.metadata?.period_start)} a {formatDate(data.metadata?.period_end)}. Fuente: SIEDCO / Policía Nacional.</p>}
                        </div>
                        {data?.suppressed && <p role="status" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm font-semibold text-amber-900">{data.suppressed.message}</p>}
                        {data && textoCobertura(mesesIncompletos([data.metadata?.cobertura, data.metadata?.cobertura_comparacion]), { publico: true }) && (
                            <p role="status" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm font-semibold text-amber-900">
                                {textoCobertura(mesesIncompletos([data.metadata?.cobertura, data.metadata?.cobertura_comparacion]), { publico: true })}
                            </p>
                        )}
                        {loading && !data ? <DataSkeleton /> : data ? (
                            <div className="grid gap-3 sm:grid-cols-3">
                                <KpiCard icon={Database} label="Casos agregados" value={formatNumber(data.kpis?.total_hechos)} helper="Casos únicos registrados en el periodo consultado." />
                                <KpiCard icon={variationTone(variation) === 'down' ? TrendingDown : TrendingUp} label="Cambio del periodo" value={formatVariation(variation)} helper={comparisonHelper(data)} tone={variationTone(variation) === 'up' ? 'red' : variationTone(variation) === 'down' ? 'green' : 'slate'} />
                                <KpiCard icon={ShieldAlert} label="Homicidios" value={formatNumber(data.kpis?.homicidios)} helper={data.kpis?.tasa_homicidios == null
                                    ? motivoSinTasa(data.metadata, appliedFilters, data.suppressed)
                                    : `${Number(data.kpis.tasa_homicidios).toLocaleString('es-CO', { maximumFractionDigits: 1 })} por cada 100.000 habitantes en el periodo consultado (no es una tasa anual).`} tone="red" />
                            </div>
                        ) : null}
                        <div className="mt-4">
                            <CitizenFilterBar filters={draftFilters} options={filterOptions} onChange={setDraftFilters} onApply={applyFilters} onClear={clearFilters} busy={refreshing} collapsible defaultOpen={filtersChanged} summary={filterSummary} />
                        </div>
                    </section>

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
                                    <button onClick={shareNeighborhood} disabled={!selectedNeighborhood || profileLoading} className="inline-flex min-h-11 items-center gap-2 bg-[#FFE000] px-4 text-sm font-black text-[#281FD0] transition-colors hover:bg-white disabled:opacity-40"><Share2 size={17} /> Compartir consulta</button>
                                    <button onClick={() => onNavigate?.('transparency', { hash: 'mapa' })} className="inline-flex min-h-11 items-center gap-2 text-sm font-black text-white"><MapPinned size={17} /> Abrir mapa</button>
                                </div>
                                {shareStatus && <p className="mt-3 text-xs font-bold text-white/75" role="status">{shareStatus}</p>}
                            </div>
                            <div className="p-6 md:p-8">
                                {profileLoading ? <div className="flex min-h-56 items-center justify-center text-sm font-bold text-slate-500"><RefreshCw className="mr-2 animate-spin" size={18} /> Consultando territorio</div> : profileData && selectedNeighborhood ? (
                                    <div>
                                        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
                                            <div><p className="text-xs font-black uppercase tracking-wide text-[#281FD0]">Perfil territorial agregado</p><h3 className="mt-1 text-2xl font-black text-slate-950">{selectedNeighborhood}</h3><p className="mt-1 text-sm font-semibold text-slate-500">{profileData.suppressed ? 'Cifras protegidas por privacidad' : (profileData.zones?.[0]?.name || 'Zona sin clasificar')}</p></div>
                                            <div className="text-right"><p className="text-4xl font-black tabular-nums text-slate-950">{formatNumber(profileData.kpis?.total_hechos)}</p><p className="text-xs font-bold text-slate-500">casos en el periodo</p></div>
                                        </div>
                                        <div className="mt-5">
                                            <NeighborhoodStory name={selectedNeighborhood} profile={profileData} municipalTotal={municipalTotal} shareUrl={neighborhoodUrl} onNavigate={onNavigate} />
                                        </div>
                                    </div>
                                ) : data?.territories?.length ? (
                                    <div>
                                        <p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Distribución municipal</p>
                                        <h3 className="mt-1 text-xl font-black text-slate-950">¿Dónde se concentran los registros?</h3>
                                        <p className="mt-2 text-sm font-semibold leading-6 text-slate-600">Volumen agregado en el periodo; no es una clasificación de barrios “buenos” o “malos”. Toca un territorio para ver su resumen.</p>
                                        <ol className="mt-4 divide-y divide-slate-200 border-y border-slate-200">
                                            {data.territories.slice(0, 5).map((item, index) => (
                                                <li key={item.name}>
                                                    <button onClick={() => { setSelectedNeighborhood(item.name); setShareStatus(''); }} className="flex min-h-12 w-full items-center gap-4 px-2 text-left transition-colors hover:bg-slate-50">
                                                        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center bg-slate-100 text-xs font-black text-[#281FD0]">{index + 1}</span>
                                                        <span className="min-w-0 flex-1 truncate text-sm font-black text-slate-800">{item.name}</span>
                                                        <span className="font-black tabular-nums text-slate-950">{formatNumber(item.total)}</span>
                                                        <ChevronRight size={16} className="shrink-0 text-[#281FD0]" />
                                                    </button>
                                                </li>
                                            ))}
                                        </ol>
                                    </div>
                                ) : (
                                    <div className="flex min-h-56 items-center justify-center text-center"><div><MapPinned size={34} className="mx-auto text-slate-300" /><p className="mt-3 font-black text-slate-800">Selecciona un territorio</p><p className="mt-1 text-sm font-semibold text-slate-500">Verás en palabras sencillas qué pasó, qué días concentran más casos y qué puedes hacer.</p></div></div>
                                )}
                            </div>
                        </div>
                    </section>

                    {data && (insights.length || data.conductas?.length) ? (
                        <section aria-labelledby="changes-title" className="grid gap-8 border-y border-slate-200 py-8 lg:grid-cols-2">
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Lectura rápida</p>
                                <h2 id="changes-title" className="mt-1 text-3xl font-black tracking-normal text-slate-950">¿Qué cambió?</h2>
                                <p className="mt-3 max-w-xl text-sm font-semibold leading-6 text-slate-600">Comparaciones calculadas sobre el periodo seleccionado. Un aumento de registros no prueba por sí solo un aumento del riesgo.</p>
                                <div className="mt-5 grid gap-3">
                                    {insights.map((insight) => (
                                        <article key={insight.id} className="border border-slate-200 bg-white p-5 shadow-sm">
                                            <p className="text-[10px] font-black uppercase tracking-[0.14em] text-[#281FD0]">{insight.eyebrow}</p>
                                            <h3 className="mt-2 text-lg font-black leading-6 text-slate-950">{insight.title}</h3>
                                            <p className="mt-2 text-sm font-semibold leading-6 text-slate-600">{insight.summary}</p>
                                        </article>
                                    ))}
                                </div>
                            </div>
                            {data.conductas?.length ? (
                                <div>
                                    <h3 className="text-xl font-black text-slate-950">Lo que más se reportó</h3>
                                    <p className="mt-2 text-sm font-semibold leading-6 text-slate-600">Un mismo caso puede incluir más de una conducta; por eso la suma puede superar el total de casos.</p>
                                    <div className="mt-5 space-y-4">
                                        {data.conductas.slice(0, 5).map((item) => (
                                            <div key={item.code || item.name}>
                                                <div className="mb-1.5 flex items-end justify-between gap-4 text-sm"><span className="font-black text-slate-800">{item.name}</span><span className="font-black tabular-nums text-slate-950">{formatNumber(item.value)}</span></div>
                                                <div className="h-3 bg-slate-200" aria-hidden="true"><div className="h-3 bg-[#384CF5]" style={{ width: `${Math.max(4, (Number(item.value || 0) / maxConducta) * 100)}%` }} /></div>
                                                <p className="mt-1 text-[11px] font-semibold text-slate-500">{formatVariation(item.variation_pct)} frente a la comparación</p>
                                            </div>
                                        ))}
                                    </div>
                                    <button onClick={() => onNavigate?.('transparency')} className="mt-5 inline-flex min-h-11 items-center gap-2 font-black text-[#281FD0]">Ver todas las tendencias <ArrowRight size={17} /></button>
                                </div>
                            ) : null}
                        </section>
                    ) : null}

                    <MetasPiscc />

                    <ComparacionMunicipios />

                    <section aria-labelledby="services-title">
                        <div className="mb-5"><p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Servicios públicos</p><h2 id="services-title" className="mt-1 text-2xl font-black text-slate-950">Más información y servicios</h2></div>
                        <div className={`grid gap-3 md:grid-cols-2 ${services.length % 3 === 0 ? 'lg:grid-cols-3' : 'xl:grid-cols-4'}`}>{services.map((service) => <ServiceLink key={service.id} {...service} onClick={() => onNavigate?.(service.id)} />)}</div>
                    </section>
                </div>
            </main>

            <footer className="border-t-4 border-[#FFE000] bg-slate-950 text-white">
                <div className="mx-auto grid max-w-[1320px] gap-8 px-4 py-10 md:grid-cols-[1.2fr_0.8fr_0.8fr] md:px-6">
                    <div className="flex items-start gap-4"><img src="/assets/escudo-limpio.png" alt="" className="h-16 w-12 object-contain" /><div><p className="text-xl font-black">SISC Jamundí</p><p className="mt-2 max-w-md text-sm font-semibold leading-6 text-white/60">Sistema de Información para la Seguridad y Convivencia. Publicación agregada de la Alcaldía de Jamundí.</p><p className="mt-2 max-w-md text-xs font-semibold leading-5 text-white/45">Herramienta del Observatorio del Delito, en desarrollo de la acción “Implementar el sistema de información para el Observatorio de justicia y análisis estadístico de la política criminal” del Plan Integral de Seguridad y Convivencia Ciudadana (PISCC) 2024–2027 (tabla 12).</p></div></div>
                    <div><p className="text-xs font-black uppercase tracking-wide text-[#FFE000]">Transparencia</p><div className="mt-3 grid gap-2 text-sm font-bold text-white/70"><button onClick={() => onNavigate?.('transparency-info')} className="min-h-10 text-left transition-colors hover:text-white">Metodología y fuentes</button><button onClick={() => onNavigate?.('open-data')} className="min-h-10 text-left transition-colors hover:text-white">Datos abiertos</button>{!HIDDEN_PUBLIC_PAGES.includes('technical-bulletins') && <button onClick={() => onNavigate?.('technical-bulletins')} className="min-h-10 text-left transition-colors hover:text-white">Boletines técnicos</button>}</div></div>
                    <div><p className="text-xs font-black uppercase tracking-wide text-[#FFE000]">Contacto</p><a href="tel:123" className="mt-3 inline-flex min-h-10 items-center gap-2 font-black"><PhoneCall size={18} /> Emergencias 123</a><p className="mt-2 text-sm font-semibold text-white/60">Centro de Mando: (602) 519 22 22</p></div>
                </div>
            </footer>
        </div>
    );
};

export default CitizenPortalHome;
