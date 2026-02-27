import React, { useState, useEffect } from 'react';
import {
    Loader2,
    Upload,
    CheckCircle2,
    AlertTriangle,
    XCircle,
    Info,
    BarChart2,
    TrendingUp,
    FileJson,
    FileSpreadsheet,
    ArrowLeft,
    History,
    FileText,
    Download,
    Calendar,
    Table as TableIcon,
    Database,
    Zap
} from "lucide-react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    LineChart,
    Line,
    Cell,
    PieChart,
    Pie
} from 'recharts';
import { API_BASE_URL } from '../utils/apiConfig';

const Card = ({ children, className = "" }) => (
    <div className={`bg-white rounded-xl shadow-sm border border-slate-200 ${className}`}>
        {children}
    </div>
);

const TabButton = ({ active, onClick, children, icon: Icon }) => (
    <button
        onClick={onClick}
        className={`px-4 py-3 text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-2 border-b-2 ${active
            ? 'border-indigo-600 text-indigo-600 bg-indigo-50/50'
            : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
            }`}
    >
        {Icon && <Icon size={14} />}
        {children}
    </button>
);

const DataQuality = ({ initialReportId }) => {
    const [report, setReport] = useState(null);
    const [issues, setIssues] = useState([]);
    const [reports, setReports] = useState([]); // Historial
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('summary');
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [error, setError] = useState(null);
    const [loadingIssues, setLoadingIssues] = useState(false);

    // Cargar historial al inicio
    useEffect(() => {
        fetchReports();
        if (initialReportId) {
            fetchReport(initialReportId);
        }
    }, [initialReportId]);

    const fetchReports = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/dq/reports?limit=10`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setReports(data);
        } catch (err) {
            console.error("Error fetching history:", err);
        }
    };

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setLoading(true);
        setError(null);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('source_name', 'MANUAL_AUDIT');

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/dq/run`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Error al procesar el archivo');
            }

            const data = await response.json();
            await fetchReport(data.report_id);
            fetchReports();
        } catch (err) {
            setError(err.message);
            setLoading(false);
        }
    };

    const fetchReport = async (reportId) => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/dq/report/${reportId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error("No se pudo cargar el reporte");
            const data = await response.json();
            setReport({ ...data, id: reportId });
            setActiveTab('summary');
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchIssues = async () => {
        if (!report?.id) return;
        setLoadingIssues(true);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/dq/report/${report.id}/issues`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setIssues(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingIssues(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'issues') {
            fetchIssues();
        }
    }, [activeTab, report?.id]);

    const downloadFile = async (format) => {
        if (!report?.id) return;
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/dq/report/${report.id}/${format}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dq_report_${report.id}.${format === 'excel' ? 'xlsx' : 'json'}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (err) {
            console.error(err);
        }
    };

    const getSemaforoColor = (semaforo) => {
        switch (semaforo) {
            case 'VERDE': return 'text-emerald-500 bg-emerald-50 border-emerald-200';
            case 'AMARILLO': return 'text-amber-500 bg-amber-50 border-amber-200';
            case 'ROJO': return 'text-red-500 bg-red-50 border-red-200';
            default: return 'text-slate-500 bg-slate-50 border-slate-200';
        }
    };

    const getScoreColor = (score) => {
        if (score >= 0.8) return 'text-emerald-500';
        if (score >= 0.5) return 'text-amber-500';
        return 'text-red-500';
    };

    return (
        <div className="flex h-[calc(100vh-120px)] gap-6 overflow-hidden">
            {/* Sidebar de Historial */}
            <div className={`transition-all duration-300 ${isSidebarOpen ? 'w-80' : 'w-0'} flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden`}>
                <div className="p-4 border-b bg-slate-50 flex justify-between items-center">
                    <h3 className="font-bold text-slate-700 flex items-center gap-2 uppercase text-xs tracking-widest">
                        <History size={16} /> Historial
                    </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {reports.length === 0 ? (
                        <div className="text-center py-8 text-slate-400 text-xs italic">No hay reportes previos</div>
                    ) : (
                        reports.map((h) => (
                            <button
                                key={h.id}
                                onClick={() => fetchReport(h.id)}
                                className={`w-full text-left p-3 rounded-lg border transition-all hover:shadow-md ${report?.id === h.id ? 'border-indigo-500 bg-indigo-50/30 ring-1 ring-indigo-500' : 'border-slate-100 hover:border-slate-200'
                                    }`}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <span className="text-[10px] font-black text-slate-400 truncate w-32 uppercase">{h.filename}</span>
                                    <span className={`text-[9px] font-black px-1.5 py-0.5 rounded border ${getSemaforoColor(h.semaforo)}`}>
                                        {h.semaforo}
                                    </span>
                                </div>
                                <div className="text-xs font-bold text-slate-700 mb-1">{Math.round(h.score_overall * 100)}% Calidad</div>
                                <div className="text-[9px] text-slate-400 font-medium">
                                    {new Date(h.created_at).toLocaleString()}
                                </div>
                            </button>
                        ))
                    )}
                </div>
            </div>

            {/* Contenido Principal */}
            <div className="flex-1 flex flex-col overflow-hidden p-6 gap-6">
                {!report && !loading && (
                    <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-3xl bg-white/50 group hover:border-indigo-400 transition-all p-12 text-center relative">
                        <input
                            type="file"
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            accept=".xlsx,.xls"
                            onChange={handleFileUpload}
                        />
                        <div className="p-6 bg-slate-100 rounded-full mb-6 group-hover:bg-indigo-600 transition-all group-hover:scale-110">
                            <Upload className="h-10 w-10 text-slate-400 group-hover:text-white" />
                        </div>
                        <h2 className="text-2xl font-black text-slate-800 mb-2">Auditar Calidad de Datos</h2>
                        <p className="text-slate-500 font-medium max-w-sm">Suba el archivo de registros para ejecutar reglas de esquema, validación y consistencia.</p>

                        {error && (
                            <div className="mt-8 p-4 bg-red-50 text-red-700 rounded-xl border border-red-200 flex items-center gap-3 max-w-md mx-auto">
                                <XCircle size={20} />
                                <span className="text-xs font-bold">{error}</span>
                            </div>
                        )}
                    </div>
                )}

                {loading && (
                    <div className="flex-1 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm rounded-3xl border border-slate-200">
                        <div className="relative mb-6">
                            <div className="h-16 w-16 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin"></div>
                            <Zap className="absolute inset-0 m-auto h-6 w-6 text-indigo-400 animate-pulse" />
                        </div>
                        <h3 className="text-xl font-bold text-slate-800">Analizando Datos...</h3>
                        <p className="text-slate-500 text-sm">Calculando scores y detectando duplicados</p>
                    </div>
                )}

                {report && !loading && (
                    <div className="flex-1 flex flex-col space-y-6 overflow-y-auto pr-2 custom-scrollbar">
                        {/* Header del Reporte */}
                        <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-200 ring-1 ring-slate-100">
                            <div className="flex items-center gap-4">
                                <div className={`p-4 rounded-2xl border ${getSemaforoColor(report.semaforo)}`}>
                                    <Zap size={32} />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-black text-slate-800 tracking-tight flex items-center gap-2">
                                        Reporte: {report.filename}
                                    </h2>
                                    <p className="text-slate-400 text-sm font-bold flex items-center gap-2">
                                        <Calendar size={14} /> {new Date().toLocaleDateString()} • {report.rows_total.toLocaleString()} registros auditados
                                    </p>
                                </div>
                            </div>
                            <div className="flex gap-3">
                                <button onClick={() => downloadFile('json')} className="flex items-center gap-2 bg-slate-100 px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-wider text-slate-600 hover:bg-slate-200 transition-all active:scale-95">
                                    <FileJson size={14} /> Exportar JSON
                                </button>
                                <button onClick={() => downloadFile('excel')} className="flex items-center gap-2 bg-slate-900 px-6 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest text-white hover:bg-indigo-600 transition-all shadow-lg active:scale-95">
                                    <Download size={16} /> Descargar Auditoría XLSX
                                </button>
                            </div>
                        </div>

                        {/* KPIS Principales */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                            <Card className="p-6 flex flex-col items-center justify-center bg-white relative overflow-hidden group">
                                <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-50 -mr-12 -mt-12 rounded-full group-hover:scale-110 transition-transform" />
                                <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 mb-2 relative">Score Global</div>
                                <div className={`text-5xl font-black relative ${getScoreColor(report.score_overall)}`}>
                                    {Math.round(report.score_overall * 100)}%
                                </div>
                            </Card>

                            <Card className="p-6 flex flex-col">
                                <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 mb-2">Hallazgos Críticos</div>
                                <div className="text-4xl font-black text-red-500">
                                    {report.issues.filter(i => i.severity === 'ERROR').reduce((acc, i) => acc + i.count, 0).toLocaleString()}
                                </div>
                                <p className="text-[10px] text-slate-400 font-bold uppercase mt-auto leading-relaxed">Requieren corrección inmediata para ingesta</p>
                            </Card>

                            <Card className="p-6">
                                <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 mb-2">Advertencias</div>
                                <div className="text-4xl font-black text-amber-500">
                                    {report.issues.filter(i => i.severity === 'WARNING').reduce((acc, i) => acc + i.count, 0).toLocaleString()}
                                </div>
                                <p className="text-[10px] text-slate-400 font-bold uppercase mt-auto leading-relaxed">Revisiones manuales recomendadas</p>
                            </Card>

                            <Card className="p-6">
                                <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 mb-2">Rango Temporal</div>
                                <div className="mt-auto space-y-1">
                                    <div className="text-xs font-black text-slate-700 flex justify-between">DESDE <span>{new Date(report.min_date).getFullYear()}</span></div>
                                    <div className="text-xs font-black text-slate-700 flex justify-between">HASTA <span>{new Date(report.max_date).getFullYear()}</span></div>
                                </div>
                            </Card>
                        </div>

                        {/* Tabs Navigation */}
                        <Card className="flex-1 flex flex-col overflow-hidden">
                            <div className="px-6 border-b flex gap-1 bg-slate-50/50">
                                <TabButton active={activeTab === 'summary'} onClick={() => setActiveTab('summary')} icon={BarChart2}>Resumen</TabButton>
                                <TabButton active={activeTab === 'issues'} onClick={() => setActiveTab('issues')} icon={AlertTriangle}>Cruces y Errores</TabButton>
                                <TabButton active={activeTab === 'profile'} onClick={() => setActiveTab('profile')} icon={Database}>Perfil Columnas</TabButton>
                                <TabButton active={activeTab === 'consistency'} onClick={() => setActiveTab('consistency')} icon={Zap}>Consistencia</TabButton>
                                <TabButton active={activeTab === 'duplicates'} onClick={() => setActiveTab('duplicates')} icon={TableIcon}>Duplicados</TabButton>
                                <TabButton active={activeTab === 'series'} onClick={() => setActiveTab('series')} icon={TrendingUp}>Tendencias</TabButton>
                            </div>

                            <div className="p-6 overflow-y-auto">
                                {activeTab === 'summary' && (
                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 animate-fade-in">
                                        <div className="space-y-8">
                                            <h4 className="text-sm font-black text-slate-800 uppercase tracking-widest border-b pb-2">Distribución Territorial (Top 10)</h4>
                                            <div className="h-80">
                                                {report.profiles?.top_values?.MUNICIPIO ? (
                                                    <ResponsiveContainer width="100%" height="100%">
                                                        <BarChart data={Object.entries(report.profiles.top_values.MUNICIPIO).map(([k, v]) => ({ name: k, value: v }))} layout="vertical">
                                                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                                                            <XAxis type="number" hide />
                                                            <YAxis dataKey="name" type="category" width={110} tick={{ fontSize: 9, fontWeight: 700 }} axisLine={false} tickLine={false} />
                                                            <Tooltip cursor={{ fill: '#f8fafc' }} />
                                                            <Bar dataKey="value" fill="#4f46e5" radius={[0, 4, 4, 0]} barSize={20} />
                                                        </BarChart>
                                                    </ResponsiveContainer>
                                                ) : (
                                                    <div className="h-full flex items-center justify-center text-slate-400 italic text-xs">Datos territoriales no disponibles para este reporte</div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="space-y-6">
                                            <h4 className="text-sm font-black text-slate-800 uppercase tracking-widest border-b pb-2">Dimensiones de Calidad</h4>
                                            {[
                                                { label: 'Completitud', score: report.score_completeness, desc: 'Falta de datos nulos' },
                                                { label: 'Validez', score: report.score_validity, desc: 'Cumplimiento de reglas y fechas' },
                                                { label: 'Unicidad', score: report.score_uniqueness, desc: 'Ausencia de duplicados lógicos' },
                                                { label: 'Consistencia', score: report.score_consistency, desc: 'Coherencia de códigos y nombres' }
                                            ].map(dim => (
                                                <div key={dim.label} className="bg-slate-50 p-4 rounded-xl border border-slate-100 group hover:shadow-md transition-all">
                                                    <div className="flex justify-between items-end mb-2">
                                                        <div>
                                                            <div className="text-xs font-black uppercase text-slate-700">{dim.label}</div>
                                                            <div className="text-[10px] font-medium text-slate-400">{dim.desc}</div>
                                                        </div>
                                                        <div className={`text-xl font-black ${getScoreColor(dim.score)}`}>{Math.round(dim.score * 100)}%</div>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full rounded-full transition-all duration-1000 ${dim.score > 0.8 ? 'bg-emerald-500' : dim.score > 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                                                            style={{ width: `${dim.score * 100}%` }}
                                                        />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'issues' && (
                                    <div className="space-y-4 animate-fade-in">
                                        <div className="flex justify-between items-center mb-2">
                                            <h4 className="text-sm font-black text-slate-800 uppercase tracking-widest">Cruces con Reglas de Negocio</h4>
                                            <span className="text-[10px] font-bold text-slate-400">{issues.length} Hallazgos específicos</span>
                                        </div>
                                        <div className="overflow-x-auto rounded-xl border border-slate-200">
                                            <table className="w-full text-left border-collapse">
                                                <thead>
                                                    <tr className="bg-slate-50 border-b border-slate-200">
                                                        <th className="px-5 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest">Severidad</th>
                                                        <th className="px-5 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest">Campo</th>
                                                        <th className="px-5 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest">Error Detectado</th>
                                                        <th className="px-5 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest text-right">Filas Afectadas</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {loadingIssues ? (
                                                        <tr><td colSpan="4" className="text-center py-20"><Loader2 className="animate-spin inline mr-2" /> Analizando muestras...</td></tr>
                                                    ) : (issues || []).length === 0 ? (
                                                        <tr><td colSpan="4" className="text-center py-20 text-slate-400 italic">No se encontraron hallazgos específicos</td></tr>
                                                    ) : issues.map(issue => (
                                                        <tr key={issue.id || Math.random()} className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors">
                                                            <td className="px-5 py-4">
                                                                <span className={`px-2 py-1 rounded-md text-[9px] font-black tracking-tighter ${issue.severity === 'ERROR' ? 'bg-red-100 text-red-700 border border-red-200' :
                                                                    issue.severity === 'WARNING' ? 'bg-amber-100 text-amber-700 border border-amber-200' :
                                                                        'bg-blue-100 text-blue-700 border border-blue-200'
                                                                    }`}>
                                                                    {issue.severity}
                                                                </span>
                                                            </td>
                                                            <td className="px-5 py-4 text-xs font-bold text-slate-700 font-mono tracking-tighter">{issue.field}</td>
                                                            <td className="px-5 py-4 text-xs text-slate-600 font-medium">{issue.rule}</td>
                                                            <td className="px-5 py-4 text-xs font-black text-slate-800 text-right">{issue.count.toLocaleString()}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'profile' && (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 animate-fade-in">
                                        {Object.entries(report.profiles.columns).map(([col, data]) => (
                                            <div key={col} className="p-5 bg-white rounded-2xl border border-slate-100 shadow-sm hover:ring-2 hover:ring-indigo-500/20 transition-all">
                                                <h5 className="font-black text-slate-800 text-xs mb-4 pb-2 border-b uppercase tracking-tighter truncate" title={col}>{col}</h5>
                                                <div className="space-y-3">
                                                    <div className="flex justify-between items-center bg-slate-50 px-3 py-1.5 rounded-lg">
                                                        <span className="text-[10px] font-black text-slate-400">TIPO</span>
                                                        <span className="text-[10px] font-bold text-slate-600 font-mono">{data.dtype.toUpperCase()}</span>
                                                    </div>
                                                    <div className="flex justify-between items-center">
                                                        <span className="text-[10px] font-black text-slate-400">UNICIDAD</span>
                                                        <span className="text-xs font-black text-indigo-600">{data.nunique.toLocaleString()}</span>
                                                    </div>
                                                    <div className="flex justify-between items-center">
                                                        <span className="text-[10px] font-black text-slate-400">INTEGRIDAD</span>
                                                        <span className={`text-xs font-black ${data.nulls > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                                                            {100 - Math.round(data.null_pct)}%
                                                        </span>
                                                    </div>
                                                    <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                                                        <div className={`h-full bg-emerald-500`} style={{ width: `${100 - data.null_pct}%` }} />
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {activeTab === 'consistency' && (
                                    <div className="space-y-8 animate-fade-in">
                                        <div className="bg-amber-50 rounded-xl p-6 border border-amber-100 text-amber-800 flex gap-4">
                                            <Zap className="text-amber-500 shrink-0" size={24} />
                                            <div>
                                                <h4 className="font-black text-sm uppercase tracking-widest mb-1">Análisis de Consistencia Dimensional</h4>
                                                <p className="text-xs font-medium opacity-80 leading-relaxed">Verificamos que cada código geográfico (Departamento/Municipio) se corresponda con un único nombre normalizado. Las inconsistencias sugieren errores tipográficos o cambios en la codificación oficial.</p>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                            <div className="space-y-4">
                                                <h5 className="text-xs font-black text-slate-400 uppercase tracking-widest">Ejemplos de Conflictos COD ↔ MUNICIPIO</h5>
                                                {report.samples?.muni_consistency ? (
                                                    <div className="overflow-x-auto rounded-xl border border-slate-200">
                                                        <table className="w-full text-left text-[10px]">
                                                            <thead className="bg-slate-50">
                                                                <tr className="border-b">
                                                                    <th className="px-3 py-2">COD_MUNI</th>
                                                                    <th className="px-3 py-2">MUNICIPIO EN EXCEL</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {report.samples.muni_consistency.slice(0, 10).map((s, idx) => (
                                                                    <tr key={idx} className="border-b">
                                                                        <td className="px-3 py-2 font-mono font-bold text-indigo-600">{s.COD_MUNI}</td>
                                                                        <td className="px-3 py-2 font-bold">{s.MUNICIPIO}</td>
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                ) : (
                                                    <div className="p-12 text-center bg-emerald-50 rounded-xl border border-emerald-100 text-emerald-600">
                                                        <CheckCircle2 size={32} className="mx-auto mb-2 opacity-50" />
                                                        <p className="text-xs font-black uppercase">Todo Consistente</p>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'duplicates' && (
                                    <div className="space-y-8 animate-fade-in">
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                            <div className="bg-white p-6 rounded-2xl border border-slate-200 flex flex-col items-center">
                                                <h5 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-6">Métrica de Redundancia</h5>
                                                <div className="h-48 w-full">
                                                    <ResponsiveContainer width="100%" height="100%">
                                                        <PieChart>
                                                            <Pie
                                                                data={[
                                                                    { name: 'Únicos', value: report.rows_total - (report.samples?.exact_duplicates?.length || 0) },
                                                                    { name: 'Duplicados', value: report.samples?.exact_duplicates?.length || 0 }
                                                                ]}
                                                                innerRadius={60}
                                                                outerRadius={80}
                                                                paddingAngle={5}
                                                                dataKey="value"
                                                            >
                                                                <Cell fill="#e2e8f0" />
                                                                <Cell fill="#ef4444" />
                                                            </Pie>
                                                            <Tooltip />
                                                        </PieChart>
                                                    </ResponsiveContainer>
                                                </div>
                                                <div className="text-center mt-4">
                                                    <div className="text-2xl font-black text-slate-800">{Math.round((1 - report.score_uniqueness) * 100)}%</div>
                                                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Tasa de Duplicidad</div>
                                                </div>
                                            </div>

                                            <div className="space-y-4">
                                                <h5 className="text-xs font-black text-slate-400 uppercase tracking-widest">Audit de Duplicados Lógicos</h5>
                                                <p className="text-xs text-slate-500 italic">Filas que comparten la misma Fecha, Lugar y Conducta pero pueden tener diferencias en campos no clave.</p>
                                                {report.samples?.logical_duplicates ? (
                                                    <div className="overflow-x-auto rounded-xl border border-red-100">
                                                        <table className="w-full text-left text-[9px]">
                                                            <thead className="bg-red-50 text-red-600">
                                                                <tr className="border-b border-red-100">
                                                                    <th className="px-3 py-2">FECHA</th>
                                                                    <th className="px-3 py-2">MUNICIPIO</th>
                                                                    <th className="px-3 py-2">CONDUCTA</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {report.samples.logical_duplicates.slice(0, 10).map((s, idx) => (
                                                                    <tr key={idx} className="border-b border-slate-100">
                                                                        <td className="px-3 py-2 font-bold">{new Date(s.FECHA_HECHO_DT).toLocaleDateString()}</td>
                                                                        <td className="px-3 py-2">{s.MUNICIPIO}</td>
                                                                        <td className="px-3 py-2 text-slate-400 truncate max-w-[150px]">{s["DESCRIPCION CONDUCTA"]}</td>
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                ) : <p className="text-xs text-emerald-600 font-bold">No se detectaron duplicados lógicos sustanciales.</p>}
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'series' && (
                                    <div className="space-y-8 animate-fade-in">
                                        <h4 className="text-sm font-black text-slate-800 uppercase tracking-widest border-b pb-2">Tendencia Histórica Auditada</h4>
                                        <div className="h-96">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={Object.entries(report.profiles.anual_sum).map(([key, val]) => ({ year: key, count: val }))}>
                                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                                    <XAxis dataKey="year" axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 700 }} />
                                                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 700 }} />
                                                    <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                                                    <Line type="monotone" dataKey="count" stroke="#4f46e5" strokeWidth={4} dot={{ r: 6, fill: '#4f46e5', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 8, strokeWidth: 0 }} />
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </Card>
                    </div>
                )}
            </div>

            {/* Toggle Historial (Mobile Floating) */}
            {!report && (
                <button
                    onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                    className="fixed bottom-6 right-6 p-4 bg-indigo-600 text-white rounded-full shadow-2xl md:hidden"
                >
                    <History />
                </button>
            )}
        </div>
    );
};

export default DataQuality;
