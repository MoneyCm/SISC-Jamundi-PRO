import React, { useCallback, useEffect, useState } from 'react';
import { Download, FileText, Loader2, X } from 'lucide-react';
import { localToday } from '../utils/localDate';
import { apiFetch, apiJson, readApiError } from '../utils/apiClient';

const KIND_LABELS = { RECOMENDACION: 'Recomendación del Observatorio', TERRITORIO: 'Situación territorial', COMPROMISO: 'Compromiso estancado' };
const today = () => localToday();

const change = (cell) => {
    if (cell.previous === null || cell.previous === undefined) return 'sin base';
    if (cell.variation_pct === null || cell.variation_pct === undefined) {
        const diff = cell.difference;
        return diff ? `${diff > 0 ? '+' : ''}${diff} ${Math.abs(diff) === 1 ? 'hecho' : 'hechos'}` : 'igual';
    }
    return `${cell.variation_pct > 0 ? '+' : ''}${String(cell.variation_pct).replace('.', ',')}%`;
};

/** Informe para decisión de una instancia: vista previa, PDF de dos páginas y hoja de una página para la sesión. */
const DecisionReportPanel = ({ instances = [], onClose }) => {
    const [instance, setInstance] = useState('CONSEJO_SEGURIDAD');
    const [sessionDate, setSessionDate] = useState(today());
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState('');
    const [error, setError] = useState('');
    const query = `instance=${encodeURIComponent(instance)}&session_date=${sessionDate}`;

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            setReport(await apiJson(`/council-commitments/decision-report?${query}`));
        } catch (loadError) {
            setError(loadError.message);
        } finally {
            setLoading(false);
        }
    }, [query]);
    useEffect(() => { load(); }, [load]);

    const download = async (kind) => {
        const file = kind === 'sheet'
            ? { path: 'session-sheet.pdf', name: `hoja-sesion-${sessionDate}.pdf` }
            : { path: 'decision-report.pdf', name: `informe-decision-${sessionDate}.pdf` };
        setDownloading(kind);
        setError('');
        try {
            const response = await apiFetch(`/council-commitments/${file.path}?${query}`);
            if (!response.ok) throw new Error(await readApiError(response));
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement('a');
            link.href = url;
            link.download = file.name;
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (downloadError) {
            setError(downloadError.message);
        } finally {
            setDownloading('');
        }
    };

    const options = instances.length ? instances : [{ code: 'CONSEJO_SEGURIDAD', label: 'Consejo de Seguridad' }];
    return (
        <section className="border border-[#281FD0] bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-lg font-black text-slate-950">Informe para decisión</h2>
                    <p className="mt-1 max-w-3xl text-sm font-semibold text-slate-600">
                        Dos páginas para la sesión: qué requiere decisión, cómo va el periodo, qué se cumplió y qué pasó con las intervenciones.
                        Es reservado: no se publica.
                    </p>
                </div>
                <button onClick={onClose} aria-label="Cerrar" className="text-slate-400 hover:text-slate-900"><X size={20} /></button>
            </div>
            <div className="mt-4 flex flex-wrap items-end gap-3">
                <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Instancia
                    <select value={instance} onChange={(event) => setInstance(event.target.value)} className="mt-1 block border border-slate-300 bg-white px-2 py-2 text-sm font-bold normal-case text-slate-800">
                        {options.map((option) => <option key={option.code} value={option.code}>{option.label}</option>)}
                    </select>
                </label>
                <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Fecha de la sesión
                    <input type="date" value={sessionDate} onChange={(event) => setSessionDate(event.target.value)} className="mt-1 block border border-slate-300 px-2 py-2 text-sm font-bold text-slate-800" />
                </label>
                <button onClick={() => download('report')} disabled={Boolean(downloading) || !report} className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white disabled:opacity-50">
                    {downloading === 'report' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} Informe (2 páginas)
                </button>
                <button onClick={() => download('sheet')} disabled={Boolean(downloading) || !report} title="Lo acordado en la última sesión, atrasados por responsable y cifras" className="inline-flex min-h-10 items-center gap-2 border border-[#281FD0] bg-white px-4 text-sm font-black text-[#281FD0] disabled:opacity-50">
                    {downloading === 'sheet' ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />} Hoja para la sesión (1 página)
                </button>
            </div>
            {error && <p role="alert" className="mt-3 text-sm font-bold text-red-700">{error}</p>}
            {loading && <p className="mt-4 flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Armando el informe…</p>}
            {report && !loading && (
                <div className="mt-5 grid gap-5 lg:grid-cols-2">
                    <div>
                        <h3 className="text-sm font-black uppercase tracking-wide text-[#281FD0]">1. Qué requiere decisión</h3>
                        {!report.decisions.items.length && <p className="mt-2 text-sm font-semibold text-slate-600">Sin asuntos nuevos: solo seguimiento.</p>}
                        <ol className="mt-2 space-y-3">
                            {report.decisions.items.map((item, index) => (
                                <li key={`${item.kind}-${index}`} className="border-l-4 border-[#FFE000] bg-slate-50 p-3">
                                    <p className="text-[11px] font-black uppercase text-slate-500">{KIND_LABELS[item.kind]}{item.ref ? ` · ${item.ref}` : ''}</p>
                                    <p className="mt-1 text-sm font-black text-slate-950">{item.title}</p>
                                    <p className="mt-1 text-sm font-semibold text-slate-600">{item.evidence}</p>
                                    <p className="mt-1 text-sm font-semibold text-slate-800"><b>Se pide:</b> {item.ask}</p>
                                </li>
                            ))}
                        </ol>
                        {report.decisions.more > 0 && <p className="mt-2 text-xs font-bold text-slate-500">{report.decisions.more} asuntos más en el Centro de análisis.</p>}
                    </div>
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-sm font-black uppercase tracking-wide text-[#281FD0]">2. Situación · últimas 4 semanas</h3>
                            {report.situation.status !== 'OK' ? <p className="mt-2 text-sm font-semibold text-slate-600">{report.situation.reason}</p> : (
                                <table className="mt-2 w-full text-sm">
                                    <tbody>
                                        {report.situation.rows.map((row) => (
                                            <tr key={row.indicator} className="border-b border-slate-100">
                                                <td className="py-1 font-bold text-slate-800">{row.label}</td>
                                                <td className="py-1 text-right font-semibold tabular-nums text-slate-600">{row.recent.previous ?? '–'} → {row.recent.current}</td>
                                                <td className="py-1 pl-3 text-right font-black tabular-nums text-slate-900">{change(row.recent)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                        <div>
                            <h3 className="text-sm font-black uppercase tracking-wide text-[#281FD0]">3. Compromisos</h3>
                            <p className="mt-2 text-sm font-semibold text-slate-700">
                                {report.commitments.open} abiertos · {report.commitments.fulfilled_since_last.length} cumplidos desde la última sesión ·{' '}
                                <span className="text-red-700">{report.commitments.overdue} atrasados</span> · {report.commitments.repeated} repetidos · {report.commitments.without_information} sin reporte
                            </p>
                            {report.commitments.last_session && (
                                <p className="mt-1 text-sm font-semibold text-slate-700">
                                    Última sesión ({report.commitments.last_session.split('-').reverse().join('/')}): {report.commitments.last_session_items.length} compromisos.
                                </p>
                            )}
                            {report.commitments.overdue_by_owner.length > 0 && (
                                <ul className="mt-2 space-y-1 text-sm">
                                    {report.commitments.overdue_by_owner.slice(0, 5).map((group) => (
                                        <li key={group.responsible} className="flex justify-between gap-3 border-b border-slate-100 py-1">
                                            <span className="font-bold text-slate-800">{group.responsible}</span>
                                            <span className="font-black tabular-nums text-red-700">{group.count} atrasado{group.count === 1 ? '' : 's'}</span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                        <div>
                            <h3 className="text-sm font-black uppercase tracking-wide text-[#281FD0]">4. Intervenciones</h3>
                            <p className="mt-2 text-sm font-semibold text-slate-700">
                                {report.interventions.length ? `${report.interventions.length} documentadas.` : 'Ninguna documentada: el Consejo no puede saber qué funcionó.'}
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
};

export default DecisionReportPanel;
