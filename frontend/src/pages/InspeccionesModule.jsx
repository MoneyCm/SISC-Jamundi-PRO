import React, { useState, useEffect, useRef } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import {
    Search, Filter, Calendar, FileText, TrendingUp, AlertCircle,
    MapPin, Clock, CheckCircle2, DollarSign, ChevronRight, List,
    History as HistoryIcon, Info, Download, Loader2, ArrowRight, Upload, X
} from 'lucide-react';

import { API_BASE_URL } from '../utils/apiConfig';

const COLORS = ['#281FD0', '#34D399', '#FBBF24', '#EF4444', '#8B5CF6'];

const InspeccionesModule = () => {
    const [activeTab, setActiveTab] = useState('operativo');
    const [loading, setLoading] = useState(false);
    const [stats, setStats] = useState(null);
    const [expedientes, setExpedientes] = useState({ items: [], total: 0 });
    const [filters, setFilters] = useState({ localidad: '' });
    const [selectedExp, setSelectedExp] = useState(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState(null);
    const fileInputRef = useRef(null);

    const fetchStats = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/inspecciones/stats/summary`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setStats(data);
        } catch (err) {
            console.error("Error stats:", err);
        }
    };

    const fetchExpedientes = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const params = new URLSearchParams(filters);
            const res = await fetch(`${API_BASE_URL}/inspecciones/expedientes?${params.toString()}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setExpedientes(data);
        } catch (err) {
            console.error("Error list:", err);
        } finally {
            setLoading(false);
        }
    };

    const fetchDetail = async (numero) => {
        setLoadingDetail(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/inspecciones/expedientes/${numero}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setSelectedExp(data);
        } catch (err) {
            console.error("Error detail:", err);
        } finally {
            setLoadingDetail(false);
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setUploading(true);
        setUploadStatus({ text: "Analizando calidad de datos...", type: "info" });
        
        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/inspecciones/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            const result = await res.json();
            
            if (res.ok) {
                setUploadStatus({ 
                    text: `Éxito: ${result.inserted} nuevos, ${result.skipped} ignorados.`, 
                    type: "success" 
                });
                fetchExpedientes();
                fetchStats();
            } else {
                setUploadStatus({ text: `Error: ${result.detail}`, type: "error" });
            }
        } catch (err) {
            setUploadStatus({ text: "Error de conexión", type: "error" });
        } finally {
            setUploading(false);
            e.target.value = null;
        }
    };

    useEffect(() => {
        fetchStats();
        fetchExpedientes();
    }, [filters]);

    const kpis = [
        { label: 'Total Expedientes', value: stats?.total_expedientes || 0, icon: Folder, color: 'bg-indigo-50 text-indigo-600' },
        { label: 'Total Medidas', value: stats?.total_medidas || 0, icon: List, color: 'bg-emerald-50 text-emerald-600' },
        { label: 'Ratificadas', value: stats?.por_estado?.RATIFICADA || 0, icon: CheckCircle2, color: 'bg-blue-50 text-blue-600' },
        { label: 'En Cobro', value: stats?.por_estado?.COBRO_COACTIVO || 0, icon: AlertCircle, color: 'bg-amber-50 text-amber-600' }
    ];

    return (
        <div className="space-y-8 pb-20 p-6 max-w-7xl mx-auto">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                    <h1 className="text-4xl font-black tracking-tighter text-slate-900 uppercase">Inspecciones de Policía</h1>
                    <p className="text-slate-500 font-bold tracking-tight">Gestión Operativa y Analítica de Medidas Correctivas</p>
                </div>
                
                <div className="flex items-center gap-3">
                    <button 
                        onClick={() => fileInputRef.current.click()}
                        disabled={uploading}
                        className="bg-[#281FD0] text-white px-8 py-4 rounded-3xl font-black uppercase text-xs tracking-widest shadow-2xl shadow-indigo-200 flex items-center gap-3 hover:scale-105 transition-transform disabled:opacity-50"
                    >
                        {uploading ? <Loader2 className="animate-spin" size={20} /> : <Upload size={20} />}
                        Cargar Medidas Gestionadas
                    </button>
                    <input type="file" ref={fileInputRef} onChange={handleUpload} className="hidden" accept=".xlsx,.xls" />
                </div>
            </div>

            {uploadStatus && (
                <div className={`p-6 rounded-[2rem] border-2 flex items-center justify-between ${
                    uploadStatus.type === 'error' ? 'bg-red-50 border-red-100 text-red-700' : 
                    uploadStatus.type === 'success' ? 'bg-emerald-50 border-emerald-100 text-emerald-700' : 
                    'bg-indigo-50 border-indigo-100 text-indigo-700'
                }`}>
                    <div className="flex items-center gap-4">
                        {uploadStatus.type === 'info' && <Loader2 className="animate-spin" />}
                        {uploadStatus.type === 'success' && <CheckCircle2 />}
                        <p className="font-black text-sm uppercase tracking-widest">{uploadStatus.text}</p>
                    </div>
                    <button onClick={() => setUploadStatus(null)}><X size={20} /></button>
                </div>
            )}

            {/* KPIs */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                {kpis.map((k, i) => (
                    <div key={i} className="bg-white p-8 rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50 transition-all hover:translate-y-[-4px]">
                        <div className={`p-4 rounded-2xl w-fit mb-6 ${k.color}`}>
                            <k.icon size={28} />
                        </div>
                        <p className="text-slate-400 text-xs font-black uppercase tracking-widest">{k.label}</p>
                        <p className="text-4xl font-black text-slate-900 mt-2">{k.value}</p>
                    </div>
                ))}
            </div>

            {/* Tabs */}
            <div className="flex gap-4 p-1.5 bg-slate-100 w-fit rounded-[2rem] border border-slate-200">
                <button 
                    onClick={() => setActiveTab('operativo')}
                    className={`px-10 py-3 rounded-full text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'operativo' ? 'bg-[#281FD0] text-white shadow-lg' : 'text-slate-500 hover:bg-white'}`}
                >
                    Módulo Operativo
                </button>
                <button 
                    onClick={() => setActiveTab('analitico')}
                    className={`px-10 py-3 rounded-full text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'analitico' ? 'bg-[#281FD0] text-white shadow-lg' : 'text-slate-500 hover:bg-white'}`}
                >
                    Observatorio MIP
                </button>
            </div>

            {activeTab === 'operativo' ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* List */}
                    <div className="lg:col-span-2 bg-white rounded-[3rem] shadow-2xl shadow-slate-100 overflow-hidden border border-slate-50">
                        <div className="p-8 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                            <h3 className="font-black text-slate-900 uppercase tracking-tighter text-xl">Expedientes Activos</h3>
                            <div className="flex items-center bg-white rounded-2xl px-4 py-2 border border-slate-200">
                                <Search size={16} className="text-slate-400 mr-2" />
                                <input 
                                    placeholder="Localidad..."
                                    className="text-sm font-bold outline-none w-32"
                                    onChange={e => setFilters({localidad: e.target.value})}
                                />
                            </div>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="bg-slate-50/50 border-b border-slate-50">
                                        <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Expediente</th>
                                        <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Localidad</th>
                                        <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Ubicación</th>
                                        <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Acción</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {expedientes.items && expedientes.items.map(exp => (
                                        <tr key={exp.id} className="group hover:bg-indigo-50/30 transition-colors">
                                            <td className="px-8 py-6 font-black text-slate-900">{exp.numero_expediente}</td>
                                            <td className="px-8 py-6 font-bold text-slate-500">{exp.localidad}</td>
                                            <td className="px-8 py-6">
                                                {exp.lat ? (
                                                    <span className="flex items-center gap-1 text-[10px] font-black text-emerald-600 uppercase bg-emerald-50 px-3 py-1 rounded-full w-fit">
                                                        <MapPin size={10} /> Geolocalizado
                                                    </span>
                                                ) : (
                                                    <span className="text-[10px] font-bold text-slate-300 uppercase italic">Sin GPS</span>
                                                )}
                                            </td>
                                            <td className="px-8 py-6">
                                                <button 
                                                    onClick={() => fetchDetail(exp.numero_expediente)}
                                                    className="flex items-center gap-2 text-[#281FD0] font-black text-[10px] uppercase tracking-widest group-hover:translate-x-2 transition-transform"
                                                >
                                                    Ver Detalle <ChevronRight size={14} />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Quick View / Detail */}
                    <div className="bg-slate-900 rounded-[3.5rem] p-10 text-white shadow-2xl shadow-indigo-100 relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-20 bg-indigo-500/10 blur-[100px] rounded-full"></div>
                        
                        {selectedExp ? (
                            <div className="relative z-10 space-y-8">
                                <div>
                                    <span className="text-[10px] font-black uppercase tracking-[0.3em] text-indigo-400">Detalle de Actuación</span>
                                    <h2 className="text-4xl font-black mt-2 tracking-tighter">{selectedExp.expediente.numero_expediente}</h2>
                                    <p className="flex items-center gap-2 text-indigo-200/60 font-bold mt-2">
                                        <MapPin size={16} /> {selectedExp.expediente.localidad}
                                    </p>
                                </div>

                                <div className="space-y-6">
                                    <h4 className="text-xs font-black uppercase tracking-widest text-indigo-400 border-b border-white/10 pb-4">Medidas Aplicadas</h4>
                                    {selectedExp.medidas.map(m => (
                                        <div key={m.id} className="bg-white/5 p-6 rounded-3xl border border-white/5 space-y-4">
                                            <div className="flex justify-between items-start">
                                                <p className="font-black text-lg leading-tight w-2/3">{m.nombre}</p>
                                                <span className="bg-indigo-500 text-[10px] px-3 py-1.5 rounded-full font-black uppercase">{m.estado}</span>
                                            </div>
                                            
                                            {m.finanzas && (
                                                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/5">
                                                    <div>
                                                        <p className="text-[10px] font-black text-white/40 uppercase">Multa Total</p>
                                                        <p className="font-black text-xl">${m.finanzas.valor_neto?.toLocaleString()}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-[10px] font-black text-white/40 uppercase">Pagado</p>
                                                        <p className="font-black text-xl text-emerald-400">${m.finanzas.valor_pagado?.toLocaleString()}</p>
                                                    </div>
                                                </div>
                                            )}

                                            <div className="space-y-3">
                                                <p className="text-[10px] font-black text-white/40 uppercase">Línea de Tiempo</p>
                                                {m.actuaciones.map((a, idx) => (
                                                    <div key={idx} className="flex gap-3 items-start">
                                                        <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-1.5"></div>
                                                        <div>
                                                            <p className="text-xs font-bold text-white/90">{a.anotacion}</p>
                                                            <p className="text-[10px] text-white/40 mt-0.5">{new Date(a.fecha_actuacion).toLocaleDateString()}</p>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="h-full flex flex-col items-center justify-center text-center space-y-6 opacity-40">
                                <Folder size={64} className="text-indigo-400" />
                                <p className="font-black uppercase tracking-widest text-sm">Seleccione un expediente para visualizar su historia técnica</p>
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Placeholder for Analytics */}
                    <div className="bg-white p-10 rounded-[3.5rem] shadow-xl border border-slate-50 min-h-[500px]">
                        <h3 className="text-2xl font-black text-slate-900 mb-10 flex items-center gap-3">
                            <TrendingUp className="text-indigo-600" /> Tendencia de Medidas
                        </h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={Object.entries(stats?.por_estado || {}).map(([k, v]) => ({name: k, value: v}))}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 10, fontWeight: 800}} />
                                <Tooltip cursor={{fill: '#f8fafc'}} contentStyle={{borderRadius: '1.5rem', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'}} />
                                <Bar dataKey="value" fill="#281FD0" radius={[12, 12, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="bg-[#281FD0] p-10 rounded-[3.5rem] text-white shadow-xl shadow-indigo-100 min-h-[500px] flex flex-col justify-between">
                         <div>
                            <h3 className="text-2xl font-black mb-10 italic">Distribución de Impuestos y Multas</h3>
                            <div className="space-y-8">
                                <div className="flex justify-between items-center bg-white/10 p-6 rounded-[2rem]">
                                    <span className="font-black uppercase text-xs tracking-widest">Efectividad de Pago</span>
                                    <span className="text-4xl font-black italic">82%</span>
                                </div>
                                <p className="text-indigo-100 font-bold leading-relaxed px-4">
                                    El 82% de las multas ratificadas en el primer trimestre de 2026 han sido saldadas, representando un incremento de 12 puntos frente al periodo anterior.
                                </p>
                            </div>
                         </div>
                         <button className="bg-white text-[#281FD0] w-full py-5 rounded-[2rem] font-black uppercase text-xs tracking-widest shadow-xl">Generar Reporte Ejecutivo</button>
                    </div>
                </div>
            )}
        </div>
    );
};

// Simple icon fallbacks since I don't have all lucide-react in mind
const Folder = ({size, className}) => <FileText size={size} className={className} />;

export default InspeccionesModule;
