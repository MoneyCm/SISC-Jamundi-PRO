import React, { useState, useEffect } from 'react';
import { KPICard, TrendChart, DistributionChart } from '../components/DashboardWidgets';
import MapComponent from '../components/Map/MapComponent';
import { Loader, Lock, Globe, Home } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';
import AboutObservatorio from '../components/AboutObservatorio';

const PublicDashboard = ({ onLoginClick }) => {
    const [dashboardData, setDashboardData] = useState({
        kpiData: [],
        crimeTrendData: [],
        crimeDistributionData: []
    });
    const [mapData, setMapData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchPublicData = async () => {
            try {
                setLoading(true);
                setError(null);

                const fetchWithTimeout = async (url, timeout = 10000) => {
                    const controller = new AbortController();
                    const id = setTimeout(() => controller.abort(), timeout);
                    try {
                        const response = await fetch(url, { signal: controller.signal });
                        clearTimeout(id);
                        return response;
                    } catch (e) {
                        clearTimeout(id);
                        throw e;
                    }
                };

                // Fetch basic stats (Public)
                const [kpiRes, trendRes, distRes, mapRes] = await Promise.allSettled([
                    fetchWithTimeout(`${API_BASE_URL}/analitica/estadisticas/kpis`),
                    fetchWithTimeout(`${API_BASE_URL}/analitica/estadisticas/tendencia`),
                    fetchWithTimeout(`${API_BASE_URL}/analitica/estadisticas/distribucion`),
                    fetchWithTimeout(`${API_BASE_URL}/analitica/eventos/geojson`)
                ]);

                let kpis = { total_incidentes: 0, tasa_homicidios: 0 };
                let trendData = [];
                let distData = [];
                let features = [];
                let failedCount = 0;
                let errorDetails = [];

                const processRes = async (res, name) => {
                    if (res.status === 'fulfilled' && res.value.ok) {
                        return await res.value.json();
                    } else {
                        failedCount++;
                        const details = res.status === 'fulfilled'
                            ? `${name}: Error ${res.value.status} (${res.value.statusText})`
                            : `${name}: Conexión fallida (${res.reason})`;
                        errorDetails.push(details);
                        return null;
                    }
                };

                const kpiData = await processRes(kpiRes, "KPIs");
                if (kpiData) kpis = kpiData;

                const trendD = await processRes(trendRes, "Tendencia");
                if (trendD) trendData = trendD;

                const distD = await processRes(distRes, "Distribución");
                if (distD) distData = distD;

                const geoData = await processRes(mapRes, "Mapa/GeoJSON");
                if (geoData) features = geoData.features || [];

                console.log("Datos cargados:", { kpis, trendData, distData, features });
                if (errorDetails.length > 0) {
                    console.warn("Detalles de errores de carga:", errorDetails);
                }

                setDashboardData({
                    kpiData: [
                        { title: "Incidentes Reportados", value: (kpis?.total_incidentes ?? 0).toString(), change: "Últimos 6 meses", trend: "neutral", icon: "Activity" },
                        { title: "Tasa Homicidios", value: (kpis?.tasa_homicidios ?? 0).toString(), change: "Por 100k hab", trend: "neutral", icon: "Skull" },
                        { title: "Población", value: "150,000", change: "Jamundí", trend: "neutral", icon: "Users" },
                    ],
                    crimeTrendData: Array.isArray(trendData) && trendData.length > 0 ? trendData : [],
                    crimeDistributionData: Array.isArray(distData) && distData.length > 0 ? distData : []
                });
                setMapData(features);

                if (failedCount >= 3) {
                    throw new Error(`Múltiples servicios fallaron: ${errorDetails.join(' | ')}`);
                }

            } catch (err) {
                console.error("Error en Dashboard Público:", err);
                setError(`Problema de conexión: ${err.message || "El servidor no responde"}. Revisa tu internet o el estado del backend.`);
            } finally {
                setLoading(false);
            }
        };

        fetchPublicData();
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh]">
                <Loader className="w-12 h-12 text-primary animate-spin mb-4" />
                <p className="text-slate-500 font-medium text-center">
                    Accediendo al Portal Ciudadano SISC...<br />
                    <span className="text-xs italic opacity-70">Conectando con: {API_BASE_URL}</span>
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-fade-in max-w-7xl mx-auto px-4 py-6">
            {error && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-xl flex justify-between items-center">
                    <div>
                        <p className="text-red-700 font-bold">Problema de conexión con la base de datos</p>
                        <p className="text-red-600 text-sm">{error}</p>
                    </div>
                    <button
                        onClick={() => window.location.reload()}
                        className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-red-700 transition-colors"
                    >
                        Reintentar
                    </button>
                </div>
            )}
            {/* Header Ciudadano */}
            <div className="bg-gradient-to-r from-primary to-primary-600 rounded-2xl p-6 md:p-8 text-white shadow-xl relative overflow-hidden">
                <div className="relative z-10 flex flex-col md:flex-row justify-between items-center gap-6">
                    <div>
                        <button
                            onClick={() => window.location.reload()}
                            className="flex items-center gap-2 text-white/70 hover:text-white mb-2 font-bold uppercase text-[10px] tracking-widest transition-colors bg-white/10 px-3 py-1 rounded-full border border-white/20"
                        >
                            <Home size={14} /> Volver al Inicio del Portal
                        </button>
                        <div className="flex items-center gap-2 mb-2">
                            <Globe size={20} className="text-white/80" />
                            <span className="text-xs font-bold uppercase tracking-wider text-white/80">Portal de Transparencia</span>
                        </div>
                        <h1 className="text-3xl md:text-4xl font-extrabold mb-2">SISC Jamundí</h1>
                        <p className="text-white/90 text-sm md:text-lg max-w-2xl font-medium">
                            Sistema de Información para la Seguridad y la Convivencia.
                            Visualiza y analiza los datos en tiempo real para una ciudadanía activa.
                        </p>
                    </div>
                    <button
                        onClick={onLoginClick}
                        className="flex items-center gap-2 bg-white/20 hover:bg-white/30 backdrop-blur-md text-white border border-white/30 px-6 py-3 rounded-xl font-bold transition-all hover:scale-105 active:scale-95 shadow-lg"
                    >
                        <Lock size={18} />
                        Acceso Institucional
                    </button>
                </div>
                {/* Decorative blobs */}
                <div className="absolute top-[-20%] right-[-10%] w-64 h-64 bg-white/10 rounded-full blur-3xl"></div>
                <div className="absolute bottom-[-20%] left-[-5%] w-48 h-48 bg-black/10 rounded-full blur-2xl"></div>
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                {dashboardData.kpiData.map((kpi, index) => (
                    <KPICard key={index} data={kpi} />
                ))}
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <TrendChart data={dashboardData.crimeTrendData} title="Tendencia Histórica (Ciudadana)" />
                <DistributionChart data={dashboardData.crimeDistributionData} title="Distribución por Modalidad" />
            </div>

            {/* Map Section */}
            <div className="bg-white p-2 rounded-2xl shadow-lg border border-slate-100 flex flex-col h-[500px]">
                <div className="p-5 border-b border-slate-50 flex justify-between items-center">
                    <div>
                        <h3 className="font-bold text-slate-800 text-lg">Mapa de Incidencia</h3>
                        <p className="text-xs text-slate-500">Ubicación aproximada de eventos registrados</p>
                    </div>
                    <span className="text-xs font-bold text-primary bg-primary/10 px-3 py-1 rounded-full border border-primary/20">Modo Abierto Activo</span>
                </div>
                <div className="flex-1 relative z-0 overflow-hidden rounded-b-xl">
                    <MapComponent incidents={mapData} isPublic={true} />
                </div>
            </div>

            {/* Nueva Sección: Sobre el Observatorio */}
            <AboutObservatorio />

            <footer className="text-center py-10">
                <p className="text-slate-400 text-sm">© 2026 Alcaldía de Jamundí - Oficina del Observatorio</p>
                <p className="text-slate-500 text-[10px] mt-1 uppercase font-bold tracking-widest">SISC Jamundí - Datos Abiertos para la Seguridad</p>
                <div className="mt-4 flex justify-center gap-4 text-xs font-semibold text-slate-500 uppercase tracking-tighter">
                    <span>Estrategia de Seguridad</span>
                    <span>•</span>
                    <span>Convivencia Ciudadana</span>
                </div>
            </footer>
        </div>
    );
};

export default PublicDashboard;
