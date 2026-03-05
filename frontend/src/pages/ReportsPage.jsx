import React, { useState, useEffect } from 'react';
import {
    Download, Calendar, Filter, FileText, Search, Clock,
    ShieldCheck, AlertCircle, Eye, Copy, ExternalLink, RefreshCw, Database, Globe, Shield
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const ReportsPage = () => {
    const [loading, setLoading] = useState(false);
    const [fuente, setFuente] = useState('MINDEFENSA');
    const [fechaInicio, setFechaInicio] = useState('2026-01-01');
    const [fechaFin, setFechaFin] = useState(new Date().toISOString().split('T')[0]);

    const handleGenerate = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            // Forzar URL absoluta en local si es necesario
            let baseUrl = API_BASE_URL;
            if (window.location.hostname === 'localhost' && !baseUrl.startsWith('http')) {
                baseUrl = 'http://localhost:8000/api';
            }
            const url = `${baseUrl}/reportes/generar-boletin?fuente=${fuente}&fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}&token=${token}`;
            
            const response = await fetch(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (!response.ok) throw new Error("No se pudo conectar con el servidor de reportes");
            
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `Reporte_SISC_${fuente}_${fechaFin}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (err) {
            alert(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-6 space-y-8 bg-slate-50 min-h-screen">
            {/* Header */}
            <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-200">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                    <div>
                        <h1 className="text-4xl font-black text-slate-800 tracking-tighter uppercase leading-none">Generador de Boletines</h1>
                        <p className="text-slate-500 font-medium mt-2">Cree reportes institucionales personalizados con fuentes oficiales.</p>
                    </div>
                    <div className="p-4 bg-indigo-50 rounded-2xl">
                        <FileText className="text-indigo-600" size={40} />
                    </div>
                </div>
            </div>

            {/* Configurador de Reporte */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-white p-8 rounded-3xl shadow-lg border border-slate-100 space-y-8">
                        <div>
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4 block">1. Seleccionar Fuente de Información</label>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {[
                                    { id: 'MINDEFENSA', label: 'Ministerio de Defensa', icon: Globe, desc: 'Datos consolidados e históricos' },
                                    { id: 'POLICIA_PORTAL', label: 'Portal Policía', icon: Shield, desc: 'Estadísticas SIEDCO (Datos Abiertos)' },
                                    { id: 'POLICIA_SEMANAL', label: 'Boletín Semanal', icon: Calendar, desc: 'Archivo compartido por correo' },
                                ].map(f => (
                                    <button
                                        key={f.id}
                                        onClick={() => setFuente(f.id)}
                                        className={`p-6 rounded-2xl border-2 transition-all text-left flex flex-col gap-3 group ${fuente === f.id ? 'border-indigo-600 bg-indigo-50/50' : 'border-slate-100 hover:border-slate-200 bg-white'}`}
                                    >
                                        <f.icon className={fuente === f.id ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-600'} size={24} />
                                        <div>
                                            <div className={`font-black text-sm uppercase tracking-tight ${fuente === f.id ? 'text-indigo-900' : 'text-slate-700'}`}>{f.label}</div>
                                            <p className="text-[10px] text-slate-400 font-bold leading-tight mt-1">{f.desc}</p>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4 border-t border-slate-50">
                            <div>
                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-3 block">2. Rango de Fecha (Inicio)</label>
                                <div className="relative">
                                    <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                    <input
                                        type="date"
                                        value={fechaInicio}
                                        onChange={(e) => setFechaInicio(e.target.value)}
                                        className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-black text-slate-700 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none transition-all"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-3 block">3. Rango de Fecha (Fin / Corte)</label>
                                <div className="relative">
                                    <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                    <input
                                        type="date"
                                        value={fechaFin}
                                        onChange={(e) => setFechaFin(e.target.value)}
                                        className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-black text-slate-700 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none transition-all"
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="space-y-6">
                    <div className="bg-[#281FD0] text-white p-8 rounded-3xl shadow-xl shadow-indigo-200 space-y-6">
                        <div className="p-3 bg-white/10 rounded-2xl inline-block">
                            <ShieldCheck size={32} />
                        </div>
                        <div>
                            <h3 className="text-xl font-black uppercase tracking-tight">Listo para Generar</h3>
                            <p className="text-white/70 text-sm font-medium mt-2 leading-relaxed">
                                El boletín incluirá la identidad visual de Jamundí y las cifras oficiales filtradas por el periodo seleccionado.
                            </p>
                        </div>
                        <button
                            onClick={handleGenerate}
                            disabled={loading}
                            className={`w-full py-5 rounded-2xl font-black text-sm uppercase tracking-[0.2em] flex items-center justify-center gap-3 transition-all shadow-2xl ${loading ? 'bg-indigo-400 cursor-wait' : 'bg-[#FFE000] text-[#1A1A2E] hover:scale-[1.02] active:scale-95'}`}
                        >
                            {loading ? <RefreshCw className="animate-spin" size={20} /> : <Download size={20} />}
                            {loading ? 'Procesando...' : 'Generar Boletín'}
                        </button>
                    </div>

                    <div className="bg-white p-6 rounded-3xl border border-slate-200">
                        <div className="flex items-center gap-3 text-slate-400 mb-4">
                            <Clock size={18} />
                            <span className="text-[10px] font-black uppercase tracking-widest">Estado de los Datos</span>
                        </div>
                        <div className="space-y-3">
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-slate-500 font-bold">Mindefensa:</span>
                                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-md font-black text-[9px]">AL DÍA</span>
                            </div>
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-slate-500 font-bold">Semanal:</span>
                                <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-md font-black text-[9px]">PENDIENTE</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ReportsPage;
