import React, { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Download, Loader2, Search } from 'lucide-react';
import { apiFetch, apiJson, readApiError } from '../utils/apiClient';
import { memoryQuery, OUTCOME_TONE, RECOMMENDATION_STATUS } from '../utils/memory';

const inputClass = 'w-full border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-900 focus:border-[#281FD0] focus:outline-none';
const formatDate = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`))
    : 'sin fecha');

const Detail = ({ item }) => {
    const d = item.detail || {};
    const line = (label, value) => value && <p><span className="font-black text-slate-700">{label}:</span> {value}</p>;
    return (
        <div className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-sm font-semibold leading-6 text-slate-600">
            {line('Pregunta', d.question)}
            {line('Factores asociados', d.associated_factors)}
            {d.field_notes > 0 && line('Trabajo de campo', `${d.field_notes} notas`)}
            {d.recommendations?.length > 0 && (
                <div>
                    <p className="font-black text-slate-700">Recomendaciones:</p>
                    <ul className="ml-4 list-disc">
                        {d.recommendations.map((rec) => (
                            <li key={rec.code}>{rec.code} · {rec.title} — {RECOMMENDATION_STATUS[rec.status] || rec.status}{rec.decision_note ? ` (${rec.decision_note})` : ''}</li>
                        ))}
                    </ul>
                </div>
            )}
            {line('Dirigida a', d.addressed_to)}
            {line('Estudio de origen', d.study_code)}
            {line('Compromiso que la ejecutó', d.commitment_code)}
            {line('Decisión', d.decision)}
            {line('Responsable', d.responsible)}
            {d.started_on && line('Ejecución', `${formatDate(d.started_on)} a ${formatDate(d.completed_on)}`)}
            {line('Valoración', d.assessment)}
            {d.evidence?.length > 0 && line('Evidencia', d.evidence.join('; '))}
        </div>
    );
};

/** Memoria institucional: lo que el Observatorio ya estudió, recomendó, decidió y evaluó. */
const InstitutionalMemory = () => {
    const [filters, setFilters] = useState({ q: '', kind: '', year: '' });
    const [applied, setApplied] = useState(filters);
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [open, setOpen] = useState(null);
    const [loading, setLoading] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            setData(await apiJson(`/observatory/memory${memoryQuery(applied)}`));
        } catch (loadError) {
            setError(loadError.message);
        } finally {
            setLoading(false);
        }
    }, [applied]);
    useEffect(() => { load(); }, [load]);

    const download = async () => {
        try {
            const response = await apiFetch(`/observatory/memory/export${memoryQuery(applied)}`);
            if (!response.ok) throw new Error(await readApiError(response));
            const url = URL.createObjectURL(await response.blob());
            Object.assign(document.createElement('a'), { href: url, download: 'memoria_observatorio.csv' }).click();
            URL.revokeObjectURL(url);
        } catch (downloadError) {
            setError(downloadError.message);
        }
    };
    const set = (field) => (event) => setFilters((current) => ({ ...current, [field]: event.target.value }));
    const choose = (field) => (event) => { const next = { ...filters, [field]: event.target.value }; setFilters(next); setApplied(next); };

    return (
        <div className="space-y-5">
            <p className="max-w-3xl text-sm font-semibold text-slate-600">
                Lo que el Observatorio ya estudió, recomendó, decidió y evaluó, para no empezar de cero cada vez: estudios cerrados,
                recomendaciones rechazadas (con su motivo) o cumplidas, e intervenciones terminadas con su evaluación.
            </p>
            <form onSubmit={(event) => { event.preventDefault(); setApplied(filters); }} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_140px_auto_auto] md:items-end">
                <label className="block">
                    <span className="text-xs font-black uppercase tracking-wide text-slate-600">Buscar</span>
                    <input className={`${inputClass} mt-1`} value={filters.q} onChange={set('q')} placeholder="Hurto de motos, Potrerito, extorsión…" />
                </label>
                <label className="block">
                    <span className="text-xs font-black uppercase tracking-wide text-slate-600">Tipo</span>
                    <select className={`${inputClass} mt-1`} value={filters.kind} onChange={choose('kind')}>
                        <option value="">Todos{data ? ` (${data.total})` : ''}</option>
                        <option value="ESTUDIO">Estudios{data ? ` (${data.counts.ESTUDIO})` : ''}</option>
                        <option value="RECOMENDACION">Recomendaciones{data ? ` (${data.counts.RECOMENDACION})` : ''}</option>
                        <option value="INTERVENCION">Intervenciones{data ? ` (${data.counts.INTERVENCION})` : ''}</option>
                    </select>
                </label>
                <label className="block">
                    <span className="text-xs font-black uppercase tracking-wide text-slate-600">Año</span>
                    <select className={`${inputClass} mt-1`} value={filters.year} onChange={choose('year')}>
                        <option value="">Todos</option>
                        {(data?.years || []).map((year) => <option key={year} value={year}>{year}</option>)}
                    </select>
                </label>
                <button type="submit" className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white"><Search size={15} /> Buscar</button>
                <button type="button" onClick={download} className="inline-flex min-h-10 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700"><Download size={15} /> CSV</button>
            </form>
            {error && <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}
            {loading && !data && <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Buscando…</p>}
            {data && !data.items.length && (
                <p className="bg-slate-50 p-4 text-sm font-semibold text-slate-600">
                    {data.total
                        ? 'Nada coincide con la búsqueda.'
                        : 'La memoria se llena sola: cuando se cierre un estudio, se decida una recomendación o termine una intervención, aparecerá aquí.'}
                </p>
            )}
            <ul className="space-y-3">
                {(data?.items || []).map((item) => {
                    const key = `${item.kind}-${item.code}`;
                    return (
                        <li key={key} className="bg-white p-4 shadow-sm">
                            <button onClick={() => setOpen(open === key ? null : key)} aria-expanded={open === key} className="flex w-full items-start justify-between gap-3 text-left">
                                <div className="min-w-0">
                                    <p className="text-xs font-black text-slate-500">
                                        {item.kind_label} · {item.code} · {formatDate(item.date)}{item.territory ? ` · ${item.territory}` : ''}{item.reserved ? ' · Reservado' : ''}
                                    </p>
                                    <h3 className="mt-1 text-base font-black text-slate-950">{item.title}</h3>
                                    <p className={`mt-1 text-sm font-black ${OUTCOME_TONE(item.outcome)}`}>{item.outcome}</p>
                                    {item.summary && <p className="mt-1 line-clamp-3 text-sm font-semibold text-slate-600">{item.summary}</p>}
                                </div>
                                {open === key ? <ChevronUp size={18} className="shrink-0" /> : <ChevronDown size={18} className="shrink-0" />}
                            </button>
                            {open === key && <Detail item={item} />}
                        </li>
                    );
                })}
            </ul>
            {data && <p className="text-xs font-semibold text-slate-500">{data.rule}</p>}
        </div>
    );
};

export default InstitutionalMemory;
