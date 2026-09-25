import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, ClipboardCopy, Clock, FileText, History, Loader2, RefreshCw, Repeat, Search, Upload } from 'lucide-react';
import ActReviewPanel from '../components/ActReviewPanel';
import RecurringTopics from '../components/RecurringTopics';
import { apiFetch, apiJson } from '../utils/apiClient';

const STATUS_STYLES = {
    SIN_INFORMACION: 'bg-slate-100 text-slate-600',
    PENDIENTE: 'bg-amber-100 text-amber-800',
    EN_CURSO: 'bg-blue-100 text-blue-800',
    CUMPLIDO: 'bg-emerald-100 text-emerald-800',
    NO_CUMPLIDO: 'bg-red-100 text-red-800',
    DESCARTADO: 'bg-slate-200 text-slate-500',
};
const FILTERS = [
    { id: '', label: 'Todos' },
    { id: 'REPETIDO', label: 'Repetidos sin cumplirse' },
    { id: 'ATRASADO', label: 'Atrasados' },
    { id: 'SIN_FECHA', label: 'Sin fecha límite' },
    { id: 'SIN_INFORMACION', label: 'Sin información' },
];
const CLOSING = new Set(['CUMPLIDO', 'NO_CUMPLIDO', 'DESCARTADO']);

const formatDate = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`))
    : '');

const Tile = ({ label, value, helper, tone = 'slate' }) => {
    const tones = { slate: 'border-slate-200', red: 'border-red-300', amber: 'border-amber-300', blue: 'border-[#281FD0]' };
    return (
        <div className={`border-t-4 bg-white p-4 shadow-sm ${tones[tone]}`}>
            <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">{label}</p>
            <p className="mt-1 text-3xl font-black tabular-nums text-slate-950">{value}</p>
            {helper && <p className="mt-1 text-xs font-semibold text-slate-500">{helper}</p>}
        </div>
    );
};

const CommitmentCard = ({ item, statuses, onSaved }) => {
    const [status, setStatus] = useState(item.status);
    const [note, setNote] = useState('');
    const [evidence, setEvidence] = useState('');
    const [deadline, setDeadline] = useState(item.deadline_date || '');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [history, setHistory] = useState(null);
    const changed = status !== item.status || note.trim() || evidence.trim() || (deadline || '') !== (item.deadline_date || '');
    const needsSupport = CLOSING.has(status) && !note.trim() && !evidence.trim();

    const save = async () => {
        setSaving(true);
        setError('');
        try {
            const updated = await apiJson(`/council-commitments/${encodeURIComponent(item.code)}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    status, expected_version: item.version, note: note || null,
                    evidence_url: evidence || null, deadline_date: deadline || null,
                }),
            });
            setNote('');
            setEvidence('');
            setHistory(null);
            onSaved(updated);
        } catch (saveError) {
            setError(saveError.message);
        } finally {
            setSaving(false);
        }
    };

    const toggleHistory = async () => {
        if (history) { setHistory(null); return; }
        try {
            setHistory(await apiJson(`/council-commitments/${encodeURIComponent(item.code)}/history`));
        } catch (historyError) {
            setError(historyError.message);
        }
    };

    return (
        <article className="border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-black text-slate-400">{item.code}</span>
                        {item.instance_label && <span className="bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600">{item.instance_label}</span>}
                        {item.kind === 'ACUERDO' && <span className="bg-violet-100 px-2 py-0.5 text-[11px] font-black text-violet-800">Acuerdo</span>}
                        <span className={`px-2 py-0.5 text-[11px] font-black ${STATUS_STYLES[item.status] || STATUS_STYLES.SIN_INFORMACION}`}>{item.status_label}</span>
                        {item.flags.includes('REPETIDO') && (
                            <span className="inline-flex items-center gap-1 bg-red-50 px-2 py-0.5 text-[11px] font-black text-red-700"><Repeat size={12} /> Mencionado {item.mentions} veces</span>
                        )}
                        {item.flags.includes('ATRASADO') && (
                            <span className="inline-flex items-center gap-1 bg-amber-50 px-2 py-0.5 text-[11px] font-black text-amber-800"><Clock size={12} /> Atrasado</span>
                        )}
                    </div>
                    <p className="mt-2 text-base font-bold leading-6 text-slate-900">{item.text}</p>
                    <p className="mt-1 text-sm font-semibold text-slate-600">
                        {item.responsible || 'Responsable por definir'} · {item.deadline_date ? `Plazo: ${formatDate(item.deadline_date)}` : item.deadline_text ? `Plazo: ${item.deadline_text}` : 'Sin fecha límite'}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-slate-400">
                        {[item.origin_act, item.origin_date && formatDate(item.origin_date), item.theme, item.territory].filter(Boolean).join(' · ')}
                        {item.mentions > 1 && item.last_mention_date ? ` · Última mención: ${formatDate(item.last_mention_date)}` : ''}
                    </p>
                </div>
            </div>

            <div className="mt-4 grid gap-3 border-t border-slate-100 pt-4 md:grid-cols-[180px_160px_1fr]">
                <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Estado
                    <select value={status} onChange={(event) => setStatus(event.target.value)} className="mt-1 w-full border border-slate-300 bg-white px-2 py-2 text-sm font-bold normal-case text-slate-800">
                        {statuses.map((option) => <option key={option.code} value={option.code}>{option.label}</option>)}
                    </select>
                </label>
                <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Fecha límite
                    <input type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} className="mt-1 w-full border border-slate-300 px-2 py-2 text-sm font-bold text-slate-800" />
                </label>
                <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Avance o cómo se verificó
                    <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} placeholder="Ej.: la Policía envió el informe el 20/09 por correo" className="mt-1 w-full border border-slate-300 px-2 py-2 text-sm font-semibold normal-case text-slate-800" />
                </label>
            </div>
            <div className="mt-3 flex flex-wrap items-end gap-3">
                <label className="min-w-[240px] flex-1 text-[11px] font-black uppercase tracking-wide text-slate-500">Enlace al soporte (opcional)
                    <input value={evidence} onChange={(event) => setEvidence(event.target.value)} maxLength={1000} placeholder="https://drive.google.com/…" className="mt-1 w-full border border-slate-300 px-2 py-2 text-sm font-semibold normal-case text-slate-800" />
                </label>
                <button onClick={save} disabled={!changed || saving || needsSupport} className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8] disabled:cursor-not-allowed disabled:opacity-40">
                    {saving ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Guardar
                </button>
                <button onClick={toggleHistory} className="inline-flex min-h-10 items-center gap-2 border border-slate-300 px-3 text-sm font-bold text-slate-600 hover:bg-slate-50">
                    <History size={16} /> Historial
                </button>
            </div>
            {needsSupport && <p className="mt-2 text-xs font-bold text-amber-700">Para cerrar un compromiso escriba cómo se verificó o agregue el enlace al soporte.</p>}
            {error && <p className="mt-2 text-sm font-bold text-red-700" role="alert">{error}</p>}
            {history && (
                <ol className="mt-3 space-y-1 border-l-2 border-slate-200 pl-3 text-xs font-semibold text-slate-600">
                    {history.map((entry) => (
                        <li key={entry.version}>
                            {new Date(entry.created_at).toLocaleString('es-CO')} · {entry.username} · {entry.action === 'IMPORTADO' ? 'Importado del acta' : entry.previous_status && entry.previous_status !== entry.new_status ? `${entry.previous_status} → ${entry.new_status}` : entry.new_status}
                            {entry.note ? ` · ${entry.note}` : ''}
                            {entry.evidence_url && <> · <a href={entry.evidence_url} target="_blank" rel="noopener noreferrer" className="text-[#281FD0] underline">soporte</a></>}
                        </li>
                    ))}
                </ol>
            )}
        </article>
    );
};

const CouncilCommitments = () => {
    const [items, setItems] = useState([]);
    const [statuses, setStatuses] = useState([]);
    const [themes, setThemes] = useState([]);
    const [instances, setInstances] = useState([]);
    const [instance, setInstance] = useState('');
    const [reader, setReader] = useState(false);
    const [pendingReads, setPendingReads] = useState([]);
    const [openReadId, setOpenReadId] = useState(null);
    const [view, setView] = useState('seguimiento');
    const [summary, setSummary] = useState(null);
    const [flag, setFlag] = useState('REPETIDO');
    const [theme, setTheme] = useState('');
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(true);
    const [message, setMessage] = useState(null);
    const [agenda, setAgenda] = useState('');
    const fileRef = useRef(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [list, totals] = await Promise.all([apiJson('/council-commitments/'), apiJson('/council-commitments/summary')]);
            setItems(list.items);
            setStatuses(list.statuses);
            setThemes(list.themes);
            setInstances(list.instances || []);
            setSummary(totals);
            apiJson('/council-commitments/acts').then(setPendingReads).catch(() => setPendingReads([]));
        } catch (loadError) {
            setMessage({ type: 'error', text: loadError.message });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const visible = useMemo(() => {
        const text = query.trim().toLowerCase();
        return items
            .filter((item) => !instance || item.instance === instance)
            .filter((item) => !flag || item.flags.includes(flag))
            .filter((item) => !theme || item.theme === theme)
            .filter((item) => !text || [item.code, item.text, item.responsible, item.territory].join(' ').toLowerCase().includes(text))
            .sort((a, b) => (b.mentions || 1) - (a.mentions || 1) || String(b.origin_date).localeCompare(String(a.origin_date)));
    }, [items, instance, flag, theme, query]);

    const instanceCounts = useMemo(() => instances
        .map((option) => ({ ...option, count: items.filter((item) => item.instance === option.code).length }))
        .filter((option) => option.count > 0), [instances, items]);

    const closeReader = () => { setReader(false); setOpenReadId(null); };

    const onActDiscarded = async (reading) => {
        closeReader();
        setMessage({ type: 'success', text: `Lectura de ${reading.filename} descartada.` });
        await load();
    };

    const onActConfirmed = async (result, reading) => {
        closeReader();
        const parts = [
            result.created.length && `${result.created.length} nuevo(s): ${result.created.join(', ')}`,
            result.linked.length && `${result.linked.length} mención(es) sumada(s) a compromisos existentes`,
            result.skipped && `${result.skipped} descartado(s)`,
        ].filter(Boolean);
        setMessage({ type: 'success', text: `${reading.instance_label}${reading.act_number ? `, acta ${reading.act_number}` : ''}: ${parts.join(' · ') || 'sin cambios'}.` });
        setFlag('');
        await load();
    };

    const onSaved = (updated) => {
        setItems((current) => current.map((item) => (item.code === updated.code ? updated : item)));
        apiJson('/council-commitments/summary').then(setSummary).catch(() => {});
        setMessage({ type: 'success', text: `${updated.code} actualizado: ${updated.status_label}.` });
    };

    const buildAgenda = async () => {
        try {
            const data = await apiJson('/council-commitments/agenda');
            setAgenda(data.text);
            try {
                await navigator.clipboard.writeText(data.text);
                setMessage({ type: 'success', text: 'Lectura de compromisos copiada. Pégala en el acta o en el orden del día.' });
            } catch {
                setMessage({ type: 'success', text: 'Lectura de compromisos lista abajo; cópiala desde el recuadro.' });
            }
        } catch (agendaError) {
            setMessage({ type: 'error', text: agendaError.message });
        }
    };

    const importFile = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        const body = new FormData();
        body.append('file', file);
        try {
            const response = await apiFetch('/council-commitments/import', { method: 'POST', body });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || 'No se pudo importar el archivo.');
            setMessage({ type: 'success', text: `Importación lista: ${data.created} nuevos, ${data.updated} actualizados, ${data.unchanged} sin cambios. Los estados registrados en el SISC se conservan.` });
            await load();
        } catch (importError) {
            setMessage({ type: 'error', text: importError.message });
        } finally {
            if (fileRef.current) fileRef.current.value = '';
        }
    };

    return (
        <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
            <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-[#281FD0]">Consejo, comités y reuniones</p>
                    <h1 className="mt-1 text-3xl font-black text-slate-950">Compromisos y acuerdos</h1>
                    <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-600">
                        Seguimiento de lo que se decide en el Consejo de Seguridad, el Comité de Orden Público, el Comité Civil de Convivencia y las reuniones de planeación. Suba cada acta, revise lo que el SISC encontró y actualice el estado antes de cada sesión.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button onClick={() => { setOpenReadId(null); setReader(true); }} className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8]">
                        <FileText size={17} /> Leer acta
                    </button>
                    <button onClick={buildAgenda} className="inline-flex min-h-11 items-center gap-2 bg-[#FFE000] px-4 text-sm font-black text-slate-950 hover:bg-[#FFB600]">
                        <ClipboardCopy size={17} /> Lectura para el próximo Consejo
                    </button>
                    <button onClick={() => fileRef.current?.click()} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50">
                        <Upload size={17} /> Importar hoja (CSV o XLSX)
                    </button>
                    <input ref={fileRef} type="file" accept=".csv,.xlsx" onChange={importFile} className="hidden" />
                    <button onClick={load} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50" aria-label="Recargar">
                        <RefreshCw size={17} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </header>

            {message && (
                <p role="status" className={`p-3 text-sm font-bold ${message.type === 'error' ? 'bg-red-50 text-red-800' : 'bg-emerald-50 text-emerald-800'}`}>{message.text}</p>
            )}

            {reader && (
                <ActReviewPanel key={openReadId || 'nueva'} instances={instances} readId={openReadId}
                    onClose={closeReader} onConfirmed={onActConfirmed} onDiscarded={onActDiscarded} />
            )}

            {!reader && pendingReads.length > 0 && (
                <section className="border border-amber-300 bg-amber-50 p-4">
                    <h2 className="text-sm font-black uppercase tracking-wide text-amber-900">Actas por confirmar ({pendingReads.length})</h2>
                    <p className="mt-1 text-sm font-semibold text-amber-900">Ya fueron leídas. Revise cada una y confirme qué compromisos y acuerdos quedan registrados.</p>
                    <ul className="mt-3 divide-y divide-amber-200">
                        {pendingReads.map((item) => (
                            <li key={item.read_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                                <div className="min-w-0">
                                    <p className="text-sm font-black text-slate-900">
                                        {item.instance_label}{item.act_number ? ` · Acta ${item.act_number}` : ''}{item.act_date ? ` · ${formatDate(item.act_date)}` : ''}
                                    </p>
                                    <p className="text-xs font-semibold text-slate-600">
                                        {item.proposals} encontrado(s){item.warnings.length ? ` · ${item.warnings.length} advertencia(s)` : ''} · {item.filename}
                                    </p>
                                </div>
                                <button onClick={() => { setOpenReadId(item.read_id); setReader(true); }} className="inline-flex min-h-9 items-center gap-2 bg-[#281FD0] px-3 text-sm font-black text-white hover:bg-[#1F18A8]">
                                    <FileText size={15} /> Revisar
                                </button>
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {summary && (
                <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <Tile label="Compromisos abiertos" value={summary.open} helper={`de ${summary.total} registrados`} tone="blue" />
                    <Tile label="Repetidos sin cumplirse" value={summary.repeated} helper="Pedidos en más de una sesión" tone="red" />
                    <Tile label="Atrasados" value={summary.overdue} helper="Con fecha límite vencida" tone="amber" />
                    <Tile label="Sin información" value={summary.without_information} helper={`${summary.without_deadline} sin fecha límite`} />
                </section>
            )}

            {summary?.without_information === summary?.total && summary?.total > 0 && (
                <p className="flex items-start gap-2 bg-amber-50 p-3 text-sm font-semibold text-amber-900">
                    <AlertTriangle size={18} className="mt-0.5 shrink-0" />
                    Ningún compromiso tiene seguimiento registrado todavía. Empiece por los repetidos: son los que el Consejo vuelve a pedir en cada sesión.
                </p>
            )}

            {agenda && (
                <textarea readOnly value={agenda} rows={12} className="w-full border border-slate-300 bg-white p-3 font-mono text-xs text-slate-800" aria-label="Lectura de compromisos" />
            )}

            <div className="flex gap-1 border-b border-slate-200" role="tablist">
                {[['seguimiento', 'Seguimiento'], ['temas', 'Temas que vuelven']].map(([id, label]) => (
                    <button key={id} role="tab" aria-selected={view === id} onClick={() => setView(id)}
                        className={`min-h-10 px-4 text-sm font-black ${view === id ? 'border-b-4 border-[#281FD0] text-slate-950' : 'text-slate-500 hover:text-slate-800'}`}>
                        {label}
                    </button>
                ))}
            </div>

            {view === 'temas' ? <RecurringTopics /> : (
            <section className="space-y-3">
                {instanceCounts.length > 1 && (
                    <div className="flex flex-wrap gap-2" role="group" aria-label="Instancia">
                        <button onClick={() => setInstance('')} className={`min-h-9 px-3 text-sm font-bold ${!instance ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}>Todas las instancias</button>
                        {instanceCounts.map((option) => (
                            <button key={option.code} onClick={() => setInstance(option.code)} className={`min-h-9 px-3 text-sm font-bold ${instance === option.code ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}>
                                {option.label} <span className="opacity-60">{option.count}</span>
                            </button>
                        ))}
                    </div>
                )}
                <div className="flex flex-wrap items-center gap-2">
                    {FILTERS.map((option) => (
                        <button key={option.id || 'todos'} onClick={() => setFlag(option.id)} className={`min-h-9 px-3 text-sm font-bold ${flag === option.id ? 'bg-[#281FD0] text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}>
                            {option.label}
                        </button>
                    ))}
                    <select value={theme} onChange={(event) => setTheme(event.target.value)} className="min-h-9 border border-slate-300 bg-white px-2 text-sm font-bold text-slate-700">
                        <option value="">Todos los temas</option>
                        {themes.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                    <label className="flex min-h-9 flex-1 items-center gap-2 border border-slate-300 bg-white px-2">
                        <Search size={15} className="text-slate-400" />
                        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por texto, responsable o territorio" className="w-full text-sm font-semibold outline-none" />
                    </label>
                </div>
                <p className="text-xs font-bold text-slate-500">{visible.length} compromiso(s) o acuerdo(s)</p>
                {loading ? (
                    <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Cargando compromisos…</p>
                ) : visible.length === 0 ? (
                    <p className="bg-white p-6 text-center text-sm font-semibold text-slate-500">No hay compromisos con este filtro.</p>
                ) : (
                    visible.map((item) => <CommitmentCard key={`${item.code}-${item.version}`} item={item} statuses={statuses} onSaved={onSaved} />)
                )}
            </section>
            )}
        </div>
    );
};

export default CouncilCommitments;
