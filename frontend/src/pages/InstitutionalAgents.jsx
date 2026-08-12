import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    AlertTriangle,
    Bot,
    Check,
    CheckCircle2,
    FileSearch,
    Loader2,
    RefreshCw,
    ShieldCheck,
    UploadCloud,
    XCircle
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const PROGRAMS = [
    { value: 'COMISARIAS', label: 'Comisarías de Familia' },
    { value: 'INSPECCIONES', label: 'Inspecciones de Policía' }
];

const STATUS = {
    PENDING: { label: 'Pendiente', style: 'bg-amber-100 text-amber-800' },
    APPROVED: { label: 'Publicado', style: 'bg-emerald-100 text-emerald-800' },
    REJECTED: { label: 'Rechazado', style: 'bg-rose-100 text-rose-800' },
    SUPERSEDED: { label: 'Reemplazado', style: 'bg-slate-200 text-slate-700' }
};

const authHeaders = () => ({
    Authorization: 'Bearer ' + localStorage.getItem('token')
});

const readError = async (response) => {
    const data = await response.json().catch(() => ({}));
    if (typeof data.detail === 'string') return data.detail;
    return 'No fue posible completar la operación.';
};

const InstitutionalAgents = () => {
    const today = new Date().toISOString().slice(0, 10);
    const month = today.slice(0, 7);
    const fileRef = useRef(null);
    const [form, setForm] = useState({
        program: 'COMISARIAS',
        reporting_entity: 'Comisaría Segunda de Familia',
        period: month,
        cutoff_date: today,
        reporting_basis: 'CUMULATIVE',
        version: 1,
        use_cloud_ocr: false
    });
    const [file, setFile] = useState(null);
    const [batches, setBatches] = useState([]);
    const [selected, setSelected] = useState(null);
    const [notes, setNotes] = useState({});
    const [loading, setLoading] = useState(true);
    const [working, setWorking] = useState(false);
    const [message, setMessage] = useState(null);
    const [detecting, setDetecting] = useState(false);
    const [detection, setDetection] = useState(null);

    const unresolved = useMemo(
        () => selected?.findings?.filter((item) => item.blocks_publication && !item.resolved) || [],
        [selected]
    );

    const loadBatches = async () => {
        setLoading(true);
        try {
            const response = await fetch(API_BASE_URL + '/institutional-indicators/batches', {
                headers: authHeaders()
            });
            if (!response.ok) throw new Error(await readError(response));
            const data = await response.json();
            setBatches(data.batches || []);
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        } finally {
            setLoading(false);
        }
    };

    const loadRun = async (runId) => {
        if (!runId) {
            setSelected(null);
            return;
        }
        setWorking(true);
        try {
            const response = await fetch(
                API_BASE_URL + '/institutional-indicators/agent-runs/' + runId,
                { headers: authHeaders() }
            );
            if (!response.ok) throw new Error(await readError(response));
            setSelected(await response.json());
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        } finally {
            setWorking(false);
        }
    };

    useEffect(() => {
        loadBatches();
    }, []);

    const detectFile = async (selectedFile) => {
        setDetecting(true);
        setDetection(null);
        try {
            const body = new FormData();
            body.append('file', selectedFile);
            const response = await fetch(API_BASE_URL + '/institutional-indicators/agent-detect', {
                method: 'POST',
                headers: authHeaders(),
                body
            });
            if (!response.ok) throw new Error(await readError(response));
            const detected = await response.json();
            setDetection(detected);
            setForm((current) => ({
                ...current,
                program: detected.program || current.program,
                reporting_entity: detected.reporting_entity || current.reporting_entity,
                period: detected.period || current.period,
                cutoff_date: detected.cutoff_date || current.cutoff_date,
                reporting_basis: detected.reporting_basis || current.reporting_basis
            }));
            setMessage({
                type: 'success',
                text: detected.requires_confirmation
                    ? 'Origen reconocido parcialmente. Revisa y completa los campos antes de procesar.'
                    : 'Origen y periodo reconocidos. Confirma los campos antes de procesar.'
            });
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        } finally {
            setDetecting(false);
        }
    };

    const handleFileSelected = (event) => {
        const selectedFile = event.target.files?.[0] || null;
        setFile(selectedFile);
        setDetection(null);
        if (selectedFile) detectFile(selectedFile);
    };
    const handleUpload = async (event) => {
        event.preventDefault();
        if (!file) {
            setMessage({ type: 'error', text: 'Selecciona un archivo institucional.' });
            return;
        }
        setWorking(true);
        setMessage(null);
        const body = new FormData();
        Object.entries(form).forEach(([key, value]) => body.append(key, String(value)));
        body.append('file', file);
        try {
            const response = await fetch(API_BASE_URL + '/institutional-indicators/agent-ingest', {
                method: 'POST',
                headers: authHeaders(),
                body
            });
            if (!response.ok) throw new Error(await readError(response));
            const run = await response.json();
            setSelected(run);
            setMessage({
                type: 'success',
                text: 'El agente procesó el informe. Revisa los resultados antes de publicar.'
            });
            setFile(null);
            setDetection(null);
            if (fileRef.current) fileRef.current.value = '';
            await loadBatches();
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        } finally {
            setWorking(false);
        }
    };

    const resolveFinding = async (finding) => {
        setWorking(true);
        try {
            const response = await fetch(
                API_BASE_URL + '/institutional-indicators/agent-findings/' + finding.id + '/resolve',
                {
                    method: 'POST',
                    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({ note: notes[finding.id] || 'Revisado contra el documento fuente.' })
                }
            );
            if (!response.ok) throw new Error(await readError(response));
            await loadRun(selected.id);
            setMessage({ type: 'success', text: 'Hallazgo marcado como revisado.' });
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        } finally {
            setWorking(false);
        }
    };

    const decideBatch = async (decision) => {
        const action = decision === 'approve' ? 'publicar' : 'rechazar';
        if (decision === 'approve' && unresolved.length) {
            setMessage({ type: 'error', text: 'Resuelve primero todos los hallazgos bloqueantes.' });
            return;
        }
        if (!window.confirm('¿Confirmas que deseas ' + action + ' este lote?')) return;
        setWorking(true);
        try {
            const response = await fetch(
                API_BASE_URL + '/institutional-indicators/batches/' + selected.batch.id + '/' + decision,
                { method: 'POST', headers: authHeaders() }
            );
            if (!response.ok) throw new Error(await readError(response));
            await loadRun(selected.id);
            await loadBatches();
            setMessage({
                type: 'success',
                text: decision === 'approve'
                    ? 'Lote aprobado. Los indicadores públicos ya están disponibles para el portal ciudadano.'
                    : 'Lote rechazado. Ningún dato fue publicado.'
            });
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        } finally {
            setWorking(false);
        }
    };

    return (
        <div className="min-h-full bg-[#f3f1e9] p-5 md:p-8">
            <div className="mx-auto max-w-7xl space-y-6">
                <header className="overflow-hidden rounded-[2rem] bg-[#102a43] text-white shadow-xl">
                    <div className="grid gap-6 p-7 md:grid-cols-[1fr_auto] md:items-end md:p-9">
                        <div>
                            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-[#f4b41a] px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-[#102a43]">
                                <Bot size={15} /> Operación asistida
                            </div>
                            <h1 className="font-titles text-3xl font-black tracking-tight md:text-5xl">
                                Agentes institucionales
                            </h1>
                            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-200 md:text-base">
                                Carga informes, revisa lo que extrajo el agente y decide qué información puede publicarse.
                            </p>
                        </div>
                        <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-4">
                            <p className="text-xs font-bold uppercase tracking-widest text-slate-300">Regla de control</p>
                            <p className="mt-1 flex items-center gap-2 font-bold"><ShieldCheck size={18} /> El agente no se aprueba a sí mismo</p>
                        </div>
                    </div>
                </header>

                {message && (
                    <div className={'flex items-start gap-3 rounded-2xl border p-4 text-sm font-semibold ' + (
                        message.type === 'error'
                            ? 'border-rose-200 bg-rose-50 text-rose-800'
                            : 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    )}>
                        {message.type === 'error' ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
                        <span>{message.text}</span>
                    </div>
                )}

                <div className="grid gap-6 xl:grid-cols-[390px_1fr]">
                    <div className="space-y-6">
                        <form onSubmit={handleUpload} className="rounded-[1.75rem] bg-white p-6 shadow-sm ring-1 ring-slate-200">
                            <div className="mb-5 flex items-center gap-3">
                                <span className="rounded-xl bg-blue-100 p-2 text-blue-700"><UploadCloud /></span>
                                <div>
                                    <h2 className="text-lg font-black text-slate-900">1. Cargar informe</h2>
                                    <p className="text-xs text-slate-500">CSV, XLSX, PPTX, DOCX o PDF. Máximo 25 MB.</p>
                                </div>
                            </div>
                            <div className="space-y-4">
                                <label className="block text-sm font-bold text-slate-700">
                                    Programa
                                    <select value={form.program} onChange={(e) => setForm({ ...form, program: e.target.value })} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5">
                                        {PROGRAMS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                                    </select>
                                </label>
                                <label className="block text-sm font-bold text-slate-700">
                                    Dependencia que reporta
                                    <input value={form.reporting_entity} onChange={(e) => setForm({ ...form, reporting_entity: e.target.value })} required className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5" />
                                </label>
                                <div className="grid grid-cols-2 gap-3">
                                    <label className="block text-sm font-bold text-slate-700">
                                        Periodo
                                        <input type="month" value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} required className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5" />
                                    </label>
                                    <label className="block text-sm font-bold text-slate-700">
                                        Fecha de corte
                                        <input type="date" value={form.cutoff_date} onChange={(e) => setForm({ ...form, cutoff_date: e.target.value })} required className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5" />
                                    </label>
                                </div>
                                <label className="block text-sm font-bold text-slate-700">
                                    Tipo de reporte
                                    <select value={form.reporting_basis} onChange={(e) => setForm({ ...form, reporting_basis: e.target.value })} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5">
                                        <option value="CUMULATIVE">Acumulado</option>
                                        <option value="MONTHLY">Solo el mes</option>
                                    </select>
                                </label>
                                <label className="block cursor-pointer rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-4 text-center hover:border-blue-500">
                                    <FileSearch className="mx-auto mb-2 text-slate-500" />
                                    <span className="block text-sm font-bold text-slate-700">{file ? file.name : 'Seleccionar archivo'}</span>
                                    <input ref={fileRef} type="file" accept=".csv,.xlsx,.pptx,.docx,.pdf" onChange={handleFileSelected} className="hidden" />
                                </label>
                                {detecting && (
                                    <div className="flex items-center gap-2 rounded-xl bg-blue-50 p-3 text-sm font-bold text-blue-800">
                                        <Loader2 size={17} className="animate-spin" /> Reconociendo origen, dependencia y periodo...
                                    </div>
                                )}
                                {detection && !detecting && (
                                    <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
                                        <div className="flex items-center justify-between gap-3">
                                            <strong>Identificación propuesta</strong>
                                            <span className="rounded-full bg-white px-2 py-1 text-xs font-black">
                                                {Math.round((detection.confidence || 0) * 100)}% confianza
                                            </span>
                                        </div>
                                        <p className="mt-2">
                                            {detection.reporting_entity || 'Dependencia sin identificar'} · {detection.period || 'Periodo sin identificar'}
                                        </p>
                                        {detection.requires_confirmation && (
                                            <p className="mt-1 text-xs font-semibold text-amber-800">Requiere confirmación o corrección manual.</p>
                                        )}
                                    </div>
                                )}                                {file?.name?.toLowerCase().endsWith('.pdf') && (
                                    <label className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                                        <input
                                            type="checkbox"
                                            checked={form.use_cloud_ocr}
                                            onChange={(e) => setForm({ ...form, use_cloud_ocr: e.target.checked })}
                                            className="mt-1"
                                        />
                                        <span>
                                            <strong>Autorizar Mistral OCR 4.</strong> El PDF será enviado temporalmente al servicio externo para extraer su contenido y luego se solicitará su eliminación.
                                        </span>
                                    </label>
                                )}                                <button disabled={working || detecting} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#176b5b] px-4 py-3 font-black text-white hover:bg-[#115347] disabled:opacity-50">
                                    {working ? <Loader2 className="animate-spin" /> : <Bot />} Procesar con agentes
                                </button>
                            </div>
                        </form>

                        <section className="rounded-[1.75rem] bg-white p-5 shadow-sm ring-1 ring-slate-200">
                            <div className="mb-4 flex items-center justify-between">
                                <h2 className="font-black text-slate-900">Cargas recientes</h2>
                                <button onClick={loadBatches} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="Actualizar"><RefreshCw size={17} /></button>
                            </div>
                            {loading ? <Loader2 className="mx-auto animate-spin text-slate-400" /> : batches.length === 0 ? (
                                <p className="text-sm text-slate-500">Todavía no hay informes procesados.</p>
                            ) : (
                                <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                                    {batches.map((batch) => {
                                        const badge = STATUS[batch.status] || STATUS.PENDING;
                                        return (
                                            <button key={batch.id} onClick={() => loadRun(batch.agent_run_id)} disabled={!batch.agent_run_id} className="w-full rounded-xl border border-slate-200 p-3 text-left hover:border-blue-400 hover:bg-blue-50 disabled:opacity-60">
                                                <div className="flex items-start justify-between gap-2">
                                                    <span className="text-sm font-black text-slate-800">{batch.reporting_entity}</span>
                                                    <span className={'shrink-0 rounded-full px-2 py-1 text-[10px] font-black uppercase ' + badge.style}>{badge.label}</span>
                                                </div>
                                                <p className="mt-1 text-xs text-slate-500">{batch.period} · {batch.records} indicadores</p>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </section>
                    </div>

                    <section className="min-h-[620px] rounded-[1.75rem] bg-white p-6 shadow-sm ring-1 ring-slate-200 md:p-8">
                        {!selected ? (
                            <div className="flex min-h-[560px] flex-col items-center justify-center text-center">
                                <span className="mb-4 rounded-full bg-slate-100 p-5 text-slate-500"><FileSearch size={42} /></span>
                                <h2 className="text-xl font-black text-slate-800">2. Revisar resultados</h2>
                                <p className="mt-2 max-w-md text-sm text-slate-500">Procesa un archivo o selecciona una carga reciente para ver indicadores y alertas.</p>
                            </div>
                        ) : (
                            <div className="space-y-7">
                                <div className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-5 md:flex-row md:items-start">
                                    <div>
                                        <p className="text-xs font-black uppercase tracking-widest text-blue-700">{selected.status}</p>
                                        <h2 className="mt-1 text-2xl font-black text-slate-900">{selected.source_filename}</h2>
                                        <p className="mt-1 text-sm text-slate-500">{selected.summary}</p>
                                    </div>
                                    {selected.batch && <span className={'self-start rounded-full px-3 py-1.5 text-xs font-black uppercase ' + (STATUS[selected.batch.status]?.style || STATUS.PENDING.style)}>{STATUS[selected.batch.status]?.label || selected.batch.status}</span>}
                                </div>

                                <div>
                                    <h3 className="mb-3 flex items-center gap-2 text-lg font-black text-slate-900"><Check size={20} className="text-emerald-600" /> Indicadores extraídos</h3>
                                    <div className="overflow-hidden rounded-xl border border-slate-200">
                                        <div className="grid grid-cols-[1fr_110px_90px] bg-slate-900 px-4 py-3 text-xs font-black uppercase text-white"><span>Indicador</span><span>Valor</span><span>Publicable</span></div>
                                        {selected.batch?.indicators?.map((item) => (
                                            <div key={item.id} className="grid grid-cols-[1fr_110px_90px] border-t border-slate-100 px-4 py-3 text-sm">
                                                <span className="font-semibold text-slate-800">{item.indicator}</span>
                                                <span className="font-black">{item.value} {item.unit}</span>
                                                <span>{item.is_public ? 'Sí' : 'No'}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div>
                                    <div className="mb-3 flex items-center justify-between">
                                        <h3 className="flex items-center gap-2 text-lg font-black text-slate-900"><AlertTriangle size={20} className="text-amber-600" /> Hallazgos del agente</h3>
                                        <span className="text-xs font-bold text-slate-500">{unresolved.length} bloqueantes pendientes</span>
                                    </div>
                                    {selected.findings?.length === 0 ? (
                                        <div className="rounded-xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-800">No se encontraron alertas.</div>
                                    ) : (
                                        <div className="space-y-3">
                                            {selected.findings.map((finding) => (
                                                <article key={finding.id} className={'rounded-xl border p-4 ' + (finding.resolved ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50')}>
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div>
                                                            <p className="text-xs font-black uppercase tracking-wider text-slate-500">{finding.agent} · {finding.code}</p>
                                                            <p className="mt-1 text-sm font-bold text-slate-800">{finding.message}</p>
                                                            {finding.evidence && <p className="mt-2 text-xs text-slate-600">Evidencia: {finding.evidence}</p>}
                                                        </div>
                                                        {finding.resolved && <CheckCircle2 className="shrink-0 text-emerald-600" />}
                                                    </div>
                                                    {!finding.resolved && (
                                                        <div className="mt-3 flex flex-col gap-2 md:flex-row">
                                                            <input value={notes[finding.id] || ''} onChange={(e) => setNotes({ ...notes, [finding.id]: e.target.value })} placeholder="Nota de revisión (opcional)" className="flex-1 rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm" />
                                                            <button onClick={() => resolveFinding(finding)} disabled={working} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-black text-white">Marcar revisado</button>
                                                        </div>
                                                    )}
                                                </article>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {selected.batch?.status === 'PENDING' && (
                                    <div className="flex flex-col gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:justify-end">
                                        <button onClick={() => decideBatch('reject')} disabled={working} className="flex items-center justify-center gap-2 rounded-xl border border-rose-300 px-5 py-3 font-black text-rose-700 hover:bg-rose-50"><XCircle size={19} /> Rechazar lote</button>
                                        <button onClick={() => decideBatch('approve')} disabled={working || unresolved.length > 0} className="flex items-center justify-center gap-2 rounded-xl bg-[#176b5b] px-5 py-3 font-black text-white disabled:cursor-not-allowed disabled:bg-slate-300"><ShieldCheck size={19} /> Aprobar y publicar</button>
                                    </div>
                                )}
                            </div>
                        )}
                    </section>
                </div>
            </div>
        </div>
    );
};

export default InstitutionalAgents;
