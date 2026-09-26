import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, BookOpen, CheckCircle2, ChevronDown, ChevronUp, Lightbulb, Loader2, Plus, RefreshCw } from 'lucide-react';
import { localToday } from '../utils/localDate';
import { apiJson } from '../utils/apiClient';
import AnomalyRadar from '../components/AnomalyRadar';
import PisccGoals from '../components/PisccGoals';
import PisccActions from '../components/PisccActions';
import DataRequests from '../components/DataRequests';
import WeekCalendar from '../components/WeekCalendar';
import TerritoryProfile from '../components/TerritoryProfile';
import { groupSignals, nextRecommendationSteps, RECOMMENDATION_LABELS } from '../utils/observatory';

const LEVEL_STYLES = {
    ALTA: { bar: 'border-red-500', chip: 'bg-red-100 text-red-800', label: 'Actuar ya' },
    MEDIA: { bar: 'border-amber-400', chip: 'bg-amber-100 text-amber-900', label: 'Revisar esta semana' },
    INFO: { bar: 'border-slate-300', chip: 'bg-slate-100 text-slate-600', label: 'Contexto' },
    OK: { bar: 'border-emerald-400', chip: 'bg-emerald-50 text-emerald-800', label: 'Al día' },
};
const STUDY_STATUS = { ABIERTO: 'Abierto', EN_CURSO: 'En curso', CERRADO: 'Cerrado' };
const PAGE_LABELS = {
    sources: 'Centro de fuentes', inspecciones: 'Inspecciones', boletin_replica: 'Boletín', alerts: 'Alertas',
    council_commitments: 'Compromisos', observatory: 'Estudios', dashboard: 'Inicio',
};
const EMPTY_STUDY = { title: '', question: '', phenomenon: '', territory: '', period_start: '', period_end: '', hypotheses: '', access_level: 'INSTITUCIONAL' };

const formatDate = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value.slice(0, 10)}T12:00:00`))
    : '');
const clean = (form) => Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value === '' ? null : value]));

const Field = ({ label, children, hint }) => (
    <label className="block">
        <span className="text-xs font-black uppercase tracking-wide text-slate-600">{label}</span>
        <div className="mt-1">{children}</div>
        {hint && <span className="mt-1 block text-xs font-semibold text-slate-500">{hint}</span>}
    </label>
);
const inputClass = 'w-full border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-900 focus:border-[#281FD0] focus:outline-none';

// --- Situación ------------------------------------------------------------------------------

const SignalCard = ({ item, onNavigate, onStudy, onTab, onGoals }) => {
    const style = LEVEL_STYLES[item.level] || LEVEL_STYLES.INFO;
    return (
        <article className={`flex flex-col gap-2 border-l-4 bg-white p-4 shadow-sm ${style.bar}`}>
            <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-black leading-snug text-slate-950">{item.title}</h3>
                <span className={`shrink-0 px-2 py-0.5 text-[11px] font-black uppercase ${style.chip}`}>{style.label}</span>
            </div>
            <p className="text-sm font-semibold leading-6 text-slate-600">{item.detail}</p>
            <div className="mt-auto flex flex-wrap gap-2 pt-1">
                {item.page && item.page !== 'observatory' && (
                    <button onClick={() => onNavigate?.(item.page)} className="inline-flex items-center gap-1 text-sm font-black text-[#281FD0] hover:underline">
                        Ver en {PAGE_LABELS[item.page] || 'el módulo'} <ArrowRight size={15} />
                    </button>
                )}
                {item.key.startsWith('anomalia') && onTab && (
                    <button onClick={() => onTab('anomalias')} className="inline-flex items-center gap-1 text-sm font-black text-[#281FD0] hover:underline">
                        Ver en Anomalías <ArrowRight size={15} />
                    </button>
                )}
                {item.key.startsWith('solicitudes') && onTab && (
                    <button onClick={() => onTab('solicitudes')} className="inline-flex items-center gap-1 text-sm font-black text-[#281FD0] hover:underline">
                        Ver solicitudes de datos <ArrowRight size={15} />
                    </button>
                )}
                {item.key.startsWith('piscc') && onGoals && (
                    <button onClick={onGoals} className="inline-flex items-center gap-1 text-sm font-black text-[#281FD0] hover:underline">
                        Ver metas del PISCC <ArrowRight size={15} />
                    </button>
                )}
                {['ALTA', 'MEDIA'].includes(item.level) && item.key.startsWith('radar') && onStudy && (
                    <button onClick={() => onStudy(item)} className="inline-flex items-center gap-1 text-sm font-bold text-slate-600 hover:text-slate-950">
                        <BookOpen size={15} /> Abrir estudio
                    </button>
                )}
            </div>
        </article>
    );
};

const Situation = ({ overview, onNavigate, onStudy, onTab, onGoals }) => {
    const groups = useMemo(() => groupSignals(overview), [overview]);
    const counts = overview.counts || {};
    return (
        <div className="space-y-8">
            <div className="flex flex-wrap gap-3 text-sm font-bold">
                {['ALTA', 'MEDIA', 'OK'].map((level) => (
                    <span key={level} className={`px-3 py-1 ${LEVEL_STYLES[level].chip}`}>
                        {counts[level] || 0} · {LEVEL_STYLES[level].label}
                    </span>
                ))}
            </div>
            {groups.map((group) => (
                <section key={group.key} aria-labelledby={`grupo-${group.key}`}>
                    <div className="mb-3 flex flex-wrap items-baseline gap-x-3">
                        <h2 id={`grupo-${group.key}`} className="text-lg font-black text-slate-950">{group.label}</h2>
                        <p className="text-sm font-semibold text-slate-500">{group.question}</p>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                        {group.signals.map((item) => (
                            <SignalCard key={item.key} item={item} onNavigate={onNavigate} onStudy={onStudy} onTab={onTab} onGoals={onGoals} />
                        ))}
                    </div>
                </section>
            ))}
            <p className="text-xs font-semibold text-slate-500">{overview.rule}</p>
        </div>
    );
};

// --- Estudios -------------------------------------------------------------------------------

const StudyForm = ({ initial, onSaved, onCancel }) => {
    const [form, setForm] = useState({ ...EMPTY_STUDY, ...initial });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
    const submit = async (event) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        try {
            const study = await apiJson('/observatory/studies', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...clean(form), sources: [] }),
            });
            onSaved(study);
        } catch (saveError) {
            setError(saveError.message);
        } finally {
            setSaving(false);
        }
    };
    return (
        <form onSubmit={submit} className="space-y-4 border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-black text-slate-950">Nuevo estudio</h2>
            <Field label="Título"><input required minLength={3} value={form.title} onChange={set('title')} className={inputClass} /></Field>
            <Field label="Pregunta que responde" hint="Una sola pregunta concreta: qué fenómeno, dónde y en qué periodo.">
                <textarea required minLength={10} rows={2} value={form.question} onChange={set('question')} className={inputClass} />
            </Field>
            <div className="grid gap-4 md:grid-cols-2">
                <Field label="Fenómeno"><input value={form.phenomenon} onChange={set('phenomenon')} className={inputClass} placeholder="Hurto de vehículos" /></Field>
                <Field label="Territorio"><input value={form.territory} onChange={set('territory')} className={inputClass} placeholder="Vía Jamundí - Potrerito" /></Field>
                <Field label="Desde"><input type="date" value={form.period_start} onChange={set('period_start')} className={inputClass} /></Field>
                <Field label="Hasta"><input type="date" value={form.period_end} onChange={set('period_end')} className={inputClass} /></Field>
            </div>
            <Field label="Hipótesis iniciales"><textarea rows={3} value={form.hypotheses} onChange={set('hypotheses')} className={inputClass} /></Field>
            <Field label="Quién lo ve" hint="Reservado: solo el equipo de análisis y la dirección.">
                <select value={form.access_level} onChange={set('access_level')} className={inputClass}>
                    <option value="INSTITUCIONAL">Institucional</option>
                    <option value="RESERVADO">Reservado</option>
                </select>
            </Field>
            {error && <p role="alert" className="text-sm font-bold text-red-700">{error}</p>}
            <div className="flex gap-2">
                <button disabled={saving} className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white disabled:opacity-60">
                    {saving && <Loader2 size={16} className="animate-spin" />} Abrir estudio
                </button>
                <button type="button" onClick={onCancel} className="min-h-11 border border-slate-300 px-4 text-sm font-bold text-slate-700">Cancelar</button>
            </div>
        </form>
    );
};

const StudyDetail = ({ study, canEdit, onChanged }) => {
    const [findings, setFindings] = useState(study.findings || '');
    const [status, setStatus] = useState(study.status);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const changed = findings !== (study.findings || '') || status !== study.status;
    const save = async () => {
        setSaving(true);
        setError('');
        try {
            const { id, code, version, created_by, updated_by, created_at, updated_at, recommendations, recommendations_count, ...fields } = study;
            onChanged(await apiJson(`/observatory/studies/${id}`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...fields, findings: findings || null, status, expected_version: version }),
            }));
        } catch (saveError) {
            setError(saveError.message);
        } finally {
            setSaving(false);
        }
    };
    return (
        <div className="space-y-4 border-t border-slate-100 pt-4">
            <dl className="grid gap-3 text-sm md:grid-cols-3">
                <div><dt className="font-black text-slate-500">Territorio</dt><dd className="font-semibold text-slate-800">{study.territory || '—'}</dd></div>
                <div><dt className="font-black text-slate-500">Periodo</dt><dd className="font-semibold text-slate-800">{study.period_start ? `${formatDate(study.period_start)} – ${formatDate(study.period_end)}` : '—'}</dd></div>
                <div><dt className="font-black text-slate-500">Abierto por</dt><dd className="font-semibold text-slate-800">{study.created_by} · {formatDate(study.created_at)}</dd></div>
            </dl>
            {study.hypotheses && <p className="whitespace-pre-line text-sm font-semibold text-slate-700"><b>Hipótesis:</b> {study.hypotheses}</p>}
            {canEdit ? (
                <div className="space-y-3">
                    <Field label="Hallazgos" hint="Para cerrar el estudio, escriba lo que encontró.">
                        <textarea rows={4} value={findings} onChange={(event) => setFindings(event.target.value)} className={inputClass} />
                    </Field>
                    <div className="flex flex-wrap items-end gap-3">
                        <Field label="Estado">
                            <select value={status} onChange={(event) => setStatus(event.target.value)} className={inputClass}>
                                {Object.entries(STUDY_STATUS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                            </select>
                        </Field>
                        <button onClick={save} disabled={!changed || saving} className="min-h-10 bg-[#281FD0] px-4 text-sm font-black text-white disabled:opacity-50">Guardar</button>
                    </div>
                    {error && <p role="alert" className="text-sm font-bold text-red-700">{error}</p>}
                </div>
            ) : study.findings && <p className="whitespace-pre-line text-sm font-semibold text-slate-700"><b>Hallazgos:</b> {study.findings}</p>}
        </div>
    );
};

const Studies = ({ studies, canEdit, draft, onDraftDone, onChanged, onRecommend }) => {
    const [creating, setCreating] = useState(false);
    const [open, setOpen] = useState(null);
    const [detail, setDetail] = useState(null);
    const showForm = creating || draft;

    const toggle = async (study) => {
        if (open === study.id) { setOpen(null); return; }
        setOpen(study.id);
        setDetail(null);
        setDetail(await apiJson(`/observatory/studies/${study.id}`));
    };
    return (
        <div className="space-y-4">
            {canEdit && !showForm && (
                <button onClick={() => setCreating(true)} className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white">
                    <Plus size={17} /> Nuevo estudio
                </button>
            )}
            {showForm && (
                <StudyForm initial={draft || {}} onCancel={() => { setCreating(false); onDraftDone(); }}
                    onSaved={(study) => { setCreating(false); onDraftDone(); onChanged(); setOpen(study.id); setDetail(study); }} />
            )}
            {!studies.length && !showForm && (
                <p className="bg-slate-50 p-4 text-sm font-semibold text-slate-600">
                    Aún no hay estudios. Un estudio responde una pregunta que una señal dejó abierta: por qué crece un delito en un territorio, qué cambió, qué se podría hacer.
                </p>
            )}
            <ul className="space-y-3">
                {studies.map((study) => (
                    <li key={study.id} className="bg-white p-4 shadow-sm">
                        <button onClick={() => toggle(study)} className="flex w-full items-start justify-between gap-3 text-left" aria-expanded={open === study.id}>
                            <div>
                                <p className="text-xs font-black text-slate-500">{study.code} · {STUDY_STATUS[study.status]}{study.access_level === 'RESERVADO' ? ' · Reservado' : ''}</p>
                                <h3 className="mt-1 text-base font-black text-slate-950">{study.title}</h3>
                                <p className="mt-1 text-sm font-semibold text-slate-600">{study.question}</p>
                                <p className="mt-1 text-xs font-bold text-slate-500">{study.recommendations_count || 0} recomendaciones</p>
                            </div>
                            {open === study.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                        </button>
                        {open === study.id && (detail ? (
                            <>
                                <StudyDetail key={detail.version} study={detail} canEdit={canEdit} onChanged={(updated) => { setDetail(updated); onChanged(); }} />
                                {canEdit && study.status !== 'CERRADO' && (
                                    <button onClick={() => onRecommend(detail)} className="mt-3 inline-flex items-center gap-1 text-sm font-black text-[#281FD0]">
                                        <Lightbulb size={15} /> Redactar recomendación
                                    </button>
                                )}
                            </>
                        ) : <Loader2 className="mt-3 animate-spin text-slate-400" size={18} />)}
                    </li>
                ))}
            </ul>
        </div>
    );
};

// --- Recomendaciones ------------------------------------------------------------------------

const RecommendationForm = ({ study, studies, onSaved, onCancel }) => {
    const [form, setForm] = useState({ study_id: study?.id || '', title: '', text: '', addressed_to: 'Consejo de Seguridad', priority: 'MEDIA', due_date: '' });
    const [error, setError] = useState('');
    const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
    const submit = async (event) => {
        event.preventDefault();
        setError('');
        try {
            onSaved(await apiJson('/observatory/recommendations', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(clean(form)),
            }));
        } catch (saveError) {
            setError(saveError.message);
        }
    };
    return (
        <form onSubmit={submit} className="space-y-4 border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-black text-slate-950">Nueva recomendación</h2>
            <Field label="Estudio que la sustenta">
                <select value={form.study_id} onChange={set('study_id')} className={inputClass}>
                    <option value="">Sin estudio (señal directa)</option>
                    {studies.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.title}</option>)}
                </select>
            </Field>
            <Field label="Título"><input required minLength={3} value={form.title} onChange={set('title')} className={inputClass} /></Field>
            <Field label="Qué se recomienda" hint="Acción concreta, responsable sugerido y cómo se sabrá si funcionó.">
                <textarea required minLength={10} rows={4} value={form.text} onChange={set('text')} className={inputClass} />
            </Field>
            <div className="grid gap-4 md:grid-cols-3">
                <Field label="Instancia que decide"><input value={form.addressed_to} onChange={set('addressed_to')} className={inputClass} /></Field>
                <Field label="Prioridad">
                    <select value={form.priority} onChange={set('priority')} className={inputClass}>
                        <option value="ALTA">Alta</option><option value="MEDIA">Media</option><option value="BAJA">Baja</option>
                    </select>
                </Field>
                <Field label="Plazo sugerido"><input type="date" value={form.due_date} onChange={set('due_date')} className={inputClass} /></Field>
            </div>
            {error && <p role="alert" className="text-sm font-bold text-red-700">{error}</p>}
            <div className="flex gap-2">
                <button className="min-h-11 bg-[#281FD0] px-4 text-sm font-black text-white">Guardar como propuesta</button>
                <button type="button" onClick={onCancel} className="min-h-11 border border-slate-300 px-4 text-sm font-bold text-slate-700">Cancelar</button>
            </div>
        </form>
    );
};

const RecommendationCard = ({ item, canEdit, onSaved, onNavigate }) => {
    const [step, setStep] = useState('');
    const [note, setNote] = useState('');
    const [onDate, setOnDate] = useState('');
    const [commitment, setCommitment] = useState(item.commitment_code || '');
    const [error, setError] = useState('');
    const steps = nextRecommendationSteps(item.status);
    const submit = async () => {
        setError('');
        try {
            onSaved(await apiJson(`/observatory/recommendations/${item.id}/status`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: step, expected_version: item.version, note: note || null,
                    on_date: onDate || null, commitment_code: commitment || null }),
            }));
            setStep('');
            setNote('');
        } catch (saveError) {
            setError(saveError.message);
        }
    };
    return (
        <article className="bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                    <p className="text-xs font-black text-slate-500">{item.code}{item.study_code ? ` · ${item.study_code}` : ''} · prioridad {item.priority.toLowerCase()}</p>
                    <h3 className="mt-1 text-base font-black text-slate-950">{item.title}</h3>
                </div>
                <span className="bg-slate-100 px-2 py-0.5 text-xs font-black uppercase text-slate-700">{RECOMMENDATION_LABELS[item.status]}</span>
            </div>
            <p className="mt-2 whitespace-pre-line text-sm font-semibold leading-6 text-slate-700">{item.text}</p>
            <p className="mt-2 text-xs font-bold text-slate-500">
                Para: {item.addressed_to || 'sin instancia'}
                {item.presented_on && ` · presentada ${formatDate(item.presented_on)}`}
                {item.decided_on && ` · decidida ${formatDate(item.decided_on)}`}
                {item.due_date && ` · plazo ${formatDate(item.due_date)}`}
            </p>
            {item.decision_note && <p className="mt-1 text-sm font-semibold text-slate-600">Decisión: {item.decision_note}</p>}
            {item.commitment_code && (
                <button onClick={() => onNavigate?.('council_commitments')} className="mt-1 inline-flex items-center gap-1 text-sm font-black text-[#281FD0]">
                    Compromiso {item.commitment_code} <ArrowRight size={14} />
                </button>
            )}
            {canEdit && steps.length > 0 && (
                <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
                    <div className="flex flex-wrap gap-2">
                        {steps.map((option) => (
                            <button key={option} onClick={() => setStep(step === option ? '' : option)}
                                className={`min-h-9 px-3 text-sm font-bold ${step === option ? 'bg-[#281FD0] text-white' : 'border border-slate-300 text-slate-700'}`}>
                                {RECOMMENDATION_LABELS[option]}
                            </button>
                        ))}
                    </div>
                    {step && (
                        <div className="grid gap-2 md:grid-cols-3">
                            <input value={note} onChange={(event) => setNote(event.target.value)} className={`${inputClass} md:col-span-2`}
                                placeholder={['ACEPTADA', 'RECHAZADA'].includes(step) ? 'Quién decidió y en qué instancia (obligatorio)' : 'Nota (opcional)'} />
                            <input type="date" value={onDate} max={localToday()} onChange={(event) => setOnDate(event.target.value)} className={inputClass} aria-label="Fecha" />
                            {['ACEPTADA', 'EN_EJECUCION'].includes(step) && (
                                <input value={commitment} onChange={(event) => setCommitment(event.target.value)} className={inputClass}
                                    placeholder="Compromiso que la ejecuta (p. ej. CS-2026-018)" />
                            )}
                            <button onClick={submit} className="min-h-10 bg-[#281FD0] px-4 text-sm font-black text-white">Registrar</button>
                        </div>
                    )}
                    {error && <p role="alert" className="text-sm font-bold text-red-700">{error}</p>}
                </div>
            )}
        </article>
    );
};

// --- Página ---------------------------------------------------------------------------------

// Metas PISCC: resultados (tabla 16) y plan de acción (43 acciones, seguimiento semestral).
const PisccPanel = ({ canEdit }) => {
    const [view, setView] = useState('resultados');
    return (
        <div className="space-y-4">
            <div className="inline-flex border border-slate-300 bg-white" role="group">
                {[['resultados', 'Resultados (tabla 16)'], ['acciones', 'Plan de acción (43 acciones)']].map(([id, label]) => (
                    <button key={id} onClick={() => setView(id)} aria-pressed={view === id}
                        className={`px-4 py-2 text-sm font-black ${view === id ? 'bg-[#281FD0] text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
                        {label}
                    </button>
                ))}
            </div>
            {view === 'resultados' ? <PisccGoals /> : <PisccActions canEdit={canEdit} />}
        </div>
    );
};

const TABS = [
    { id: 'situacion', label: 'Situación actual' },
    { id: 'estudios', label: 'Estudios' },
    { id: 'recomendaciones', label: 'Recomendaciones' },
    { id: 'piscc', label: 'Metas PISCC' },
    { id: 'anomalias', label: 'Anomalías', internal: true },
    { id: 'territorios', label: 'Territorios', internal: true },
    { id: 'solicitudes', label: 'Solicitudes de datos', internal: true },
];

const ObservatoryCenter = ({ userRoles = [], onNavigate }) => {
    const [tab, setTab] = useState('situacion');
    const [overview, setOverview] = useState(null);
    const [studies, setStudies] = useState([]);
    const [recommendations, setRecommendations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [studyDraft, setStudyDraft] = useState(null);
    const [territory, setTerritory] = useState('');
    const [recommendFor, setRecommendFor] = useState(undefined);
    const canEdit = userRoles.some((role) => ['ANALYST', 'DIRECTIVE', 'FUNC_ADMIN', 'TI_ADMIN'].includes(role));

    const loadLists = useCallback(async () => {
        const [studyRows, recRows] = await Promise.all([apiJson('/observatory/studies'), apiJson('/observatory/recommendations')]);
        setStudies(studyRows);
        setRecommendations(recRows);
    }, []);
    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const [data] = await Promise.all([apiJson('/observatory/overview'), loadLists()]);
            setOverview(data);
        } catch (loadError) {
            setError(loadError.message);
        } finally {
            setLoading(false);
        }
    }, [loadLists]);
    useEffect(() => { load(); }, [load]);

    const studyFromSignal = (item) => {
        setStudyDraft({ title: item.title, question: `¿Qué explica que ${item.title.charAt(0).toLowerCase()}${item.title.slice(1)}?`, hypotheses: item.detail });
        setTab('estudios');
    };
    const pending = recommendations.filter((item) => !['RECHAZADA', 'CUMPLIDA'].includes(item.status));
    const closed = recommendations.filter((item) => ['RECHAZADA', 'CUMPLIDA'].includes(item.status));
    const replaceRecommendation = (updated) => {
        setRecommendations((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
        load();
    };

    return (
        <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
            <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-[#281FD0]">Observatorio del Delito · Centro de análisis</p>
                    <h1 className="mt-1 text-3xl font-black text-slate-950">Jamundí hoy</h1>
                    <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-600">
                        Lo que merece atención{overview?.as_of ? ` al ${formatDate(overview.as_of)}` : ''}: si los datos son confiables, qué cambia en el territorio,
                        qué decisiones siguen pendientes y qué está investigando y recomendando el Observatorio.
                    </p>
                </div>
                <button onClick={load} className="inline-flex min-h-11 items-center gap-2 self-start border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50" aria-label="Recargar">
                    <RefreshCw size={17} className={loading ? 'animate-spin' : ''} /> Actualizar
                </button>
            </header>

            <nav role="tablist" className="flex flex-wrap gap-2 border-b border-slate-200">
                {TABS.filter((item) => canEdit || !item.internal).map(({ id, label }) => (
                    <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                        className={`-mb-px border-b-4 px-4 py-2 text-sm font-black ${tab === id ? 'border-[#281FD0] text-[#281FD0]' : 'border-transparent text-slate-500 hover:text-slate-900'}`}>
                        {label}
                        {id === 'recomendaciones' && pending.length > 0 && <span className="ml-2 bg-slate-100 px-1.5 text-xs text-slate-700">{pending.length}</span>}
                        {id === 'estudios' && studies.length > 0 && <span className="ml-2 bg-slate-100 px-1.5 text-xs text-slate-700">{studies.length}</span>}
                    </button>
                ))}
            </nav>

            {error && <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}

            {tab === 'situacion' && canEdit && <WeekCalendar onTab={setTab} onNavigate={onNavigate} />}

            {tab === 'situacion' && (overview
                ? <Situation overview={overview} onNavigate={onNavigate} onStudy={canEdit ? studyFromSignal : null} onTab={canEdit ? setTab : null} onGoals={() => setTab('piscc')} />
                : loading && <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Reuniendo señales de los módulos…</p>)}

            {tab === 'estudios' && (
                <Studies studies={studies} canEdit={canEdit} draft={studyDraft} onDraftDone={() => setStudyDraft(null)}
                    onChanged={load} onRecommend={(study) => { setRecommendFor(study); setTab('recomendaciones'); }} />
            )}

            {tab === 'anomalias' && canEdit && <AnomalyRadar onStudy={studyFromSignal} onTerritory={(name) => { setTerritory(name); setTab('territorios'); }} />}

            {tab === 'piscc' && <PisccPanel canEdit={canEdit} />}

            {tab === 'solicitudes' && canEdit && <DataRequests />}

            {tab === 'territorios' && canEdit && <TerritoryProfile initialName={territory} onOpenCommitments={() => onNavigate?.('council_commitments')} />}

            {tab === 'recomendaciones' && (
                <div className="space-y-4">
                    {canEdit && recommendFor === undefined && (
                        <button onClick={() => setRecommendFor(null)} className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white">
                            <Plus size={17} /> Nueva recomendación
                        </button>
                    )}
                    {recommendFor !== undefined && (
                        <RecommendationForm study={recommendFor} studies={studies.filter((item) => item.status !== 'CERRADO')}
                            onCancel={() => setRecommendFor(undefined)}
                            onSaved={() => { setRecommendFor(undefined); load(); }} />
                    )}
                    <p className="text-sm font-semibold text-slate-600">
                        Cada recomendación va de propuesta a presentada y decidida. Si se acepta, se enlaza al compromiso que la ejecuta para seguirla hasta el final.
                    </p>
                    {!recommendations.length && <p className="bg-slate-50 p-4 text-sm font-semibold text-slate-600">Aún no hay recomendaciones.</p>}
                    <div className="grid gap-3">
                        {pending.map((item) => <RecommendationCard key={`${item.id}-${item.version}`} item={item} canEdit={canEdit} onSaved={replaceRecommendation} onNavigate={onNavigate} />)}
                    </div>
                    {closed.length > 0 && (
                        <details className="bg-slate-50 p-3">
                            <summary className="cursor-pointer text-sm font-black text-slate-700"><CheckCircle2 size={15} className="mr-1 inline" /> Cerradas ({closed.length})</summary>
                            <div className="mt-3 grid gap-3">
                                {closed.map((item) => <RecommendationCard key={item.id} item={item} canEdit={false} onNavigate={onNavigate} />)}
                            </div>
                        </details>
                    )}
                </div>
            )}
        </div>
    );
};

export default ObservatoryCenter;
