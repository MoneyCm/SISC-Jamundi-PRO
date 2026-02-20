import React, { useState, useEffect, useCallback, useRef } from 'react';
import { KPICard, TrendChart, DistributionChart, RecentActivity, AIInsightWidget, EarlyWarningWidget, CommunityInboxWidget } from '../components/DashboardWidgets';
import MapComponent from '../components/Map/MapComponent';
import DashboardFilters from '../components/DashboardFilters';
import ComparisonWidget from '../components/ComparisonWidget';
import { Loader, Download, RefreshCcw } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const Dashboard = () => {
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
                    { title: `Incidentes`, value: (kpisCurrent?.total_incidentes ?? 0).toString(), change: incidentChange.text, trend: incidentChange.trend, icon: "AlertTriangle" },
                    { title: "Tasa Homicidios", value: (kpisCurrent?.tasa_homicidios ?? 0).toString(), change: "x 100k hab", trend: "neutral", icon: "Skull" },
                    { title: "Zonas Críticas", value: (kpisCurrent?.zonas_criticas ?? 0).toString(), change: "Concentración", trend: "neutral", icon: "Activity" },
                    { title: "Población", value: (kpisCurrent?.poblacion ?? 180942).toLocaleString(), change: "Jamundí", trend: "neutral", icon: "Users" },
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
                }
                if (alertsRes.ok) {
                    const alertsData = await alertsRes.json();
                    setAlerts(alertsData.alertas || []);
                }
                if (inboxRes.ok) {
                    const inboxData = await inboxRes.json();
                    setInboxItems(inboxData.items || []);
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
            const response = await fetch(`${API_BASE_URL}/reportes/generar-boletin`, {
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
        <div className="space-y-6 animate-in fade-in duration-700 pb-20">
            {/* Barra de Filtros y Control - Alta Visibilidad */}
            <div className="sticky top-0 z-30 flex flex-col md:flex-row justify-between items-center gap-4 bg-slate-900 text-white p-4 md:px-8 rounded-b-2xl shadow-2xl -mx-4 md:-mx-8">
                <div className="flex items-center gap-4">
                    <div className="hidden md:block">
                        <h2 className="text-xl font-black tracking-tight">Centro de Control SISC</h2>
                        <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                            <p className="text-[9px] text-slate-400 font-bold uppercase tracking-widest whitespace-nowrap">
                                Cobertura: {dashboardData.coverage.start || '...'} / {dashboardData.coverage.end || '...'}
                            </p>
                        </div>
                    </div>
                    <div className="h-8 w-px bg-slate-800 hidden md:block"></div>
                    <DashboardFilters onFilterChange={handleFilterChange} referenceDate={dashboardData.referenceDate} currentRange={dashboardData.currentRange} />
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleExportCSV}
                        className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-white px-5 py-2.5 rounded-xl text-xs font-black transition-all shadow-lg active:scale-95"
                    >
                        <Download size={14} />
                        EXPORTAR DATOS
                    </button>
                </div>
            </div>

            {loading && (
                <div className="fixed top-6 right-6 z-[100] bg-slate-900 text-white px-5 py-2.5 rounded-2xl shadow-2xl flex items-center gap-3 text-xs font-black animate-pulse border border-slate-700">
                    <RefreshCcw size={14} className="animate-spin text-primary" />
                    ACTUALIZANDO...
                </div>
            )}

            <EarlyWarningWidget alerts={alerts} />

            {comparisonData && !comparisonData.isLegacy && (
                <ComparisonWidget comparisonData={comparisonData} />
            )}

            <AIInsightWidget
                insight={aiInsight}
                loading={aiLoading}
                provider={aiProvider}
                onTechnicalReport={handleDownloadPDF}
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                {dashboardData.kpiData.map((kpi, index) => (
                    <KPICard key={index} data={kpi} />
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <TrendChart data={dashboardData.crimeTrendData} year={dashboardData.referenceDate.getFullYear()} />
                </div>
                <div>
                    <DistributionChart data={dashboardData.crimeDistributionData} />
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-white p-1 rounded-2xl shadow-sm border border-slate-100 h-[450px] flex flex-col">
                    <div className="p-5 border-b border-slate-50 flex justify-between items-center">
                        <h3 className="font-black text-slate-800 tracking-tight">Georreferenciación Institucional</h3>
                        <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-1 rounded-md border border-primary/20">POLICIAL / EJÉRCITO</span>
                    </div>
                    <div className="flex-1 relative z-0">
                        <MapComponent incidents={mapData} />
                    </div>
                </div>
                <div className="lg:col-span-1 space-y-6">
                    <RecentActivity data={dashboardData.recentActivity} />
                    <CommunityInboxWidget items={inboxItems} loading={inboxLoading} />
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
