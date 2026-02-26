import React, { useState, useEffect } from 'react';
import {
    Download, Calendar, Filter, FileText, Search, Clock,
    ShieldCheck, AlertCircle, Eye, Copy, ExternalLink, RefreshCw
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const ReportsPage = () => {
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedReport, setSelectedReport] = useState(null);
    const [filterType, setFilterType] = useState('all');
    const [searchTerm, setSearchTerm] = useState('');
    const [exportLoading, setExportLoading] = useState(false);

    const fetchHistory = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const typeParam = filterType !== 'all' ? `?type=${filterType}` : '';
            const response = await fetch(`${API_BASE_URL}/intelligence/reports/history${typeParam}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setReports(data);
            }
        } catch (err) {
            console.error("Error fetching reports:", err);
        } finally {
            setLoading(false);
        }
    };

    const handleExportPdf = async () => {
        if (!selectedReport) return;
        setExportLoading(true);
        try {
            const token = localStorage.getItem('token');
            // Si ya existe el path, descargar directamente, si no, generarlo
            if (!selectedReport.pdf_path) {
                const genRes = await fetch(`${API_BASE_URL}/intelligence/reports/${selectedReport.id}/export/pdf`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (!genRes.ok) throw new Error("Error generando PDF");
                const updatedData = await genRes.json();
                // Actualizar el reporte seleccionado con la nueva meta
                setSelectedReport(prev => ({ ...prev, ...updatedData, pdf_path: "exists" })); // marcamos path como existente
                alert("PDF Generado con éxito. Iniciando descarga...");
            }

            // Descarga via Blob (para pasar el Token)
            const dlRes = await fetch(`${API_BASE_URL}/intelligence/reports/${selectedReport.id}/export/pdf`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!dlRes.ok) throw new Error("Error descargando PDF");

            const blob = await dlRes.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `SISC_Reporte_${selectedReport.period_key}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);

        } catch (err) {
            alert(err.message);
        } finally {
            setExportLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [filterType]);

    const viewReport = async (id) => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/intelligence/reports/${id}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setSelectedReport(data);
            }
        } catch (err) {
            alert("Error al cargar el detalle del reporte");
        }
    };

    // Minimal markdown renderer (simple replacements for basic MD)
    const renderMarkdown = (md) => {
        if (!md) return "";
        return md
            .replace(/^### (.*$)/gim, '<h3 class="text-xl font-bold mt-6 mb-4 text-slate-800">$1</h3>')
            .replace(/^#### (.*$)/gim, '<h4 class="text-lg font-bold mt-4 mb-2 text-slate-700">$1</h4>')
            .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*)\*/gim, '<em>$1</em>')
            .replace(/\|/g, '') // Remove pipes for simpler look if table not full
            .replace(/\n/g, '<br />');
    };

    const copyToClipboard = () => {
        if (selectedReport) {
            navigator.clipboard.writeText(selectedReport.output_markdown);
            alert("Contenido copiado al portapapeles");
        }
    };

    return (
        <div className="p-6 space-y-6 bg-slate-50 min-h-screen relative">
            {/* Header */}
            <div className="flex justify-between items-end bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <div>
                    <h1 className="text-3xl font-black text-slate-800 tracking-tighter uppercase">Archivo de Boletines</h1>
                    <p className="text-slate-500 font-medium">Historial de reportes automáticos y estratégicos del SISC</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={fetchHistory}
                        className="p-2.5 rounded-xl bg-slate-100 text-slate-500 hover:bg-slate-200 transition-all font-bold group"
                    >
                        <RefreshCw size={20} className={loading ? "animate-spin" : "group-hover:rotate-180 transition-transform duration-500"} />
                    </button>
                    <div className="flex items-center gap-2 bg-slate-100 p-1.5 rounded-xl">
                        {['all', 'SEMANAL', 'MENSUAL'].map(t => (
                            <button
                                key={t}
                                onClick={() => setFilterType(t)}
                                className={`px-4 py-1.5 rounded-lg text-xs font-black transition-all ${filterType === t ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-500 hover:text-slate-800'}`}
                            >
                                {t === 'all' ? 'TODOS' : t}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* List Table */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                {loading ? (
                    <div className="p-20 text-center space-y-4">
                        <RefreshCw className="mx-auto animate-spin text-indigo-500" size={40} />
                        <p className="text-slate-400 font-black tracking-widest uppercase text-xs">Cargando Archivo...</p>
                    </div>
                ) : reports.length === 0 ? (
                    <div className="p-20 text-center text-slate-400 border-2 border-dashed m-6 rounded-2xl">
                        No se encontraron reportes generados.
                    </div>
                ) : (
                    <table className="w-full text-left">
                        <thead className="bg-slate-50 border-b border-slate-200">
                            <tr>
                                <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest">Tipo</th>
                                <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest">Periodo</th>
                                <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest">Generado</th>
                                <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest">Estado</th>
                                <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest text-right">Acciones</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {reports.map((rep) => (
                                <tr key={rep.id} className="hover:bg-indigo-50/30 transition-colors group">
                                    <td className="px-6 py-4">
                                        <span className={`px-2.5 py-1 rounded-lg text-[10px] font-black uppercase ${rep.report_type === 'SEMANAL' ? 'bg-amber-100 text-amber-700' : 'bg-indigo-100 text-indigo-700'}`}>
                                            {rep.report_type}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 font-black text-slate-700">{rep.period_key}</td>
                                    <td className="px-6 py-4 text-xs font-medium text-slate-500">
                                        {new Date(rep.generated_at).toLocaleString('es-CO')}
                                    </td>
                                    <td className="px-6 py-4 text-[10px] font-black text-emerald-600 italic">
                                        {rep.status}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <button
                                            onClick={() => viewReport(rep.id)}
                                            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-400 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50 transition-all shadow-sm"
                                        >
                                            <Eye size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Detail View Modal Overlay */}
            {selectedReport && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-6">
                    <div className="bg-white w-full max-w-5xl max-h-[90vh] rounded-3xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
                        {/* Modal Header */}
                        <div className="bg-slate-50 p-6 border-b border-slate-200 flex justify-between items-center">
                            <div className="flex items-center gap-4">
                                <div className="p-3 bg-indigo-600 rounded-2xl text-white shadow-lg shadow-indigo-200">
                                    <FileText size={24} />
                                </div>
                                <div>
                                    <h2 className="text-xl font-black text-slate-800 tracking-tighter uppercase leading-none">
                                        {selectedReport.report_type}: {selectedReport.period_key}
                                    </h2>
                                    <p className="text-slate-500 text-xs font-bold mt-1 uppercase tracking-widest">ID: {selectedReport.id} • Fuente: {selectedReport.source_id}</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setSelectedReport(null)}
                                className="w-10 h-10 flex items-center justify-center rounded-xl hover:bg-slate-200 transition-colors text-slate-400 hover:text-slate-800 font-black"
                            >
                                ✕
                            </button>
                        </div>

                        {/* Modal Content */}
                        <div className="flex-1 overflow-y-auto grid grid-cols-1 lg:grid-cols-3">
                            <div className="lg:col-span-2 p-8 bg-white prose max-w-none">
                                <div
                                    className="text-slate-600 leading-relaxed font-medium markdown-preview"
                                    dangerouslySetInnerHTML={{ __html: renderMarkdown(selectedReport.output_markdown) }}
                                />
                            </div>
                            <div className="bg-slate-50 p-6 border-l border-slate-200 space-y-6 shadow-inner">
                                <div>
                                    <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">Evidencia Técnica</h4>
                                    <div className="bg-white p-4 rounded-2xl border border-slate-200 space-y-3">
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="text-slate-500">Corte de Datos</span>
                                            <span className="font-bold text-slate-700">{selectedReport.meta_info?.fecha_corte || 'N/A'}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="text-slate-500">Generado el</span>
                                            <span className="font-bold text-slate-700">{new Date(selectedReport.generated_at).toLocaleDateString()}</span>
                                        </div>
                                        {selectedReport.forced && (
                                            <div className="p-3 bg-amber-50 rounded-xl border border-amber-200">
                                                <div className="flex items-center gap-2 text-amber-700 font-black text-[10px] uppercase">
                                                    <AlertCircle size={12} /> Forzado Manual
                                                </div>
                                                <p className="text-[10px] text-amber-600 mt-1 font-bold">Por: {selectedReport.forced_by}</p>
                                                <p className="text-[10px] text-amber-600 italic mt-0.5">"{selectedReport.forced_reason}"</p>
                                            </div>
                                        )}
                                        {selectedReport.pdf_generated_at && (
                                            <div className="pt-2 border-t border-slate-100">
                                                <div className="text-[9px] font-black text-slate-400 uppercase mb-1">Evidencia PDF</div>
                                                <div className="text-[9px] text-slate-500 break-all bg-slate-100 p-2 rounded-lg font-mono">
                                                    SHA256: {selectedReport.pdf_sha256}
                                                </div>
                                                <div className="text-[9px] text-slate-400 mt-1 italic">
                                                    Exportado: {new Date(selectedReport.pdf_generated_at).toLocaleString()}
                                                </div>
                                            </div>
                                        )}
                                        <div className="pt-2">
                                            <div className="flex items-center gap-1.5 p-2 bg-emerald-50 rounded-lg text-emerald-700 border border-emerald-100">
                                                <ShieldCheck size={14} />
                                                <span className="text-[10px] font-black uppercase">Validado por Observatorio</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="space-y-2 pt-4 border-t border-slate-200">
                                    <button
                                        onClick={copyToClipboard}
                                        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-white border border-slate-300 rounded-xl text-slate-700 font-bold hover:bg-slate-50 text-sm transition-all"
                                    >
                                        <Copy size={16} /> Copiar Contenido
                                    </button>
                                    <button
                                        onClick={handleExportPdf}
                                        disabled={exportLoading}
                                        className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-bold text-sm transition-all ${exportLoading
                                            ? 'bg-slate-300 text-slate-600 cursor-not-allowed'
                                            : selectedReport.pdf_path
                                                ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-lg shadow-indigo-100'
                                                : 'bg-emerald-600 text-white hover:bg-emerald-700'
                                            }`}
                                    >
                                        {exportLoading ? (
                                            <RefreshCw size={16} className="animate-spin" />
                                        ) : (
                                            <Download size={16} />
                                        )}
                                        {exportLoading ? 'Procesando...' : (selectedReport.pdf_path ? 'Descargar PDF' : 'Generar PDF')}
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Modal Footer */}
                        <div className="p-4 bg-white border-t border-slate-100 text-center">
                            <p className="text-[10px] font-black text-slate-300 uppercase tracking-[0.2em] italic">SISC Jamundí - Inteligencia Estratégica Transaccional</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ReportsPage;
