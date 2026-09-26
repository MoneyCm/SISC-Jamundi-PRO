import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, Plus, Send } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import { localToday } from '../utils/localDate';
import {
    CADENCE_LABELS, PROGRAM_LABELS, REQUEST_STATUS_LABELS, STATE_LABELS, defaultRequest, stateDetail,
} from '../utils/dataRequests';

const inputClass = 'w-full border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-900 focus:border-[#281FD0] focus:outline-none';
const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const shortDate = (value) => (value ? value.split('-').reverse().slice(0, 2).join('/') : '—');

const Field = ({ label, children }) => (
    <label className="block">
        <span className="text-xs font-black uppercase tracking-wide text-slate-600">{label}</span>
        <div className="mt-1">{children}</div>
    </label>
);

const RequestForm = ({ entities, onSaved, onCancel }) => {
    const today = localToday();
    const due = entities.filter((entity) => entity.active && ['TOCA_PEDIR', 'ATRASADA'].includes(entity.state));
    const [selected, setSelected] = useState(() => new Set((due.length ? due : entities.filter((e) => e.active)).map((e) => e.id)));
    const [form, setForm] = useState(() => defaultRequest(today));
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const set = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
    const toggle = (id) => setSelected((current) => {
        const next = new Set(current);
        if (next.has(id)) next.delete(id); else next.add(id);
        return next;
    });

    const save = async (event) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        try {
            await apiJson('/observatory/data-requests', json('POST', { ...form, entity_ids: [...selected], channel: form.channel || null }));
            onSaved();
        } catch (saveError) {
            setError(saveError.message);
            setSaving(false);
        }
    };

    return (
        <form onSubmit={save} className="space-y-4 border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm font-black text-slate-900">Registrar solicitud</p>
            <fieldset className="grid gap-2 md:grid-cols-2">
                <legend className="mb-1 text-xs font-black uppercase tracking-wide text-slate-600">Dependencias</legend>
                {entities.filter((entity) => entity.active).map((entity) => (
                    <label key={entity.id} className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                        <input type="checkbox" checked={selected.has(entity.id)} onChange={() => toggle(entity.id)} />
                        {entity.name} <span className="text-xs text-slate-500">({CADENCE_LABELS[entity.cadence].toLowerCase()})</span>
                    </label>
                ))}
            </fieldset>
            <div className="grid gap-3 md:grid-cols-3">
                <div className="md:col-span-3">
                    <Field label="Qué se pide"><input className={inputClass} value={form.what} onChange={set('what')} required minLength={3} maxLength={300} /></Field>
                </div>
                <Field label="Periodo desde"><input type="date" className={inputClass} value={form.period_start} onChange={set('period_start')} /></Field>
                <Field label="Periodo hasta"><input type="date" className={inputClass} value={form.period_end} onChange={set('period_end')} /></Field>
                <Field label="Medio">
                    <select className={inputClass} value={form.channel} onChange={set('channel')}>
                        {['Correo', 'Oficio', 'WhatsApp', 'Llamada', 'Reunión'].map((item) => <option key={item}>{item}</option>)}
                    </select>
                </Field>
                <Field label="Fecha de la solicitud"><input type="date" className={inputClass} value={form.requested_on} onChange={set('requested_on')} required /></Field>
                <Field label="Plazo de respuesta"><input type="date" className={inputClass} value={form.due_on} onChange={set('due_on')} required /></Field>
            </div>
            {error && <p role="alert" className="bg-red-50 p-2 text-sm font-bold text-red-800">{error}</p>}
            <div className="flex gap-2">
                <button type="submit" disabled={saving || !selected.size} className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white disabled:opacity-60">
                    {saving ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Registrar {selected.size} {selected.size === 1 ? 'solicitud' : 'solicitudes'}
                </button>
                <button type="button" onClick={onCancel} className="min-h-10 border border-slate-300 px-4 text-sm font-bold text-slate-700">Cancelar</button>
            </div>
        </form>
    );
};

const OpenRequest = ({ request, onSaved }) => {
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    const mark = async (status) => {
        setBusy(status);
        setError('');
        try {
            await apiJson(`/observatory/data-requests/${request.id}`, json('PUT', { status, received_on: null, note: request.note, expected_version: request.version }));
            onSaved();
        } catch (saveError) {
            setError(saveError.message);
            setBusy('');
        }
    };
    return (
        <div className="mt-2 border-l-2 border-slate-200 pl-3">
            <p className="text-xs font-semibold text-slate-600">
                {request.what}{request.period_start ? ` · ${shortDate(request.period_start)} al ${shortDate(request.period_end)}` : ''} · pedido el {shortDate(request.requested_on)}{request.channel ? ` por ${request.channel.toLowerCase()}` : ''}
            </p>
            <div className="mt-1 flex flex-wrap gap-3">
                {[['RECIBIDA', 'Llegó hoy'], ['INCOMPLETA', 'Llegó incompleta'], ['SIN_RESPUESTA', 'No respondió']].map(([status, label]) => (
                    <button key={status} disabled={Boolean(busy)} onClick={() => mark(status)} className="inline-flex items-center gap-1 text-xs font-black text-[#281FD0] hover:underline disabled:opacity-50">
                        {busy === status && <Loader2 size={12} className="animate-spin" />} {label}
                    </button>
                ))}
            </div>
            {error && <p role="alert" className="mt-1 text-xs font-bold text-red-700">{error}</p>}
        </div>
    );
};

const EntityForm = ({ onSaved, onCancel }) => {
    const [form, setForm] = useState({ name: '', program: 'INSPECCIONES', cadence: 'SEMANAL', contact: '' });
    const [error, setError] = useState('');
    const set = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
    const save = async (event) => {
        event.preventDefault();
        setError('');
        try {
            await apiJson('/observatory/data-entities', json('POST', { ...form, contact: form.contact || null }));
            onSaved();
        } catch (saveError) {
            setError(saveError.message);
        }
    };
    return (
        <form onSubmit={save} className="grid gap-3 border border-slate-200 bg-white p-4 md:grid-cols-4">
            <div className="md:col-span-2"><Field label="Dependencia"><input className={inputClass} value={form.name} onChange={set('name')} required minLength={3} placeholder="Inspección Primera de Policía" /></Field></div>
            <Field label="Tipo">
                <select className={inputClass} value={form.program} onChange={set('program')}>
                    {Object.entries(PROGRAM_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
            </Field>
            <Field label="Periodicidad">
                <select className={inputClass} value={form.cadence} onChange={set('cadence')}>
                    {Object.entries(CADENCE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
            </Field>
            <div className="md:col-span-4"><Field label="Contacto"><input className={inputClass} value={form.contact} onChange={set('contact')} maxLength={300} placeholder="Correo o persona a quien se pide" /></Field></div>
            {error && <p role="alert" className="bg-red-50 p-2 text-sm font-bold text-red-800 md:col-span-4">{error}</p>}
            <div className="flex gap-2 md:col-span-4">
                <button type="submit" className="min-h-10 bg-[#281FD0] px-4 text-sm font-black text-white">Agregar dependencia</button>
                <button type="button" onClick={onCancel} className="min-h-10 border border-slate-300 px-4 text-sm font-bold text-slate-700">Cancelar</button>
            </div>
        </form>
    );
};

const CadenceSelect = ({ entity, onSaved }) => {
    const [error, setError] = useState('');
    const change = async (field, value) => {
        setError('');
        try {
            const { name, program, cadence, contact, active } = entity;
            await apiJson(`/observatory/data-entities/${entity.id}`, json('PUT', { name, program, cadence, contact, active, [field]: value }));
            onSaved();
        } catch (saveError) {
            setError(saveError.message);
        }
    };
    return (
        <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-600">
            <select aria-label={`Periodicidad de ${entity.name}`} className="border border-slate-300 bg-white px-2 py-1 text-xs font-bold" value={entity.cadence} onChange={(event) => change('cadence', event.target.value)}>
                {Object.entries(CADENCE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <button onClick={() => change('active', !entity.active)} className="font-black text-slate-500 hover:text-slate-900">
                {entity.active ? 'Dejar de pedir' : 'Volver a pedir'}
            </button>
            {error && <span className="font-bold text-red-700">{error}</span>}
        </div>
    );
};

/** Solicitudes de datos: a quién se pidió qué y si respondió (modelo operativo, sección 2). */
const DataRequests = () => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [mode, setMode] = useState('');

    const load = useCallback(async () => {
        setError('');
        try {
            setData(await apiJson('/observatory/data-requests'));
        } catch (loadError) {
            setError(loadError.message);
        }
    }, []);
    useEffect(() => { load(); }, [load]);
    const saved = () => { setMode(''); load(); };

    if (error && !data) return <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Cargando solicitudes…</p>;

    const active = data.entities.filter((entity) => entity.active);
    const inactive = data.entities.filter((entity) => !entity.active);

    return (
        <div className="space-y-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <p className="max-w-3xl text-sm font-semibold text-slate-600">
                    Lo que se pide a Inspecciones, Comisarías y otras dependencias que no publican sus datos solas: cuándo se pidió, el plazo y si llegó.
                    El último corte cargado confirma que lo recibido entró al SISC.
                </p>
                {!mode && (
                    <div className="flex gap-2">
                        <button onClick={() => setMode('request')} className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white"><Send size={15} /> Pedir datos</button>
                        <button onClick={() => setMode('entity')} className="inline-flex min-h-10 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700"><Plus size={15} /> Dependencia</button>
                    </div>
                )}
            </div>
            {error && <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}
            {mode === 'request' && <RequestForm entities={data.entities} onSaved={saved} onCancel={() => setMode('')} />}
            {mode === 'entity' && <EntityForm onSaved={saved} onCancel={() => setMode('')} />}

            <div className="grid gap-3">
                {active.map((entity) => {
                    const state = STATE_LABELS[entity.state];
                    return (
                        <article key={entity.id} className="bg-white p-4 shadow-sm">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                                <div>
                                    <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">{PROGRAM_LABELS[entity.program]}{entity.contact ? ` · ${entity.contact}` : ''}</p>
                                    <h3 className="text-base font-black text-slate-950">{entity.name}</h3>
                                    <p className="mt-0.5 text-sm font-semibold text-slate-600">{stateDetail(entity)}</p>
                                    <p className="text-xs font-semibold text-slate-500">Último corte cargado en el SISC: {entity.loaded_cutoff ? shortDate(entity.loaded_cutoff) + '/' + entity.loaded_cutoff.slice(0, 4) : 'ninguno'}</p>
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                    <span className={`px-2 py-0.5 text-[11px] font-black uppercase ${state.chip}`}>{state.label}</span>
                                    <CadenceSelect entity={entity} onSaved={load} />
                                </div>
                            </div>
                            {entity.open_requests.map((request) => <OpenRequest key={`${request.id}-${request.version}`} request={request} onSaved={load} />)}
                        </article>
                    );
                })}
            </div>

            {inactive.length > 0 && (
                <details className="bg-slate-50 p-3">
                    <summary className="cursor-pointer text-sm font-black text-slate-700">Dependencias a las que ya no se pide ({inactive.length})</summary>
                    <ul className="mt-2 space-y-2">
                        {inactive.map((entity) => (
                            <li key={entity.id} className="flex flex-wrap items-center justify-between gap-2 text-sm font-semibold text-slate-700">
                                {entity.name} <CadenceSelect entity={entity} onSaved={load} />
                            </li>
                        ))}
                    </ul>
                </details>
            )}

            {data.recent.length > 0 && (
                <section>
                    <h3 className="border-b-2 border-slate-200 pb-1 text-sm font-black uppercase tracking-wide text-slate-700">Historial reciente</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[640px] text-left text-sm">
                            <thead>
                                <tr className="text-[11px] font-black uppercase tracking-wide text-slate-500">
                                    <th className="py-2 pr-3">Pedido</th><th className="py-2 pr-3">Dependencia</th><th className="py-2 pr-3">Qué</th>
                                    <th className="py-2 pr-3">Plazo</th><th className="py-2 pr-3">Estado</th><th className="py-2">Llegó</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.recent.map((request) => (
                                    <tr key={request.id} className="border-t border-slate-100 font-semibold text-slate-700">
                                        <td className="py-2 pr-3 tabular-nums">{shortDate(request.requested_on)}</td>
                                        <td className="py-2 pr-3">{request.entity}</td>
                                        <td className="py-2 pr-3">{request.what}</td>
                                        <td className="py-2 pr-3 tabular-nums">{shortDate(request.due_on)}</td>
                                        <td className="py-2 pr-3">{REQUEST_STATUS_LABELS[request.status]}</td>
                                        <td className="py-2 tabular-nums">{shortDate(request.received_on)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
            <p className="text-xs font-semibold text-slate-500">{data.rule}</p>
        </div>
    );
};

export default DataRequests;
