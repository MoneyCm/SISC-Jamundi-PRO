import React, { useState, useRef, useEffect } from 'react';
import { Loader2, TrendingUp, Upload, Activity, BarChart2 } from "lucide-react";
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
    Line
} from 'recharts';

import { API_BASE_URL } from '../utils/apiConfig';

const Card = ({ children, className }) => <div className={`bg-white rounded-xl shadow-sm border border-slate-200 ${className}`}>{children}</div>;
const CardHeader = ({ children, className }) => <div className={`p-6 pb-2 ${className}`}>{children}</div>;
const CardTitle = ({ children, className }) => <h3 className={`font-semibold leading-none tracking-tight ${className}`}>{children}</h3>;
const CardContent = ({ children, className }) => <div className={`p-6 pt-0 ${className}`}>{children}</div>;

const Button = ({ children, variant = "default", className, ...props }) => {
    const baseStyles = "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 h-9 px-4 py-2";
    const variants = {
        default: "bg-indigo-600 text-white hover:bg-indigo-700 shadow",
        outline: "border border-input bg-background shadow-sm hover:bg-slate-100 hover:text-slate-900"
    };
    return <button className={`${baseStyles} ${variants[variant] || variants.default} ${className}`} {...props}>{children}</button>;
};

const IntelligenceModule = () => {
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [ingestStatus, setIngestStatus] = useState(null);
    const [selectedYear, setSelectedYear] = useState(2025);
    const [selectedMunicipio, setSelectedMunicipio] = useState("JAMUNDI");
    const [stats, setStats] = useState({ summary: [], trend: [] });

    const fileInputRef = useRef(null);

    const fetchStats = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const url = `${API_BASE_URL}/api/intelligence/stats?municipio=${selectedMunicipio}&anio=${selectedYear}`;
            console.log("Fetching stats from:", url);

            const response = await fetch(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const data = await response.json();
                console.log("Stats received:", data);
                setStats(data);
            } else {
                console.warn("Stats fetch failed with status:", response.status);
            }
        } catch (error) {
            console.error("Error fetching stats:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStats();
    }, [selectedMunicipio, selectedYear]);

    const handleFileChange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setUploading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('token');
            const url = `${API_BASE_URL}/api/intelligence/upload`;
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                setIngestStatus(`Éxito: ${data.message} (${data.records_inserted} registros)`);
                fetchStats();
            } else {
                setIngestStatus(`Error: ${data.detail || 'Fallo en la carga'}`);
            }
        } catch (error) {
            console.error("Error uploading file:", error);
            setIngestStatus("Error de conexión al cargar el archivo.");
        } finally {
            setUploading(false);
            event.target.value = null;
        }
    };

    const monthNames = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const trendData = (stats.trend || []).map(item => ({
        ...item,
        name: monthNames[item.mes - 1] || item.mes
    }));

    return (
        <div className="p-6 space-y-6 bg-slate-50 min-h-screen">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-slate-800 tracking-tight">Inteligencia Estratégica Nacional</h1>
                    <p className="text-slate-500 mt-1">Comparativa estratégica con datos oficiales de MinDefensa</p>
                </div>
                <Button
                    variant="default"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    className="bg-indigo-600 hover:bg-indigo-700 shadow-lg border-none"
                >
                    {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                    Cargar Excel Nacional
                </Button>
                <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept=".xlsx,.xls" />
            </div>

            {ingestStatus && (
                <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-md animate-in fade-in slide-in-from-top-4 duration-300">
                    <div className="flex">
                        <div className="flex-shrink-0">
                            <Activity className="h-5 w-5 text-blue-400" />
                        </div>
                        <div className="ml-3">
                            <p className="text-sm text-blue-700">{ingestStatus}</p>
                        </div>
                        <button onClick={() => setIngestStatus(null)} className="ml-auto text-blue-400 hover:text-blue-600">×</button>
                    </div>
                </div>
            )}

            {/* Filtros */}
            <Card className="border-none shadow-sm bg-white">
                <CardContent className="p-4 flex gap-4 items-center">
                    <div className="flex-1">
                        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1 block">Municipio Objetivo</label>
                        <select
                            className="w-full p-2 border border-slate-200 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                            value={selectedMunicipio}
                            onChange={(e) => setSelectedMunicipio(e.target.value)}
                        >
                            <option value="JAMUNDI">JAMUNDÍ (VALLE)</option>
                            <option value="CALI">CALI (VALLE)</option>
                            <option value="BOGOTA">BOGOTÁ, D.C.</option>
                            <option value="MEDELLIN">MEDELLÍN (ANTIOQUIA)</option>
                        </select>
                    </div>
                    <div className="w-48">
                        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1 block">Año de Análisis</label>
                        <select
                            className="w-full p-2 border border-slate-200 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                            value={selectedYear}
                            onChange={(e) => setSelectedYear(Number(e.target.value))}
                        >
                            <option value={2025}>2025</option>
                            <option value={2024}>2024</option>
                            <option value={2023}>2023</option>
                        </select>
                    </div>
                    <Button variant="outline" onClick={fetchStats} className="mt-5">
                        <Loader2 className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                </CardContent>
            </Card>

            {/* KPIs */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {stats.summary?.map((item, idx) => (
                    <Card key={idx} className="hover:shadow-md transition-shadow">
                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                            <CardTitle className="text-sm font-medium text-slate-600">{item.delito} (vs Nacional)</CardTitle>
                            <TrendingUp className={`h-4 w-4 ${item.local > item.nacional_avg ? 'text-red-500' : 'text-emerald-500'}`} />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-slate-800">
                                {item.local}
                                <span className="text-xs text-slate-400 font-normal ml-2">/ {item.nacional_avg} avg</span>
                            </div>
                            <p className={`text-xs mt-1 flex items-center ${item.local > item.nacional_avg ? 'text-red-600' : 'text-emerald-600'}`}>
                                <span className="font-bold mr-1">
                                    {item.nacional_avg > 0 ? (((item.local - item.nacional_avg) / item.nacional_avg) * 100).toFixed(1) : 0}%
                                </span>
                                {item.local > item.nacional_avg ? 'más alto' : 'más bajo'} que el promedio
                            </p>
                        </CardContent>
                    </Card>
                ))}
                {(!stats.summary || stats.summary.length === 0) && !loading && (
                    <Card className="col-span-3 p-10 text-center text-slate-400 border-dashed border-2">
                        No se encontraron registros para los filtros seleccionados. Intenta cargar un archivo Excel.
                    </Card>
                )}
            </div>

            {/* Gráficas Principales */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-6">
                <Card className="p-6">
                    <CardTitle className="text-lg text-slate-800 mb-6 flex items-center">
                        <BarChart2 className="mr-2 h-5 w-5 text-indigo-500" />
                        Comparativa de Incidencias
                    </CardTitle>
                    <div className="h-[300px] min-h-[300px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={stats.summary || []} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="delito" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} interval={0} angle={-15} textAnchor="end" />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                                <Tooltip
                                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                    cursor={{ fill: '#f8fafc' }}
                                />
                                <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />
                                <Bar name={`${selectedMunicipio} (Local)`} dataKey="local" fill="#4f46e5" radius={[4, 4, 0, 0]} barSize={40} />
                                <Bar name="Promedio Nacional" dataKey="nacional_avg" fill="#cbd5e1" radius={[4, 4, 0, 0]} barSize={40} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </Card>

                <Card className="p-6">
                    <CardTitle className="text-lg text-slate-800 mb-6 flex items-center">
                        <TrendingUp className="mr-2 h-5 w-5 text-emerald-500" />
                        Tendencia Mensual {selectedYear}
                    </CardTitle>
                    <div className="h-[300px] min-h-[300px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={trendData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                                <Tooltip
                                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="cantidad"
                                    stroke="#10b981"
                                    strokeWidth={3}
                                    dot={{ r: 4, fill: '#10b981', strokeWidth: 2, stroke: '#fff' }}
                                    activeDot={{ r: 6, strokeWidth: 0 }}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>

            <div className="bg-emerald-50 border border-emerald-100 p-4 rounded-xl text-center">
                <p className="text-emerald-600 text-sm font-medium">
                    Analítica estratégica activada utilizando Recharts v3.
                </p>
            </div>
        </div>
    );
};

export default IntelligenceModule;
