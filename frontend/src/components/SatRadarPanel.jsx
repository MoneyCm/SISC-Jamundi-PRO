import React, { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, EyeOff, ExternalLink, FileWarning, Loader2, Radar, RefreshCw, ShieldAlert } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const numberFormat = new Intl.NumberFormat('es-CO');
const fmt = (value) => numberFormat.format(Number(value) || 0);
const fmtPct = (value) => (value == null ? 'sin base' : `${value > 0 ? '+' : ''}${String(value).replace('.', ',')}%`);
const fmtDate = (value) => new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`));

const SIGNAL_STYLES = {
    DIVERGENCIA: 'border-l-[#281FD0]',
    LETALIDAD: 'border-l-red-600',
    HOMICIDIO_CONCENTRADO: 'border-l-red-600',
    AUMENTO_TERRITORIAL: 'border-l-amber-500',
    CONDUCTA_ADVERTIDA: 'border-l-amber-500',
    DESPLAZAMIENTO_URBANO: 'border-l-slate-900',
};

const GROUP_ORDER = ['AT', 'SECTOR_AT', 'RURAL_NO_AT', 'URBANO'];

const SatRadarPanel = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const load = async () => {
        setLoading(true);
        setError('');
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/intelligence/sat-radar`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!response.ok) throw new Error(`No se pudo consultar el radar (${response.status}).`);
            setData(await response.json());
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    if (loading && !data) {
        return (
            <section className="flex items-center justify-center gap-3 rounded-3xl border border-slate-100 bg-white py-16 text-sm font-bold text-slate-500">
                <Loader2 className="animate-spin text-[#281FD0]" size={20} /> Cruzando alertas de la Defensoría con la sábana policial…
            </section>
        );
    }
    if (error || !data) {
        return (
            <section className="rounded-3xl border border-red-100 bg-red-50 p-6 text-sm font-bold text-red-700">
                {error || 'El radar no devolvió datos.'} <button onClick={load} className="ml-2 underline">Reintentar</button>
            </section>
        );
    }
    if (data.status !== 'OK') {
        return <section className="rounded-3xl border border-slate-100 bg-white p-6 text-sm font-semibold text-slate-600">{data.reason}</section>;
    }

    const { generated_for: period, groups, territories, signals, advised_conducts: advised, blind_spots: blind, forensic_homicides: forensic, data_quality: quality } = data;
    const years = period.windows.map((window) => String(window.year));
    const firstYear = years[0];
    const currentYear = years[years.length - 1];
    const groupsByKey = Object.fromEntries(groups.map((group) => [group.key, group]));
    const forensicChart = (forensic?.definitive_series || []).map((row) => ({ year: String(row.year), Cabecera: row.cabecera, Rural: row.rural }));
    const notMeasured = advised.filter((item) => !item.measurable);

    return (
        <section className="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <p className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#281FD0]"><Radar size={15} /> Alertas tempranas de la Defensoría del Pueblo × hechos del SISC</p>
                    <h2 className="mt-2 text-2xl font-black text-slate-950">¿Se está cumpliendo lo que advirtió la Defensoría?</h2>
                    <p className="mt-2 max-w-3xl text-sm font-medium leading-6 text-slate-600">
                        Cruza los territorios y conductas de las Alertas Tempranas para Jamundí con los hechos de la sábana policial y los homicidios de Medicina Legal.
                        Ventana comparable: <strong className="text-slate-900">{period.window_label}</strong>; corte {fmtDate(period.cutoff)}.
                    </p>
                </div>
                <button onClick={load} disabled={loading} className="inline-flex shrink-0 items-center gap-2 self-start rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
                    <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Recalcular
                </button>
            </header>

            <div className="grid gap-3 md:grid-cols-2">
                {data.alerts.map((alert) => (
                    <a key={alert.id} href={alert.url} target="_blank" rel="noopener noreferrer" className="group rounded-2xl border border-slate-200 p-4 transition hover:border-[#281FD0]/40 hover:bg-slate-50">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <p className="text-xs font-black uppercase tracking-wide text-slate-500">AT {alert.numero} · {alert.tipo}</p>
                                <p className="mt-1 text-sm font-bold text-slate-900">{fmtDate(alert.fecha_emision)} · {alert.estado}</p>
                            </div>
                            <ExternalLink size={15} className="shrink-0 text-slate-400 group-hover:text-[#281FD0]" />
                        </div>
                        <p className="mt-2 text-xs font-medium leading-5 text-slate-600">{alert.actor}. {alert.ambito}.</p>
                        {alert.territorios_oficiales?.length > 0 && (
                            <p className="mt-2 text-xs font-semibold leading-5 text-slate-700">Territorios: {alert.territorios_oficiales.join(', ')}.</p>
                        )}
                    </a>
                ))}
            </div>

            {signals.length > 0 && (
                <div>
                    <h3 className="mb-3 text-sm font-black uppercase tracking-wide text-slate-900">Hallazgos</h3>
                    <div className="grid gap-3 lg:grid-cols-2">
                        {signals.map((signal, index) => (
                            <article key={`${signal.kind}-${index}`} className={`rounded-xl border border-slate-200 border-l-4 bg-slate-50/60 p-4 ${SIGNAL_STYLES[signal.kind] || 'border-l-slate-400'}`}>
                                <p className="text-sm font-black text-slate-950">{signal.title}</p>
                                <p className="mt-1 text-xs font-medium leading-5 text-slate-600">{signal.detail}</p>
                            </article>
                        ))}
                    </div>
                </div>
            )}

            <div className="grid gap-6 xl:grid-cols-2">
                <div>
                    <h3 className="text-sm font-black uppercase tracking-wide text-slate-900">Hechos registrados por zona</h3>
                    <p className="mt-1 text-xs font-medium text-slate-500">Sábana SIEDCO, un hecho por identidad. Cambio de {firstYear} a {currentYear}; cada zona con su propia escala para comparar tendencias.</p>
                    <div className="mt-4 space-y-4">
                        {GROUP_ORDER.map((key) => {
                            const group = groupsByKey[key];
                            if (!group) return null;
                            const change = group.variation_vs_first_pct ?? group.variation_pct;
                            const groupMax = Math.max(1, ...years.map((year) => group.series[year] || 0));
                            return (
                                <div key={key}>
                                    <div className="flex items-baseline justify-between gap-3">
                                        <p className="text-xs font-bold text-slate-800">{group.label}</p>
                                        <p className={`text-xs font-black ${change > 0 ? 'text-red-600' : change < 0 ? 'text-emerald-700' : 'text-slate-500'}`}>{fmtPct(change)}</p>
                                    </div>
                                    <div className="mt-1.5 space-y-1">
                                        {years.map((year) => (
                                            <div key={year} className="flex items-center gap-2">
                                                <span className="w-9 text-[10px] font-bold text-slate-400">{year}</span>
                                                <div className="h-2.5 flex-1 rounded-sm bg-slate-100">
                                                    <div className={`h-2.5 rounded-sm ${key === 'AT' || key === 'SECTOR_AT' ? 'bg-[#281FD0]' : 'bg-slate-400'}`} style={{ width: `${Math.max(1.5, ((group.series[year] || 0) / groupMax) * 100)}%` }} />
                                                </div>
                                                <span className="w-9 text-right text-[11px] font-bold tabular-nums text-slate-700">{fmt(group.series[year])}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {forensicChart.length > 0 && (
                    <div>
                        <h3 className="text-sm font-black uppercase tracking-wide text-slate-900">Homicidios por zona · Medicina Legal</h3>
                        <p className="mt-1 text-xs font-medium text-slate-500">Fuente independiente de la Policía. Cifras definitivas por año.</p>
                        <div className="mt-3 h-64">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={forensicChart} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                                    <CartesianGrid vertical={false} stroke="#E2E8F0" />
                                    <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#64748B' }} tickLine={false} axisLine={false} />
                                    <YAxis tick={{ fontSize: 10, fill: '#64748B' }} tickLine={false} axisLine={false} allowDecimals={false} />
                                    <Tooltip cursor={{ fill: '#F1F5F9' }} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                                    <Legend wrapperStyle={{ fontSize: 11 }} iconType="square" />
                                    <Bar dataKey="Cabecera" stackId="h" fill="#281FD0" />
                                    <Bar dataKey="Rural" stackId="h" fill="#94A3B8" radius={[3, 3, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        {forensic.preliminary_comparable && (
                            <p className="mt-2 text-xs font-medium leading-5 text-slate-600">
                                Preliminar {forensic.preliminary_comparable.months}:{' '}
                                {forensic.preliminary_comparable.years.map((row) => `${row.year}: ${fmt(row.total)} (${fmt(row.cabecera)} en cabecera)`).join(' · ')}
                                {' '}({fmtPct(forensic.preliminary_comparable.variation_pct)}).
                                {forensic.explosive_homicides_preliminary > 0 && ` ${fmt(forensic.explosive_homicides_preliminary)} homicidios con artefacto explosivo en el registro preliminar.`}
                            </p>
                        )}
                    </div>
                )}
            </div>

            <div>
                <h3 className="text-sm font-black uppercase tracking-wide text-slate-900">Territorios y corredores advertidos</h3>
                <div className="mt-3 overflow-x-auto">
                    <table className="w-full min-w-[560px] text-left text-xs">
                        <thead>
                            <tr className="border-b border-slate-200 text-[10px] font-black uppercase tracking-wide text-slate-500">
                                <th className="py-2 pr-3">Territorio</th>
                                {years.map((year) => <th key={year} className="py-2 pr-3 text-right">{year}</th>)}
                                <th className="py-2 pr-3 text-right">vs {years[years.length - 2]}</th>
                                <th className="py-2">Predomina en {currentYear}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {territories.map((item) => (
                                <tr key={item.name} className="border-b border-slate-100">
                                    <td className="py-2 pr-3 font-bold text-slate-900">
                                        {item.name}
                                        {item.group === 'SECTOR_AT' && <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-black uppercase text-slate-500">sector</span>}
                                    </td>
                                    {years.map((year) => <td key={year} className="py-2 pr-3 text-right font-semibold tabular-nums text-slate-700">{fmt(item.series[year])}</td>)}
                                    <td className={`py-2 pr-3 text-right font-black tabular-nums ${item.variation_pct > 0 ? 'text-red-600' : item.variation_pct < 0 ? 'text-emerald-700' : 'text-slate-400'}`}>{fmtPct(item.variation_pct)}</td>
                                    <td className="py-2 font-medium text-slate-600">{item.top_conductas.map((conducta) => `${conducta.label} (${conducta.total})`).join(', ') || '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
                    <p className="flex items-center gap-2 text-sm font-black text-amber-900"><EyeOff size={16} /> Lo que la sábana policial no ve</p>
                    <p className="mt-1 text-xs font-medium leading-5 text-amber-900/80">La Defensoría advirtió conductas que el SIEDCO no registra. Sin estas fuentes, el SISC no puede decir si ocurrieron.</p>
                    <ul className="mt-3 space-y-1.5">
                        {notMeasured.map((item) => (
                            <li key={item.conducta} className="text-xs font-semibold text-amber-950">
                                {item.conducta} <span className="font-medium text-amber-800">→ {item.fuente_sugerida}</span>
                            </li>
                        ))}
                    </ul>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                    <p className="flex items-center gap-2 text-sm font-black text-slate-900"><ShieldAlert size={16} /> Fuentes para cerrar los puntos ciegos</p>
                    <ul className="mt-3 space-y-2">
                        {blind.map((source) => (
                            <li key={source.source} className="flex items-start justify-between gap-3 text-xs">
                                <div>
                                    <p className="font-bold text-slate-900">{source.source}</p>
                                    <p className="font-medium text-slate-500">{source.covers}{source.note ? `. ${source.note}` : ''}</p>
                                </div>
                                <span className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-black uppercase ${source.loaded ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                                    {source.loaded ? `${fmt(source.records)} registros` : source.records ? `${fmt(source.records)} registro(s)` : 'Sin datos'}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>

            <footer className="space-y-2 border-t border-slate-100 pt-4 text-[11px] font-medium leading-5 text-slate-500">
                {quality?.events_with_conflicting_location > 0 && (
                    <p className="flex items-start gap-2 text-slate-700"><FileWarning size={14} className="mt-0.5 shrink-0 text-amber-600" />
                        Calidad de datos: {fmt(quality.events_with_conflicting_location)} hechos aparecen con ubicaciones distintas entre entregas. Aquí se usa una sola versión por hecho ({quality.rule.toLowerCase()})
                    </p>
                )}
                <p className="flex items-start gap-2"><AlertTriangle size={14} className="mt-0.5 shrink-0" /> {data.disclaimer} {data.registry_note} Registro verificado el {fmtDate(data.registry_verified_on)}.</p>
            </footer>
        </section>
    );
};

export default SatRadarPanel;
