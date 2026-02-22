import React, { useState, useRef, useEffect } from 'react';
import { Loader2, TrendingUp, Upload, Activity, BarChart2, Clock, ArrowUpRight, Brain } from "lucide-react";
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
    const [municipios, setMunicipios] = useState([]);
    const [stats, setStats] = useState({ summary: [], trend: [] });
    const [insight, setInsight] = useState(null);
    const [insightLoading, setInsightLoading] = useState(false);
    const [activeProvider, setActiveProvider] = useState("Gemini Pro");

    const [chatOpen, setChatOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, chatOpen]);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim() || chatLoading) return;

        const userMsg = { id: Date.now(), text: input, sender: 'user' };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setChatLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/ia/chat_ciudadano`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: input })
            });

            if (!response.ok) throw new Error('Error de conexión');
            const data = await response.json();

            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                text: data.response || 'Error al procesar consulta.',
                sender: 'ai'
            }]);
        } catch (err) {
            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                text: 'Error de conexión con el servicio de IA.',
                sender: 'ai'
            }]);
        } finally {
            setChatLoading(false);
        }
    };

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

    const fetchInsight = async () => {
        if (!stats.summary || stats.summary.length === 0) {
            return;
        }

        setInsightLoading(true);
        try {
            const token = localStorage.getItem('token');
            const url = `${API_BASE_URL}/api/intelligence/insights?municipio=${selectedMunicipio}&anio=${selectedYear}`;
            const response = await fetch(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setInsight(data.insight);
                if (data.provider) setActiveProvider(data.provider === "MISTRAL" ? "Mistral Large" : "Gemini Pro");
            } else {
                setInsight("Error al obtener el análisis estratégico.");
            }
        } catch (error) {
            console.error("Error fetching insight:", error);
            setInsight("El motor de IA está experimentando alta demanda o un error de conexión (Timeout). Reintente en unos momentos o revise la llave API.");
        } finally {
            setInsightLoading(false);
        }
    };

    const fetchMunicipios = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/api/intelligence/municipios`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setMunicipios(data);
                // Si Jamundí no está, pero hay municipios, seleccionar el primero
                if (data.length > 0 && !data.find(m => m.id === "JAMUNDI")) {
                    setSelectedMunicipio(data[0].id);
                }
            }
        } catch (error) {
            console.error("Error fetching municipios:", error);
        }
    };

    useEffect(() => {
        fetchMunicipios();
    }, []);

    useEffect(() => {
        setInsight(null);
        fetchStats();
    }, [selectedMunicipio, selectedYear]);

    useEffect(() => {
        if (stats.summary && stats.summary.length > 0) {
            fetchInsight();
        }
    }, [stats.summary]);

    const handleAutoIngest = async () => {
        setUploading(true);
        setIngestStatus({ text: "Iniciando sincronización con fuentes oficiales (MinDefensa/Policía)...", type: "info", progress: 0 });

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/api/intelligence/ingest`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const data = await response.json();
                setIngestStatus({ text: "Sincronización iniciada en segundo plano. Esto tardará unos minutos...", type: "info", progress: 0 });

                // Poll for status
                const logId = data.log_id;
                if (logId) {
                    const checkInterval = setInterval(async () => {
                        try {
                            const statusRes = await fetch(`${API_BASE_URL}/api/intelligence/ingest/status/${logId}`, {
                                headers: { 'Authorization': `Bearer ${token}` }
                            });
                            if (statusRes.ok) {
                                const statusData = await statusRes.json();
                                if (statusData.estado === 'SUCCESS') {
                                    clearInterval(checkInterval);
                                    setUploading(false);
                                    setIngestStatus({ text: `Finalizado: Se ingestaron ${statusData.registros_insertados} registros desde ${statusData.archivos_procesados} archivos.`, type: "success" });
                                    fetchStats(); // recargar datos
                                } else if (statusData.estado === 'ERROR') {
                                    clearInterval(checkInterval);
                                    setUploading(false);
                                    setIngestStatus({ text: `Error en sincronización: ${statusData.errores}`, type: "error" });
                                } else {
                                    // Sigue en progreso
                                    const progress = statusData.detalles?.progress || 0;
                                    setIngestStatus({
                                        text: `Sincronizando... Descargados ${statusData.detalles?.processed_files || 0} de ${statusData.detalles?.found_files || '?'} archivos oficiales.`,
                                        type: "info",
                                        progress: progress
                                    });
                                }
                            }
                        } catch (e) {
                            console.error("Error polling status", e);
                        }
                    }, 5000); // Check every 5 seconds
                } else {
                    setUploading(false);
                }
            } else {
                setIngestStatus({ text: "Error al iniciar la sincronización.", type: "error" });
                setUploading(false);
            }
        } catch (error) {
            console.error("Error in auto ingest:", error);
            setIngestStatus({ text: "Error de conexión con el servidor al iniciar sincronización. Revise la consola del servidor.", type: "error" });
            setUploading(false);
        }
    };

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
                setIngestStatus({ text: `Éxito: ${data.message} (${data.records_inserted} registros)`, type: "success" });
                fetchStats();
            } else {
                setIngestStatus({ text: `Error: ${data.detail || 'Fallo en la carga'}`, type: "error" });
            }
        } catch (error) {
            console.error("Error uploading file:", error);
            setIngestStatus({ text: "Error de conexión al cargar el archivo.", type: "error" });
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
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        onClick={handleAutoIngest}
                        disabled={uploading}
                        className="border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                    >
                        {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Activity className="mr-2 h-4 w-4" />}
                        Sincronizar con la Web
                    </Button>
                    <Button
                        variant="default"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        className="bg-indigo-600 hover:bg-indigo-700 shadow-lg border-none"
                    >
                        {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                        Cargar Excel Manual
                    </Button>
                </div>
                <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept=".xlsx,.xls" />
            </div>

            {ingestStatus && (
                <div className={`border-l-4 p-4 rounded-md animate-in fade-in slide-in-from-top-4 duration-300 ${ingestStatus.type === 'error' ? 'bg-red-50 border-red-500' :
                    ingestStatus.type === 'success' ? 'bg-emerald-50 border-emerald-500' :
                        'bg-blue-50 border-blue-500'
                    }`}>
                    <div className="flex">
                        <div className="flex-shrink-0">
                            {ingestStatus.type === 'error' ? <Activity className="h-5 w-5 text-red-400" /> :
                                ingestStatus.type === 'success' ? <Activity className="h-5 w-5 text-emerald-400" /> :
                                    <Activity className="h-5 w-5 text-blue-400 animate-pulse" />}
                        </div>
                        <div className="ml-3 w-full">
                            <p className={`text-sm ${ingestStatus.type === 'error' ? 'text-red-700' :
                                ingestStatus.type === 'success' ? 'text-emerald-700' :
                                    'text-blue-700'
                                }`}>{ingestStatus.text}</p>

                            {ingestStatus.progress !== undefined && ingestStatus.type === 'info' && (
                                <div className="mt-3">
                                    <div className="w-full bg-blue-200 rounded-full h-2.5 dark:bg-blue-300 overflow-hidden relative">
                                        <div
                                            className="bg-blue-600 h-2.5 rounded-full transition-all duration-1000 ease-in-out relative z-10"
                                            style={{ width: `${Math.max(ingestStatus.progress, 3)}%` }}
                                        >
                                            {ingestStatus.progress < 100 && (
                                                <div className="absolute top-0 left-0 right-0 bottom-0 bg-white/20 animate-[shimmer_2s_infinite]"></div>
                                            )}
                                        </div>
                                    </div>
                                    <p className="text-xs text-blue-500 mt-1 italic animate-pulse">Analizando cientos de miles de registros (esto tomará varios minutos por archivo)...</p>
                                </div>
                            )}
                        </div>
                        <button onClick={() => setIngestStatus(null)} className="ml-auto flex-shrink-0 text-slate-400 hover:text-slate-600">×</button>
                    </div>
                </div>
            )}

            {/* AI Insights Panel */}
            <Card className={`bg-gradient-to-br from-indigo-900 to-indigo-950 text-white border-none overflow-hidden relative transition-all duration-500 ${chatOpen ? 'h-[500px]' : ''}`}>
                <div className="absolute top-0 right-0 p-4 opacity-10">
                    <Brain className="h-24 w-24" />
                </div>
                <div className="relative z-10 h-full flex flex-col">
                    <CardHeader className={`flex flex-row items-center justify-between pb-2 ${chatOpen ? 'p-6 pb-2' : ''}`}>
                        <div className="flex items-center gap-2">
                            <div className="bg-indigo-500 p-1.5 rounded-lg">
                                <Brain className="h-5 w-5" />
                            </div>
                            <h2 className="text-lg font-semibold">Perspectiva Estratégica Nacional</h2>
                            {insightLoading && !chatOpen && <Loader2 className="h-4 w-4 animate-spin ml-2 text-indigo-300" />}
                        </div>
                        {chatOpen && (
                            <button
                                onClick={() => setChatOpen(false)}
                                className="text-indigo-400 hover:text-white transition-colors"
                            >
                                <Clock size={18} />
                            </button>
                        )}
                    </CardHeader>
                    {!chatOpen ? (
                        <CardContent className="p-6 pt-2">
                            <div className="bg-white/5 border border-white/10 p-4 rounded-lg backdrop-blur-sm">
                                <p className="text-indigo-100 leading-relaxed italic">
                                    {insightLoading ? "Analizando tendencias estratégicas..." : (insight || "Selecciona un municipio y año con datos para ver el análisis.")}
                                </p>
                            </div>
                            <div className="mt-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <span className="text-[10px] text-indigo-400 uppercase tracking-widest font-bold">
                                        Análisis Procesado por {insightLoading ? "Motor IA" : activeProvider}
                                    </span>
                                    {insight && (
                                        <button
                                            onClick={() => setChatOpen(true)}
                                            className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 hover:text-emerald-300 transition-colors bg-emerald-400/10 px-3 py-1.5 rounded-lg border border-emerald-400/20"
                                        >
                                            <Activity size={12} />
                                            Consultar al SISC
                                        </button>
                                    )}
                                </div>
                                <span className="text-[10px] text-indigo-400 uppercase tracking-widest font-bold">Datos MinDefensa Oficiales</span>
                            </div>
                        </CardContent>
                    ) : (
                        <>
                            <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 space-y-4 scrollbar-thin scrollbar-thumb-indigo-700">
                                <div className="flex justify-start">
                                    <div className="max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed bg-white/5 text-indigo-100 border border-white/10 rounded-bl-none italic">
                                        Hola analista. Estoy listo para profundizar en los datos estratégicos de MinDefensa para {municipios.find(m => m.id === selectedMunicipio)?.nombre || selectedMunicipio}. ¿Qué deseas saber?
                                    </div>
                                </div>
                                {messages.map(msg => (
                                    <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                                        <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed ${msg.sender === 'user'
                                            ? 'bg-indigo-500 text-white rounded-br-none'
                                            : 'bg-white/10 text-indigo-100 border border-white/10 rounded-bl-none'}`}>
                                            {msg.text}
                                        </div>
                                    </div>
                                ))}
                                {chatLoading && (
                                    <div className="text-[10px] text-indigo-400 animate-pulse font-bold uppercase tracking-widest px-6">
                                        Procesando...
                                    </div>
                                )}
                            </div>
                            <form onSubmit={handleSend} className="p-4 bg-indigo-950/50 border-t border-indigo-900/50">
                                <div className="relative">
                                    <input
                                        type="text"
                                        value={input}
                                        onChange={(e) => setInput(e.target.value)}
                                        placeholder="Pregunta sobre los datos nacionales..."
                                        className="w-full bg-indigo-950/80 border border-indigo-800 text-white rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all pr-10 placeholder-indigo-400"
                                        disabled={chatLoading}
                                    />
                                    <button
                                        type="submit"
                                        disabled={!input.trim() || chatLoading}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 text-indigo-400 hover:text-white disabled:text-indigo-800 transition-colors"
                                    >
                                        <ArrowUpRight size={20} />
                                    </button>
                                </div>
                            </form>
                        </>
                    )}
                </div>
            </Card>

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
                            {municipios.length === 0 ? (
                                <option value="JAMUNDI">JAMUNDÍ (VALLE)</option>
                            ) : (
                                municipios.map((m) => (
                                    <option key={m.id} value={m.id}>{m.nombre}</option>
                                ))
                            )}
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
