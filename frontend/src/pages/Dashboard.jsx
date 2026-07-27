import React, { useState, useEffect, useCallback, useRef } from 'react';
import { KPICard, TrendChart, DistributionChart, RecentActivity, AIInsightWidget, EarlyWarningWidget, CommunityInboxWidget } from '../components/DashboardWidgets';
import MapComponent from '../components/Map/MapComponent';
import DashboardFilters from '../components/DashboardFilters';
import ComparisonWidget from '../components/ComparisonWidget';
import IntelligenceBriefTicker from '../components/IntelligenceBriefTicker';
import { Loader, Download, RefreshCcw, ShieldCheck, Activity, Users, Globe, FileText, ArrowUpRight, Skull, UserMinus, Car, PhoneForwarded, Home, Brain, Zap } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const Dashboard = ({ userRoles = [], dataLevel = 1, onNavigate }) => {
    const isCitizen = userRoles.length === 0;
    const isInstitutional = dataLevel >= 2;

    const [dashboardData, setDashboardData] = useState({
        kpiData: [],
        crimeTrendData: [],
        crimeDistributionData: [],
        recentActivity: [],
        referenceDate: new Date(),
        coverage: { start: null, end: null }
    });
    const [mapData, setMapData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [aiInsight, setAiInsight] = useState('');
    const [aiLoading, setAiLoading] = useState(true);
    const [aiProvider, setAiProvider] = useState('IA');
    const [alerts, setAlerts] = useState([]);
    const [inboxItems, setInboxItems] = useState([]);
    const [inboxLoading, setInboxLoading] = useState(true);

    // Filters and Comparison states
    const [filters, setFilters] = useState({ start: null, end: null });
    const [comparisonData, setComparisonData] = useState(null);

    // Evitar loop infinito: fetchData NO depende de comparisonData
    const fetchData = useCallback(async (currentFilters) => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

            // 0. Determinar fechas
            let start = currentFilters.start;
            let end = currentFilters.end;
            let refDate = new Date();
            let coverage = { start: null, end: null };

            const dateRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/ultima-actualizacion`, { headers });
            if (dateRes.ok) {
                const dateData = await dateRes.json();
                if (dateData.ultima_fecha) {
                    refDate = new Date(dateData.ultima_fecha);
                    coverage = { start: dateData.fecha_inicial, end: dateData.ultima_fecha };
                }
            }

            if (!start) start = new Date(refDate.getFullYear(), refDate.getMonth(), 1).toISOString().split('T')[0];
            if (!end) end = new Date(refDate.getFullYear(), refDate.getMonth() + 1, 0).toISOString().split('T')[0];

            // 1. Fetch KPIs
            const kpiRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/kpis?start_date=${start}&end_date=${end}`, { headers });
            const kpisCurrent = await kpiRes.json();

            let compResult = null;
            if (currentFilters.compare) {
                const compQuery = `start1=${start}&end1=${end}&start2=${currentFilters.startCompare}&end2=${currentFilters.endCompare}`;
                const compRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/comparativa?${compQuery}`, { headers });
                if (compRes.ok) {
                    compResult = await compRes.json();
                }
            } else {
                const prevDate = new Date(start);
                const prevStart = new Date(prevDate.getFullYear(), prevDate.getMonth() - 1, 1).toISOString().split('T')[0];
                const prevEnd = new Date(prevDate.getFullYear(), prevDate.getMonth(), 0).toISOString().split('T')[0];
                const kpiPrevRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/kpis?start_date=${prevStart}&end_date=${prevEnd}`, { headers });
                if (kpiPrevRes.ok) {
                    const kpisPrev = await kpiPrevRes.json();
                    compResult = {
                        isLegacy: true,
                        prevTotal: kpisPrev.total_incidentes,
                        prevHomicidios: kpisPrev.tasa_homicidios
                    };
                }
            }

            // Actualizar el estado de comparación
            setComparisonData(compResult);

            const calculateChange = (current, last) => {
                if (last === 0) return { text: current > 0 ? "Nuevo registro" : "Sin previos", trend: current > 0 ? "negative" : "neutral" };
                const diff = current - last;
                const percent = ((diff / last) * 100).toFixed(1);
                return { text: `${diff > 0 ? '+' : ''}${percent}% vs anterior`, trend: diff > 0 ? "negative" : "positive" };
            };

            const incidentChange = compResult?.isLegacy
                ? calculateChange(kpisCurrent?.total_incidentes || 0, compResult.prevTotal || 0)
                : (compResult ? { text: `${compResult.cambios_porcentaje.total > 0 ? '+' : ''}${compResult.cambios_porcentaje.total}% vs ref`, trend: compResult.cambios_porcentaje.total > 0 ? 'negative' : 'positive' } : { text: "Filtrado", trend: "neutral" });

            // 2, 3, 4. Fetch Resto
            const [trendRes, distRes, recentRes] = await Promise.all([
                fetch(`${API_BASE_URL}/analitica/estadisticas/tendencia?start_date=${start}&end_date=${end}`, { headers }),
                fetch(`${API_BASE_URL}/analitica/estadisticas/distribucion?start_date=${start}&end_date=${end}`, { headers }),
                fetch(`${API_BASE_URL}/analitica/estadisticas/resumen?start_date=${start}&end_date=${end}`, { headers })
            ]);

            const trendData = await trendRes.json();
            const distData = await distRes.json();
            const recentData = await recentRes.json();

            // 5. Map
            const mapRes = await fetch(`${API_BASE_URL}/analitica/eventos/geojson?token=${token || ''}&start_date=${start}&end_date=${end}`);
            let mapFeatures = [];
            if (mapRes.ok) {
                const geoData = await mapRes.json();
                mapFeatures = geoData.features || [];
            }

            setDashboardData({
                kpiData: [
                    { title: `Homicidios`, value: (kpisCurrent?.homicidios ?? 0).toString(), change: "Corte MinDefensa", trend: "neutral", icon: "Skull" },
                    { title: "Hurto Personas", value: (kpisCurrent?.hurto_personas ?? 0).toString(), change: "Denuncias", trend: "neutral", icon: "UserMinus" },
                    { title: "Hurto Vehículos", value: (kpisCurrent?.hurto_vehiculos ?? 0).toString(), change: "Autos/Motos", trend: "neutral", icon: "Car" },
                    { title: "Extorsión", value: (kpisCurrent?.extorsion ?? 0).toString(), change: "Reportes", trend: "neutral", icon: "PhoneForwarded" },
                    { title: "VIF", value: (kpisCurrent?.vif ?? 0).toString(), change: "V. Intrafamiliar", trend: "neutral", icon: "Home" },
                    { title: "Lesiones", value: (kpisCurrent?.lesiones ?? 0).toString(), change: "Convivencia", trend: "neutral", icon: "Activity" },
                ],
                crimeTrendData: Array.isArray(trendData) ? trendData : [],
                crimeDistributionData: Array.isArray(distData) ? distData : [],
                recentActivity: Array.isArray(recentData) ? recentData.slice(0, 5).map(i => ({
                    id: i?.id, type: i?.tipo, location: i?.barrio, time: i?.fecha, status: i?.estado
                })) : [],
                referenceDate: refDate,
                currentRange: { start, end },
                coverage: coverage
            });
            setMapData(mapFeatures);

        } catch (err) {
            console.error("Error cargando datos:", err);
            setError("Error conectando con el sistema.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData(filters);
    }, [filters, fetchData]);

    useEffect(() => {
        const fetchExtras = async () => {
            const token = localStorage.getItem('token');
            const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
            try {
                const [aiRes, alertsRes, inboxRes] = await Promise.all([
                    fetch(`${API_BASE_URL}/ia/insights`, { headers }),
                    fetch(`${API_BASE_URL}/ia/alertas`, { headers }),
                    fetch(`${API_BASE_URL}/participacion/admin/bandeja`, { headers })
                ]);

                if (aiRes.ok) {
                    const aiData = await aiRes.json();
                    setAiInsight(aiData.insight);
                    setAiProvider(aiData.provider || 'IA');
                } else if (aiRes.status === 401) {
                    setAiInsight("La sesión de seguridad ha expirado. Por favor, inicie sesión nuevamente para visualizar los análisis de la IA y alertas estratégicas.");
                    setAiProvider("SISTEMA");
                }
                if (alertsRes.ok) {
                    const alertsData = await alertsRes.json();
                    setAlerts(alertsData.alertas || []);
                } else if (alertsRes.status === 401) {
                    setAlerts([{ nivel: "ADVERTENCIA", mensaje: "Sesión expirada. Alertas en pausa hasta nuevo inicio de sesión.", actual: 0, anterior: 0 }]);
                }

                if (inboxRes.ok) {
                    const inboxData = await inboxRes.json();
                    setInboxItems(inboxData.items || []);
                } else if (inboxRes.status === 401) {
                    setInboxItems([{ id: 'exp', tipo: "SISTEMA", titulo: "Sesión Expirada", subtitulo: "Requiere autenticación", descripcion: "Inicie sesión nuevamente para ver solicitudes.", fecha: new Date().toISOString() }]);
                }
            } catch (e) {
                console.error(e);
            } finally {
                setAiLoading(false);
                setInboxLoading(false);
            }
        };
        fetchExtras();
    }, []);

    const handleFilterChange = (newFilters) => {
        setFilters(newFilters);
    };

    const handleDownloadPDF = async () => {
        try {
            const token = localStorage.getItem('token');
            const { start, end } = dashboardData.currentRange || {};
            const queryParams = start && end ? `?fecha_inicio=${start}&fecha_fin=${end}` : '';
            const response = await fetch(`${API_BASE_URL}/reportes/generar-boletin${queryParams}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error("Error de servidor");
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Boletin_SISC_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (err) {
            alert("Error al descargar PDF");
        }
    };

    const handleDownloadExecutivePDF = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/reportes/generar-boletin-ejecutivo?token=${token || ''}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error("Error de servidor");
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Boletin_Ejecutivo_IA_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (err) {
            alert("Error al generar Boletín IA");
        }
    };

    const handleExportCSV = () => {
        if (!dashboardData.recentActivity.length) return;
        const headers = ["ID", "Tipo", "Barrio", "Fecha", "Estado"];
        const rows = dashboardData.recentActivity.map(i => [i.id, i.type, i.location, i.time, i.status]);
        const csvContent = "data:text/csv;charset=utf-8," + headers.join(",") + "\n" + rows.map(e => e.join(",")).join("\n");
        const link = document.createElement("a");
        link.setAttribute("href", encodeURI(csvContent));
        link.setAttribute("download", `Reporte_SISC.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    if (loading && !dashboardData.currentRange) {
        return (
            <div className="flex flex-col items-center justify-center h-screen bg-slate-50">
                <Loader className="w-12 h-12 text-primary animate-spin mb-4" />
                <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">SISC Jamundí: Cargando Inteligencia</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-in fade-in duration-700 pb-20">
            {/* Orla Institucional Superior */}
            <div className="orla-hidirica mb-2"></div>

            {/* Barra de Filtros y Control - Centro de Mando Institucional */}
            <div className="sticky top-0 z-40 flex flex-col md:flex-row justify-between items-center gap-4 bg-white text-slate-800 p-5 md:px-10 rounded-2xl shadow-xl -mx-4 md:-mx-10 border border-slate-200">
                <div className="flex items-center gap-6">
                    <div className="hidden md:flex items-center gap-4">
                        <div className="relative bg-white p-1 rounded-lg border border-slate-100 shadow-sm flex items-center justify-center">
                            <img src="/assets/escudo.png" alt="Escudo Jamundí" className="w-10 h-10 object-contain" />
                        </div>
                        <div className="space-y-0.5">
                            <h2 className="text-xl font-black tracking-tight leading-none text-primary font-titles">
                                CENTRO DE MANDO <span className="text-slate-900">SISC</span>
                            </h2>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">
                                    ALCALDÍA DE JAMUNDÍ
                                </span>
                            </div>
                        </div>
                    </div>
                    <div className="h-10 w-px bg-slate-200 hidden lg:block"></div>
                    <DashboardFilters onFilterChange={handleFilterChange} referenceDate={dashboardData.referenceDate} currentRange={dashboardData.currentRange} />
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={handleDownloadExecutivePDF}
                        className="flex items-center gap-2 bg-primary hover:bg-primary-secondary text-white px-4 py-2.5 rounded-xl text-xs font-black transition-all shadow-md active:scale-95 group relative overflow-hidden"
                    >
                        <Brain size={14} />
                        BOLETÍN IA
                    </button>
                    <button
                        onClick={handleDownloadPDF}
                        className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 px-4 py-2.5 rounded-xl text-xs font-black transition-all active:scale-95"
                    >
                        <RefreshCcw size={14} />
                        DETALLADO
                    </button>
                    <button
                        onClick={handleExportCSV}
                        className="flex items-center gap-2 bg-accent-gold hover:opacity-90 text-white px-5 py-2.5 rounded-xl text-xs font-black transition-all shadow-md active:scale-95"
                    >
                        <Download size={14} />
                        EXPORTAR
                    </button>
                </div>
            </div>

            {/* Banner de Bienvenida Institucional */}
            <div className="relative overflow-hidden bg-white p-10 rounded-3xl border border-slate-100 shadow-xl">
                <div className="absolute top-0 right-0 w-1/4 h-full opacity-[0.03] pointer-events-none">
                    <img src="/assets/escudo.png" alt="" className="w-full h-full object-contain translate-x-10 translate-y-10" />
                </div>
                <div className="relative z-10 max-w-4xl">
                    <div className="inline-flex items-center gap-2 px-3 py-1 bg-primary/5 rounded-full border border-primary/10 mb-4">
                        <ShieldCheck size={14} className="text-primary" />
                        <span className="text-[10px] font-black text-primary uppercase tracking-widest">Portal Oficial de Seguridad</span>
                    </div>
                    <h1 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tighter mb-4 font-titles">
                        Observatorio del Delito <span className="text-primary italic">SISC JAMUNDÍ</span>
                    </h1>
                    <p className="text-slate-500 font-medium text-lg leading-relaxed mb-8">
                        Sistema integral de monitoreo y análisis para la <span className="text-slate-900 font-bold uppercase">Alcaldía de Jamundí</span>.
                        Toma de decisiones estratégica basada en evidencia científica y datos regionales.
                    </p>
                    <div className="flex flex-wrap gap-3">
                        <div className="bg-slate-50 text-slate-600 px-5 py-2 rounded-xl border border-slate-100 text-xs font-bold uppercase tracking-wider flex items-center gap-2">
                            <Activity size={16} className="text-primary" />
                            Inteligencia Predictiva
                        </div>
                        <div className="bg-slate-50 text-slate-600 px-5 py-2 rounded-xl border border-slate-100 text-xs font-bold uppercase tracking-wider flex items-center gap-2">
                            <Users size={16} className="text-accent-gold" />
                            Gestión Institucional
                        </div>
                    </div>
                </div>
            </div>

            <IntelligenceBriefTicker />

            {loading && (
                <div className="fixed top-24 right-6 z-[100] bg-white text-slate-900 px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-3 text-xs font-black border border-slate-200 animate-in slide-in-from-right-10">
                    <RefreshCcw size={16} className="animate-spin text-primary" />
                    ACTUALIZANDO INTELIGENCIA...
                </div>
            )}

            {/* SECCIÓN 1: INTELIGENCIA ESTRATÉGICA */}
            <section className="space-y-6">
                <div className="flex items-center gap-3 mb-2 px-1">
                    <div className="w-1 h-6 bg-primary rounded-full"></div>
                    <h2 className="text-xl font-black text-slate-800 tracking-tight uppercase">I. Inteligencia Estratégica</h2>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
                    <div className="xl:col-span-4 flex flex-col gap-6">
                        <EarlyWarningWidget alerts={alerts} />
                        <div className="grid grid-cols-2 gap-4">
                            {dashboardData.kpiData.slice(0, 2).map((kpi, index) => (
                                <KPICard key={index} data={kpi} />
                            ))}
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            {dashboardData.kpiData.slice(2, 4).map((kpi, index) => (
                                <KPICard key={index + 2} data={kpi} />
                            ))}
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            {dashboardData.kpiData.slice(4, 6).map((kpi, index) => (
                                <KPICard key={index + 4} data={kpi} />
                            ))}
                        </div>
                    </div>

                    <div className="xl:col-span-8 space-y-6">
                        <AIInsightWidget
                            insight={aiInsight}
                            loading={aiLoading}
                            provider={aiProvider}
                            onTechnicalReport={handleDownloadPDF}
                        />
                        {comparisonData && !comparisonData.isLegacy && (
                            <ComparisonWidget comparisonData={comparisonData} />
                        )}
                    </div>
                </div>
            </section>

            {/* SECCIÓN 2: SITUACIÓN OPERACIONAL */}
            <section className="space-y-6">
                <div className="flex items-center gap-3 mb-2 px-1">
                    <div className="w-1 h-6 bg-emerald-500 rounded-full"></div>
                    <h2 className="text-xl font-black text-slate-800 tracking-tight uppercase">II. Situación Operacional</h2>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2 space-y-6">
                        <div className="bg-white p-1 rounded-2xl shadow-xl border border-slate-200 h-[550px] flex flex-col group transition-shadow hover:shadow-2xl">
                            <div className="p-5 border-b border-slate-50 flex justify-between items-center bg-slate-50/50 rounded-t-2xl">
                                <div>
                                    <h3 className="font-black text-slate-800 tracking-tight text-lg">Georreferenciación Estratégica</h3>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-0.5">Visualización de incidentes y activos institucionales</p>
                                </div>
                                <div className="flex gap-2">
                                    <span className="text-[10px] font-black text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-100">EJÉRCITO</span>
                                    <span className="text-[10px] font-black text-primary bg-primary/5 px-3 py-1.5 rounded-lg border border-primary/10">POLICÍA</span>
                                </div>
                            </div>
                            <div className="flex-1 relative z-0 overflow-hidden rounded-b-2xl">
                                <MapComponent incidents={mapData} />
                            </div>
                        </div>
                        <TrendChart data={dashboardData.crimeTrendData} year={dashboardData.referenceDate.getFullYear()} />
                    </div>

                    <div className="lg:col-span-1 space-y-6">
                        <DistributionChart data={dashboardData.crimeDistributionData} />
                        <RecentActivity data={dashboardData.recentActivity} />
                    </div>
                </div>
            </section>

            {/* SECCIÓN 3: GESTIÓN SOCIAL Y CONVIVENCIA */}
            <section className="space-y-6">
                <div className="flex items-center gap-3 mb-2 px-1">
                    <div className="w-1 h-6 bg-amber-500 rounded-full"></div>
                    <h2 className="text-xl font-black text-slate-800 tracking-tight uppercase">III. Gestión y Convivencia</h2>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                    <div className="xl:col-span-2">
                        <CommunityInboxWidget items={inboxItems} loading={inboxLoading} />
                    </div>
                    <div className="bg-slate-900 rounded-[2rem] p-8 text-white flex flex-col justify-between shadow-2xl relative overflow-hidden group">
                        {/* Background Decoration */}
                        <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-primary opacity-20 rounded-full blur-3xl group-hover:scale-150 transition-transform duration-700"></div>

                        <div>
                            <h3 className="text-2xl font-black tracking-tight mb-4">Módulos de Respuesta</h3>
                            <p className="text-slate-400 text-sm font-medium mb-8 leading-relaxed">
                                Acceda rápidamente a las herramientas de gestión externa y coordinación institucional.
                            </p>

                            <div className="space-y-3">
                                <button
                                    onClick={() => onNavigate?.('monitoring')}
                                    className="w-full flex items-center justify-between p-4 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/10 transition-all group/btn"
                                >
                                    <div className="flex items-center gap-3">
                                        <Globe className="text-primary" size={20} />
                                        <span className="font-bold text-sm">Monitor Mindefensa</span>
                                    </div>
                                    <ArrowUpRight size={16} className="text-slate-500 group-hover/btn:text-white transition-colors" />
                                </button>
                                <button
                                    onClick={() => onNavigate?.('police_monitor')}
                                    className="w-full flex items-center justify-between p-4 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/10 transition-all group/btn"
                                >
                                    <div className="flex items-center gap-3">
                                        <ShieldCheck className="text-emerald-500" size={20} />
                                        <span className="font-bold text-sm">Monitor Policial</span>
                                    </div>
                                    <ArrowUpRight size={16} className="text-slate-500 group-hover/btn:text-white transition-colors" />
                                </button>
                                <button
                                    onClick={() => onNavigate?.('reports')}
                                    className="w-full flex items-center justify-between p-4 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/10 transition-all group/btn"
                                >
                                    <div className="flex items-center gap-3">
                                        <FileText className="text-amber-500" size={20} />
                                        <span className="font-bold text-sm">Reportes Técnicos</span>
                                    </div>
                                    <ArrowUpRight size={16} className="text-slate-500 group-hover/btn:text-white transition-colors" />
                                </button>
                            </div>
                        </div>

                        <div className="mt-8 pt-6 border-t border-white/10 flex items-center justify-between">
                            <span className="text-[10px] font-black text-white/30 uppercase tracking-[0.2em]">SISC v2.5 Admin</span>
                            <div className="flex gap-2">
                                <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
};

export default Dashboard;
