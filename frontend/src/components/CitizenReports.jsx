import React, { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import { localToday } from '../utils/localDate';
import { REPORT_ACTIONS, REPORT_STATES, waitingText } from '../utils/citizenReports';

const formatDateTime = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
    : '');
const formatDate = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`))
    : '');

const ReportCard = ({ report, today, onSaved }) => {
    const [action, setAction] = useState(null);
    const [note, setNote] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const state = REPORT_STATES[report.estado] || REPORT_STATES.RECIBIDO;

    const apply = async (target) => {
        setSaving(true);
        setError('');
        try {
            await apiJson(`/participacion/admin/reportes-seguros/${report.id}/estado`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ estado: target.to, nota: note || null, expected_version: report.version }),
            });
            setAction(null);
            setNote('');
            onSaved();
        } catch (saveError) {
            setError(saveError.message);
        } finally {
            setSaving(false);
        }
    };
    const choose = (target) => (target.needsNote ? setAction(target) : apply(target));

    return (
        <article className="bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                    <p className="text-xs font-black text-slate-500">
                        {report.barrio} · hecho del {formatDate(report.fecha)}{report.hora ? ` a las ${report.hora}` : ''} · recibido {formatDateTime(report.recibido)}
                    </p>
                    <h3 className="mt-1 text-base font-black text-slate-950">{report.tipo}</h3>
                </div>
                <div className="flex flex-col items-end gap-1">
                    <span className={`px-2 py-0.5 text-[11px] font-black uppercase ${state.chip}`}>{state.label}</span>
                    <span className="text-xs font-bold text-slate-500">{waitingText(report, today)}</span>
                </div>
            </div>
            <p className="mt-2 whitespace-pre-line text-sm font-semibold text-slate-700">{report.descripcion}</p>
            <p className="mt-1 text-xs font-semibold text-slate-500">
                {report.es_anonimo ? 'Reporte anónimo: no hay a quién contactar.' : `Contacto: ${report.nombre || 'sin nombre'}${report.contacto ? ` · ${report.contacto}` : ''}`}
            </p>
            {report.gestion.length > 0 && (
                <ul className="mt-2 space-y-1 border-l-2 border-slate-200 pl-3 text-xs font-semibold text-slate-600">
                    {report.gestion.map((event) => (
                        <li key={event.at}>
                            {formatDateTime(event.at)} · {REPORT_STATES[event.a]?.label || event.a} · {event.por}{event.nota ? `: ${event.nota}` : ''}
                        </li>
                    ))}
                </ul>
            )}
            {action ? (
                <div className="mt-3 space-y-2">
                    <label className="block">
                        <span className="text-xs font-black uppercase tracking-wide text-slate-600">
                            {action.to === 'CERRADO' ? 'Cómo se cerró' : 'Por qué se reabre'}
                        </span>
                        <textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000}
                            placeholder={action.to === 'CERRADO' ? 'Remitido a la Policía (cuadrante…), atendido, sin información suficiente…' : ''}
                            className="mt-1 w-full border border-slate-300 bg-white px-3 py-2 text-sm font-semibold focus:border-[#281FD0] focus:outline-none" />
                    </label>
                    <div className="flex gap-2">
                        <button onClick={() => apply(action)} disabled={saving || !note.trim()}
                            className="inline-flex min-h-9 items-center gap-2 bg-[#281FD0] px-3 text-sm font-black text-white disabled:opacity-50">
                            {saving && <Loader2 size={14} className="animate-spin" />} {action.label}
                        </button>
                        <button onClick={() => { setAction(null); setNote(''); }} className="min-h-9 border border-slate-300 px-3 text-sm font-bold text-slate-700">Cancelar</button>
                    </div>
                </div>
            ) : (
                <div className="mt-3 flex flex-wrap gap-3">
                    {(REPORT_ACTIONS[report.estado] || []).map((target) => (
                        <button key={target.to} onClick={() => choose(target)} disabled={saving}
                            className="text-sm font-black text-[#281FD0] hover:underline disabled:opacity-50">{target.label}</button>
                    ))}
                </div>
            )}
            {error && <p role="alert" className="mt-2 text-sm font-bold text-red-700">{error}</p>}
        </article>
    );
};

/** Reportes seguros del portal ciudadano con su estado de atención. */
const CitizenReports = () => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [showClosed, setShowClosed] = useState(false);
    const today = localToday();

    const load = useCallback(async () => {
        try {
            setData(await apiJson('/participacion/admin/reportes-seguros'));
            setError('');
        } catch (loadError) {
            setError(loadError.message);
        }
    }, []);
    useEffect(() => { load(); }, [load]);

    if (error && !data) return <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Cargando reportes…</p>;

    const open = data.items.filter((item) => item.estado !== 'CERRADO');
    const closed = data.items.filter((item) => item.estado === 'CERRADO');
    return (
        <div className="space-y-4">
            <p className="max-w-3xl text-sm font-semibold text-slate-600">
                Reportes que la ciudadanía envía por el portal ("Reporte seguro"). Cada uno queda recibido, en gestión o cerrado,
                con la nota de qué se hizo. Los más antiguos van primero.
            </p>
            <div className="flex flex-wrap gap-2 text-sm font-bold">
                {Object.entries(REPORT_STATES).map(([key, state]) => (
                    <span key={key} className={`px-3 py-1 ${state.chip}`}>{data.counts[key] || 0} · {state.label}</span>
                ))}
            </div>
            {error && <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}
            {!open.length && <p className="bg-emerald-50 p-4 text-sm font-semibold text-emerald-900">No hay reportes abiertos.</p>}
            <div className="grid gap-3">
                {open.map((report) => <ReportCard key={`${report.id}-${report.version}`} report={report} today={today} onSaved={load} />)}
            </div>
            {closed.length > 0 && (
                <div>
                    <button onClick={() => setShowClosed(!showClosed)} className="text-sm font-black text-slate-600 hover:text-slate-900">
                        {showClosed ? 'Ocultar' : 'Ver'} cerrados ({closed.length})
                    </button>
                    {showClosed && (
                        <div className="mt-3 grid gap-3">
                            {closed.map((report) => <ReportCard key={`${report.id}-${report.version}`} report={report} today={today} onSaved={load} />)}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default CitizenReports;
