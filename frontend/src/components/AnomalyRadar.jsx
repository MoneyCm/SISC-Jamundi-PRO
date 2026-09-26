import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

const LEVELS = {
    ALTA: { bar: 'border-red-500', chip: 'bg-red-100 text-red-800', label: 'Muy improbable (< 0,1 %)' },
    MEDIA: { bar: 'border-amber-400', chip: 'bg-amber-100 text-amber-900', label: 'Improbable (< 1 %)' },
};
const RULE_LABELS = { R1: 'Municipio · semana', R2: 'Territorio · 28 días', R3: 'Calidad del dato' };

const formatDate = (value) => new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short' }).format(new Date(`${value}T12:00:00`));

/** Radar de anomalías (uso interno): cifras que se salen de lo esperado, con sus reglas publicadas. */
const AnomalyRadar = ({ onStudy }) => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        let alive = true;
        apiJson('/observatory/anomalies').then((result) => alive && setData(result)).catch((loadError) => alive && setError(loadError.message));
        return () => { alive = false; };
    }, []);

    if (error) return <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Calculando…</p>;
    if (data.status !== 'OK') return <p className="bg-slate-50 p-4 text-sm font-semibold text-slate-600">{data.reason}</p>;

    return (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-3">
                <p className="text-sm font-semibold text-slate-600">
                    Corte {formatDate(data.cutoff)} · {data.tests} pruebas · por azar se esperan cerca de {String(data.expected_false_alarms).replace('.', ',')} anomalías medias aunque nada haya cambiado.
                </p>
                {!data.anomalies.length && (
                    <p className="bg-emerald-50 p-4 text-sm font-semibold text-emerald-900">Ninguna cifra se sale de lo esperado con las reglas vigentes.</p>
                )}
                {data.anomalies.map((item, index) => {
                    const style = LEVELS[item.level];
                    return (
                        <article key={`${item.rule}-${item.territory}-${item.conducta}-${index}`} className={`border-l-4 bg-white p-4 shadow-sm ${style.bar}`}>
                            <div className="flex flex-wrap items-start justify-between gap-2">
                                <div>
                                    <p className="text-[11px] font-black uppercase text-slate-500">
                                        {RULE_LABELS[item.rule]} · {formatDate(item.window.start)} al {formatDate(item.window.end)}
                                        {item.kind === 'CAIDA' ? ' · caída' : ''}
                                    </p>
                                    <h3 className="mt-1 text-base font-black text-slate-950">{item.title}</h3>
                                </div>
                                <span className={`px-2 py-0.5 text-[11px] font-black ${style.chip}`}>{style.label}</span>
                            </div>
                            <p className="mt-2 text-sm font-semibold leading-6 text-slate-600">{item.detail}</p>
                            {item.rule === 'R2' && onStudy && (
                                <button onClick={() => onStudy({ title: item.title, detail: item.detail })} className="mt-2 text-sm font-black text-[#281FD0] hover:underline">
                                    Abrir estudio
                                </button>
                            )}
                        </article>
                    );
                })}
                <p className="text-xs font-semibold text-slate-500">{data.note}</p>
            </div>
            <aside className="space-y-3 bg-slate-50 p-4">
                <h3 className="text-sm font-black uppercase tracking-wide text-slate-700">Reglas</h3>
                {data.rules.map((rule) => (
                    <div key={rule.code}>
                        <p className="text-sm font-black text-slate-900">{rule.title}</p>
                        <p className="mt-0.5 text-xs font-semibold leading-5 text-slate-600">{rule.text}</p>
                    </div>
                ))}
            </aside>
        </div>
    );
};

export default AnomalyRadar;
