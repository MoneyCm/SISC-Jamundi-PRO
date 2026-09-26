import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, FileText, Loader2, Trash2, X } from 'lucide-react';
import { apiFetch, apiJson } from '../utils/apiClient';

const FLAG_LABELS = {
    SIN_PLAZO: 'Sin plazo',
    PLAZO_VAGO: 'Plazo sin fecha',
    FECHA_ANIO_DISTINTO: 'Año del plazo distinto al del acta',
    FECHA_ANTERIOR_AL_ACTA: 'Plazo anterior al acta',
    SIN_RESPONSABLE: 'Sin responsable',
    RESPONSABLE_GENERICO: 'Responsable genérico',
    ACUERDO_SIN_CONTENIDO: 'El acta no dice qué se aprobó',
    RESPONSABLE_POR_VERIFICAR: 'Verifique el responsable (tabla del PDF)',
};
const METHOD_LABELS = { TABLA: 'tabla de compromisos', LISTA: 'lista de compromisos', EN_LINEA: 'texto del acta', APROBACION: 'votación' };

const initialDecision = (proposal) => ({
    action: proposal.suggested_action === 'LINK' ? `LINK:${proposal.similar[0].code}` : proposal.suggested_action === 'SKIP' ? 'SKIP' : 'CREATE',
    text: proposal.text,
    responsible: proposal.responsible || '',
    deadline_date: proposal.deadline_date || '',
});

const ProposalRow = ({ proposal, decision, onChange }) => {
    const skipped = decision.action === 'SKIP';
    const creating = decision.action === 'CREATE';
    return (
        <li className={`border p-3 ${skipped ? 'border-slate-200 bg-slate-50 opacity-60' : 'border-slate-300 bg-white'}`}>
            <div className="flex flex-wrap items-center gap-2 text-[11px] font-black">
                <span className={proposal.kind === 'ACUERDO' ? 'bg-violet-100 px-2 py-0.5 text-violet-800' : 'bg-blue-50 px-2 py-0.5 text-blue-800'}>
                    {proposal.kind === 'ACUERDO' ? 'Acuerdo' : 'Compromiso'}
                </span>
                <span className="text-slate-400">Leído de la {METHOD_LABELS[proposal.method] || 'acta'}</span>
                {proposal.flags.map((flag) => (
                    flag.startsWith('VOTOS_')
                        ? <span key={flag} className="bg-emerald-50 px-2 py-0.5 text-emerald-800">Aprobado con {flag.slice(6)} votos</span>
                        : <span key={flag} className="bg-amber-50 px-2 py-0.5 text-amber-800">{FLAG_LABELS[flag] || flag}</span>
                ))}
            </div>
            <div className="mt-2 grid gap-2 md:grid-cols-[1fr_220px]">
                <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Qué se decidió
                    <textarea value={decision.text} disabled={!creating} rows={Math.min(5, Math.max(2, Math.ceil(decision.text.length / 70)))} onChange={(event) => onChange({ text: event.target.value })}
                        className="mt-1 w-full border border-slate-300 px-2 py-1.5 text-sm font-semibold normal-case text-slate-800 disabled:bg-slate-50" />
                </label>
                <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Qué hacer con esto
                    <select value={decision.action} onChange={(event) => onChange({ action: event.target.value })}
                        className="mt-1 w-full border border-slate-300 bg-white px-2 py-2 text-sm font-bold normal-case text-slate-800">
                        <option value="CREATE">Crear compromiso nuevo</option>
                        {proposal.similar.map((item) => (
                            <option key={item.code} value={`LINK:${item.code}`}>Ya existe: {item.code}</option>
                        ))}
                        <option value="SKIP">{proposal.already_registered ? 'Ya registrado, no hacer nada' : 'No es un compromiso, descartar'}</option>
                    </select>
                </label>
            </div>
            {creating ? (
                <div className="mt-2 grid gap-2 md:grid-cols-[1fr_180px]">
                    <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Responsable
                        <input value={decision.responsible} maxLength={300} onChange={(event) => onChange({ responsible: event.target.value })}
                            placeholder="Por definir" className="mt-1 w-full border border-slate-300 px-2 py-1.5 text-sm font-semibold normal-case text-slate-800" />
                    </label>
                    <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Fecha límite
                        <input type="date" value={decision.deadline_date} onChange={(event) => onChange({ deadline_date: event.target.value })}
                            className="mt-1 w-full border border-slate-300 px-2 py-1.5 text-sm font-bold text-slate-800" />
                    </label>
                    {proposal.deadline_text && !decision.deadline_date && (
                        <p className="text-xs font-semibold text-slate-500 md:col-span-2">El acta dice: “{proposal.deadline_text}”.</p>
                    )}
                </div>
            ) : decision.action.startsWith('LINK:') && (
                <p className="mt-2 text-xs font-semibold text-slate-600">
                    Se sumará una mención a {decision.action.slice(5)} ({Math.round((proposal.similar.find((item) => `LINK:${item.code}` === decision.action)?.score || 0) * 100)} % parecido): “{proposal.similar.find((item) => `LINK:${item.code}` === decision.action)?.text}”
                </p>
            )}
            {skipped && proposal.already_registered && (
                <p className="mt-2 text-xs font-semibold text-slate-600">
                    Ya está en el SISC como {proposal.similar[0].code}, registrado desde esta misma acta: sumarle una mención lo contaría dos veces.
                </p>
            )}
        </li>
    );
};

const ActReviewPanel = ({ instances, readId = null, onClose, onConfirmed, onDiscarded }) => {
    const fileRef = useRef(null);
    const [instance, setInstance] = useState('');
    const [useOcr, setUseOcr] = useState(false);
    const [reading, setReading] = useState(null);
    const [decisions, setDecisions] = useState({});
    const [rereadLinks, setRereadLinks] = useState({});
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    const showReading = (data) => {
        setReading(data);
        setDecisions(Object.fromEntries(data.proposals.map((proposal) => [proposal.index, initialDecision(proposal)])));
        setRereadLinks(Object.fromEntries(data.reread.map((item) => [item.index, item.already_counted ? '' : item.similar[0]?.code || ''])));
    };

    useEffect(() => {
        if (!readId) return undefined;
        let cancelled = false;
        setBusy(true);
        setError('');
        apiJson(`/council-commitments/acts/${readId}`)
            .then((data) => { if (!cancelled) showReading(data); })
            .catch((openError) => { if (!cancelled) setError(openError.message); })
            .finally(() => { if (!cancelled) setBusy(false); });
        return () => { cancelled = true; };
    }, [readId]);

    const discard = async () => {
        if (!window.confirm('¿Descartar esta lectura? El acta no se registra; puede volver a subirla después.')) return;
        setBusy(true);
        setError('');
        try {
            await apiJson(`/council-commitments/acts/${reading.read_id}`, { method: 'DELETE' });
            onDiscarded?.(reading);
        } catch (discardError) {
            setError(discardError.message);
        } finally {
            setBusy(false);
        }
    };

    const readFile = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        setBusy(true);
        setError('');
        setReading(null);
        const body = new FormData();
        body.append('file', file);
        if (instance) body.append('instance', instance);
        if (useOcr) body.append('use_ocr', 'true');
        try {
            const response = await apiFetch('/council-commitments/acts/read', { method: 'POST', body });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || 'No se pudo leer el acta.');
            showReading(data);
        } catch (readError) {
            setError(readError.message);
        } finally {
            setBusy(false);
            if (fileRef.current) fileRef.current.value = '';
        }
    };

    const confirm = async () => {
        setBusy(true);
        setError('');
        try {
            const payload = {
                decisions: reading.proposals.map((proposal) => {
                    const decision = decisions[proposal.index];
                    if (decision.action.startsWith('LINK:')) return { index: proposal.index, action: 'LINK', link_code: decision.action.slice(5) };
                    if (decision.action === 'SKIP') return { index: proposal.index, action: 'SKIP' };
                    return {
                        index: proposal.index, action: 'CREATE', text: decision.text,
                        responsible: decision.responsible, deadline_date: decision.deadline_date || null,
                    };
                }),
                reread_links: Object.entries(rereadLinks).filter(([, code]) => code).map(([index, code]) => ({ index: Number(index), link_code: code })),
            };
            const result = await apiJson(`/council-commitments/acts/${reading.read_id}/confirm`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
            });
            onConfirmed(result, reading);
        } catch (confirmError) {
            setError(confirmError.message);
        } finally {
            setBusy(false);
        }
    };

    const counts = reading ? reading.proposals.reduce((acc, proposal) => {
        const { action } = decisions[proposal.index];
        const key = action.startsWith('LINK:') ? 'link' : action === 'SKIP' ? (proposal.already_registered ? 'registered' : 'skip') : 'create';
        return { ...acc, [key]: acc[key] + 1 };
    }, { create: 0, link: 0, registered: 0, skip: 0 }) : null;

    return (
        <section className="border-2 border-[#281FD0] bg-white p-4 shadow-sm" aria-label="Leer acta">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <h2 className="flex items-center gap-2 text-lg font-black text-slate-950"><FileText size={20} /> Leer acta</h2>
                    <p className="mt-1 max-w-3xl text-sm font-semibold text-slate-600">
                        {readId
                            ? 'Acta ya leída por el SISC. Revise lo que encontró, corrija lo necesario y confirme; nada se registra hasta que usted confirme.'
                            : 'Suba el acta en Word o PDF. El SISC propone los compromisos y acuerdos que encuentra; nada se guarda hasta que usted lo revise y confirme.'}
                    </p>
                </div>
                <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-900" aria-label="Cerrar"><X size={20} /></button>
            </div>

            {!readId && (
            <div className="mt-3 flex flex-wrap items-end gap-2">
                <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Instancia
                    <select value={instance} onChange={(event) => setInstance(event.target.value)} className="mt-1 block min-h-10 border border-slate-300 bg-white px-2 text-sm font-bold normal-case text-slate-800">
                        <option value="">Detectar desde el acta</option>
                        {instances.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
                    </select>
                </label>
                <button onClick={() => fileRef.current?.click()} disabled={busy} className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8] disabled:opacity-50">
                    {busy && !reading ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />} Elegir acta (.docx o .pdf)
                </button>
                <input ref={fileRef} type="file" accept=".docx,.pdf" onChange={readFile} className="hidden" />
                <label className="flex max-w-md items-start gap-2 text-xs font-semibold text-slate-600">
                    <input type="checkbox" checked={useOcr} onChange={(event) => setUseOcr(event.target.checked)} className="mt-0.5" />
                    <span>Si el PDF es escaneado, leerlo con OCR (Gemini). El documento se envía a Google para transcribirlo; úselo solo si está autorizado.</span>
                </label>
            </div>
            )}
            {readId && busy && !reading && (
                <p className="mt-3 flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Abriendo lectura…</p>
            )}

            {error && <p className="mt-3 bg-red-50 p-3 text-sm font-bold text-red-800" role="alert">{error}</p>}

            {reading && (
                <div className="mt-4 space-y-4">
                    <div className="bg-slate-50 p-3 text-sm font-semibold text-slate-700">
                        <p className="font-black text-slate-950">
                            {reading.instance_label}{reading.act_number ? ` · Acta ${reading.act_number}` : ''}{reading.act_date ? ` · ${new Intl.DateTimeFormat('es-CO', { dateStyle: 'long' }).format(new Date(`${reading.act_date}T12:00:00`))}` : ''}
                        </p>
                        {reading.objective && <p className="mt-1 text-xs">{reading.objective}</p>}
                        <p className="mt-1 text-xs text-slate-500">{reading.filename}{reading.created_by ? ` · leída por ${reading.created_by}` : ''}</p>
                    </div>

                    {reading.warnings.length > 0 && (
                        <ul className="space-y-1">
                            {reading.warnings.map((warning) => (
                                <li key={warning.code} className={`flex items-start gap-2 p-2 text-sm font-semibold ${warning.code === 'ACTA_YA_PROCESADA' ? 'bg-red-50 text-red-800' : 'bg-amber-50 text-amber-900'}`}>
                                    <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {warning.message}
                                </li>
                            ))}
                        </ul>
                    )}

                    {reading.proposals.length > 0 ? (
                        <div>
                            <h3 className="text-sm font-black uppercase tracking-wide text-slate-500">Encontrados en el acta ({reading.proposals.length})</h3>
                            <ol className="mt-2 space-y-2">
                                {reading.proposals.map((proposal) => (
                                    <ProposalRow key={proposal.index} proposal={proposal} decision={decisions[proposal.index]}
                                        onChange={(change) => setDecisions((current) => ({ ...current, [proposal.index]: { ...current[proposal.index], ...change } }))} />
                                ))}
                            </ol>
                        </div>
                    ) : (
                        <p className="bg-slate-50 p-3 text-sm font-semibold text-slate-600">El acta no trae compromisos ni acuerdos que el SISC pueda reconocer.</p>
                    )}

                    {reading.reread.length > 0 && (
                        <div>
                            <h3 className="text-sm font-black uppercase tracking-wide text-slate-500">Compromisos anteriores que se releyeron ({reading.reread.length})</h3>
                            <p className="mt-1 text-xs font-semibold text-slate-500">No son nuevos. Si corresponden a uno registrado, se le suma la mención para saber que se volvió a pedir.</p>
                            <ul className="mt-2 space-y-2">
                                {reading.reread.map((item) => (
                                    <li key={item.index} className="grid gap-2 border border-slate-200 p-3 md:grid-cols-[1fr_220px]">
                                        <p className="text-sm font-semibold text-slate-700">
                                            {item.text}
                                            {item.already_counted && <span className="mt-1 block text-xs text-slate-500">{item.similar[0].code} ya tiene registrada la mención de esta fecha.</span>}
                                        </p>
                                        <select value={rereadLinks[item.index] || ''} onChange={(event) => setRereadLinks((current) => ({ ...current, [item.index]: event.target.value }))}
                                            className="min-h-9 border border-slate-300 bg-white px-2 text-sm font-bold text-slate-800">
                                            <option value="">No sumar mención</option>
                                            {item.similar.map((match) => <option key={match.code} value={match.code}>Es {match.code}</option>)}
                                        </select>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-3">
                        <button onClick={confirm} disabled={busy} className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-5 text-sm font-black text-white hover:bg-[#1F18A8] disabled:opacity-50">
                            {busy ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Confirmar
                        </button>
                        <p className="text-sm font-semibold text-slate-600">
                            {[
                                `${counts.create} nuevo(s)`,
                                counts.link && `${counts.link} repetido(s): se suma la mención`,
                                counts.registered && `${counts.registered} ya registrado(s) desde esta acta`,
                                counts.skip && `${counts.skip} descartado(s)`,
                            ].filter(Boolean).join(' · ')}
                        </p>
                        <button onClick={discard} disabled={busy} className="ml-auto inline-flex min-h-10 items-center gap-2 border border-slate-300 px-3 text-sm font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
                            <Trash2 size={15} /> Descartar lectura
                        </button>
                    </div>
                </div>
            )}
        </section>
    );
};

export default ActReviewPanel;
