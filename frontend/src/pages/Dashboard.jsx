import React, { useState, useEffect } from 'react';
import { KPICard, TrendChart, DistributionChart, RecentActivity, AIInsightWidget, EarlyWarningWidget } from '../components/DashboardWidgets';
import MapComponent from '../components/Map/MapComponent';
import { kpiData as mockKpiData, crimeTrendData as mockTrendData, crimeDistributionData as mockDistributionData, recentActivity as mockRecentActivity } from '../data/mockData';
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
                const token = localStorage.getItem('token');
                const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

                // 0. Obtener fecha de referencia (último dato disponible)
                const dateRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/ultima-actualizacion`, { headers });
                let referenceDate = new Date();
                if (dateRes.ok) {
                    const dateData = await dateRes.json();
                    if (dateData.ultima_fecha) {
                        // Ajustar referenceDate al último día del mes de la última fecha de datos
                        // Esto asegura que mostremos el mes completo más reciente con información
                        const lastDataDate = new Date(dateData.ultima_fecha);
                        referenceDate = lastDataDate;

                        // Forzar UTC para evitar problemas de zona horaria si la fecha viene simple
                        // referenceDate = new Date(lastDataDate.getUTCFullYear(), lastDataDate.getUTCMonth(), lastDataDate.getUTCDate());
                    }
                }

                // Calcular rangos basados en la fecha de referencia (Simulando que "hoy" es referenceDate)
                const startOfCurrentMonth = new Date(referenceDate.getFullYear(), referenceDate.getMonth(), 1).toISOString().split('T')[0];
                // El fin del mes actual es el último día de ese mes
                const endOfCurrentMonth = new Date(referenceDate.getFullYear(), referenceDate.getMonth() + 1, 0).toISOString().split('T')[0];

                const startOfLastMonth = new Date(referenceDate.getFullYear(), referenceDate.getMonth() - 1, 1).toISOString().split('T')[0];
                const endOfLastMonth = new Date(referenceDate.getFullYear(), referenceDate.getMonth(), 0).toISOString().split('T')[0];

                console.log(`Analizando datos desde ${startOfCurrentMonth} hasta ${endOfCurrentMonth} (vs mes previo)`);

                // 1. Fetch KPIs (Actual vs Anterior)
                const [kpiCurrentRes, kpiLastRes] = await Promise.all([
                    fetch(`${API_BASE_URL}/analitica/estadisticas/kpis?start_date=${startOfCurrentMonth}&end_date=${endOfCurrentMonth}`, { headers }),
                    fetch(`${API_BASE_URL}/analitica/estadisticas/kpis?start_date=${startOfLastMonth}&end_date=${endOfLastMonth}`, { headers })
                ]);

                const kpisCurrent = await kpiCurrentRes.json();
                const kpisLast = await kpiLastRes.json();

                // Helper para calcular variación
                const calculateChange = (current, last) => {
                    if (!last && current > 0) return { text: "Nuevo registro", trend: "negative" };
                    if (!last) return { text: "Sin datos previos", trend: "neutral" };

                    const diff = current - last;
                    const percent = ((diff / last) * 100).toFixed(1);
                    const trend = diff > 0 ? "negative" : "positive"; // Aumento de delitos es negativo
                    const sign = diff > 0 ? "+" : "";
                    return { text: `${sign}${percent}% vs mes anterior`, trend };
                };

                const incidentChange = calculateChange(kpisCurrent?.total_incidentes || 0, kpisLast?.total_incidentes || 0);
                const homicideChange = calculateChange(kpisCurrent?.tasa_homicidios || 0, kpisLast?.tasa_homicidios || 0);

                // Nombre del mes para mostrar en la UI
                const monthName = new Intl.DateTimeFormat('es-ES', { month: 'long' }).format(referenceDate);
                const capitalizedMonth = monthName.charAt(0).toUpperCase() + monthName.slice(1);

                // 2. Fetch Tendencia
                const trendRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/tendencia`, { headers });
                const trendData = await trendRes.json();

                // 3. Fetch Distribución
                const distRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/distribucion`, { headers });
                const distData = await distRes.json();

                // 4. Fetch Actividad Reciente (Resumen)
                const recentRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/resumen`, { headers });
                const recentData = await recentRes.json();

                // 5. Fetch Map Data (GeoJSON)
                const mapRes = await fetch(`${API_BASE_URL}/analitica/eventos/geojson?token=${token || ''}`);
                let mapFeatures = [];
                if (mapRes.ok) {
                    const geoData = await mapRes.json();
                    mapFeatures = geoData.features || [];
                }

                setDashboardData({
                    kpiData: [
                        {
                            title: `Total Incidentes (${capitalizedMonth})`,
                            value: (kpisCurrent?.total_incidentes ?? 0).toString(),
                            change: incidentChange.text,
                            trend: incidentChange.trend,
                            icon: "AlertTriangle"
                        },
                        {
                            title: "Tasa Homicidios (Est.)",
                            value: (kpisCurrent?.tasa_homicidios ?? 0).toString(),
                            change: homicideChange.text,
                            trend: homicideChange.trend,
                            icon: "Skull"
                        },
                        { title: "Zonas Críticas", value: (kpisCurrent?.zonas_criticas ?? 0).toString(), change: "Sectores activos", trend: "neutral", icon: "MapPin" },
                        { title: "Población", value: (kpisCurrent?.poblacion ?? 180942).toLocaleString(), change: "Jamundí (PISCC)", trend: "neutral", icon: "Users" },
                    ],
                    crimeTrendData: Array.isArray(trendData) ? trendData : [],
                    crimeDistributionData: Array.isArray(distData) ? distData : [],
                    recentActivity: Array.isArray(recentData) ? recentData.slice(0, 5).map(i => ({
                        id: i?.id,
                        type: i?.tipo,
                        location: i?.barrio,
                        time: i?.fecha,
                        status: i?.estado
                    })) : []
                });
                setMapData(mapFeatures);

                try {
                    const aiRes = await fetch(`${API_BASE_URL}/ia/insights`, { headers });
                    if (aiRes.ok) {
                        const aiData = await aiRes.json();
                        setAiInsight(aiData.insight);
                        setAiProvider(aiData.provider || 'IA');
                    }

                    const alertsRes = await fetch(`${API_BASE_URL}/ia/alertas`, { headers });
                    if (alertsRes.ok) {
                        const alertsData = await alertsRes.json();
                        setAlerts(alertsData.alertas || []);
                    }
                } catch (aiErr) {
                    console.error("Error cargando IA:", aiErr);
                } finally {
                    setAiLoading(false);
                }
            } catch (err) {
                console.error("Error cargando datos:", err);
                setError("Error conectando con el sistema.");
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
                <p className="text-slate-500 font-medium">Cargando SISC Jamundí...</p>
            </div>
        );
    }

    const handleDownloadPDF = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/reportes/generar-boletin`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error("Acceso denegado o error de servidor");

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Boletin_SISC_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (err) {
            alert("No tienes permiso o el servidor no respondió.");
        }
    };

    const handleExportCSV = () => {
        if (!dashboardData.recentActivity.length) return;
        const headers = ["ID", "Tipo", "Barrio", "Fecha", "Estado"];
        const rows = dashboardData.recentActivity.map(i => [i.id, i.type, i.location, i.time, i.status]);
        const csvContent = "data:text/csv;charset=utf-8," + headers.join(",") + "\n" + rows.map(e => e.join(",")).join("\n");
        const link = document.createElement("a");
        link.setAttribute("href", encodeURI(csvContent));
        link.setAttribute("download", `SISC_Reporte_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const { kpiData, crimeTrendData, crimeDistributionData, recentActivity } = dashboardData;

    return (
        <div className="space-y-6 animate-fade-in">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-xl md:text-2xl font-bold text-neutral">Panel Administrativo</h2>
                    <p className="text-slate-500 text-sm italic">SISC Jamundí - Acceso Restringido</p>
                </div>
                <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
                    <button
                        onClick={handleExportCSV}
                        className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-all shadow-sm"
                    >
                        <Download size={16} />
                        Exportar
                    </button>
                </div>
            </div>

            <EarlyWarningWidget alerts={alerts} />

            <div className="grid grid-cols-1 gap-6">
                <AIInsightWidget
                    insight={aiInsight}
                    loading={aiLoading}
                    provider={aiProvider}
                    onTechnicalReport={handleDownloadPDF}
                />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
                {kpiData.map((kpi, index) => (
                    <KPICard key={index} data={kpi} />
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <TrendChart data={crimeTrendData} />
                </div>
                <div>
                    <DistributionChart data={crimeDistributionData} />
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-white p-1 rounded-xl shadow-sm border border-slate-100 h-[400px] flex flex-col">
                    <div className="p-4 border-b border-slate-50 flex justify-between items-center">
                        <h3 className="font-bold text-slate-800">Mapa Georreferenciado Institucional (SISC)</h3>
                        <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full border border-primary/20 uppercase tracking-tighter">Precisión Máxima</span>
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
