import React, { useState, useEffect } from 'react';
import { 
    AlertCircle, 
    CheckCircle2, 
    ChevronLeft, 
    Table as TableIcon, 
    FileText, 
    Info,
    ShieldAlert,
    Download
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const PoliceIngestionAudit = ({ runId, onBack }) => {
    const [run, setRun] = useState(null);
    const [issues, setIssues] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchData();
    }, [runId]);

    const fetchData = async () => {
        try {
            const token = localStorage.getItem('token');
            const [runRes, issuesRes] = await Promise.all([
                fetch(`${API_BASE_URL}/ingesta/runs/${runId}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                }),
                fetch(`${API_BASE_URL}/ingesta/runs/${runId}/issues`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
            ]);

            if (!runRes.ok || !issuesRes.ok) throw new Error("Error obteniendo datos de la auditoría");

            const runData = await runRes.json();
            const issuesData = await issuesRes.json();

            setRun(runData);
            setIssues(issuesData);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div className="p-20 text-center animate-pulse font-black text-slate-400">CARGANDO AUDITORÍA...</div>;
    if (error) return <div className="p-20 text-center text-red-500 font-bold">{error}</div>;

    const topConductas = run?.resumen?.top_conductas || {};
    const snapshotSummary = run?.resumen?.snapshot || {};
    const existingHistory = snapshotSummary.existentes_historico ?? run?.duplicadas ?? 0;
    const repeatedInFile = snapshotSummary.repetidas_en_archivo ?? 0;

    return (
        <div className="max-w-6xl mx-auto space-y-8 py-6 animate-fade-in">
            <button 
                onClick={onBack}
                className="flex items-center gap-2 text-slate-500 hover:text-indigo-600 font-black uppercase text-xs tracking-widest transition-all"
            >
                <ChevronLeft size={16} /> Volver a Ingesta
            </button>

            <div className="bg-white rounded-[2.5rem] shadow-xl border border-slate-100 overflow-hidden">
                <div className="bg-slate-900 p-8 text-white flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-black tracking-tighter uppercase">Reporte de Auditoría: Policía Jamundí</h1>
                        <p className="text-slate-400 font-bold text-sm">Proceso ID: {runId}</p>
                    </div>
                    <div className="text-right">
                        <div className={`px-4 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${run.status === 'COMPLETED' ? 'bg-emerald-500' : 'bg-red-500'}`}>
                            {run.status}
                        </div>
                        <p className="text-[10px] text-slate-400 mt-2 font-bold uppercase">{new Date(run.fecha_inicio).toLocaleString()}</p>
                    </div>
                </div>

                <div className="p-8 grid grid-cols-1 md:grid-cols-5 gap-4">
                    <div className="bg-slate-50 p-6 rounded-3xl border border-slate-100">
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Total Leídos</p>
                        <p className="text-3xl font-black text-slate-800">{run.total_filas}</p>
                    </div>
                    <div className="bg-emerald-50 p-6 rounded-3xl border border-emerald-100">
                        <p className="text-[10px] font-black text-emerald-600 uppercase tracking-widest mb-1">Aprobados</p>
                        <p className="text-3xl font-black text-emerald-700">{run.aprobadas}</p>
                    </div>
                    <div className="bg-red-50 p-6 rounded-3xl border border-red-100">
                        <p className="text-[10px] font-black text-red-600 uppercase tracking-widest mb-1">Rechazados</p>
                        <p className="text-3xl font-black text-red-700">{run.rechazadas}</p>
                    </div>
                    <div className="bg-amber-50 p-6 rounded-3xl border border-amber-100">
                        <p className="text-[10px] font-black text-amber-600 uppercase tracking-widest mb-1">Ya existentes</p>
                        <p className="text-3xl font-black text-amber-700">{existingHistory}</p>
                    </div>
                    <div className="bg-violet-50 p-6 rounded-3xl border border-violet-100">
                        <p className="text-[10px] font-black text-violet-600 uppercase tracking-widest mb-1">Repetidos en archivo</p>
                        <p className="text-3xl font-black text-violet-700">{repeatedInFile}</p>
                    </div>
                </div>

                <div className="px-8 pb-8 grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div className="space-y-4">
                        <h3 className="text-sm font-black text-slate-800 uppercase tracking-widest flex items-center gap-2">
                            <Info size={16} className="text-indigo-500" /> Resumen de Hallazgos
                        </h3>
                        <div className="bg-slate-50 rounded-3xl p-6 border border-slate-100 overflow-auto max-h-80">
                            {issues.length === 0 ? (
                                <div className="text-center py-10">
                                    <CheckCircle2 size={40} className="mx-auto text-emerald-300 mb-2" />
                                    <p className="text-xs font-bold text-slate-400 uppercase">No se detectaron errores críticos</p>
                                </div>
                            ) : (
                                <table className="w-full text-left">
                                    <thead>
                                        <tr className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-200">
                                            <th className="pb-3">Fila</th>
                                            <th className="pb-3">Regla</th>
                                            <th className="pb-3">Descripción</th>
                                        </tr>
                                    </thead>
                                    <tbody className="text-xs">
                                        {issues.map((issue, i) => (
                                            <tr key={i} className="border-b border-slate-100 last:border-0">
                                                <td className="py-3 font-black text-slate-600">{issue.fila}</td>
                                                <td className="py-3 font-bold text-red-600">{issue.regla}</td>
                                                <td className="py-3 text-slate-500">{issue.descripcion}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>

                    <div className="space-y-4">
                        <h3 className="text-sm font-black text-slate-800 uppercase tracking-widest flex items-center gap-2">
                            <TableIcon size={16} className="text-indigo-500" /> Distribución Detectada
                        </h3>
                        <div className="bg-slate-50 rounded-3xl p-6 border border-slate-100">
                            <div className="space-y-4">
                                {Object.entries(topConductas).map(([label, count], i) => (
                                    <div key={i}>
                                        <div className="flex justify-between text-[11px] font-bold text-slate-600 mb-1 uppercase">
                                            <span>{label}</span>
                                            <span className="font-black">{count}</span>
                                        </div>
                                        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                                            <div 
                                                className="h-full bg-indigo-500 rounded-full" 
                                                style={{ width: `${(count / run.total_filas) * 100}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                ))}
                                {Object.keys(topConductas).length === 0 && (
                                    <p className="text-center py-10 text-xs font-bold text-slate-400 uppercase tracking-widest">Sin datos de distribución</p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PoliceIngestionAudit;


