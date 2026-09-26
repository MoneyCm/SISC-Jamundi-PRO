import React, { useEffect, useState } from 'react';
import { ArrowRight, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import { BRIEF_LEVELS, briefHeadline } from '../utils/mondayBrief';

/** Resumen del lunes: las ocho preguntas del Observatorio, cada una con su respuesta y adónde ir. */
const MondayBrief = ({ onTab, onNavigate }) => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [open, setOpen] = useState(null);

    useEffect(() => {
        let alive = true;
        apiJson('/observatory/monday').then((result) => alive && setData(result)).catch((loadError) => alive && setError(loadError.message));
        return () => { alive = false; };
    }, []);

    if (error) return <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Respondiendo las ocho preguntas…</p>;

    const go = (target) => (target.tab ? onTab?.(target.tab) : target.page && onNavigate?.(target.page));
    return (
        <section className="bg-white p-4 shadow-sm">
            <div className="border-b border-slate-200 pb-3">
                <h2 className="text-sm font-black uppercase tracking-wide text-slate-700">Las ocho preguntas de la semana</h2>
                <p className="mt-1 text-sm font-semibold text-slate-600">{briefHeadline(data)}</p>
            </div>
            <ol className="divide-y divide-slate-100">
                {data.answers.map((item, index) => {
                    const level = BRIEF_LEVELS[item.level] || BRIEF_LEVELS.INFO;
                    const expanded = open === item.key;
                    return (
                        <li key={item.key} className="py-2.5">
                            <div className="grid gap-2 md:grid-cols-[28px_minmax(0,260px)_minmax(0,1fr)_auto] md:items-start">
                                <span className={`flex h-6 w-6 items-center justify-center text-xs font-black ${level.badge}`} aria-label={level.label}>{index + 1}</span>
                                <p className="text-sm font-black text-slate-900">{item.question}</p>
                                <div className="min-w-0">
                                    <p className="text-sm font-semibold text-slate-700">{item.answer}</p>
                                    {item.items.length > 0 && (
                                        <button onClick={() => setOpen(expanded ? null : item.key)} aria-expanded={expanded}
                                            className="mt-0.5 inline-flex items-center gap-1 text-xs font-black text-slate-500 hover:text-slate-900">
                                            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />} {expanded ? 'Ocultar' : `Ver ${item.items.length}`}
                                        </button>
                                    )}
                                    {expanded && (
                                        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs font-semibold leading-5 text-slate-600">
                                            {item.items.map((line) => <li key={line}>{line}</li>)}
                                        </ul>
                                    )}
                                </div>
                                {(item.target.tab || item.target.page) && item.level !== 'OK' && (
                                    <button onClick={() => go(item.target)} className="inline-flex items-center gap-1 text-sm font-black text-[#281FD0] hover:underline">
                                        Ir <ArrowRight size={14} />
                                    </button>
                                )}
                            </div>
                        </li>
                    );
                })}
            </ol>
        </section>
    );
};

export default MondayBrief;
