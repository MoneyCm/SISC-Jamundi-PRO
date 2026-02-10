import React, { useState, useEffect } from 'react';
import { KPICard, TrendChart, DistributionChart, RecentActivity, AIInsightWidget, EarlyWarningWidget } from '../components/DashboardWidgets';
import MapComponent from '../components/Map/MapComponent';
import { kpiData as mockKpiData, crimeTrendData as mockTrendData, crimeDistributionData as mockDistributionData, recentActivity as mockRecentActivity } from '../data/mockData';
import { transformDashboardData } from '../utils/dataTransformers';
import { Loader, Download, Calendar } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const Dashboard = () => {
    const [dashboardData, setDashboardData] = useState({
        kpiData: mockKpiData,
        crimeTrendData: mockTrendData,
        crimeDistributionData: mockDistributionData,
        recentActivity: mockRecentActivity
    });
    const [mapData, setMapData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [aiInsight, setAiInsight] = useState('');
    const [aiLoading, setAiLoading] = useState(true);
    const [aiProvider, setAiProvider] = useState('IA');
    const [alerts, setAlerts] = useState([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                // 1. Fetch KPIs
                const kpiRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/kpis`);
                const kpis = await kpiRes.json();

                // 2. Fetch Tendencia
                const trendRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/tendencia`);
                const trendData = await trendRes.json();

                // 3. Fetch Distribución
                const distRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/distribucion`);
                const distData = await distRes.json();

                // 4. Fetch Actividad Reciente (Resumen)
                const recentRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/resumen`);
                const recentData = await recentRes.json();

                // 5. Fetch Map Data (GeoJSON)
                const mapRes = await fetch(`${API_BASE_URL}/analitica/eventos/geojson`);
                let mapFeatures = [];
                if (mapRes.ok) {
                    const geoData = await mapRes.json();
                    mapFeatures = geoData.features || [];
                }

                setDashboardData({
                    kpiData: [
                        { title: "Total Incidentes", value: kpis.total_incidentes.toString(), change: "En vivo", trend: "neutral", icon: "AlertTriangle" },
                        { title: "Tasa Homicidios", value: kpis.tasa_homicidios.toString(), change: "Por 100k hab", trend: "neutral", icon: "Skull" },
                        { title: "Zonas Críticas", value: kpis.zonas_criticas.toString(), change: "Sectores", trend: "neutral", icon: "MapPin" },
                        { title: "Población", value: "150,000", change: "Jamundí", trend: "neutral", icon: "Users" },
                    ],
                    crimeTrendData: trendData,
                    crimeDistributionData: distData,
                    recentActivity: recentData.slice(0, 5).map(i => ({
                        id: i.id,
                        type: i.tipo,
                        location: i.barrio,
                        time: i.fecha,
                        status: i.estado
                    }))
                });
                setMapData(mapFeatures);

                try {
                    const aiRes = await fetch(`${API_BASE_URL}/ia/insights`);
                    const aiData = await aiRes.json();
                    setAiInsight(aiData.insight);
                    setAiProvider(aiData.provider || 'IA');

                    // 7. Fetch Alerts
                    const alertsRes = await fetch(`${API_BASE_URL}/ia/alertas`);
                    const alertsData = await alertsRes.json();
                    setAlerts(alertsData.alertas || []);
                } catch (aiErr) {
                    console.error("Error cargando IA insights o alertas:", aiErr);
                } finally {
                    setAiLoading(false);
                }
            } catch (err) {
                console.error("Error cargando datos reales:", err.message);
                setError("Error conectando con el sistema local.");
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-96">
                <Loader className="w-12 h-12 text-primary animate-spin mb-4" />
                <p className="text-slate-500 font-medium">Cargando Observatorio del Delito...</p>
            </div>
        );
    }

    const handleDownloadPDF = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/reportes/generar-boletin`);
            if (!response.ok) throw new Error("Error generando PDF");

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Boletin_Observatorio_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (err) {
            console.error("Error al descargar PDF:", err);
            alert("No se pudo generar el reporte técnico en este momento.");
        }
    };

    const handleExportCSV = () => {
        if (!dashboardData.recentActivity.length) return;

        const headers = ["ID", "Tipo", "Barrio", "Fecha", "Estado"];
        const rows = dashboardData.recentActivity.map(i => [i.id, (i.type || 'N/A'), (i.location || 'N/A'), (i.time || 'N/A'), (i.status || 'N/A')]);

        let csvContent = "data:text/csv;charset=utf-8,"
            + headers.join(",") + "\n"
            + rows.map(e => e.join(",")).join("\n");

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `Observatorio_Reporte_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const { kpiData, crimeTrendData, crimeDistributionData, recentActivity } = dashboardData;

    return (
        <div className="space-y-6 animate-fade-in">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-xl md:text-2xl font-bold text-neutral">Tablero de Control</h2>
                    <p className="text-slate-500 text-sm italic">Observatorio del Delito</p>
                </div>
                <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
                    <div className="relative flex-1 md:flex-none">
                        <select className="appearance-none w-full bg-white border border-slate-200 text-slate-600 text-sm rounded-lg focus:ring-primary focus:border-primary block pl-3 pr-8 py-2.5 shadow-sm cursor-pointer hover:border-slate-300 transition-colors">
                            <option>Últimos 6 meses</option>
                            <option>Este año</option>
                            <option>Año anterior</option>
                        </select>
                        <Calendar className="absolute right-2.5 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
                    </div>
                    <button
                        onClick={handleExportCSV}
                        className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-all shadow-sm hover:shadow-md active:scale-95"
                    >
                        <Download size={16} />
                        Exportar
                    </button>
                </div>
            </div>

            {/* Early Warning Section */}
            <EarlyWarningWidget alerts={alerts} />

            <div className="grid grid-cols-1 gap-6">
                <AIInsightWidget
                    insight={aiInsight}
                    loading={aiLoading}
                    provider={aiProvider}
                    onTechnicalReport={handleDownloadPDF}
                />
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
                {kpiData && kpiData.map((kpi, index) => (
                    <KPICard key={index} data={kpi} />
                ))}
            </div>

            {/* Main Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <TrendChart data={crimeTrendData} />
                </div>
                <div>
                    <DistributionChart data={crimeDistributionData} />
                </div>
            </div>

            {/* Bottom Section: Map & Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-white p-1 rounded-xl shadow-sm border border-slate-100 h-[300px] md:h-[400px] flex flex-col">
                    <div className="p-4 border-b border-slate-50 flex justify-between items-center">
                        <h3 className="font-bold text-slate-800 text-sm md:text-base">Georreferenciación</h3>
                        <span className="text-[10px] font-medium text-primary bg-primary/10 px-2 py-0.5 rounded-full">En vivo</span>
                    </div>
                    <div className="flex-1 relative z-0">
                        <MapComponent incidents={mapData} />
                    </div>
                </div>
                <div className="lg:col-span-1">
                    <RecentActivity data={recentActivity} />
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
