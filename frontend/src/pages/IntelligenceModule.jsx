import React, { useState, useRef, useEffect } from 'react';
import { Loader2, TrendingUp, Activity, BarChart2, Clock, ArrowUpRight, Brain } from "lucide-react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
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
    const [selectedYear, setSelectedYear] = useState(2025);
    const [selectedMunicipio, setSelectedMunicipio] = useState("JAMUNDI");
    const [municipios, setMunicipios] = useState([]);
    const [availableYears, setAvailableYears] = useState([2026, 2025, 2024, 2023]);
    const [stats, setStats] = useState({ summary: [], trend: [], context: null });
    const [insight, setInsight] = useState(null);
    const [insightLoading, setInsightLoading] = useState(false);
    const [activeProvider, setActiveProvider] = useState("Gemini Pro");
    const [comparisonCrime, setComparisonCrime] = useState("");

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

    const fetchStats = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const url = `${API_BASE_URL}/intelligence/stats?municipio=${selectedMunicipio}&anio=${selectedYear}`;
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
            const url = `${API_BASE_URL}/intelligence/insights?municipio=${selectedMunicipio}&anio=${selectedYear}`;
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
            const response = await fetch(`${API_BASE_URL}/intelligence/municipios`, {
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

    const fetchYears = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/intelligence/years`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                if (data && data.length > 0) {
                    setAvailableYears(data);
                    // Si el año seleccionado no está en la lista, elegir el más reciente
                    if (!data.includes(selectedYear)) {
                        setSelectedYear(data[0]);
                    }
                }
            }
        } catch (error) {
            console.error("Error fetching years:", error);
        }
    };

    useEffect(() => {
        fetchMunicipios();
        fetchYears();
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

    const monthNames = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const selectedMunicipioNombre = municipios.find(m => m.id === selectedMunicipio)?.nombre || selectedMunicipio;
    const territorialReference = stats.context?.territorial_reference;
    const comparisonOptions = (stats.summary || []).filter(item => item.territorial_comparison?.rows?.length > 1);
    const selectedComparisonItem = comparisonOptions.find(item => item.delito === comparisonCrime) || comparisonOptions[0];
    const territorialComparison = selectedComparisonItem?.territorial_comparison;
    const rateComparisonData = (stats.summary || [])
        .filter(item => item.rate_per_100k != null)
        .map(item => ({
            delito: item.delito,
            localRate: item.rate_per_100k,
            regionalRate: item.territorial_benchmark?.available
                ? item.territorial_benchmark.reference_rate_per_100k
                : null,
            nationalRate: item.national_benchmark?.available
                ? item.national_benchmark.national_rate_per_100k
                : null
        }));

    useEffect(() => {
        if (comparisonOptions.length > 0 && !comparisonOptions.some(item => item.delito === comparisonCrime)) {
            setComparisonCrime(comparisonOptions[0].delito);
        }
    }, [stats.summary, comparisonCrime]);

    return (
        <div className="p-6 space-y-6 bg-slate-50 min-h-screen">
            <div>
                <h1 className="text-3xl font-bold text-slate-800 tracking-tight">Contexto comparado</h1>
                <p className="text-slate-500 mt-1">Referencia mensual e histórica de MinDefensa para ubicar a Jamundí frente a municipios comparables y al país.</p>
            </div>

            <Card className="border-slate-200 bg-white">
                <CardContent className="p-5">
                    <div className="flex items-start gap-3">
                        <BarChart2 className="h-5 w-5 mt-0.5 text-indigo-700 flex-shrink-0" />
                        <div className="min-w-0">
                            <p className="font-semibold text-slate-800">Lectura comparada de {selectedMunicipioNombre}</p>
                            <p className="mt-1 text-sm text-slate-600">
                                MinDefensa se usa como referencia mensual e histórica. Para decisiones operativas semanales consulte la Sábana SIEDCO en el Resumen operativo. Las comparaciones se publican únicamente cuando el periodo, el corte y la cobertura son equivalentes.
                            </p>
                            {territorialReference && (
                                <p className={`mt-2 text-xs font-medium ${territorialReference.available ? 'text-emerald-700' : 'text-slate-500'}`}>
                                    {territorialReference.available
                                        ? `${territorialReference.title}: disponible en ${territorialReference.conductas_with_complete_coverage} de ${territorialReference.conductas_evaluated} conductas.`
                                        : `${territorialReference.title}: pendiente de cobertura verificable.`}
                                </p>
                            )}
                            <p className="mt-1 text-xs text-slate-500">
                                {stats.context?.available
                                    ? 'Referencia nacional disponible solo para las conductas que cumplen validación completa.'
                                    : (stats.context?.reason || 'La referencia nacional permanece sin publicar hasta verificar una tasa equivalente y cobertura completa.')}
                            </p>
                            {stats.context?.population?.municipality_total && (
                                <p className="mt-1 text-xs text-slate-500">
                                    Población de referencia DANE {stats.context.population.year}: {Number(stats.context.population.municipality_total).toLocaleString('es-CO')} habitantes.
                                    {stats.context.coverage && ` Municipios con registros codificados: ${stats.context.coverage.observed_municipalities || 0} de ${stats.context.coverage.required_municipalities || 0}.`}
                                </p>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>

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
                            <h2 className="text-lg font-semibold">Lectura comparada del periodo</h2>
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
                                        Redacción asistida por {insightLoading ? "Motor IA" : activeProvider}
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
                                <span className="text-[10px] text-indigo-400 uppercase tracking-widest font-bold">Sin recomendaciones operativas</span>
                            </div>
                        </CardContent>
                    ) : (
                        <>
                            <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 space-y-4 scrollbar-thin scrollbar-thumb-indigo-700">
                                <div className="flex justify-start">
                                    <div className="max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed bg-white/5 text-indigo-100 border border-white/10 rounded-bl-none italic">
                                        Hola analista. Estoy listo para profundizar en las brechas regionales, nacionales e históricas de {municipios.find(m => m.id === selectedMunicipio)?.nombre || selectedMunicipio}. ¿Qué deseas comparar?
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
                                        placeholder="Pregunta sobre el contexto comparado..."
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
                            {availableYears.map(year => (
                                <option key={year} value={year}>{year}</option>
                            ))}
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
                            <CardTitle className="text-sm font-medium text-slate-600">{item.delito}</CardTitle>
                            <TrendingUp className={`h-4 w-4 ${item.yoy_pct == null ? 'text-slate-400' : item.yoy_pct > 2 ? 'text-red-500' : item.yoy_pct < -2 ? 'text-emerald-500' : 'text-slate-500'}`} />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-slate-800">
                                {item.local}
                                <span className="text-xs text-slate-400 font-normal ml-2">casos registrados</span>
                            </div>
                            <div className="flex flex-col gap-1 mt-2">
                                <p className={`text-[10px] font-bold flex items-center ${item.yoy_pct == null ? 'text-slate-500' : item.yoy_pct > 2 ? 'text-red-600' : (item.yoy_pct < -2 ? 'text-emerald-600' : 'text-slate-500')}`}>
                                    <Activity className="mr-1 h-3 w-3" />
                                    {item.yoy_pct == null
                                        ? `Sin base comparable en ${selectedYear - 1}`
                                        : `${item.yoy_pct > 0 ? '+' : ''}${item.yoy_pct}% frente a ${selectedYear - 1}`}
                                </p>
                                {item.rate_per_100k != null && (
                                    <p className="text-[10px] text-slate-500">Tasa local DANE: {item.rate_per_100k} por 100.000 hab.</p>
                                )}
                                {item.territorial_benchmark?.available && (
                                    <p className="text-[10px] font-bold text-emerald-700">
                                        Referencia territorial: {item.territorial_benchmark.reference_rate_per_100k} por 100.000 hab.
                                    </p>
                                )}
                                {item.territorial_benchmark && !item.territorial_benchmark.available && (
                                    <p className="text-[10px] text-slate-400">
                                        Referencia territorial pendiente: {item.territorial_benchmark.coverage.observed_municipalities}/{item.territorial_benchmark.coverage.expected_municipalities} municipios con cobertura verificable.
                                    </p>
                                )}
                                {item.national_benchmark?.available && (
                                    <p className="text-[10px] font-bold text-indigo-700">
                                        Referencia nacional: {item.national_benchmark.national_rate_per_100k} por 100.000 hab.
                                    </p>
                                )}
                                {item.national_benchmark && !item.national_benchmark.available && (
                                    <p className="text-[10px] text-slate-400">
                                        Referencia nacional pendiente: {item.national_benchmark.coverage.observed_municipalities}/{item.national_benchmark.coverage.expected_municipalities} municipios con cobertura verificable.
                                    </p>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                ))}
                {(!stats.summary || stats.summary.length === 0) && !loading && (
                    <Card className="col-span-3 p-10 text-center text-slate-400 border-dashed border-2">
                        No hay datos comparables para el municipio y año seleccionados. Revise la cobertura en el Centro de fuentes.
                    </Card>
                )}
            </div>

            {territorialComparison && (
                <section className="space-y-4" aria-labelledby="regional-comparison-title">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                        <div>
                            <p className="text-xs font-bold uppercase text-indigo-700">Comparación territorial verificable</p>
                            <h2 id="regional-comparison-title" className="mt-1 text-xl font-bold text-slate-900">
                                ¿Cómo está {selectedMunicipioNombre} frente a municipios comparables?
                            </h2>
                            <p className="mt-1 max-w-3xl text-sm text-slate-600">
                                La tasa por 100.000 habitantes permite comparar municipios de distinto tamaño. El grupo incluye municipios de Valle del Cauca y Cauca con población entre 50% y 200% de la población del municipio seleccionado.
                            </p>
                        </div>
                        <div className="w-full lg:w-72">
                            <label htmlFor="regional-crime" className="mb-1 block text-xs font-semibold uppercase text-slate-500">Conducta</label>
                            <select
                                id="regional-crime"
                                value={selectedComparisonItem?.delito || ""}
                                onChange={(event) => setComparisonCrime(event.target.value)}
                                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 outline-none focus:ring-2 focus:ring-indigo-500"
                            >
                                {comparisonOptions.map(item => <option key={item.delito} value={item.delito}>{item.delito}</option>)}
                            </select>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2 text-xs font-semibold">
                        <span className="rounded-full bg-indigo-50 px-3 py-1 text-indigo-700">
                            Periodo: enero a {monthNames[(selectedComparisonItem?.period_end_month || 12) - 1]} de {selectedYear}
                        </span>
                        <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">
                            {territorialComparison.observed_municipalities} de {territorialComparison.expected_municipalities} municipios con dato verificable
                        </span>
                        {territorialComparison.cutoff && (
                            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">Corte de fuente: {territorialComparison.cutoff}</span>
                        )}
                    </div>

                    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                        <div className="max-h-[440px] overflow-auto">
                            <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                                <thead className="sticky top-0 z-10 bg-slate-100 text-xs uppercase text-slate-600">
                                    <tr>
                                        <th className="w-20 px-4 py-3 text-center">Posición</th>
                                        <th className="px-4 py-3">Municipio</th>
                                        <th className="px-4 py-3 text-right">Casos</th>
                                        <th className="px-4 py-3 text-right">Población DANE</th>
                                        <th className="px-4 py-3 text-right">Tasa por 100.000</th>
                                        <th className="px-4 py-3 text-right">Frente a {selectedMunicipioNombre}</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {territorialComparison.rows.map(row => (
                                        <tr key={row.codigo_dane} className={row.es_objetivo ? 'bg-indigo-50 font-bold text-indigo-950' : 'text-slate-700 hover:bg-slate-50'}>
                                            <td className="px-4 py-3 text-center">{row.posicion || '—'}</td>
                                            <td className="px-4 py-3">
                                                <div className="flex items-center gap-2">
                                                    <span>{row.municipio}</span>
                                                    {row.es_objetivo && <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[10px] uppercase text-white">Municipio objetivo</span>}
                                                </div>
                                            </td>
                                            <td className="px-4 py-3 text-right tabular-nums">{row.casos == null ? 'Sin dato' : Number(row.casos).toLocaleString('es-CO')}</td>
                                            <td className="px-4 py-3 text-right tabular-nums">{row.poblacion == null ? '—' : Number(row.poblacion).toLocaleString('es-CO')}</td>
                                            <td className="px-4 py-3 text-right font-bold tabular-nums">{row.tasa_por_100k == null ? '—' : Number(row.tasa_por_100k).toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                                            <td className={`px-4 py-3 text-right font-bold tabular-nums ${row.es_objetivo ? 'text-indigo-700' : row.diferencia_tasa_objetivo > 0 ? 'text-red-600' : row.diferencia_tasa_objetivo < 0 ? 'text-emerald-700' : 'text-slate-500'}`}>
                                                {row.es_objetivo || row.diferencia_tasa_objetivo == null
                                                    ? (row.es_objetivo ? 'Base' : 'No comparable')
                                                    : `${row.diferencia_tasa_objetivo > 0 ? '+' : ''}${Number(row.diferencia_tasa_objetivo).toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <div className="border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
                            Fuente: MinDefensa. Población: proyecciones municipales DANE. Una posición más alta indica una mayor tasa registrada para la conducta seleccionada; no representa por sí sola una evaluación integral de seguridad.
                        </div>
                    </div>
                </section>
            )}

            {rateComparisonData.length > 0 && (
                <Card className="p-6">
                    <div className="mb-5 flex flex-col gap-1">
                        <CardTitle className="flex items-center text-lg text-slate-800">
                            <BarChart2 className="mr-2 h-5 w-5 text-indigo-600" />
                            Brecha por tasa registrada
                        </CardTitle>
                        <p className="text-sm text-slate-600">
                            Comparación por 100.000 habitantes. Una barra ausente significa que la referencia no cumple todavía la cobertura requerida.
                        </p>
                    </div>
                    <div className="h-[360px] min-h-[360px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={rateComparisonData} margin={{ top: 12, right: 24, left: 10, bottom: 55 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                <XAxis dataKey="delito" axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 11 }} interval={0} angle={-18} textAnchor="end" />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                                <Tooltip
                                    formatter={(value) => value == null ? 'Sin dato verificable' : `${Number(value).toLocaleString('es-CO', { maximumFractionDigits: 2 })} por 100.000`}
                                    contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                    cursor={{ fill: '#f8fafc' }}
                                />
                                <Legend iconType="circle" wrapperStyle={{ paddingTop: '14px' }} />
                                <Bar name={selectedMunicipioNombre} dataKey="localRate" fill="#4338ca" radius={[3, 3, 0, 0]} maxBarSize={30} />
                                <Bar name="Referencia regional" dataKey="regionalRate" fill="#0f766e" radius={[3, 3, 0, 0]} maxBarSize={30} />
                                <Bar name="Referencia nacional" dataKey="nationalRate" fill="#eab308" radius={[3, 3, 0, 0]} maxBarSize={30} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">
                        Fuente de casos: MinDefensa. Denominadores: proyecciones municipales DANE. Consulte la tabla territorial para revisar cobertura, corte y municipios incluidos.
                    </p>
                </Card>
            )}
        </div>
    );
};

export default IntelligenceModule;
