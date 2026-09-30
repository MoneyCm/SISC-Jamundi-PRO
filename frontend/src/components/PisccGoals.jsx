import React, { Fragment, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import { formatVersusLastYear, goalReading } from '../utils/pisccGoals';

const STATUS_STYLES = {
    DESVIACION: 'bg-amber-100 text-amber-900',
    SUPERADA: 'bg-red-100 text-red-800',
    EN_META: 'bg-emerald-50 text-emerald-800',
    PRELIMINAR: 'bg-slate-100 text-slate-600',
    SIN_DATOS: 'bg-slate-100 text-slate-500',
};
// Semáforo de un año cerrado frente a la meta 2027 y la línea base 2023.
const SEMAFORO_STYLES = {
    VERDE: { dot: 'bg-emerald-500', text: 'text-emerald-800' },
    AMARILLO: { dot: 'bg-amber-400', text: 'text-amber-900' },
    ROJO: { dot: 'bg-red-500', text: 'text-red-800' },
};

const formatDate = (value) => new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`));
const number = (value) => new Intl.NumberFormat('es-CO').format(value);
const pct = (value) => `${String(value ?? 0).replace('.', ',')} %`;
const titleCase = (text) => String(text || '').toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());

const ClosedYear = ({ year }) => {
    if (year.total === null || year.total === undefined) {
        return <span className="text-xs font-semibold text-slate-400">{year.semaforo_label}</span>;
    }
    const style = SEMAFORO_STYLES[year.semaforo];
    return (
        <span title={year.semaforo_label} className="inline-flex flex-col items-end">
            <span className="inline-flex items-center gap-1.5 font-black tabular-nums text-slate-950">
                {style && <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} aria-hidden="true" />}
                {number(year.total)}
            </span>
            <span className={`text-[10px] font-bold leading-tight ${style ? style.text : 'text-slate-400'}`}>{year.semaforo_label}</span>
        </span>
    );
};

/** Lo que se despliega al hacer clic en una meta: meses por año y, según la fuente, barrios, horario o comportamientos. */
const GoalDetail = ({ goalId }) => {
    const [detail, setDetail] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        let alive = true;
        apiJson(`/observatory/piscc-goals/${goalId}/detalle`).then((result) => alive && setDetail(result)).catch((loadError) => alive && setError(loadError.message));
        return () => { alive = false; };
    }, [goalId]);

    if (error) return <p role="alert" className="text-sm font-bold text-red-800">{error}</p>;
    if (!detail) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Cargando detalle…</p>;

    const series = detail.series || [];
    return (
        <div className="space-y-4">
            {series.length > 0 && (
                <div>
                    <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">Mes a mes</p>
                    <div className="mt-2 overflow-x-auto">
                        <table className="w-full min-w-[640px] text-xs">
                            <thead>
                                <tr className="text-left text-slate-500">
                                    <th className="py-1 pr-2 font-black">Año</th>
                                    {detail.meses.map((mes) => <th key={mes} className="py-1 px-1 text-right font-black">{mes}</th>)}
                                    <th className="py-1 pl-2 text-right font-black">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                {series.map((serie) => {
                                    const conDatos = serie.valores.filter((valor) => valor !== null && valor !== undefined);
                                    return (
                                        <tr key={serie.anio} className="border-t border-slate-200">
                                            <td className="py-1.5 pr-2 font-black text-slate-900">{serie.anio}</td>
                                            {serie.valores.map((valor, index) => (
                                                <td key={index} className="py-1.5 px-1 text-right tabular-nums text-slate-700">{valor === null || valor === undefined ? '—' : number(valor)}</td>
                                            ))}
                                            <td className="py-1.5 pl-2 text-right font-black tabular-nums text-slate-950">{conDatos.length ? number(conDatos.reduce((a, b) => a + b, 0)) : '—'}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    <p className="mt-1 text-[11px] font-semibold text-slate-500">Fuente: {detail.fuente_series}. Un mes con «—» todavía no está publicado.</p>
                </div>
            )}

            {detail.comportamientos?.length > 0 && (
                <div>
                    <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">Comportamientos más frecuentes</p>
                    <ul className="mt-2 space-y-2">
                        {detail.comportamientos.map((item) => (
                            <li key={item.articulo} title={item.texto_oficial}>
                                <div className="flex justify-between gap-3 text-sm">
                                    <span className="font-bold text-slate-800">{item.etiqueta} <span className="font-semibold text-slate-400">(art. {item.articulo})</span></span>
                                    <span className="whitespace-nowrap font-black tabular-nums text-slate-950">{number(item.total)} · {pct(item.porcentaje)}</span>
                                </div>
                                <div className="mt-1 h-2 rounded-full bg-slate-200"><div className="h-2 rounded-full bg-[#281FD0]" style={{ width: `${Math.max(item.porcentaje, 1)}%` }} /></div>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
                {detail.barrios?.length > 0 && (
                    <div>
                        <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">Barrios con más casos este año</p>
                        <ol className="mt-2 space-y-1 text-sm">
                            {detail.barrios.map((barrio, index) => (
                                <li key={barrio.nombre} className="flex justify-between gap-3">
                                    <span className="font-semibold text-slate-800">{index + 1}. {titleCase(barrio.nombre)}{barrio.principal && <span className="block text-xs font-semibold text-slate-500">Sobre todo: {barrio.principal.charAt(0).toLowerCase() + barrio.principal.slice(1)}</span>}</span>
                                    <span className="font-black tabular-nums text-slate-950">{number(barrio.total)}</span>
                                </li>
                            ))}
                        </ol>
                    </div>
                )}
                {detail.franjas?.length > 0 && (
                    <div>
                        <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">Horario de los hechos este año</p>
                        <ul className="mt-2 space-y-1 text-sm">
                            {detail.franjas.map((franja) => (
                                <li key={franja.nombre} className="flex justify-between gap-3"><span className="font-semibold text-slate-800">{franja.nombre}</span><span className="font-black tabular-nums text-slate-950">{number(franja.total)}</span></li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
            {detail.fuente_detalle && <p className="text-[11px] font-semibold text-slate-500">Barrios y horario: {detail.fuente_detalle}.</p>}
            {detail.nota && <p className="text-xs font-semibold text-amber-800">{detail.nota}</p>}
        </div>
    );
};

/** Metas de resultado del PISCC 2024-2027 (tabla 16): cada indicador con su fuente y su corte. */
const PisccGoals = () => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [open, setOpen] = useState('');

    useEffect(() => {
        let alive = true;
        apiJson('/observatory/piscc-goals').then((result) => alive && setData(result)).catch((loadError) => alive && setError(loadError.message));
        return () => { alive = false; };
    }, []);

    if (error) return <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Calculando…</p>;

    const closedYears = data.indicators[0]?.closed_years?.map((year) => year.anio) || [];
    const columns = 7 + closedYears.length;
    return (
        <div className="space-y-4">
            <p className="text-sm font-semibold text-slate-600">
                {data.source}. La meta es la cifra anual a la que el plan quiere llegar en 2027. Haga clic en un indicador para ver el detalle.
            </p>
            {/* Celular: una tarjeta por meta, con los años y su semáforo a la vista; el detalle se abre al tocarla. */}
            <div className="space-y-3 md:hidden">
                {data.indicators.map((item) => {
                    const isOpen = open === item.id;
                    return (
                        <div key={item.id} className="border border-slate-200 bg-white shadow-sm">
                            <button type="button" onClick={() => setOpen(isOpen ? '' : item.id)} aria-expanded={isOpen} className="w-full p-3 text-left">
                                <div className="flex items-start justify-between gap-2">
                                    <p className="text-base font-black text-[#281FD0]">{item.label}</p>
                                    {isOpen ? <ChevronDown size={18} className="mt-0.5 shrink-0 text-slate-400" /> : <ChevronRight size={18} className="mt-0.5 shrink-0 text-slate-400" />}
                                </div>
                                <p className="mt-0.5 text-xs font-semibold text-slate-500">Meta 2027: <b className="text-slate-900">{number(item.goal_2027)}</b> · Línea base 2023: {number(item.baseline_2023)}</p>
                                <div className="mt-3 grid grid-cols-3 gap-2">
                                    {(item.closed_years || []).map((year) => (
                                        <div key={year.anio} className="bg-slate-50 p-2">
                                            <p className="text-[11px] font-black text-slate-500">{year.anio}</p>
                                            {year.total === null || year.total === undefined ? (
                                                <p className="text-xs font-semibold text-slate-400">Sin dato</p>
                                            ) : (
                                                <p className="flex items-center gap-1.5 text-lg font-black tabular-nums text-slate-950">
                                                    {SEMAFORO_STYLES[year.semaforo] && <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${SEMAFORO_STYLES[year.semaforo].dot}`} aria-hidden="true" />}
                                                    {number(year.total)}
                                                </p>
                                            )}
                                        </div>
                                    ))}
                                    <div className="bg-slate-50 p-2">
                                        <p className="text-[11px] font-black text-slate-500">Este año</p>
                                        <p className="text-lg font-black tabular-nums text-slate-950">{item.count === undefined ? '—' : number(item.count)}</p>
                                    </div>
                                </div>
                                <p className="mt-2"><span className={`inline-block px-2 py-0.5 text-[11px] font-black uppercase ${STATUS_STYLES[item.status]}`}>{item.status_label}</span></p>
                                <p className="mt-1 text-xs font-semibold leading-5 text-slate-600">{goalReading(item)}</p>
                                {item.cutoff && <p className="mt-1 text-[11px] font-semibold text-slate-500">{item.source} · hasta el {formatDate(item.cutoff)}</p>}
                            </button>
                            {isOpen && <div className="border-t border-slate-200 bg-slate-50 p-3"><GoalDetail goalId={item.id} /></div>}
                        </div>
                    );
                })}
            </div>
            <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[900px] border-collapse bg-white text-sm shadow-sm">
                    <thead>
                        <tr className="border-b border-slate-200 text-left text-[11px] font-black uppercase tracking-wide text-slate-500">
                            <th className="w-6 px-2 py-2" aria-label="Desplegar" />
                            <th className="px-3 py-2">Indicador</th>
                            <th className="px-3 py-2 text-right">Línea base 2023</th>
                            <th className="px-3 py-2 text-right">Meta 2027</th>
                            {closedYears.map((year) => <th key={year} className="px-3 py-2 text-right">{year}</th>)}
                            <th className="px-3 py-2 text-right">Año en curso</th>
                            <th className="px-3 py-2">Lectura</th>
                            <th className="px-3 py-2">Fuente y corte</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.indicators.map((item) => {
                            const isOpen = open === item.id;
                            return (
                                <Fragment key={item.id}>
                                    <tr
                                        className={`cursor-pointer border-b border-slate-100 align-top hover:bg-slate-50 ${isOpen ? 'bg-slate-50' : ''}`}
                                        onClick={() => setOpen(isOpen ? '' : item.id)}
                                        aria-expanded={isOpen}
                                    >
                                        <td className="px-2 py-3 text-slate-400">{isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</td>
                                        <td className="px-3 py-3 font-black text-[#281FD0] underline-offset-2 hover:underline">{item.label}</td>
                                        <td className="px-3 py-3 text-right font-semibold tabular-nums text-slate-600">{number(item.baseline_2023)}</td>
                                        <td className="px-3 py-3 text-right font-black tabular-nums text-slate-950">{number(item.goal_2027)}</td>
                                        {(item.closed_years || []).map((year) => <td key={year.anio} className="px-3 py-3 text-right"><ClosedYear year={year} /></td>)}
                                        <td className="px-3 py-3 text-right tabular-nums">
                                            {item.count === undefined ? '—' : (
                                                <>
                                                    <span className="font-black text-slate-950">{number(item.count)}</span>
                                                    <span className="block text-xs font-semibold text-slate-500">{formatVersusLastYear(item)}</span>
                                                </>
                                            )}
                                        </td>
                                        <td className="px-3 py-3">
                                            <span className={`inline-block px-2 py-0.5 text-[11px] font-black uppercase ${STATUS_STYLES[item.status]}`}>{item.status_label}</span>
                                            <p className="mt-1 text-xs font-semibold leading-5 text-slate-600">{goalReading(item)}</p>
                                        </td>
                                        <td className="px-3 py-3 text-xs font-semibold leading-5 text-slate-600">
                                            {item.source || '—'}
                                            {item.cutoff && <span className="block">Hasta el {formatDate(item.cutoff)}</span>}
                                            {item.stale && <span className="block font-black text-amber-800">Corte con {item.lag_days} días de atraso</span>}
                                        </td>
                                    </tr>
                                    {isOpen && (
                                        <tr className="border-b border-slate-200 bg-slate-50">
                                            <td colSpan={columns} className="px-5 py-4"><GoalDetail goalId={item.id} /></td>
                                        </tr>
                                    )}
                                </Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            {data.closed_years_legend && (
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs font-semibold text-slate-600">
                    {Object.entries(data.closed_years_legend).map(([key, label]) => (
                        <span key={key} className="inline-flex items-center gap-1.5"><span className={`h-2.5 w-2.5 rounded-full ${SEMAFORO_STYLES[key].dot}`} aria-hidden="true" />{label}</span>
                    ))}
                </div>
            )}
            <p className="text-xs font-semibold text-slate-500">
                Años cerrados: {data.closed_years_source} (la misma fuente de la línea base 2023). {data.note}
            </p>
        </div>
    );
};

export default PisccGoals;
