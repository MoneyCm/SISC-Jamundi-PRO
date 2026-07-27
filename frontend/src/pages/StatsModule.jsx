import React, { useState, useEffect, useCallback } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    LineChart, Line, AreaChart, Area, Cell, PieChart, Pie, Legend
} from 'recharts';
import {
    Activity, Skull, Users, HeartPulse, ShieldAlert, Phone,
    ChevronRight, Filter, Loader, TrendingDown, TrendingUp, Minus,
    MapPin, Calendar, RefreshCcw
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const COLORS_YEAR = { v2025: '#00b4ff', v2026: '#ffa500' };
const PRIMARY = '#281FD0';
const ACCENT  = '#FFE000';

const CATEGORY_KEYS = {
    homicidios:    ['HOMICIDIO', 'Homicidio'],
    lesiones:      ['LESIONES', 'Lesiones personales'],
    hurtos:        ['HURTO_PERSONAS', 'Hurto a personas', 'HURTO_MOTOS', 'Hurto a motocicletas',
                    'HURTO_AUTOMOTORES', 'Hurto a automotores', 'HURTO_COMERCIO', 'Hurto a comercio',
                    'HURTO_RESIDENCIAS', 'Hurto a residencias'],
    hurto_pers:    ['HURTO_PERSONAS', 'Hurto a personas'],
    hurto_veh:     ['HURTO_MOTOS', 'Hurto a motocicletas', 'HURTO_AUTOMOTORES', 'Hurto a automotores'],
    hurto_com:     ['HURTO_COMERCIO', 'Hurto a comercio'],
    hurto_res:     ['HURTO_RESIDENCIAS', 'Hurto a residencias'],
};

const categories = [
    { id: 'resumen',    label: 'Resumen General',       icon: Activity   },
    { id: 'homicidios', label: 'Homicidios',            icon: Skull      },
    { id: 'lesiones',   label: 'Lesiones Personales',   icon: HeartPulse },
    { id: 'hurtos',     label: 'Hurtos',                icon: ShieldAlert },
    { id: 'zona',       label: 'Por Zona',              icon: MapPin     },
    { id: 'semanal',    label: 'Análisis Semanal',      icon: Calendar   },
];

// ─── helpers ───────────────────────────────────────────────────────────────
const fmt = (n) => n?.toLocaleString('es-CO') ?? '—';

const DeltaBadge = ({ v1, v2 }) => {
    if (v2 == null || v2 === 0) return null;
    const pct = (((v1 - v2) / v2) * 100).toFixed(1);
    const up  = v1 > v2;
    const eq  = v1 === v2;
    const color = eq ? 'text-slate-400' : up ? 'text-red-500' : 'text-emerald-500';
    const Icon  = eq ? Minus : up ? TrendingUp : TrendingDown;
    return (
        <span className={`inline-flex items-center gap-1 text-[10px] font-black ${color}`}>
            <Icon size={12} /> {pct}%
        </span>
    );
};

const KpiCard = ({ label, value2026, value2025, color = PRIMARY }) => (
    <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 flex flex-col gap-2">
        <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">{label}</p>
        <p className="text-3xl font-black" style={{ color }}>{fmt(value2026)}</p>
        <div className="flex items-center gap-2">
            <span className="text-[10px] text-slate-400">vs {value2025 ?? '—'} en 2025</span>
            <DeltaBadge v1={value2026} v2={value2025} />
        </div>
    </div>
);

// ─── main component ────────────────────────────────────────────────────────
const StatsModule = ({ userRoles = [] }) => {
    const [selectedCategory, setSelectedCategory] = useState('resumen');
    const [loading, setLoading]   = useState(false);
    const [kpis2026,  setKpis2026]  = useState(null);
    const [kpis2025,  setKpis2025]  = useState(null);
    const [tendencia, setTendencia] = useState([]);
    const [semanal,   setSemanal]   = useState([]);
    const [distribucion, setDistribucion] = useState([]);
    const [zonas, setZonas]         = useState([]);
    const [barrios, setBarrios]     = useState([]);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [error, setError]         = useState(null);

    const token = localStorage.getItem('token');
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    const fetchAll = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const base = API_BASE_URL;

            const [metaRes, kpi26Res, kpi25Res, tendRes, sem26Res, sem25Res, distRes, zonaRes, barriosRes] = await Promise.all([
                fetch(`${base}/analitica/estadisticas/ultima-actualizacion`, { headers }),
                fetch(`${base}/analitica/estadisticas/kpis?start_date=2026-01-01&end_date=2026-12-31`, { headers }),
                fetch(`${base}/analitica/estadisticas/kpis?start_date=2025-01-01&end_date=2025-12-31`, { headers }),
                fetch(`${base}/analitica/estadisticas/tendencia`, { headers }),
                fetch(`${base}/analitica/estadisticas/por-semana?anio=2026`, { headers }),
                fetch(`${base}/analitica/estadisticas/por-semana?anio=2025`, { headers }),
                fetch(`${base}/analitica/estadisticas/distribucion`, { headers }),
                fetch(`${base}/analitica/estadisticas/por-zona`, { headers }),
                fetch(`${base}/analitica/estadisticas/barrios`, { headers }),
            ]);

            const [meta, k26, k25, tend, s26, s25, dist, zona, barr] = await Promise.all([
                metaRes.ok  ? metaRes.json()  : null,
                kpi26Res.ok ? kpi26Res.json() : null,
                kpi25Res.ok ? kpi25Res.json() : null,
                tendRes.ok  ? tendRes.json()  : [],
                sem26Res.ok ? sem26Res.json() : [],
                sem25Res.ok ? sem25Res.json() : [],
                distRes.ok  ? distRes.json()  : [],
                zonaRes.ok  ? zonaRes.json()  : [],
                barriosRes.ok ? barriosRes.json() : [],
            ]);

            setLastUpdate(meta);
            setKpis2026(k26);
            setKpis2025(k25);
            setTendencia(tend);
            setDistribucion(dist);
            setZonas(zona);
            setBarrios(barr);

            // Merge semanas: [{ semana, v2025, v2026 }]
            const map25 = Object.fromEntries((s25 || []).map(r => [r.semana, r]));
            const map26 = Object.fromEntries((s26 || []).map(r => [r.semana, r]));
            const allWeeks = [...new Set([...Object.keys(map25), ...Object.keys(map26)])].map(Number).sort((a,b)=>a-b);
            setSemanal(allWeeks.map(w => ({
                semana: `S${w}`,
                v2025: map25[w]?.total ?? 0,
                v2026: map26[w]?.total ?? 0,
                hom25: map25[w]?.homicidios ?? 0,
                hom26: map26[w]?.homicidios ?? 0,
            })));

        } catch(e) {
            setError('Error cargando datos de analítica.');
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    // ── Vista: Resumen General ──────────────────────────────────────────────
    const ViewResumen = () => (
        <div className="space-y-6 animate-fade-in">
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
                <KpiCard label="Total Hechos"       value2026={kpis2026?.total_incidentes} value2025={kpis2025?.total_incidentes} />
                <KpiCard label="Homicidios"         value2026={kpis2026?.homicidios}       value2025={kpis2025?.homicidios}       color="#ef4444" />
                <KpiCard label="Hurto Personas"     value2026={kpis2026?.hurto_personas}   value2025={kpis2025?.hurto_personas}   color="#f97316" />
                <KpiCard label="Hurto Vehículos"    value2026={kpis2026?.hurto_vehiculos}  value2025={kpis2025?.hurto_vehiculos}  color="#8b5cf6" />
                <KpiCard label="Lesiones"           value2026={kpis2026?.lesiones}         value2025={kpis2025?.lesiones}         color="#06b6d4" />
                <KpiCard label="Tasa Homic/100k"    value2026={kpis2026?.tasa_homicidios}  value2025={kpis2025?.tasa_homicidios}  color="#ef4444" />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {/* Distribución */}
                <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                    <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">Distribución por Delito</h3>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={distribucion} layout="vertical" margin={{ left: 20 }}>
                            <XAxis type="number" hide />
                            <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 700 }} width={110} />
                            <Tooltip formatter={(v) => [fmt(v), 'Hechos']} />
                            <Bar dataKey="value" fill={PRIMARY} radius={[0, 6, 6, 0]} label={{ position: 'right', fontSize: 10, fontWeight: 700 }} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* Tendencia mensual */}
                <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                    <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">Tendencia Mensual</h3>
                    <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={tendencia}>
                            <defs>
                                <linearGradient id="gradH" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="gradO" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%"  stopColor={PRIMARY} stopOpacity={0.2} />
                                    <stop offset="95%" stopColor={PRIMARY} stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 700 }} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                            <Tooltip />
                            <Area type="monotone" dataKey="homicidios" stroke="#ef4444" fill="url(#gradH)" strokeWidth={2} name="Homicidios" />
                            <Area type="monotone" dataKey="hurtos"     stroke={PRIMARY}  fill="url(#gradO)" strokeWidth={2} name="Otros" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );

    // ── Vista: Homicidios ───────────────────────────────────────────────────
    const ViewHomicidios = () => {
        const semHom = semanal.map(s => ({ semana: s.semana, v2025: s.hom25, v2026: s.hom26 }));
        return (
            <div className="space-y-6 animate-fade-in">
                <div className="grid grid-cols-3 gap-4">
                    <KpiCard label="Homicidios 2026" value2026={kpis2026?.homicidios} value2025={kpis2025?.homicidios} color="#ef4444" />
                    <KpiCard label="Tasa / 100k hab" value2026={kpis2026?.tasa_homicidios} value2025={kpis2025?.tasa_homicidios} color="#ef4444" />
                    <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100">
                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-2">Sem. más crítica (2026)</p>
                        {(() => {
                            const peak = [...semHom].sort((a,b) => b.v2026 - a.v2026)[0];
                            return peak ? (
                                <>
                                    <p className="text-3xl font-black text-red-500">{peak.semana}</p>
                                    <p className="text-[10px] text-slate-400">{peak.v2026} homicidios</p>
                                </>
                            ) : <p className="text-slate-300 text-sm">—</p>;
                        })()}
                    </div>
                </div>
                <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                    <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">Homicidios por Semana: 2025 vs 2026</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={semHom}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                            <XAxis dataKey="semana" axisLine={false} tickLine={false} tick={{ fontSize: 9, fontWeight: 700 }} interval={1} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                            <Tooltip />
                            <Legend formatter={(v) => v === 'v2025' ? '2025' : '2026'} />
                            <Bar dataKey="v2025" fill={COLORS_YEAR.v2025} radius={[4,4,0,0]} name="v2025" />
                            <Bar dataKey="v2026" fill="#ef4444" radius={[4,4,0,0]} name="v2026" />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        );
    };

    // ── Vista: Lesiones ─────────────────────────────────────────────────────
    const ViewLesiones = () => (
        <div className="space-y-6 animate-fade-in">
            <div className="grid grid-cols-2 gap-4">
                <KpiCard label="Lesiones 2026" value2026={kpis2026?.lesiones} value2025={kpis2025?.lesiones} color="#06b6d4" />
                <KpiCard label="Total Hechos 2026" value2026={kpis2026?.total_incidentes} value2025={kpis2025?.total_incidentes} />
            </div>
            <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">Lesiones por Semana: 2025 vs 2026</h3>
                <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={semanal}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                        <XAxis dataKey="semana" axisLine={false} tickLine={false} tick={{ fontSize: 9, fontWeight: 700 }} interval={1} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Legend formatter={(v) => v === 'v2025' ? '2025' : '2026'} />
                        <Line type="monotone" dataKey="v2025" stroke={COLORS_YEAR.v2025} strokeWidth={2} dot={false} name="v2025" />
                        <Line type="monotone" dataKey="v2026" stroke="#06b6d4" strokeWidth={2} dot={false} name="v2026" />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );

    // ── Vista: Hurtos ───────────────────────────────────────────────────────
    const ViewHurtos = () => {
        const hurtoDist = distribucion.filter(d =>
            ['HURTO PERSONAS','HURTO VEHÍCULOS','HURTO COMERCIO','HURTO RESIDENCIAS'].includes(d.name)
        );
        return (
            <div className="space-y-6 animate-fade-in">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <KpiCard label="Hurto Personas"    value2026={kpis2026?.hurto_personas}    value2025={kpis2025?.hurto_personas}    color="#f97316" />
                    <KpiCard label="Hurto Vehículos"   value2026={kpis2026?.hurto_vehiculos}   value2025={kpis2025?.hurto_vehiculos}   color="#8b5cf6" />
                    <KpiCard label="Hurto Comercio"    value2026={kpis2026?.hurto_comercio}    value2025={kpis2025?.hurto_comercio}    color="#eab308" />
                    <KpiCard label="Hurto Residencias" value2026={kpis2026?.hurto_residencias} value2025={kpis2025?.hurto_residencias} color="#ec4899" />
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                    <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                        <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">Distribución de Modalidades</h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <PieChart>
                                <Pie data={hurtoDist} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) => `${name.replace('HURTO ','')}: ${(percent*100).toFixed(0)}%`} labelLine={false}>
                                    {hurtoDist.map((_, i) => (
                                        <Cell key={i} fill={[PRIMARY, '#f97316','#8b5cf6','#ec4899'][i % 4]} />
                                    ))}
                                </Pie>
                                <Tooltip formatter={(v) => [fmt(v), 'Hechos']} />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                        <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">Hurtos Totales por Semana</h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <AreaChart data={semanal}>
                                <defs>
                                    <linearGradient id="gradHurto26" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%"  stopColor="#f97316" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                                <XAxis dataKey="semana" axisLine={false} tickLine={false} tick={{ fontSize: 9, fontWeight: 700 }} interval={2} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                                <Tooltip />
                                <Area type="monotone" dataKey="v2025" stroke={COLORS_YEAR.v2025} fill="none" strokeWidth={2} strokeDasharray="4 4" name="2025" />
                                <Area type="monotone" dataKey="v2026" stroke="#f97316" fill="url(#gradHurto26)" strokeWidth={2} name="2026" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>
        );
    };

    // ── Vista: Por Zona ─────────────────────────────────────────────────────
    const ViewZona = () => (
        <div className="space-y-6 animate-fade-in">
            <div className="grid grid-cols-2 gap-4">
                {zonas.map(z => (
                    <div key={z.zona} className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col gap-2">
                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">{z.zona}</p>
                        <p className="text-4xl font-black text-primary">{fmt(z.total)}</p>
                        <p className="text-[10px] text-slate-400">{((z.total / (kpis2026?.total_incidentes || 1)) * 100).toFixed(1)}% del total</p>
                    </div>
                ))}
            </div>
            <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">Top 10 Barrios / Sectores</h3>
                <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={barrios} layout="vertical" margin={{ left: 20 }}>
                        <XAxis type="number" hide />
                        <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 700 }} width={150} />
                        <Tooltip formatter={(v) => [fmt(v), 'Hechos']} />
                        <Bar dataKey="delitos" fill={PRIMARY} radius={[0, 6, 6, 0]} label={{ position: 'right', fontSize: 10, fontWeight: 700 }} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );

    // ── Vista: Análisis Semanal ─────────────────────────────────────────────
    const ViewSemanal = () => {
        const lastSem26 = [...semanal].filter(s => s.v2026 > 0).pop();
        const lastSem25 = semanal.find(s => s.semana === lastSem26?.semana);
        return (
            <div className="space-y-6 animate-fade-in">
                <div className="grid grid-cols-3 gap-4">
                    <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100">
                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-2">Última Semana (2026)</p>
                        <p className="text-3xl font-black text-primary">{lastSem26?.semana ?? '—'}</p>
                        <p className="text-[10px] text-slate-400">{lastSem26?.v2026 ?? 0} hechos registrados</p>
                    </div>
                    <KpiCard label="Esta semana vs igual sem. 2025" value2026={lastSem26?.v2026 ?? 0} value2025={lastSem25?.v2025 ?? 0} />
                    <KpiCard label="Homicidios última sem." value2026={lastSem26?.hom26 ?? 0} value2025={lastSem26?.hom25 ?? 0} color="#ef4444" />
                </div>
                <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                    <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">Todos los Hechos por Semana — 2025 vs 2026</h3>
                    <ResponsiveContainer width="100%" height={320}>
                        <BarChart data={semanal} barGap={2}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                            <XAxis dataKey="semana" axisLine={false} tickLine={false} tick={{ fontSize: 9, fontWeight: 700 }} interval={1} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                            <Tooltip />
                            <Legend formatter={(v) => v === 'v2025' ? '2025' : '2026'} />
                            <Bar dataKey="v2025" fill={COLORS_YEAR.v2025} radius={[3,3,0,0]} name="v2025" />
                            <Bar dataKey="v2026" fill={COLORS_YEAR.v2026} radius={[3,3,0,0]} name="v2026" />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        );
    };

    const VIEWS = {
        resumen:    ViewResumen,
        homicidios: ViewHomicidios,
        lesiones:   ViewLesiones,
        hurtos:     ViewHurtos,
        zona:       ViewZona,
        semanal:    ViewSemanal,
    };
    const ActiveView = VIEWS[selectedCategory];

    return (
        <div className="flex flex-col bg-[#F2F4F7]" style={{ minHeight: '100%' }}>
            {/* Header */}
            <div className="bg-primary px-6 py-3 flex justify-between items-center shadow-md">
                <div className="flex items-center gap-3">
                    <img src="/assets/escudo.png" alt="Jamundí" className="w-7 h-7 object-contain brightness-0 invert" />
                    <h2 className="text-white font-black text-base uppercase tracking-tighter font-titles">
                        Indicadores de Seguridad
                        <span className="text-white/40 italic font-normal text-xs ml-2">| SIEDCO · Policía Nacional</span>
                    </h2>
                </div>
                <div className="flex items-center gap-3">
                    {lastUpdate && (
                        <div className="text-white/70 text-[9px] font-bold uppercase tracking-widest">
                            Al: {lastUpdate.ultima_fecha} · {fmt(lastUpdate.total_hechos)} registros
                        </div>
                    )}
                    <button onClick={fetchAll} className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition text-white" title="Actualizar">
                        <RefreshCcw size={13} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            {/* Tabs horizontales */}
            <div className="bg-white border-b border-slate-200 shadow-sm px-4">
                <div className="flex overflow-x-auto gap-1 py-2">
                    {categories.map(cat => (
                        <button
                            key={cat.id}
                            onClick={() => setSelectedCategory(cat.id)}
                            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl whitespace-nowrap text-xs font-black uppercase tracking-tight transition-all flex-shrink-0 ${
                                selectedCategory === cat.id
                                    ? 'bg-primary text-white shadow-md shadow-primary/20'
                                    : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                            }`}
                        >
                            <cat.icon size={14} />
                            {cat.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Contenido */}
            <div className="flex-1 p-6 relative">
                {loading && (
                    <div className="absolute inset-0 bg-white/70 backdrop-blur-sm z-50 flex items-center justify-center">
                        <div className="text-center">
                            <Loader size={36} className="text-primary animate-spin mx-auto mb-2" />
                            <p className="text-[10px] font-black text-primary uppercase tracking-[0.2em]">Cargando datos SIEDCO...</p>
                        </div>
                    </div>
                )}
                {error && (
                    <div className="bg-red-50 text-red-600 p-4 rounded-xl text-sm font-bold mb-4 border border-red-100">{error}</div>
                )}
                {!loading && ActiveView && <ActiveView />}
            </div>
        </div>
    );
};

export default StatsModule;
