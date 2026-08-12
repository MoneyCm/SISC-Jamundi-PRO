import React from 'react';
import { Filter, RotateCcw, Search } from 'lucide-react';
import { COMPARISON_OPTIONS, PERIOD_OPTIONS } from '../../utils/citizenInsights';

const Field = ({ label, children }) => (
    <label className="grid gap-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-600">
        {label}
        {children}
    </label>
);

const inputClass = 'min-h-11 w-full border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 outline-none transition focus:border-[#281FD0] focus:ring-2 focus:ring-[#281FD0]/20';

const CitizenFilterBar = ({ filters, options = {}, onChange, onApply, onClear, busy = false }) => {
    const update = (key) => (event) => onChange?.({ ...filters, [key]: event.target.value });

    return (
        <form onSubmit={(event) => { event.preventDefault(); onApply?.(); }} className="border border-slate-200 bg-white shadow-sm" aria-label="Filtros de datos públicos">
            <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
                <Filter size={16} className="text-[#281FD0]" />
                <h2 className="text-sm font-black text-slate-900">Filtrar la información</h2>
                <span className="ml-auto text-[11px] font-semibold text-slate-500">Los resultados conservan fuente y fecha de corte</span>
            </div>
            <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-4">
                <Field label="Periodo">
                    <select value={filters.periodMode} onChange={update('periodMode')} className={inputClass}>
                        {PERIOD_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                </Field>
                <Field label="Comparar con">
                    <select value={filters.comparison} onChange={update('comparison')} className={inputClass}>
                        {COMPARISON_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                </Field>
                <Field label="Año de corte">
                    <select value={filters.year} onChange={update('year')} className={inputClass} disabled={filters.periodMode === 'custom'}>
                        <option value="">Último disponible</option>
                        {(options.years || []).map((year) => <option key={year} value={year}>{year}</option>)}
                    </select>
                </Field>
                <Field label="Conducta">
                    <select value={filters.conducta} onChange={update('conducta')} className={inputClass}>
                        <option value="">Todas las conductas</option>
                        {(options.conductas || []).map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
                    </select>
                </Field>
                <Field label="Zona">
                    <select value={filters.zona} onChange={update('zona')} className={inputClass}>
                        <option value="">Urbana y rural</option>
                        {(options.zones || []).map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
                    </select>
                </Field>
                <Field label="Barrio, vereda o sector">
                    <select value={filters.territorio} onChange={update('territorio')} className={inputClass}>
                        <option value="">Todo Jamundí</option>
                        {(options.territories || []).map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
                    </select>
                </Field>
                {filters.periodMode === 'custom' && (
                    <>
                        <Field label="Desde"><input type="date" value={filters.startDate} onChange={update('startDate')} className={inputClass} required /></Field>
                        <Field label="Hasta"><input type="date" value={filters.endDate} onChange={update('endDate')} className={inputClass} required /></Field>
                    </>
                )}
                <div className="flex items-end gap-2 md:col-span-2 xl:col-span-1">
                    <button type="submit" disabled={busy} className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1f18a8] disabled:opacity-60">
                        <Search size={17} /> {busy ? 'Consultando' : 'Aplicar'}
                    </button>
                    <button type="button" onClick={onClear} className="inline-flex h-11 w-11 shrink-0 items-center justify-center border border-slate-300 bg-white text-slate-600 hover:border-[#281FD0] hover:text-[#281FD0]" title="Limpiar filtros" aria-label="Limpiar filtros">
                        <RotateCcw size={17} />
                    </button>
                </div>
            </div>
        </form>
    );
};

export default CitizenFilterBar;
