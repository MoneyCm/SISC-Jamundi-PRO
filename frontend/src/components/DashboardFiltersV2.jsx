import React, { useEffect, useState } from 'react';
import { CalendarDays, Check, ChevronDown } from 'lucide-react';

const toIso = (value) => value.toISOString().slice(0, 10);
const parseIso = (value) => new Date(`${value}T00:00:00`);

const buildPreset = (preset, referenceDate) => {
    const reference = referenceDate || new Date();
    if (preset === 'last7') {
        const start = new Date(reference);
        start.setDate(start.getDate() - 6);
        return { start: toIso(start), end: toIso(reference) };
    }
    if (preset === 'last30') {
        const start = new Date(reference);
        start.setDate(start.getDate() - 29);
        return { start: toIso(start), end: toIso(reference) };
    }
    if (preset === 'year') {
        return { start: `${reference.getFullYear()}-01-01`, end: toIso(reference) };
    }
    return {
        start: toIso(new Date(reference.getFullYear(), reference.getMonth(), 1)),
        end: toIso(reference),
    };
};

const formatRange = (range) => {
    if (!range?.start || !range?.end) return 'Seleccionar periodo';
    const formatter = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' });
    return `${formatter.format(parseIso(range.start))} – ${formatter.format(parseIso(range.end))}`;
};

const PRESETS = [
    { id: 'latestMonth', label: 'Último mes disponible' },
    { id: 'last7', label: 'Últimos 7 días cargados' },
    { id: 'last30', label: 'Últimos 30 días cargados' },
    { id: 'year', label: 'Acumulado anual' },
    { id: 'custom', label: 'Rango personalizado' },
];

const DashboardFilters = ({ range, referenceDate, comparisonMode, onRangeChange, onComparisonChange }) => {
    const [open, setOpen] = useState(false);
    const [preset, setPreset] = useState('latestMonth');
    const [draft, setDraft] = useState(range || { start: '', end: '' });

    useEffect(() => {
        if (range?.start && range?.end) setDraft(range);
    }, [range]);

    const selectPreset = (id) => {
        setPreset(id);
        if (id !== 'custom') {
            onRangeChange(buildPreset(id, referenceDate));
            setOpen(false);
        }
    };

    const applyCustom = () => {
        if (!draft.start || !draft.end || draft.start > draft.end) return;
        onRangeChange(draft);
        setOpen(false);
    };

    return (
        <div className="flex flex-col xl:flex-row xl:items-center gap-3">
            <div className="relative">
                <button onClick={() => setOpen(!open)} className="w-full xl:w-auto min-w-[265px] flex items-center justify-between gap-3 bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-left hover:border-primary/40">
                    <CalendarDays size={18} className="text-primary shrink-0" />
                    <span className="flex-1 min-w-0"><span className="block text-[10px] uppercase font-bold text-slate-500">Periodo analizado</span><span className="block text-sm font-bold text-slate-800 truncate">{formatRange(range)}</span></span>
                    <ChevronDown size={16} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
                </button>
                {open && (
                    <>
                        <button aria-label="Cerrar selector" className="fixed inset-0 z-40 cursor-default" onClick={() => setOpen(false)} />
                        <div className="absolute z-50 top-full left-0 mt-2 w-[min(360px,calc(100vw-2rem))] bg-white border border-slate-200 rounded-lg shadow-xl p-3">
                            <div className="space-y-1">
                                {PRESETS.map((option) => (
                                    <button key={option.id} onClick={() => selectPreset(option.id)} className={`w-full flex items-center justify-between rounded-lg px-3 py-2.5 text-sm text-left ${preset === option.id ? 'bg-primary/5 text-primary font-bold' : 'text-slate-700 hover:bg-slate-50'}`}>
                                        {option.label}{preset === option.id && <Check size={15} />}
                                    </button>
                                ))}
                            </div>
                            {preset === 'custom' && (
                                <div className="border-t border-slate-200 mt-3 pt-3 space-y-3">
                                    <div className="grid grid-cols-2 gap-2">
                                        <label className="text-xs font-bold text-slate-600">Inicio<input type="date" value={draft.start || ''} max={draft.end || undefined} onChange={(event) => setDraft({ ...draft, start: event.target.value })} className="mt-1 w-full border border-slate-200 rounded-lg px-2 py-2 text-sm font-normal" /></label>
                                        <label className="text-xs font-bold text-slate-600">Fin<input type="date" value={draft.end || ''} min={draft.start || undefined} max={referenceDate ? toIso(referenceDate) : undefined} onChange={(event) => setDraft({ ...draft, end: event.target.value })} className="mt-1 w-full border border-slate-200 rounded-lg px-2 py-2 text-sm font-normal" /></label>
                                    </div>
                                    <button onClick={applyCustom} disabled={!draft.start || !draft.end || draft.start > draft.end} className="w-full bg-primary text-white rounded-lg py-2.5 text-sm font-bold disabled:opacity-40">Aplicar periodo</button>
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>

            <div className="flex items-center p-1 bg-slate-100 rounded-lg" aria-label="Periodo de comparación">
                {[
                    ['previous_period', 'Periodo anterior'],
                    ['previous_year', 'Mismo periodo año anterior'],
                ].map(([value, label]) => (
                    <button key={value} onClick={() => onComparisonChange(value)} className={`flex-1 xl:flex-none px-3 py-2 rounded-md text-xs font-bold whitespace-normal xl:whitespace-nowrap ${comparisonMode === value ? 'bg-white text-primary shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
                        {label}
                    </button>
                ))}
            </div>
        </div>
    );
};

export default DashboardFilters;
