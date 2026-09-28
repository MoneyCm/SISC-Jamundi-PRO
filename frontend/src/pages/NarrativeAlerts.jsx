import React, { useCallback, useEffect, useState } from 'react';
import { Ban, CheckCircle2, ClipboardCopy, History, Loader2, MessageCircle, RefreshCcwDot, RefreshCw, RotateCcw, Save, Sparkles } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import {
    ACTION_LABELS, DIMENSION_LABELS, SOURCE_LABELS, STATE_LABELS, STATUS_LABELS, TRIGGER_LABELS, TYPES,
    checkText, formatProbability, typeLabel, whatsappUrl,
} from '../utils/narrativeAlerts';

const STATUS_STYLES = {
    BORRADOR: 'bg-amber-100 text-amber-800',
    ENVIADO: 'bg-emerald-100 text-emerald-800',
    DESCARTADO: 'bg-slate-200 text-slate-500',
    REEMPLAZADO: 'bg-slate-100 text-slate-500',
};
const FILTERS = [{ id: '', label: 'Todas' }, ...TYPES.map((type) => ({ id: type.code, label: type.label }))];

const formatDate = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value.slice(0, 10)}T12:00:00`))
    : '');
const formatDateTime = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
    : '');

const Chip = ({ status }) => (
    <span className={`px-2 py-0.5 text-[11px] font-black uppercase tracking-wide ${STATUS_STYLES[status] || ''}`}>{STATUS_LABELS[status] || status}</span>
);

const Evidence = ({ evidence }) => {
    if (!evidence) return null;
    const { selected = [], commitments = {}, periods = {}, totals = {} } = evidence;
    return (
        <section className="space-y-3 border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-black uppercase tracking-wide text-slate-700">Por qué dice esto</h3>
            <p className="text-sm font-semibold text-slate-600">
                {formatDate(periods.current?.start)} a {formatDate(periods.current?.end)}: {totals.current} hechos · periodo anterior: {totals.previous}.
                {' '}Se hicieron {evidence.tests} comparaciones; por azar se esperan unas {String(evidence.expected_by_chance).replace('.', ',')} variaciones que parecen significativas sin serlo.
            </p>
            {selected.length === 0 && <p className="text-sm font-semibold text-slate-600">Ninguna variación cumplió los criterios.</p>}
            <ul className="space-y-2">
                {selected.map((item, index) => {
                    const related = commitments.related?.[index] || [];
                    return (
                        <li key={`${item.dimension}-${item.category}`} className="border-l-4 border-[#281FD0] bg-slate-50 p-3 text-sm">
                            <p className="font-black text-slate-900">{DIMENSION_LABELS[item.dimension]}: {item.label || item.category}</p>
                            <p className="font-semibold text-slate-600">
                                {item.previous} → {item.current} hechos · {item.baseline_expected == null ? 'sin periodos anteriores para comparar' : `promedio de ${evidence.baseline_periods === 1 ? 'el periodo anterior con datos' : `los ${evidence.baseline_periods ?? 4} periodos anteriores`}: ${String(item.baseline_expected).replace('.', ',')}`}
                                {' '}· probabilidad de verlo por azar: {formatProbability(item.p_value)}{item.strict ? ' (supera también el umbral estricto)' : ''}
                            </p>
                            <p className="mt-1 font-semibold text-slate-600">
                                {related.length
                                    ? <>Compromisos relacionados: {related.map((c) => `${c.code} (${STATE_LABELS[c.state] || c.state})`).join(', ')}</>
                                    : 'Sin compromisos del Consejo relacionados.'}
                            </p>
                        </li>
                    );
                })}
            </ul>
            {(evidence.context || []).length > 0 && (
                <div className="space-y-1">
                    <p className="text-xs font-black uppercase tracking-wide text-slate-500">Otras fuentes</p>
                    <ul className="space-y-1 text-sm">
                        {evidence.context.map((item) => (
                            <li key={item.source} className={`border-l-4 p-2 ${item.included ? 'border-emerald-500 bg-emerald-50' : 'border-slate-300 bg-slate-50'}`}>
                                <span className="font-black text-slate-900">{SOURCE_LABELS[item.source] || item.source}</span>
                                {item.included ? '' : ' (no cupo en el mensaje)'}: <span className="font-semibold text-slate-700">{item.line}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            <p className="text-sm font-semibold text-slate-600">
                Compromisos: {commitments.overdue?.length || 0} vencidos
                {commitments.overdue?.length ? ` (${commitments.overdue.slice(0, 8).join(', ')}${commitments.overdue.length > 8 ? '…' : ''})` : ''}
                {' '}· {commitments.due_soon?.length || 0} por vencer · {commitments.fulfilled_recent?.length || 0} cumplidos recientes · {commitments.open} abiertos.
            </p>
        </section>
    );
};

const Rules = ({ rules }) => (
    <details className="border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-sm font-black uppercase tracking-wide text-slate-700">Criterios de variación significativa</summary>
        <dl className="mt-3 space-y-3 text-sm">
            {rules.map((rule) => (
                <div key={rule.code}>
                    <dt className="font-black text-slate-900">{rule.title}</dt>
                    <dd className="font-semibold leading-6 text-slate-600">{rule.text}</dd>
                </div>
            ))}
        </dl>
    </details>
);

const Editor = ({ alert, onChanged }) => {
    const [text, setText] = useState(alert.text);
    const [note, setNote] = useState('');
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    const [copied, setCopied] = useState(false);
    const editable = alert.status === 'BORRADOR';
    const dirty = text !== alert.text;
    const check = checkText(text, alert.max_lines, alert.max_chars);

    useEffect(() => { setText(alert.text); setNote(''); setError(''); }, [alert.id, alert.version, alert.text]);

    const act = async (label, path, body, method = 'POST') => {
        setBusy(label);
        setError('');
        try {
            await apiJson(`/narrative-alerts/${alert.id}${path}`, {
                method, headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ expected_version: alert.version, ...body }),
            });
            setNote('');
            await onChanged();
        } catch (actionError) {
            setError(actionError.message);
        } finally {
            setBusy('');
        }
    };

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(alert.text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            setError('No se pudo copiar. Seleccione el texto y cópielo a mano.');
        }
    };

    return (
        <section className="space-y-3 border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-black uppercase tracking-wide text-slate-700">Mensaje</h3>
                <p className={`text-xs font-bold ${check.error ? 'text-red-700' : 'text-slate-500'}`}>
                    {check.lines} de {alert.max_lines} líneas · {check.chars} de {alert.max_chars} caracteres{alert.edited ? ' · editado a mano' : ''}
                </p>
            </div>
            <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                readOnly={!editable}
                rows={Math.min(16, (alert.max_lines || 6) + 2)}
                aria-label="Texto del mensaje"
                className="w-full resize-y border border-slate-300 p-3 font-mono text-sm leading-6 text-slate-900 read-only:bg-slate-50"
            />
            {(check.error || error) && <p role="alert" className="bg-red-50 p-2 text-sm font-bold text-red-800">{check.error || error}</p>}
            {editable && (
                <input
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    maxLength={300}
                    placeholder="Nota opcional: qué cambió, a quién se envió o por qué se descarta"
                    className="w-full border border-slate-300 p-2 text-sm"
                />
            )}
            <div className="flex flex-wrap gap-2">
                {editable && (
                    <>
                        <button disabled={!dirty || !!check.error || !!busy} onClick={() => act('save', '/text', { text, note: note || null }, 'PUT')}
                            className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-3 text-sm font-black text-white hover:bg-[#1F18A8] disabled:opacity-40">
                            {busy === 'save' ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Guardar cambios
                        </button>
                        <button disabled={dirty || !!busy} onClick={() => act('refresh', '/refresh', {})}
                            title={dirty ? 'Guarde o deshaga sus cambios antes de actualizar' : 'Recalcula con la última sábana y el estado actual de los compromisos'}
                            className="inline-flex min-h-10 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40">
                            {busy === 'refresh' ? <Loader2 size={16} className="animate-spin" /> : <RefreshCcwDot size={16} />} Actualizar borrador
                        </button>
                        {(dirty || alert.edited) && (
                            <button disabled={!!busy} onClick={() => setText(dirty ? alert.text : alert.generated_text)}
                                className="inline-flex min-h-10 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">
                                <RotateCcw size={16} /> {dirty ? 'Deshacer cambios' : 'Volver al texto generado'}
                            </button>
                        )}
                    </>
                )}
                <button disabled={dirty} onClick={copy} title={dirty ? 'Guarde los cambios antes de copiar' : ''}
                    className="inline-flex min-h-10 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40">
                    <ClipboardCopy size={16} /> {copied ? 'Copiado' : 'Copiar'}
                </button>
                <a href={dirty ? undefined : whatsappUrl(alert.text)} target="_blank" rel="noreferrer" aria-disabled={dirty}
                    className={`inline-flex min-h-10 items-center gap-2 bg-[#25D366] px-3 text-sm font-black text-slate-950 hover:bg-[#1FB855] ${dirty ? 'pointer-events-none opacity-40' : ''}`}>
                    <MessageCircle size={16} /> Abrir en WhatsApp
                </a>
                {editable && (
                    <>
                        <button disabled={dirty || !!busy} onClick={() => act('sent', '/sent', { note: note || null })}
                            className="inline-flex min-h-10 items-center gap-2 border border-emerald-600 bg-white px-3 text-sm font-black text-emerald-800 hover:bg-emerald-50 disabled:opacity-40">
                            <CheckCircle2 size={16} /> Marcar como enviado
                        </button>
                        <button disabled={!!busy || !note.trim()} onClick={() => act('discard', '/discard', { note })}
                            title={note.trim() ? '' : 'Escriba en la nota por qué se descarta'}
                            className="inline-flex min-h-10 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                            <Ban size={16} /> Descartar
                        </button>
                    </>
                )}
            </div>
            {dirty && <p className="text-xs font-semibold text-slate-500">Guarde los cambios para copiar, abrir en WhatsApp o marcar como enviado: así queda registrado exactamente lo que salió.</p>}
            {alert.status === 'ENVIADO' && (
                <p className="text-sm font-semibold text-emerald-800">Enviado por {alert.sent_by} el {formatDateTime(alert.sent_at)}{alert.sent_note ? ` · ${alert.sent_note}` : ''}.</p>
            )}
        </section>
    );
};

const Revisions = ({ revisions }) => (
    <details className="border border-slate-200 bg-white p-4">
        <summary className="inline-flex cursor-pointer items-center gap-2 text-sm font-black uppercase tracking-wide text-slate-700">
            <History size={16} /> Historial ({revisions.length})
        </summary>
        <ol className="mt-3 space-y-3">
            {revisions.slice().reverse().map((revision) => (
                <li key={`${revision.version}-${revision.action}`} className="border-l-2 border-slate-300 pl-3 text-sm">
                    <p className="font-black text-slate-900">{ACTION_LABELS[revision.action] || revision.action} · {revision.username} · {formatDateTime(revision.created_at)}</p>
                    {revision.note && <p className="font-semibold text-slate-600">{revision.note}</p>}
                    <pre className="mt-1 whitespace-pre-wrap bg-slate-50 p-2 font-mono text-xs text-slate-700">{revision.text}</pre>
                </li>
            ))}
        </ol>
    </details>
);

const NarrativeAlerts = () => {
    const [items, setItems] = useState([]);
    const [filter, setFilter] = useState('');
    const [selectedId, setSelectedId] = useState(null);
    const [detail, setDetail] = useState(null);
    const [rules, setRules] = useState([]);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState('');
    const [newType, setNewType] = useState('SEMANAL');
    const [message, setMessage] = useState(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const rows = await apiJson(`/narrative-alerts/${filter ? `?frequency=${filter}` : ''}`);
            setItems(rows);
            setSelectedId((current) => (current && rows.some((row) => row.id === current) ? current : rows[0]?.id || null));
        } catch (loadError) {
            setMessage({ type: 'error', text: loadError.message });
        } finally {
            setLoading(false);
        }
    }, [filter]);

    const loadDetail = useCallback(async () => {
        if (!selectedId) { setDetail(null); return; }
        try {
            setDetail(await apiJson(`/narrative-alerts/${selectedId}`));
        } catch (detailError) {
            setMessage({ type: 'error', text: detailError.message });
        }
    }, [selectedId]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { loadDetail(); }, [loadDetail]);
    useEffect(() => { apiJson('/narrative-alerts/rules').then((data) => setRules(data.rules)).catch(() => setRules([])); }, []);

    const refresh = async () => { await load(); await loadDetail(); };

    const generate = async (frequency) => {
        setGenerating(frequency);
        setMessage(null);
        try {
            const data = await apiJson('/narrative-alerts/generate', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ frequency }),
            });
            const name = `${typeLabel(frequency).toLowerCase()} (${data.occasion_label ? `sesión ${data.occasion_label}` : data.period_label})`;
            setMessage({
                type: 'success',
                text: data.created
                    ? `Mensaje ${name} generado.`
                    : data.status === 'BORRADOR'
                        ? `Ya existe el mensaje ${name} con estos datos; se abrió ese. Use «Actualizar borrador» para recalcularlo con los compromisos al día.`
                        : `El mensaje ${name} ya está ${data.status.toLowerCase()}; se abrió ese.`,
            });
            setFilter('');
            setSelectedId(data.id);
            await load();
        } catch (generateError) {
            setMessage({ type: 'error', text: generateError.message });
        } finally {
            setGenerating('');
        }
    };

    return (
        <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
            <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-[#281FD0]">Antes: Alertas Narrativas</p>
                    <h1 className="mt-1 text-3xl font-black text-slate-950">Resúmenes para WhatsApp</h1>
                    <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-600">
                        El SISC redacta mensajes cortos con las variaciones más significativas por delito, barrio y franja horaria, el estado de los
                        compromisos del Consejo y lo que aportan otras fuentes. La semanal sale al cargar cada sábana; la mensual, semestral y anual cuando
                        la sábana completa el periodo; la del Consejo, el día antes de la sesión. También puede generarlas cuando las necesite. Uso interno.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <label className="sr-only" htmlFor="alert-type">Tipo de alerta</label>
                    <select id="alert-type" value={newType} onChange={(event) => setNewType(event.target.value)} disabled={!!generating}
                        className="min-h-11 border border-slate-300 bg-white px-2 text-sm font-bold text-slate-800">
                        {TYPES.map((type) => <option key={type.code} value={type.code}>{type.label} (hasta {type.maxLines} líneas)</option>)}
                    </select>
                    <button disabled={!!generating} onClick={() => generate(newType)}
                        className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8] disabled:opacity-50">
                        {generating ? <Loader2 size={17} className="animate-spin" /> : <Sparkles size={17} />} Generar
                    </button>
                    <button onClick={refresh} aria-label="Recargar" className="inline-flex min-h-11 items-center border border-slate-300 bg-white px-3 text-slate-700 hover:bg-slate-50">
                        <RefreshCw size={17} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </header>

            {message && (
                <p role="status" className={`p-3 text-sm font-bold ${message.type === 'error' ? 'bg-red-50 text-red-800' : 'bg-emerald-50 text-emerald-800'}`}>{message.text}</p>
            )}

            <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
                <aside className="space-y-3">
                    <div className="flex flex-wrap gap-1" role="tablist">
                        {FILTERS.map((item) => (
                            <button key={item.id || 'todas'} role="tab" aria-selected={filter === item.id} onClick={() => setFilter(item.id)}
                                className={`min-h-9 px-3 text-xs font-black ${filter === item.id ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700'}`}>
                                {item.label}
                            </button>
                        ))}
                    </div>
                    {!items.length && !loading && <p className="text-sm font-semibold text-slate-500">Aún no hay mensajes. Genere uno o cargue una sábana nueva.</p>}
                    <ul className="space-y-2">
                        {items.map((item) => (
                            <li key={item.id}>
                                <button onClick={() => setSelectedId(item.id)}
                                    className={`w-full border p-3 text-left ${selectedId === item.id ? 'border-[#281FD0] bg-indigo-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}>
                                    <span className="flex items-center justify-between gap-2">
                                        <span className="text-xs font-black uppercase tracking-wide text-slate-500">{typeLabel(item.frequency)}</span>
                                        <Chip status={item.status} />
                                    </span>
                                    <span className="mt-1 block font-black text-slate-900">{item.occasion_label ? `Sesión: ${item.occasion_label}` : item.period_label}</span>
                                    <span className="block text-xs font-semibold text-slate-500">
                                        {TRIGGER_LABELS[item.trigger] || `Generado por ${item.created_by}`} · {formatDateTime(item.created_at)}{item.edited ? ' · editado' : ''}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                </aside>

                <main className="min-w-0 space-y-4">
                    {detail ? (
                        <>
                            <div className="flex flex-wrap items-center gap-2">
                                <h2 className="text-xl font-black text-slate-950">{detail.type_title}: {detail.occasion_label ? `sesión ${detail.occasion_label}` : detail.period_label}</h2>
                                <Chip status={detail.status} />
                            </div>
                            <p className="text-sm font-semibold text-slate-600">
                                Comparado con {formatDate(detail.previous_start)} a {formatDate(detail.previous_end)} · sábana policial con corte al {formatDate(detail.data_cutoff)} · reglas {detail.rules_version}
                            </p>
                            {detail.status === 'REEMPLAZADO' && (
                                <p className="bg-slate-100 p-3 text-sm font-bold text-slate-700">Una entrega policial más reciente generó otra versión de este periodo.</p>
                            )}
                            <Editor alert={detail} onChanged={refresh} />
                            <Evidence evidence={detail.evidence} />
                            {rules.length > 0 && <Rules rules={rules} />}
                            <Revisions revisions={detail.revisions || []} />
                        </>
                    ) : (
                        rules.length > 0 && <Rules rules={rules} />
                    )}
                </main>
            </div>
        </div>
    );
};

export default NarrativeAlerts;
