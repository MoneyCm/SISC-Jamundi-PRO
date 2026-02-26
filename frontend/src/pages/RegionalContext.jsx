import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts';
import { MapPin, TrendingUp, ShieldAlert, Layers, ExternalLink, Activity } from "lucide-react";
import { API_BASE_URL } from '../utils/apiConfig';

// Reusable Basic UI Components since shadcn/ui is not present
const Card = ({ children, className = "" }) => (
    <div className={`bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden ${className}`}>
        {children}
    </div>
);

const CardHeader = ({ children, className = "" }) => (
    <div className={`p-5 border-b border-slate-50 ${className}`}>
        {children}
    </div>
);

const CardTitle = ({ children, className = "" }) => (
    <h3 className={`font-black text-slate-800 tracking-tight flex items-center gap-2 ${className}`}>
        {children}
    </h3>
);

const CardContent = ({ children, className = "" }) => (
    <div className={`p-6 ${className}`}>
        {children}
    </div>
);

const RegionalContext = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const token = localStorage.getItem('token');
                const response = await fetch(`${API_BASE_URL}/intelligence/territorial-context?fuente=ASPERSION`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (response.ok) {
                    const result = await response.json();
                    setData(result);
                }
            } catch (error) {
                console.error("Error fetching regional context:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return (
        <div className="flex flex-col items-center justify-center h-screen bg-slate-50">
            <Activity className="w-12 h-12 text-indigo-600 animate-spin mb-4" />
            <p className="text-slate-500 font-bold uppercase tracking-widest text-xs tracking-tighter">Cargando inteligencia regional...</p>
        </div>
    );

    if (!data || !data.top_municipios.length) {
        return (
            <div className="p-12 text-center bg-white rounded-3xl border-2 border-dashed border-slate-200 m-8 shadow-sm">
                <ShieldAlert className="mx-auto h-16 w-16 text-slate-200 mb-6" />
                <h2 className="text-2xl font-black text-slate-800 uppercase tracking-tight">Sin datos de contexto regional</h2>
                <p className="text-slate-500 mt-2 font-medium">Cargue archivos de 'Aspersión' en el módulo de Inteligencia para activar este panel táctico.</p>
                <div className="mt-8 flex justify-center">
                    <span className="bg-slate-100 text-slate-400 px-4 py-2 rounded-xl text-xs font-black tracking-widest uppercase">Esperando Ingesta ...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-8 bg-slate-50 min-h-screen animate-fade-in">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-4xl font-black text-slate-900 tracking-tighter flex items-center gap-3">
                        <Layers className="text-indigo-600 w-10 h-10" />
                        Contexto Territorial Regional
                    </h1>
                    <div className="flex items-center gap-2 mt-1">
                        <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                        <p className="text-slate-500 font-bold uppercase text-[10px] tracking-[0.2em]">Variable Externa: Dinámica de Aspersión (Glifosato) - Valle del Cauca</p>
                    </div>
                </div>
                <div className="bg-indigo-600 text-white px-6 py-2 rounded-2xl text-xs font-black shadow-xl shadow-indigo-200 uppercase tracking-widest">
                    VALLE DEL CAUCA
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <Card className="hover:shadow-lg transition-all duration-300">
                    <CardHeader className="pb-2 border-none">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Área Total Intervenida</span>
                    </CardHeader>
                    <CardContent className="pt-0">
                        <div className="text-4xl font-black text-slate-900 tracking-tighter">
                            {data.top_municipios.reduce((acc, curr) => acc + curr.total, 0).toLocaleString()} <span className="text-sm font-bold text-slate-400 uppercase">ha</span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-2 text-emerald-600 font-black text-[10px] uppercase bg-emerald-50 w-fit px-2 py-1 rounded-lg">
                            <TrendingUp size={12} /> Acumulado Histórico Regional
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-[#281FD0] text-white border-none shadow-xl shadow-indigo-100 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:scale-110 transition-transform duration-500">
                        <MapPin size={100} />
                    </div>
                    <CardHeader className="pb-2 border-none">
                        <span className="text-[10px] font-black text-indigo-300 uppercase tracking-widest">Foco Crítico Regional</span>
                    </CardHeader>
                    <CardContent className="relative z-10 pt-0">
                        <div className="text-3xl font-black tracking-tighter group-hover:translate-x-1 transition-transform">{data.top_municipios[0]?.municipio || 'N/A'}</div>
                        <p className="text-[10px] text-white/60 mt-1 uppercase font-black tracking-widest">Máxima concentración detectada</p>
                    </CardContent>
                </Card>

                <Card className="hover:shadow-lg transition-all duration-300">
                    <CardHeader className="pb-2 border-none">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Fuentes Activas</span>
                    </CardHeader>
                    <CardContent className="pt-0">
                        <div className="text-4xl font-black text-slate-900 tracking-tighter">01</div>
                        <div className="text-[10px] text-indigo-600 font-black mt-2 uppercase">ASPERSIÓN GLIFOSATO</div>
                    </CardContent>
                </Card>

                <Card className="hover:shadow-lg transition-all duration-300 bg-emerald-50 border-emerald-100">
                    <CardHeader className="pb-2 border-none">
                        <span className="text-[10px] font-black text-emerald-600 uppercase tracking-widest">Estado del Panel</span>
                    </CardHeader>
                    <CardContent className="pt-0">
                        <div className="text-4xl font-black text-emerald-700 tracking-tighter">ACTIVO</div>
                        <div className="text-[10px] text-emerald-600 font-black mt-2 uppercase">SINCRONIZADO CON DB</div>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <Card className="lg:col-span-2 border-none shadow-sm h-[450px] flex flex-col">
                    <CardHeader>
                        <CardTitle>
                            <TrendingUp className="text-indigo-600" size={20} />
                            Tendencia Histórica de Área Afectada (Valle)
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0 pt-8">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={data.trend} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="anio" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 'bold' }} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 'bold' }} />
                                <Tooltip
                                    contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }}
                                    itemStyle={{ fontWeight: '800', fontSize: '12px' }}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="total"
                                    stroke="#4f46e5"
                                    strokeWidth={4}
                                    dot={{ r: 4, fill: '#4f46e5', strokeWidth: 2, stroke: '#fff' }}
                                    activeDot={{ r: 7, strokeWidth: 0, fill: '#4f46e5' }}
                                    name="Hectáreas"
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                <Card className="h-[450px] flex flex-col">
                    <CardHeader>
                        <CardTitle>Top Municipios Valle (ha)</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 overflow-y-auto space-y-4 pt-4 custom-scrollbar">
                        {data.top_municipios.slice(0, 10).map((m, i) => (
                            <div key={i} className="flex items-center justify-between group p-2 hover:bg-slate-50 rounded-xl transition-all">
                                <div className="flex items-center gap-4">
                                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-black transition-colors ${i === 0 ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                                        {i + 1}
                                    </div>
                                    <span className="text-xs font-black text-slate-700 uppercase tracking-tight">{m.municipio}</span>
                                </div>
                                <div className="text-sm font-black text-slate-900">{m.total.toLocaleString(undefined, { minimumFractionDigits: 1 })}</div>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            </div>

            <div className="bg-slate-900 border-none shadow-2xl rounded-3xl p-8 relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-8 opacity-5">
                    <ShieldAlert size={140} className="text-white" />
                </div>
                <div className="flex flex-col md:flex-row items-start gap-8 relative z-10">
                    <div className="bg-indigo-500/20 p-4 rounded-2xl text-indigo-400 border border-indigo-500/30">
                        <ShieldAlert size={32} />
                    </div>
                    <div className="flex-1">
                        <h3 className="font-black text-white tracking-widest uppercase text-xs mb-3 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
                            Análisis Estratégico SISC
                        </h3>
                        <p className="text-slate-300 text-sm leading-relaxed font-medium">
                            Los datos regionales de aspersión en el Valle del Cauca actúan como <strong className="text-indigo-400 font-black">factores de empuje o atracción</strong> para grupos armados y economías ilícitas.
                            Aunque el casco urbano de Jamundí pueda presentar cero registros directos, la presión táctica en nodos vecinos como <strong className="text-white">Dagua</strong> o <strong className="text-white">Buenaventura</strong> influye directamente
                            en los corredores de movilidad hacia la zona rural alta del municipio.
                        </p>
                        <div className="mt-6 flex items-center gap-4">
                            <div className="text-[10px] font-black py-1 px-3 bg-white/5 border border-white/10 rounded-lg text-slate-400 uppercase tracking-widest">
                                Correlación: Desplazamiento de Dinámicas Criminales
                            </div>
                            <div className="text-[10px] font-black py-1 px-3 bg-white/5 border border-white/10 rounded-lg text-slate-400 uppercase tracking-widest">
                                Prioridad: Inteligencia Territorial
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default RegionalContext;
