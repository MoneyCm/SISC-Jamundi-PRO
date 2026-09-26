import React, { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Download, Loader2 } from 'lucide-react';
import { apiFetch, apiJson, readApiError } from '../utils/apiClient';
import { ACTION_STATUS_LABELS, emptyReport, progressReading, reportPayload, semesterLabel } from '../utils/pisccActions';

const inputClass = 'w-full border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-900 focus:border-[#281FD0] focus:outline-none';
const TONES = { current: 'text-slate-900', stale: 'text-amber-800', empty: 'text-slate-400' };

const ReportForm = ({ action, semester, onSaved, onCancel }) => {
    const [form, setForm] = useState(() => emptyReport(action));
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const set = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

    const save = async (event) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        try {
            await apiJson(`/observatory/piscc-actions/${action.code}/${semester}`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(reportPayload(form, action)),
            });
            onSaved();
        } catch (saveError) {
            setError(saveError.message);
            setSaving(false);
        }
    };

    return (
        <form onSubmit={save} className="mt-3 grid gap-3 border-t border-slate-200 pt-3 md:grid-cols-2">
            <label className="block">
                <span className="text-xs font-black uppercase tracking-wide text-slate-600">Avance acumulado del cuatrienio</span>
                <input className={`${inputClass} mt-1`} inputMode="decimal" value={form.value} onChange={set('value')} placeholder={`Meta: ${action.goal}`} />
            </label>
            <label className="block">
                <span className="text-xs font-black uppercase tracking-wide text-slate-600">Estado</span>
                <select className={`${inputClass} mt-1`} value={form.status} onChange={set('status')}>
                    {Object.entries(ACTION_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
            </label>
            <label className="block">
                <span className="text-xs font-black uppercase tracking-wide text-slate-600">Entidad que reporta</span>
                <input className={`${inputClass} mt-1`} value={form.reporting_entity} onChange={set('reporting_entity')} maxLength={200} />
            </label>
            <label className="block">
                <span className="text-xs font-black uppercase tracking-wide text-slate-600">Fecha de recibo</span>
                <input type="date" className={`${inputClass} mt-1`} value={form.received_on} onChange={set('received_on')} />
            </label>
            <label className="block md:col-span-2">
                <span className="text-xs font-black uppercase tracking-wide text-slate-600">Soporte</span>
                <input className={`${inputClass} mt-1`} value={form.evidence} onChange={set('evidence')} maxLength={2000} placeholder="Oficio, acta o enlace que respalda el avance" />
            </label>
            <label className="block md:col-span-2">
                <span className="text-xs font-black uppercase tracking-wide text-slate-600">Observación</span>
                <textarea className={`${inputClass} mt-1`} rows={2} value={form.note} onChange={set('note')} maxLength={2000} />
            </label>
            {error && <p role="alert" className="bg-red-50 p-2 text-sm font-bold text-red-800 md:col-span-2">{error}</p>}
            <div className="flex gap-2 md:col-span-2">
                <button type="submit" disabled={saving} className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white disabled:opacity-60">
                    {saving && <Loader2 size={15} className="animate-spin" />} Guardar reporte de {semester}
                </button>
                <button type="button" onClick={onCancel} className="min-h-10 border border-slate-300 px-4 text-sm font-bold text-slate-700">Cancelar</button>
            </div>
        </form>
    );
};

const ActionRow = ({ action, semester, canEdit, onSaved }) => {
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(false);
    const reading = progressReading(action);
    const report = action.report || action.last_report;
    return (
        <li className="border-b border-slate-100 py-3">
            <div className="grid gap-2 md:grid-cols-[64px_minmax(0,1fr)_200px_130px] md:items-start">
                <p className="text-xs font-black text-[#281FD0]">{action.code}</p>
                <div className="min-w-0">
                    <button onClick={() => setOpen(!open)} className="flex w-full items-start gap-1 text-left text-sm font-bold leading-snug text-slate-900 hover:text-[#281FD0]">
                        <span className={open ? '' : 'line-clamp-2'}>{action.action}</span>
                        {open ? <ChevronUp size={15} className="mt-0.5 shrink-0" /> : <ChevronDown size={15} className="mt-0.5 shrink-0" />}
                    </button>
                    <p className="mt-1 text-xs font-semibold text-slate-500">{action.lead_entity}</p>
                </div>
                <div>
                    <p className={`text-sm font-black ${TONES[reading.tone]}`}>{reading.text}</p>
                    {action.progress_pct !== null && action.progress_pct !== undefined && (
                        <div className="mt-1 h-1.5 w-full bg-slate-100" aria-hidden="true">
                            <div className={`h-1.5 ${action.report ? 'bg-[#281FD0]' : 'bg-amber-400'}`} style={{ width: `${action.progress_pct}%` }} />
                        </div>
                    )}
                </div>
                <div className="flex flex-col items-start gap-1">
                    <span className={`px-2 py-0.5 text-[11px] font-black uppercase ${action.reported ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
                        {action.reported ? ACTION_STATUS_LABELS[report.status] : 'Sin reporte'}
                    </span>
                    {canEdit && !editing && (
                        <button onClick={() => { setEditing(true); setOpen(true); }} className="text-xs font-black text-[#281FD0] hover:underline">
                            {action.reported ? 'Editar reporte' : 'Registrar reporte'}
                        </button>
                    )}
                </div>
            </div>
            {open && (
                <div className="mt-2 grid gap-1 pl-0 text-xs font-semibold leading-5 text-slate-600 md:pl-[72px]">
                    <p><span className="font-black text-slate-700">Indicador:</span> {action.indicator} <span className="font-black text-slate-700">Meta:</span> {action.goal}</p>
                    <p><span className="font-black text-slate-700">Responsables:</span> {action.responsible}</p>
                    {report?.evidence && <p><span className="font-black text-slate-700">Soporte ({report.semester}):</span> {report.evidence}</p>}
                    {report?.note && <p><span className="font-black text-slate-700">Observación:</span> {report.note}</p>}
                    <p className="text-slate-400">PISCC, página {action.page}</p>
                </div>
            )}
            {editing && (
                <div className="md:pl-[72px]">
                    <ReportForm action={action} semester={semester} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); onSaved(); }} />
                </div>
            )}
        </li>
    );
};

/** Plan de acción del PISCC: seguimiento semestral de las 43 acciones (PISCC 9.1). */
const PisccActions = ({ canEdit }) => {
    const [semester, setSemester] = useState('');
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [downloading, setDownloading] = useState(false);

    const load = useCallback(async () => {
        setError('');
        try {
            setData(await apiJson(`/observatory/piscc-actions${semester ? `?semester=${semester}` : ''}`));
        } catch (loadError) {
            setError(loadError.message);
        }
    }, [semester]);
    useEffect(() => { load(); }, [load]);

    const download = async () => {
        setDownloading(true);
        try {
            const response = await apiFetch(`/observatory/piscc-actions/export?semester=${data.semester}`);
            if (!response.ok) throw new Error(await readApiError(response));
            const url = URL.createObjectURL(await response.blob());
            const link = Object.assign(document.createElement('a'), { href: url, download: `PISCC_seguimiento_${data.semester}.csv` });
            link.click();
            URL.revokeObjectURL(url);
        } catch (downloadError) {
            setError(downloadError.message);
        } finally {
            setDownloading(false);
        }
    };

    if (error && !data) return <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Cargando el plan de acción…</p>;

    return (
        <div className="space-y-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div>
                    <p className="text-sm font-semibold text-slate-600">
                        {data.plan}: {data.totals.actions} acciones en 4 vectores. Cada semestre las entidades responsables reportan su avance (PISCC 9.1).
                    </p>
                    <p className="mt-1 text-2xl font-black text-slate-950">
                        {data.totals.reported} de {data.totals.actions} acciones con reporte · {semesterLabel(data.semester)}
                    </p>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                    <label className="block">
                        <span className="text-xs font-black uppercase tracking-wide text-slate-600">Semestre</span>
                        <select className={`${inputClass} mt-1`} value={data.semester} onChange={(event) => setSemester(event.target.value)}>
                            {data.semesters.map((item) => <option key={item} value={item}>{semesterLabel(item)}</option>)}
                        </select>
                    </label>
                    <button onClick={download} disabled={downloading} className="inline-flex min-h-10 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">
                        {downloading ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} CSV para SisPT
                    </button>
                </div>
            </div>

            {!data.transcription.verified && (
                <p className="border-l-4 border-amber-500 bg-amber-50 p-3 text-sm font-semibold text-amber-900">
                    Acciones, indicadores y metas transcritos desde el documento del PISCC ({data.source}). Falta que el Observatorio los verifique contra el original.
                </p>
            )}
            {error && <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}

            <div className="grid gap-3 md:grid-cols-4">
                {data.vectors.map((vector) => (
                    <div key={vector.code} className="bg-white p-4 shadow-sm">
                        <p className="text-[11px] font-black uppercase tracking-wide text-[#281FD0]">Vector {vector.code}</p>
                        <p className="mt-1 text-sm font-black leading-snug text-slate-900">{vector.name}</p>
                        <p className="mt-3 text-xs font-semibold text-slate-600">
                            {vector.reported} de {vector.actions} con reporte · {vector.completed} cumplidas
                        </p>
                        <p className="text-xs font-semibold text-slate-600">
                            Avance promedio: {vector.with_progress ? `${String(vector.average_progress).replace('.', ',')} %` : 'sin datos'}
                        </p>
                    </div>
                ))}
            </div>

            {data.pending_by_entity.length > 0 && (
                <details className="bg-slate-50 p-4">
                    <summary className="cursor-pointer text-sm font-black text-slate-800">
                        Pedir el reporte a {data.pending_by_entity.length} {data.pending_by_entity.length === 1 ? 'entidad' : 'entidades'}
                    </summary>
                    <ul className="mt-3 grid gap-1 text-sm font-semibold text-slate-700 md:grid-cols-2">
                        {data.pending_by_entity.map((item) => (
                            <li key={item.entity}><span className="font-black">{item.entity}</span>: {item.actions.join(', ')}</li>
                        ))}
                    </ul>
                </details>
            )}

            {data.vectors.map((vector) => (
                <section key={vector.code}>
                    <h3 className="border-b-2 border-slate-200 pb-1 text-sm font-black uppercase tracking-wide text-slate-700">Vector {vector.code} · {vector.name}</h3>
                    <ul>
                        {data.actions.filter((action) => action.vector === vector.code).map((action) => (
                            <ActionRow key={`${action.code}-${action.report?.version ?? 'n'}`} action={action} semester={data.semester} canEdit={canEdit} onSaved={load} />
                        ))}
                    </ul>
                </section>
            ))}
            <p className="text-xs font-semibold text-slate-500">{data.rule}</p>
        </div>
    );
};

export default PisccActions;
