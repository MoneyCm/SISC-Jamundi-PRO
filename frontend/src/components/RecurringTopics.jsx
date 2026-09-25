import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, History, Loader2 } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

const formatDate = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`))
    : '');

const YEAR_TONES = ['bg-slate-200 text-slate-700', 'bg-amber-100 text-amber-900', 'bg-red-100 text-red-800'];

const TopicRow = ({ topic, allYears }) => {
    const [open, setOpen] = useState(false);
    const spans = Object.keys(topic.years).length;
    return (
        <li className="border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                    <p className="text-base font-black text-slate-950">{topic.label}</p>
                    <p className="mt-1 text-sm font-semibold text-slate-600">
                        {topic.sessions} sesiones · desde {formatDate(topic.first_date)}
                        {topic.sessions_with_commitment ? ` · en ${topic.sessions_with_commitment} quedó un compromiso` : ' · nunca quedó un compromiso'}
                    </p>
                </div>
                <div className="flex gap-1" aria-label="Sesiones por año">
                    {allYears.map((year, index) => (
                        <span key={year} title={`${topic.years[year] || 0} sesiones en ${year}`}
                            className={`min-w-[52px] px-2 py-1 text-center text-xs font-black ${topic.years[year] ? YEAR_TONES[Math.min(index, YEAR_TONES.length - 1)] : 'bg-slate-50 text-slate-300'}`}>
                            {year}<br />{topic.years[year] || '–'}
                        </span>
                    ))}
                </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-bold">
                {spans >= 2 && <span className="bg-red-50 px-2 py-1 text-red-800">Aparece en {spans} años distintos</span>}
                {topic.open_commitments > 0 ? (
                    <span className="bg-amber-50 px-2 py-1 text-amber-900">
                        {topic.open_commitments} compromiso(s) abierto(s) hoy: {topic.open_codes.join(', ')}{topic.open_commitments > topic.open_codes.length ? '…' : ''}
                    </span>
                ) : (
                    <span className="bg-emerald-50 px-2 py-1 text-emerald-800">Sin compromisos abiertos</span>
                )}
                {topic.examples.length > 0 && (
                    <button onClick={() => setOpen((value) => !value)} className="ml-auto inline-flex items-center gap-1 text-[#281FD0] hover:underline">
                        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />} {open ? 'Ocultar' : 'Ver'} primer y último compromiso
                    </button>
                )}
            </div>
            {open && (
                <ol className="mt-3 space-y-2 border-l-2 border-slate-200 pl-3">
                    {topic.examples.map((example) => (
                        <li key={`${example.date}-${example.text.slice(0, 20)}`} className="text-sm text-slate-700">
                            <span className="font-black text-slate-900">{formatDate(example.date)}</span> · {example.instance}
                            <span className="block font-semibold">{example.text}</span>
                        </li>
                    ))}
                </ol>
            )}
        </li>
    );
};

const RecurringTopics = () => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        apiJson('/council-commitments/recurrence').then(setData).catch((loadError) => setError(loadError.message));
    }, []);

    if (error) return <p className="bg-red-50 p-3 text-sm font-bold text-red-800" role="alert">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Buscando temas que vuelven…</p>;

    const allYears = Object.keys(data.coverage);
    return (
        <section className="space-y-4" aria-label="Temas que vuelven">
            <div className="bg-slate-50 p-4 text-sm font-semibold text-slate-700">
                <p className="flex items-center gap-2 font-black text-slate-950"><History size={17} /> Qué temas se repiten sesión tras sesión</p>
                <p className="mt-1">
                    Se cuenta una sesión cuando el tema se trató en el acta o quedó un compromiso sobre él. Las actas de años anteriores sirven solo para este análisis: no crean compromisos abiertos.
                </p>
                <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                    {allYears.map((year) => (
                        <li key={year}><span className="font-black">{year}:</span> {Object.entries(data.coverage[year]).map(([label, count]) => `${count} ${label}`).join(' · ')}</li>
                    ))}
                </ul>
            </div>
            {data.topics.length === 0 ? (
                <p className="bg-white p-6 text-center text-sm font-semibold text-slate-500">Todavía no hay suficientes actas para ver temas repetidos.</p>
            ) : (
                <ol className="space-y-2">
                    {data.topics.map((topic) => <TopicRow key={topic.key} topic={topic} allYears={allYears} />)}
                </ol>
            )}
        </section>
    );
};

export default RecurringTopics;
