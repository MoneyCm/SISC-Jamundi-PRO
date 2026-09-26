import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, Plus, Target, Trash2 } from 'lucide-react';
import { localToday } from '../utils/localDate';
import { apiJson } from '../utils/apiClient';
import { allowedStages, describeWindow, missingFor, STAGE_LABELS } from '../utils/interventions';

const inputClass = 'mt-1 w-full border border-slate-300 bg-white px-2 py-2 text-sm font-semibold normal-case text-slate-800';
const labelClass = 'block text-[11px] font-black uppercase tracking-wide text-slate-500';
const today = () => localToday();
const WINDOW_STYLES = { MEDIDO: 'text-slate-900', PENDIENTE: 'text-slate-500', ESPERANDO_DATOS: 'text-amber-800', SIN_BASE: 'text-slate-500' };

const DOC_FIELDS = ['problem', 'assessment', 'recommendation', 'decision', 'responsible', 'decision_date', 'deadline',
    'intervention', 'started_on', 'completed_on', 'evidence', 'status', 'indicator'];
const editable = (doc) => Object.fromEntries(DOC_FIELDS.map((key) => [key, doc[key] ?? (key === 'evidence' ? [] : '')]));
// Fechas e indicador vacíos van como null; los textos vacíos se envían tal cual (el backend los exige según la etapa).
const NULLABLE = ['decision_date', 'deadline', 'started_on', 'completed_on', 'indicator'];
const payload = (form) => Object.fromEntries(Object.entries(form).map(([key, value]) => [key, NULLABLE.includes(key) && value === '' ? null : value]));

const Followup = ({ caseId, version }) => {
    const [data, setData] = useState(null);
    useEffect(() => {
        let alive = true;
        apiJson(`/interventions/${caseId}/followup`).then((result) => alive && setData(result)).catch(() => alive && setData(null));
        return () => { alive = false; };
    }, [caseId, version]);
    if (!data) return null;
    return (
        <section className="mt-4 bg-slate-50 p-3">
            <h4 className="flex items-center gap-2 text-sm font-black text-slate-900"><Target size={15} /> Seguimiento a 30, 60 y 90 días</h4>
            {data.status !== 'OK' ? (
                <p className="mt-1 text-sm font-semibold text-slate-600">{data.reason}</p>
            ) : (
                <>
                    <p className="mt-1 text-xs font-semibold text-slate-500">
                        {data.indicator_label} en {data.territory}, {data.unit_label}. Cada ventana compara los días desde el inicio con el mismo número de días antes.
                    </p>
                    <table className="mt-2 w-full text-sm">
                        <thead><tr className="text-left text-[11px] font-black uppercase text-slate-500"><th className="py-1">Ventana</th><th>Antes → después</th></tr></thead>
                        <tbody>
                            {data.windows.map((window) => (
                                <tr key={window.days} className="border-t border-slate-200">
                                    <td className="py-1.5 font-black tabular-nums text-slate-700">{window.days} días</td>
                                    <td className={`font-semibold tabular-nums ${WINDOW_STYLES[window.status] || ''}`}>{describeWindow(window)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    <p className="mt-2 text-xs font-semibold text-slate-500">{data.note} Sábana policial al {data.coverage.end.split('-').reverse().join('/')}.</p>
                </>
            )}
        </section>
    );
};

const CaseEditor = ({ item, indicators, canEdit, onSaved }) => {
    const [form, setForm] = useState(editable(item.document));
    const [evidence, setEvidence] = useState({ description: '', url: '' });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
    const missing = missingFor(form, form.status);
    const locked = !canEdit || item.status === 'EVALUADA';

    const addEvidence = () => {
        if (!evidence.description.trim() || !/^https?:\/\//i.test(evidence.url.trim())) {
            setError('La evidencia necesita una descripción y un enlace que empiece por http(s)://');
            return;
        }
        setError('');
        setForm((current) => ({ ...current, evidence: [...current.evidence, { description: evidence.description.trim(), url: evidence.url.trim() }] }));
        setEvidence({ description: '', url: '' });
    };
    const save = async () => {
        setSaving(true);
        setError('');
        try {
            onSaved(await apiJson(`/interventions/${item.id}`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ expected_version: item.version, document: payload(form) }),
            }));
        } catch (saveError) {
            setError(saveError.message);
        } finally {
            setSaving(false);
        }
    };

    const text = (key, label, placeholder) => (
        <label className={labelClass}>{label}
            <textarea rows={2} value={form[key]} onChange={set(key)} disabled={locked} placeholder={placeholder} className={inputClass} />
        </label>
    );
    const day = (key, label) => (
        <label className={labelClass}>{label}
            <input type="date" value={form[key] || ''} max={['deadline'].includes(key) ? undefined : today()} onChange={set(key)} disabled={locked} className={inputClass} />
        </label>
    );
    return (
        <div className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
                {text('problem', 'Problema', 'Qué se busca resolver')}
                {text('assessment', 'Lectura del Observatorio', 'Qué muestran los datos')}
                {text('recommendation', 'Recomendación')}
                {text('decision', 'Decisión', 'Qué se decidió y en qué instancia')}
                <label className={labelClass}>Responsable
                    <input value={form.responsible} onChange={set('responsible')} disabled={locked} className={inputClass} />
                </label>
                <label className={labelClass}>Indicador que debería cambiar
                    <select value={form.indicator || ''} onChange={set('indicator')} disabled={locked} className={inputClass}>
                        <option value="">Sin indicador (no medible con la sábana)</option>
                        {indicators.map((option) => <option key={option.code} value={option.code}>{option.label}</option>)}
                    </select>
                </label>
                {day('decision_date', 'Fecha de la decisión')}
                {day('deadline', 'Plazo')}
                {text('intervention', 'Qué se hizo', 'Acción concreta ejecutada')}
                <div className="grid grid-cols-2 gap-3">{day('started_on', 'Inicio')}{day('completed_on', 'Fin')}</div>
            </div>
            <div>
                <p className={labelClass}>Evidencias</p>
                <ul className="mt-1 space-y-1 text-sm font-semibold">
                    {form.evidence.map((entry, index) => (
                        <li key={`${entry.url}-${index}`} className="flex items-center gap-2">
                            <a href={entry.url} target="_blank" rel="noopener noreferrer" className="text-[#281FD0] underline">{entry.description}</a>
                            {!locked && (
                                <button onClick={() => setForm((current) => ({ ...current, evidence: current.evidence.filter((_, i) => i !== index) }))} aria-label="Quitar evidencia" className="text-slate-400 hover:text-red-700"><Trash2 size={14} /></button>
                            )}
                        </li>
                    ))}
                </ul>
                {!locked && (
                    <div className="mt-2 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                        <input value={evidence.description} onChange={(event) => setEvidence({ ...evidence, description: event.target.value })} placeholder="Descripción (acta, informe, fotos)" className={inputClass} />
                        <input value={evidence.url} onChange={(event) => setEvidence({ ...evidence, url: event.target.value })} placeholder="https://…" className={inputClass} />
                        <button onClick={addEvidence} className="mt-1 border border-slate-300 px-3 text-sm font-bold text-slate-700">Agregar</button>
                    </div>
                )}
            </div>
            {!locked && (
                <div className="flex flex-wrap items-end gap-3 border-t border-slate-100 pt-3">
                    <label className={labelClass}>Etapa
                        <select value={form.status} onChange={set('status')} className={inputClass}>
                            {allowedStages(item.status).map((stage) => <option key={stage.code} value={stage.code}>{stage.label}</option>)}
                        </select>
                    </label>
                    <button onClick={save} disabled={saving || missing.length > 0} className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white disabled:opacity-40">
                        {saving && <Loader2 size={15} className="animate-spin" />} Guardar intervención
                    </button>
                    {missing.length > 0 && <p className="text-xs font-bold text-amber-700">Para «{STAGE_LABELS[form.status]}» falta: {missing.join(', ')}.</p>}
                </div>
            )}
            {error && <p role="alert" className="text-sm font-bold text-red-700">{error}</p>}
            <Followup caseId={item.id} version={item.version} />
        </div>
    );
};

/** Intervenciones de un compromiso: qué se hizo para cumplirlo y qué pasó después. */
const InterventionPanel = ({ commitment, canEdit, onChanged }) => {
    const [items, setItems] = useState(null);
    const [indicators, setIndicators] = useState([]);
    const [error, setError] = useState('');
    const [creating, setCreating] = useState(false);

    const load = useCallback(async () => {
        try {
            const [list, options] = await Promise.all([
                apiJson(`/interventions/?commitment_code=${encodeURIComponent(commitment.code)}`),
                apiJson('/interventions/indicators'),
            ]);
            setItems(list.items);
            setIndicators(options);
        } catch (loadError) {
            setError(loadError.message);
        }
    }, [commitment.code]);
    useEffect(() => { load(); }, [load]);

    const create = async () => {
        setCreating(true);
        setError('');
        try {
            await apiJson('/interventions/', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ commitment_code: commitment.code, document: {
                    problem: commitment.text,
                    assessment: 'Pendiente: lectura del Observatorio sobre el problema.',
                    decision: [commitment.origin_act, commitment.instance_label].filter(Boolean).join(' · '),
                    responsible: commitment.responsible || '',
                } }),
            });
            await load();
            onChanged?.();
        } catch (createError) {
            setError(createError.message);
        } finally {
            setCreating(false);
        }
    };

    if (!items) return <Loader2 size={16} className="mt-3 animate-spin text-slate-400" />;
    return (
        <section className="mt-4 border-t border-slate-100 pt-4">
            <h3 className="text-sm font-black uppercase tracking-wide text-slate-700">Intervención</h3>
            <p className="mt-1 text-xs font-semibold text-slate-500">
                Qué se hizo para cumplir el compromiso, con evidencia, y qué pasó en los datos a 30, 60 y 90 días.
            </p>
            {!items.length && canEdit && (
                <button onClick={create} disabled={creating} className="mt-3 inline-flex min-h-10 items-center gap-2 border border-[#281FD0] px-4 text-sm font-black text-[#281FD0] disabled:opacity-50">
                    {creating ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Documentar intervención
                </button>
            )}
            {!items.length && !canEdit && <p className="mt-2 text-sm font-semibold text-slate-500">Sin intervención documentada.</p>}
            {items.map((item) => (
                <div key={`${item.id}-${item.version}`} className="mt-3">
                    <p className="mb-2 text-xs font-black text-slate-500">Etapa: {STAGE_LABELS[item.status] || item.status} · versión {item.version}</p>
                    <CaseEditor item={item} indicators={indicators} canEdit={canEdit}
                        onSaved={(saved) => { setItems((rows) => rows.map((row) => (row.id === saved.id ? saved : row))); onChanged?.(); }} />
                </div>
            ))}
            {error && <p role="alert" className="mt-2 text-sm font-bold text-red-700">{error}</p>}
        </section>
    );
};

export default InterventionPanel;
