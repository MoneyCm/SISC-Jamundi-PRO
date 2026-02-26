import React, { useState, useEffect, useRef } from 'react';
import {
    BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import {
    Search, Filter, Calendar, FileText, TrendingUp, AlertCircle,
    MapPin, Clock, CheckCircle2, DollarSign, ChevronRight, List,
    History as HistoryIcon, Info, Download, Loader2, ArrowRight, Upload
} from 'lucide-react';

import { API_BASE_URL } from '../utils/apiConfig';

const COLORS = ['#281FD0', '#34D399', '#FBBF24', '#EF4444', '#8B5CF6'];

const RNMCModule = ({ externalFilters, clearExternalFilters }) => {
    const [activeTab, setActiveTab] = useState('operativo');
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [backlog, setBacklog] = useState({ items: [], total: 0 });
    const [filters, setFilters] = useState({
        from_date: '',
        to_date: '',
        min_dias: '',
        estado: '',
        medida: '',
        localidad: ''
    });
    const [selectedMeasure, setSelectedMeasure] = useState(null);
    const [history, setHistory] = useState(null);
    const [loadingHistory, setLoadingHistory] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState(null);
    const fileInputRef = useRef(null);

    const [error, setError] = useState(null);

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        const token = localStorage.getItem('token');
        try {
            const statsRes = await fetch(`${API_BASE_URL}/intelligence/stats/rnmc?type=monthly`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!statsRes.ok) throw new Error(`Stats: ${statsRes.status}`);

            const statsData = await statsRes.json();
            setData(statsData);

            // Construct backlog query
            const params = new URLSearchParams();
            if (filters.from_date) params.append('from_date', filters.from_date);
            if (filters.to_date) params.append('to_date', filters.to_date);
            if (filters.min_dias) params.append('min_dias', filters.min_dias);
            if (filters.estado) params.append('estado', filters.estado);

            const backlogRes = await fetch(`${API_BASE_URL}/intelligence/rnmc/medidas/backlog?${params.toString()}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!backlogRes.ok) throw new Error(`Backlog: ${backlogRes.status}`);

            const backlogData = await backlogRes.json();
            setBacklog(backlogData);
        } catch (err) {
            console.error("Error fetching RNMC data:", err);
            setError("No se pudieron cargar los datos de RNMC. Por favor, verifique su conexión.");
        } finally {
            setLoading(false);
        }
    };

    const fetchHistory = async (measure) => {
        setLoadingHistory(true);
        setSelectedMeasure(measure);
        const token = localStorage.getItem('token');
        try {
            const res = await fetch(`${API_BASE_URL}/intelligence/rnmc/medidas/history?event_fingerprint=${measure.event_fingerprint}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const historyData = await res.json();
            setHistory(historyData);
            if (historyData.current) {
                setSelectedMeasure(prev => ({ ...prev, ...historyData.current }));
            }
        } catch (err) {
            console.error("Error fetching history:", err);
        } finally {
            setLoadingHistory(false);
        }
    };

    const handleFileChange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setUploading(true);
        setUploadStatus({ text: "Procesando archivo RNMC...", type: "info" });
        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/intelligence/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });

            const data = await response.json();
            if (response.ok) {
                const inserted = data.inserted ?? data.inserted_count ?? 0;
                const updated = data.updated ?? 0;
                const total = data.total ?? inserted + updated;

                if ((inserted + updated) === 0) {
                    const sheetInfo = data.detected_sheet ? `Hoja: ${data.detected_sheet}. ` : '';
                    const detailInfo = data.detail || (data.municipio_uniques ? `Municipios detectados: ${data.municipio_uniques.slice(0, 5).join(', ')}` : (data.message || 'Verifica que el archivo corresponda a la tabla RNMC de Jamundí.'));

                    setUploadStatus({
                        text: data.status === 'REJECTED' ? `Archivo ya procesado: ${data.message}` : `No se cargaron registros. ${sheetInfo}${detailInfo}`,
                        type: data.status === 'REJECTED' ? "info" : "error"
                    });
                } else {
                    setUploadStatus({
                        text: `Éxito: Se procesaron ${inserted} insertados y ${updated} actualizados (total ${total}).`,
                        type: "success"
                    });
                    fetchData(); // Recargar datos para ver lo nuevo
                }
            } else {
                setUploadStatus({
                    text: `Error: ${data.detail || 'Fallo en la carga'}`,
                    type: "error"
                });
            }
        } catch (error) {
            setUploadStatus({ text: "Error de conexión al cargar el archivo.", type: "error" });
        } finally {
            setUploading(false);
            event.target.value = null; // Reset
        }
    };

    // Fetch stats and backlog
    useEffect(() => {
        fetchData();
    }, [filters]);

    // Responder a filtros externos (ej. desde el muro de alertas)
    useEffect(() => {
        if (externalFilters?.event_fingerprint) {
            setActiveTab('operativo');

            // Reconstruir un objeto medida mínimo para el drawer
            const measure = {
                event_fingerprint: externalFilters.event_fingerprint,
                medida: 'Cargando desde alerta...',
                expediente_masked: '***',
                estado: 'EN PROCESO',
                valor_neto: 0,
                valor_pagado: 0
            };

            fetchHistory(measure);

            // Limpiar para evitar re-triggers
            if (clearExternalFilters) {
                setTimeout(clearExternalFilters, 100);
            }
        }
    }, [externalFilters]);

    if (loading && !data) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-20">
                <Loader2 className="animate-spin text-indigo-600 mb-4" size={48} />
                <p className="text-slate-500 font-medium tracking-tight">Cargando Inteligencia RNMC...</p>
            </div>
        );
    }

    if (error && !data) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-20 text-center">
                <AlertCircle className="text-red-400 mb-4" size={48} />
                <h2 className="text-xl font-black text-slate-900 mb-2 font-black uppercase">¡Vaya! Algo salió mal</h2>
                <p className="text-slate-500 mb-8 max-w-sm">{error}</p>
                <button
                    onClick={fetchData}
                    className="px-8 py-3 bg-[#281FD0] text-white rounded-2xl font-black uppercase tracking-widest shadow-xl shadow-indigo-200"
                >
                    Reintentar
                </button>
            </div>
        );
    }

    const kpis = [
        { label: 'Total Medidas', value: data?.kpis?.total || 0, icon: List, color: 'bg-indigo-50 text-indigo-600' },
        { label: 'En Proceso', value: data?.kpis?.en_proceso || 0, icon: Clock, color: 'bg-amber-50 text-amber-600' },
        { label: 'Ratificadas', value: data?.kpis?.ratificadas || 0, icon: CheckCircle2, color: 'bg-emerald-50 text-emerald-600' },
        { label: 'Recaudo Total', value: `$${(data?.kpis?.recaudo || 0).toLocaleString()}`, icon: DollarSign, color: 'bg-blue-50 text-blue-600' },
        { label: '% Pago', value: `${data?.kpis?.efectividad_pct || 0}%`, icon: TrendingUp, color: 'bg-purple-50 text-purple-600' }
    ];

    return (
        <div className="space-y-8 pb-20">
            {/* Header Secction */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">RNMC / Medidas Gestionadas</h1>
                    <p className="text-slate-500 font-medium">Inspección de Policía y Cumplimiento de Medidas Jamundí</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 bg-white p-1 rounded-2xl shadow-sm border border-slate-200">
                        <button
                            onClick={() => setActiveTab('operativo')}
                            className={`px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${activeTab === 'operativo' ? 'bg-[#281FD0] text-white shadow-lg' : 'text-slate-500 hover:bg-slate-50'}`}
                        >
                            Operativo
                        </button>
                        <button
                            onClick={() => setActiveTab('estrategico')}
                            className={`px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${activeTab === 'estrategico' ? 'bg-[#281FD0] text-white shadow-lg' : 'text-slate-500 hover:bg-slate-50'}`}
                        >
                            Estratégico
                        </button>
                    </div>

                    <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        className="bg-[#281FD0] text-white px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest shadow-lg shadow-indigo-100 flex items-center gap-2 hover:translate-y-[-2px] transition-transform disabled:opacity-50"
                    >
                        {uploading ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}
                        Cargar Excel Manual
                    </button>
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        className="hidden"
                        accept=".xlsx,.xls"
                    />
                </div>
            </div>

            {uploadStatus && (
                <div className={`p-4 rounded-2xl border flex items-center justify-between animate-in fade-in slide-in-from-top-4 duration-300 ${uploadStatus.type === 'error' ? 'bg-red-50 border-red-100 text-red-700' :
                    uploadStatus.type === 'success' ? 'bg-emerald-50 border-emerald-100 text-emerald-700' :
                        'bg-indigo-50 border-indigo-100 text-indigo-700'
                    }`}>
                    <div className="flex items-center gap-3">
                        {uploadStatus.type === 'info' && <Loader2 className="animate-spin" size={18} />}
                        {uploadStatus.type === 'success' && <CheckCircle2 size={18} />}
                        {uploadStatus.type === 'error' && <AlertCircle size={18} />}
                        <p className="text-sm font-bold">{uploadStatus.text}</p>
                    </div>
                    <button onClick={() => setUploadStatus(null)} className="text-current opacity-50 hover:opacity-100">
                        <ArrowRight size={18} />
                    </button>
                </div>
            )}

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
                {kpis.map((kpi, idx) => {
                    const Icon = kpi.icon;
                    return (
                        <div key={idx} className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
                            <div className={`p-3 rounded-2xl w-fit mb-4 ${kpi.color}`}>
                                <Icon size={24} />
                            </div>
                            <p className="text-slate-500 text-xs font-bold uppercase tracking-widest">{kpi.label}</p>
                            <p className="text-2xl font-black text-slate-900 mt-1">{kpi.value}</p>
                        </div>
                    );
                })}
            </div>

            {activeTab === 'operativo' ? (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Filters Bar */}
                    <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 flex flex-wrap items-center gap-4">
                        <div className="flex flex-col gap-1.5 flex-1 min-w-[200px]">
                            <label className="text-[10px] font-black uppercase tracking-wider text-slate-400">Estado</label>
                            <select
                                value={filters.estado}
                                onChange={(e) => setFilters({ ...filters, estado: e.target.value })}
                                className="bg-slate-50 border-none rounded-xl px-4 py-2.5 text-sm font-bold text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500"
                            >
                                <option value="">Todos los Estados</option>
                                <option value="EN PROCESO">En Proceso</option>
                                <option value="RATIFICADA">Ratificada</option>
                                <option value="PAGADO">Pagado</option>
                            </select>
                        </div>

                        <div className="flex flex-col gap-1.5 w-32">
                            <label className="text-[10px] font-black uppercase tracking-wider text-slate-400">Días Rezagos</label>
                            <input
                                type="number"
                                placeholder="> X días"
                                className="bg-slate-50 border-none rounded-xl px-4 py-2.5 text-sm font-bold text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500"
                                value={filters.min_dias}
                                onChange={(e) => setFilters({ ...filters, min_dias: e.target.value })}
                            />
                        </div>

                        <button
                            onClick={() => setFilters({ from_date: '', to_date: '', min_dias: '', estado: '', medida: '', localidad: '' })}
                            className="mt-5 px-6 py-2.5 text-sm font-bold text-slate-500 hover:text-indigo-600 transition-colors"
                        >
                            Limpiar
                        </button>
                    </div>

                    {/* Table Backlog */}
                    <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
                        <div className="p-6 border-b border-slate-50 flex items-center justify-between">
                            <h3 className="font-black text-slate-900 uppercase tracking-tight">Backlog Operacional ({backlog.total})</h3>
                            <div className="flex items-center gap-2">
                                <span className="flex items-center gap-1.5 text-xs font-bold text-amber-600 bg-amber-50 px-3 py-1.5 rounded-full">
                                    <AlertCircle size={14} /> Rezagos detectados
                                </span>
                            </div>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead className="bg-slate-50">
                                    <tr>
                                        <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Fecha Actuación</th>
                                        <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Localidad</th>
                                        <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Medida</th>
                                        <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Estado</th>
                                        <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Días</th>
                                        <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest text-right">Valor Neto</th>
                                        <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest text-right">Pagado</th>
                                        <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest text-center">Acciones</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {(backlog?.items || []).map((row) => (
                                        <tr key={row.id} className="hover:bg-slate-50/50 transition-colors">
                                            <td className="px-6 py-4 text-sm font-black text-slate-700 whitespace-nowrap">{row.fecha_actuacion}</td>
                                            <td className="px-6 py-4 text-sm font-bold text-slate-600">{row.localidad}</td>
                                            <td className="px-6 py-4 text-sm font-bold text-slate-900">{row.medida}</td>
                                            <td className="px-6 py-4">
                                                <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase ${row.estado === 'RATIFICADA' ? 'bg-emerald-100 text-emerald-700' :
                                                    row.estado === 'EN PROCESO' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'
                                                    }`}>
                                                    {row.estado}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`text-sm font-bold ${row.dias > 30 ? 'text-red-500' : 'text-slate-600'}`}>
                                                    {row.dias}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-sm font-bold text-slate-900 text-right">${(row.valor_neto || 0).toLocaleString()}</td>
                                            <td className="px-6 py-4 text-sm font-bold text-emerald-600 text-right">${(row.valor_pagado || 0).toLocaleString()}</td>
                                            <td className="px-6 py-4 text-center">
                                                <button
                                                    onClick={() => fetchHistory(row)}
                                                    className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors inline-flex items-center gap-1.5 font-bold text-xs"
                                                >
                                                    <HistoryIcon size={16} /> Trazabilidad
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {backlog.total === 0 && (
                            <div className="p-20 text-center">
                                <Info className="mx-auto text-slate-200 mb-4" size={48} />
                                <p className="text-slate-400 font-bold">No se encontraron medidas para este filtro</p>
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Trend Chart */}
                    <div className="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 min-h-[450px]">
                        <h3 className="text-xl font-black text-slate-900 mb-8 flex items-center gap-2 italic">
                            <TrendingUp className="text-indigo-600" /> Tendencia por Periodo
                        </h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={data?.series || []}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                <XAxis dataKey="period" axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 12, fontWeight: 700 }} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 12, fontWeight: 700 }} />
                                <Tooltip
                                    contentStyle={{ borderRadius: '20px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                    itemStyle={{ fontWeight: 800 }}
                                />
                                <Line type="monotone" dataKey="total" stroke="#281FD0" strokeWidth={4} dot={{ r: 6, fill: '#281FD0', strokeWidth: 2, stroke: '#fff' }} />
                                <Line type="monotone" dataKey="recaudo" stroke="#34D399" strokeWidth={3} dot={false} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Localities Chart */}
                    <div className="bg-white p-8 rounded-[40px] shadow-sm border border-slate-100 min-h-[450px]">
                        <h3 className="text-xl font-black text-slate-900 mb-8 flex items-center gap-2 italic">
                            <MapPin className="text-indigo-600" /> Distribución por Localidad
                        </h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={data?.top_localidades || []}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                <XAxis dataKey="localidad" axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 10, fontWeight: 700 }} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 12, fontWeight: 700 }} />
                                <Tooltip
                                    contentStyle={{ borderRadius: '20px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                    itemStyle={{ fontWeight: 800 }}
                                />
                                <Bar dataKey="total" fill="#281FD0" radius={[10, 10, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* History Drawer Modal Overlay */}
            {selectedMeasure && (
                <div className="fixed inset-0 z-50 flex justify-end animate-in fade-in duration-300">
                    <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={() => setSelectedMeasure(null)}></div>
                    <div className="relative w-full max-w-xl bg-white h-full shadow-2xl p-8 flex flex-col animate-in slide-in-from-right duration-500">
                        <button
                            onClick={() => setSelectedMeasure(null)}
                            className="absolute top-6 right-6 p-2 rounded-full hover:bg-slate-100 text-slate-400"
                        >
                            <ArrowRight size={24} />
                        </button>

                        <div className="mb-10 pr-12">
                            <span className="text-[10px] font-black uppercase tracking-widest text-[#281FD0] mb-2 bg-indigo-50 px-3 py-1 rounded-full">Línea de Vida</span>
                            <h2 className="text-3xl font-black text-slate-900 mt-2">{selectedMeasure.medida}</h2>
                            <p className="text-slate-500 font-bold mt-1">Expediente: {selectedMeasure.expediente_masked}</p>
                            <p className="text-xs text-slate-400 mt-1 font-medium italic">ID Fingerprint: {selectedMeasure.event_fingerprint}</p>
                        </div>

                        <div className="flex-1 overflow-y-auto pr-4 custom-scrollbar">
                            {loadingHistory ? (
                                <div className="flex flex-col items-center justify-center h-40">
                                    <Loader2 className="animate-spin text-indigo-600 mb-2" />
                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Consultando Auditoría...</p>
                                </div>
                            ) : (
                                <div className="space-y-8 py-4 relative">
                                    <div className="absolute left-[15px] top-6 bottom-6 w-0.5 bg-slate-100"></div>

                                    {/* Timeline Start - Current Event */}
                                    <div className="relative flex gap-6 group">
                                        <div className="w-8 h-8 rounded-full bg-emerald-500 shadow-lg shadow-emerald-200 flex items-center justify-center relative z-10">
                                            <CheckCircle2 size={18} className="text-white" />
                                        </div>
                                        <div>
                                            <p className="text-[10px] font-black uppercase tracking-widest text-emerald-600">Estado Actual</p>
                                            <h4 className="text-lg font-black text-slate-900 uppercase tracking-tighter">{selectedMeasure.estado}</h4>
                                            <div className="flex items-center gap-2 mt-1">
                                                <Clock size={14} className="text-slate-400" />
                                                <p className="text-xs font-bold text-slate-400">Verificado Hoy</p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Historical Events */}
                                    {history?.history?.map((h, i) => (
                                        <div key={i} className="relative flex gap-6 group">
                                            <div className="w-8 h-8 rounded-full bg-white border-2 border-slate-200 flex items-center justify-center relative z-10 group-hover:border-indigo-500 transition-colors">
                                                <HistoryIcon size={16} className="text-slate-400 group-hover:text-indigo-600" />
                                            </div>
                                            <div className="flex-1">
                                                <div className="flex items-center justify-between">
                                                    <h4 className="font-black text-slate-800 uppercase tracking-tighter">{h.estado_anterior}</h4>
                                                    <span className="text-[10px] bg-slate-100 px-2 py-0.5 rounded text-slate-500 font-bold">{h.changed_at.split('T')[0]}</span>
                                                </div>
                                                <p className="text-xs font-bold text-slate-500 mt-1">Tránsito a {h.estado_nuevo}</p>
                                                <div className="mt-3 p-3 bg-slate-50 rounded-2xl text-[10px] space-y-1">
                                                    <p className="text-slate-400 font-bold">FUERTE: <span className="text-slate-600">{h.fuente_archivo}</span></p>
                                                    <p className="text-slate-400 font-bold">INGESTION ID: <span className="text-slate-600">{h.ingestion_id}</span></p>
                                                </div>
                                            </div>
                                        </div>
                                    ))}

                                    {(!history || history.history.length === 0) && (
                                        <div className="relative flex gap-6 opacity-60">
                                            <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center z-10">
                                                <Info size={16} className="text-slate-400" />
                                            </div>
                                            <p className="text-xs font-bold text-slate-400 py-2 uppercase tracking-widest italic">No hay cambios de estado registrados</p>
                                        </div>
                                    )}

                                    {/* Document Info */}
                                    <div className="mt-12 p-6 rounded-3xl bg-indigo-50 border border-indigo-100">
                                        <div className="flex items-center gap-3 mb-4">
                                            <FileText className="text-indigo-600" />
                                            <h4 className="font-black text-indigo-900 uppercase text-xs tracking-widest">Resumen de Medida</h4>
                                        </div>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <p className="text-[10px] font-black text-indigo-300 uppercase">Valor Neto</p>
                                                <p className="text-lg font-black text-indigo-900">${(selectedMeasure.valor_neto || 0).toLocaleString()}</p>
                                            </div>
                                            <div>
                                                <p className="text-[10px] font-black text-indigo-300 uppercase">Valor Pagado</p>
                                                <p className="text-lg font-black text-indigo-900">${(selectedMeasure.valor_pagado || 0).toLocaleString()}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        <button
                            className="mt-8 w-full py-4 bg-[#281FD0] text-white rounded-2xl font-black uppercase tracking-widest shadow-xl shadow-indigo-200 flex items-center justify-center gap-2 hover:translate-y-[-2px] transition-transform"
                        >
                            <Download size={20} /> Descargar Ficha Técnica
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default RNMCModule;
