import React, { useEffect, useState } from 'react';
import { BarChart3, Filter, LockKeyhole, MapPin, RefreshCcw, ShieldCheck, AlertCircle } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const number = (value) => new Intl.NumberFormat('es-CO').format(value || 0);

const BarList = ({ title, items = [], tone = 'bg-indigo-500' }) => {
    const max = Math.max(...items.map((item) => item.value), 1);
    return (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-5 text-sm font-black uppercase tracking-widest text-slate-700">{title}</h3>
            {items.length === 0 ? <p className="text-sm text-slate-400">No hay datos para estos filtros.</p> : (
                <div className="space-y-4">
                    {items.map((item) => (
                        <div key={item.label}>
                            <div className="mb-1 flex justify-between gap-3 text-xs font-bold text-slate-600">
                                <span className="truncate">{item.label}</span><span>{number(item.value)}</span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                                <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max((item.value / max) * 100, 3)}%` }} />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
};

const PoliceWeeklyExplorer = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [filters, setFilters] = useState({ year: '', conducta: '', zona: '', semana: '' });

    const load = async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key === 'year' ? 'anio' : key, value); });
            const response = await fetch(`${API_BASE_URL}/ingesta/policia/explorer?${params.toString()}`, {
                headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'No fue posible cargar el explorador.');
            setData(payload);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, [filters.year, filters.conducta, filters.zona, filters.semana]);

    const setFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
    const catalog = data?.filters || { years: [], conductas: [], zonas: [], semanas: [] };
    const detailed = Boolean(data?.access?.can_filter_detailed);

    if (loading && !data) return <div className="p-20 text-center text-sm font-black uppercase tracking-widest text-slate-400">Cargando explorador policial</div>;
    if (error && !data) return <div className="m-8 rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700"><AlertCircle className="mb-2" />{error}</div>;

    return (
        <div className="mx-auto max-w-7xl space-y-6 p-6">
            <header className="overflow-hidden rounded-[2rem] bg-slate-950 p-8 text-white shadow-xl">
                <div className="flex flex-wrap items-start justify-between gap-6">
                    <div>
                        <div className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.22em] text-cyan-300"><BarChart3 size={16} /> Analisis institucional agregado</div>
                        <h1 className="text-3xl font-black tracking-tight">Explorador de la sabana semanal</h1>
                        <p className="mt-2 max-w-2xl text-sm text-slate-300">Consulta patrones consolidados de seguridad. Esta vista no muestra personas, direcciones ni registros individuales.</p>
                    </div>
                    <button type="button" onClick={load} className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-3 text-xs font-black uppercase tracking-wider hover:bg-white/20"><RefreshCcw size={15} className={loading ? 'animate-spin' : ''} /> Actualizar</button>
                </div>
            </header>

            <section className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-indigo-100 bg-indigo-50 p-5"><p className="text-[10px] font-black uppercase tracking-widest text-indigo-600">Hechos analizados</p><p className="mt-2 text-3xl font-black text-indigo-950">{number(data?.summary?.total)}</p></div>
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-5"><p className="text-[10px] font-black uppercase tracking-widest text-emerald-600">Fecha de corte</p><p className="mt-2 text-2xl font-black text-emerald-950">{data?.summary?.corte || 'Sin dato'}</p></div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5"><p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Nivel de consulta</p><p className="mt-2 text-lg font-black text-slate-800">{data?.access?.label || 'Institucional'}</p></div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 text-sm font-black uppercase tracking-widest text-slate-700"><Filter size={16} /> Filtros de analisis</h2><p className="mt-1 text-sm text-slate-500">{detailed ? 'Los filtros producen resultados agregados.' : 'Tu rol consulta el panorama agregado; los cruces detallados estan reservados para analistas.'}</p></div>{!detailed && <LockKeyhole size={20} className="text-slate-400" />}</div>
                <div className="grid gap-3 md:grid-cols-4">
                    <select value={filters.year} onChange={(event) => setFilter('year', event.target.value)} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-bold text-slate-700"><option value="">Todos los anos</option>{catalog.years.map((item) => <option key={item} value={item}>{item}</option>)}</select>
                    {detailed && <select value={filters.conducta} onChange={(event) => setFilter('conducta', event.target.value)} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-bold text-slate-700"><option value="">Todas las conductas</option>{catalog.conductas.map((item) => <option key={item} value={item}>{item}</option>)}</select>}
                    {detailed && <select value={filters.zona} onChange={(event) => setFilter('zona', event.target.value)} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-bold text-slate-700"><option value="">Todas las zonas</option>{catalog.zonas.map((item) => <option key={item} value={item}>{item}</option>)}</select>}
                    {detailed && <select value={filters.semana} onChange={(event) => setFilter('semana', event.target.value)} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-bold text-slate-700"><option value="">Todas las semanas</option>{catalog.semanas.map((item) => <option key={item} value={item}>Semana {item}</option>)}</select>}
                </div>
            </section>

            {error && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm font-bold text-amber-800">{error}</div>}
            <div className="grid gap-6 lg:grid-cols-2">
                <BarList title="Conductas con mayor registro" items={data?.breakdowns?.conductas} tone="bg-indigo-500" />
                <BarList title="Comportamiento por semana" items={data?.breakdowns?.semanas} tone="bg-cyan-500" />
                <BarList title="Territorios con mayor registro" items={data?.breakdowns?.barrios} tone="bg-emerald-500" />
                <BarList title="Zonas" items={data?.breakdowns?.zonas} tone="bg-amber-500" />
                {detailed && <BarList title="Modalidades" items={data?.breakdowns?.modalidades} tone="bg-fuchsia-500" />}
                {detailed && <BarList title="Armas o medios" items={data?.breakdowns?.armas_medios} tone="bg-rose-500" />}
                {detailed && <BarList title="Grupos de edad" items={data?.breakdowns?.grupos_edad} tone="bg-violet-500" />}
                {detailed && <BarList title="Sexo registrado" items={data?.breakdowns?.sexo} tone="bg-sky-500" />}
            </div>
            <footer className="flex gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600"><ShieldCheck className="shrink-0 text-emerald-600" size={20} /><p>Fuente: sabana semanal de Policia. Los resultados se calculan sobre la base maestra consolidada y se presentan como conteos agregados.</p></footer>
        </div>
    );
};

export default PoliceWeeklyExplorer;
