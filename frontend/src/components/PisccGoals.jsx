import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import { formatVersusLastYear, goalReading } from '../utils/pisccGoals';

const STATUS_STYLES = {
    DESVIACION: 'bg-amber-100 text-amber-900',
    SUPERADA: 'bg-red-100 text-red-800',
    EN_META: 'bg-emerald-50 text-emerald-800',
    PRELIMINAR: 'bg-slate-100 text-slate-600',
    SIN_DATOS: 'bg-slate-100 text-slate-500',
};

const formatDate = (value) => new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`));
const number = (value) => new Intl.NumberFormat('es-CO').format(value);

/** Metas de resultado del PISCC 2024-2027 (tabla 16): cada indicador con su fuente y su corte. */
const PisccGoals = () => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        let alive = true;
        apiJson('/observatory/piscc-goals').then((result) => alive && setData(result)).catch((loadError) => alive && setError(loadError.message));
        return () => { alive = false; };
    }, []);

    if (error) return <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Calculando…</p>;

    return (
        <div className="space-y-4">
            <p className="text-sm font-semibold text-slate-600">
                {data.source}. La meta es la cifra anual a la que el plan quiere llegar en 2027; aquí se compara con el ritmo del año en curso.
            </p>
            <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse bg-white text-sm shadow-sm">
                    <thead>
                        <tr className="border-b border-slate-200 text-left text-[11px] font-black uppercase tracking-wide text-slate-500">
                            <th className="px-3 py-2">Indicador</th>
                            <th className="px-3 py-2 text-right">Línea base 2023</th>
                            <th className="px-3 py-2 text-right">Meta 2027</th>
                            <th className="px-3 py-2 text-right">Año en curso</th>
                            <th className="px-3 py-2">Lectura</th>
                            <th className="px-3 py-2">Fuente y corte</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.indicators.map((item) => (
                            <tr key={item.id} className="border-b border-slate-100 align-top">
                                <td className="px-3 py-3 font-black text-slate-950">{item.label}</td>
                                <td className="px-3 py-3 text-right font-semibold tabular-nums text-slate-600">{number(item.baseline_2023)}</td>
                                <td className="px-3 py-3 text-right font-black tabular-nums text-slate-950">{number(item.goal_2027)}</td>
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
                        ))}
                    </tbody>
                </table>
            </div>
            <p className="text-xs font-semibold text-slate-500">{data.note}</p>
        </div>
    );
};

export default PisccGoals;
