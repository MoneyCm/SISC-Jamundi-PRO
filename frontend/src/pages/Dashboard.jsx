import React, { useState, useEffect } from 'react';
import { KPICard, TrendChart, DistributionChart, RecentActivity } from '../components/DashboardWidgets';
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

    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch Dashboard Summary
                const summaryRes = await fetch(`${API_BASE_URL}/analitica/estadisticas/resumen`);
                if (!summaryRes.ok) throw new Error('Error al cargar resumen');
                const summaryData = await summaryRes.json();

                // Fetch Map Data (GeoJSON)
                const mapRes = await fetch(`${API_BASE_URL}/analitica/eventos/geojson`);
                if (mapRes.ok) {
                    const geoData = await mapRes.json();
                    setMapData(geoData.features || []);
                }

                const transformed = transformDashboardData(summaryData);
                setDashboardData(transformed);
            } catch (err) {
                console.log("Error cargando datos reales:", err.message);
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
                    <h2 className="text-2xl font-bold text-neutral">Tablero de Control</h2>
                    <p className="text-slate-500 text-sm italic">Observatorio de Seguridad y Convivencia de Jamundí</p>
                </div>
                <div className="flex space-x-3">
                    <div className="relative">
                        <select className="appearance-none bg-white border border-slate-200 text-slate-600 text-sm rounded-lg focus:ring-primary focus:border-primary block pl-3 pr-8 py-2.5 shadow-sm cursor-pointer hover:border-slate-300 transition-colors">
                            <option>Últimos 6 meses</option>
                            <option>Este año</option>
                            <option>Año anterior</option>
                        </select>
                        <Calendar className="absolute right-2.5 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
                    </div>
                    <button
                        onClick={handleExportCSV}
                        className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 transition-all shadow-sm hover:shadow-md active:scale-95"
                    >
                        <Download size={16} />
                        Exportar Reporte
                    </button>
                </div>
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
                <div className="lg:col-span-2 bg-white p-1 rounded-xl shadow-sm border border-slate-100 h-[400px] flex flex-col">
                    <div className="p-4 border-b border-slate-50 flex justify-between items-center">
                        <h3 className="font-bold text-slate-800">Georreferenciación del Delito</h3>
                        <span className="text-xs font-medium text-primary bg-primary/10 px-2 py-1 rounded-full">En vivo</span>
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
