import React, { useState, useEffect } from 'react';
import { 
    Bell, 
    ShieldAlert, 
    MapPin, 
    Clock, 
    CheckCircle2, 
    XCircle, 
    ExternalLink, 
    Video, 
    Image as ImageIcon,
    AlertTriangle,
    Navigation,
    Shield,
    Check
} from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { API_BASE_URL } from '../utils/apiConfig';

// DivIcon instead of standard icons to avoid path issues
const createEmergencyIcon = () => {
    return L.divIcon({
        className: 'custom-emergency-icon',
        html: `<div style="
            background-color: #ef4444;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            border: 3px solid white;
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.8);
            animation: pulse-emergency 1.5s infinite;
        "></div>
        <style>
            @keyframes pulse-emergency {
                0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
                70% { transform: scale(1.2); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
                100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
            }
        </style>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });
};

const PanicMonitoring = () => {
    const [alerts, setAlerts] = useState([]);
    const [selectedAlert, setSelectedAlert] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('OPEN');
    const [stats, setStats] = useState({ total: 0, open: 0, dispatched: 0 });

    const fetchAlerts = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/panic/history?status=${filter}`);
            if (!response.ok) throw new Error("Error fetching alerts");
            const data = await response.json();
            setAlerts(data);
            setLoading(false);
        } catch (error) {
            console.error("Error fetching panic alerts:", error);
            setLoading(false);
        }
    };

    const fetchStats = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/panic/stats`);
            if (response.ok) {
                const data = await response.json();
                setStats(data);
            }
        } catch (error) {
            console.error("Error fetching stats:", error);
        }
    };

    useEffect(() => {
        fetchAlerts();
        fetchStats();
        const interval = setInterval(() => {
            fetchAlerts();
            fetchStats();
        }, 10000);
        return () => clearInterval(interval);
    }, [filter]);

    const handleUpdateStatus = async (alertId, newStatus) => {
        try {
            const response = await fetch(`${API_BASE_URL}/panic/alert/${alertId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    status: newStatus,
                    assigned_to: 'Centro de Mando Jamundí'
                })
            });
            
            if (response.ok) {
                fetchAlerts();
                fetchStats();
                if (selectedAlert && selectedAlert.id === alertId) {
                    setSelectedAlert({ ...selectedAlert, status: newStatus });
                }
            }
        } catch (error) {
            console.error("Error updating status:", error);
        }
    };

    const formatTime = (isoString) => {
        if (!isoString) return '---';
        try {
            return new Date(isoString).toLocaleString('es-CO', {
                hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short'
            });
        } catch (e) { return '---'; }
    };

    const getStatusStyle = (status) => {
        switch (status) {
            case 'OPEN': return 'bg-red-100 text-red-700 border-red-200 animate-pulse';
            case 'DISPATCHED': return 'bg-blue-100 text-blue-700 border-blue-200';
            case 'RESOLVED': return 'bg-emerald-100 text-emerald-700 border-emerald-200';
            case 'FALSE_ALARM': return 'bg-slate-100 text-slate-700 border-slate-200';
            default: return 'bg-slate-50 text-slate-600';
        }
    };

    return (
        <div className="flex h-[calc(100vh-100px)] gap-6 p-6">
            {/* Sidebar de alertas */}
            <div className="w-96 flex flex-col gap-4">
                <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6 flex flex-col h-full">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-xl font-black text-slate-900 flex items-center gap-2">
                            <ShieldAlert className="text-red-600" /> Monitoreo
                        </h2>
                        <span className="bg-red-600 text-white text-[10px] font-black px-2 py-1 rounded-full animate-pulse-slow">
                            VIVO
                        </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 mb-6">
                        <button 
                            onClick={() => setFilter('OPEN')}
                            className={`p-4 rounded-2xl border text-center transition-all ${filter === 'OPEN' ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-transparent text-slate-400'}`}
                        >
                            <p className="text-3xl font-black text-red-600">{stats.open}</p>
                            <p className="text-[10px] font-bold uppercase tracking-widest">Activas</p>
                        </button>
                        <button 
                            onClick={() => setFilter('')}
                            className={`p-4 rounded-2xl border text-center transition-all ${filter === '' ? 'bg-slate-100 border-slate-200' : 'bg-slate-50 border-transparent text-slate-400'}`}
                        >
                            <p className="text-3xl font-black text-slate-900">{stats.total}</p>
                            <p className="text-[10px] font-bold uppercase tracking-widest">Total</p>
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                        {loading && alerts.length === 0 ? (
                            <div className="text-center py-20 text-slate-400 italic">Consultando alertas...</div>
                        ) : alerts.length === 0 ? (
                            <div className="text-center py-20 text-slate-400 italic">No hay alertas registradas</div>
                        ) : (
                            alerts.map(alert => (
                                <button
                                    key={alert.id}
                                    onClick={() => setSelectedAlert(alert)}
                                    className={`w-full text-left p-4 rounded-2xl border transition-all ${selectedAlert?.id === alert.id ? 'bg-indigo-50 border-indigo-200 shadow-md ring-2 ring-indigo-500/20' : 'bg-white border-slate-100 hover:border-indigo-100'}`}
                                >
                                    <div className="flex justify-between items-start mb-2">
                                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{formatTime(alert.timestamp)}</span>
                                        <span className={`px-2 py-0.5 rounded-lg text-[9px] font-black border ${getStatusStyle(alert.status)}`}>
                                            {alert.status}
                                        </span>
                                    </div>
                                    <h4 className="text-xs font-bold text-slate-800 line-clamp-1 italic italic">
                                        COORD: {alert.lat?.toFixed(4)}, {alert.lon?.toFixed(4)}
                                    </h4>
                                </button>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Panel Principal */}
            <div className="flex-1 flex flex-col gap-6">
                {selectedAlert ? (
                    <>
                        {/* Mapa (con Key para forzar re-renderizado al cambiar alerta) */}
                        <div className="flex-1 bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden relative">
                            {selectedAlert.lat && selectedAlert.lon ? (
                                <MapContainer 
                                    key={selectedAlert.id}
                                    center={[selectedAlert.lat, selectedAlert.lon]} 
                                    zoom={16} 
                                    className="h-full w-full"
                                >
                                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                                    <Marker position={[selectedAlert.lat, selectedAlert.lon]} icon={createEmergencyIcon()}>
                                        <Popup><div className="font-bold">Ubicación del Alertante</div></Popup>
                                    </Marker>
                                </MapContainer>
                            ) : (
                                <div className="h-full w-full flex items-center justify-center bg-slate-50 italic text-slate-400">Sin datos GPS</div>
                            )}
                            
                            <div className="absolute top-4 right-4 z-[1000] bg-white/90 backdrop-blur-md p-4 rounded-2xl border border-white shadow-xl">
                                <div className="flex items-center gap-2 text-slate-900 font-black text-xs uppercase italic italic">
                                    <Navigation size={14} className="text-indigo-600" /> Jamundí - Centro Control
                                </div>
                            </div>
                        </div>

                        {/* Detalles */}
                        <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm flex gap-8">
                            <div className="flex-1">
                                <div className="flex items-center gap-3 mb-4">
                                    <h3 className="text-xl font-black text-slate-900 uppercase">Detalle de Alerta</h3>
                                    <span className={`px-3 py-1 rounded-xl text-[10px] font-black border ${getStatusStyle(selectedAlert.status)}`}>
                                        {selectedAlert.status}
                                    </span>
                                </div>
                                <p className="text-sm font-medium text-slate-600 bg-slate-50 p-4 rounded-xl border border-slate-200 italic">
                                    "{selectedAlert.note || 'Sin comentarios adicionales del ciudadano.'}"
                                </p>
                            </div>

                            <div className="w-64 flex flex-col gap-3">
                                <button 
                                    onClick={() => handleUpdateStatus(selectedAlert.id, 'DISPATCHED')}
                                    className="bg-indigo-600 text-white font-black text-xs py-3 rounded-xl hover:bg-indigo-700 transition-all flex items-center justify-center gap-2"
                                >
                                    <Video size={16} /> DESPACHAR
                                </button>
                                <button 
                                    onClick={() => handleUpdateStatus(selectedAlert.id, 'RESOLVED')}
                                    className="bg-emerald-600 text-white font-black text-xs py-3 rounded-xl hover:bg-emerald-700 transition-all flex items-center justify-center gap-2"
                                >
                                    <CheckCircle2 size={16} /> RESOLVER
                                </button>
                                <button 
                                    onClick={() => handleUpdateStatus(selectedAlert.id, 'FALSE_ALARM')}
                                    className="bg-slate-100 text-slate-600 font-black text-xs py-3 rounded-xl hover:bg-slate-200 transition-all flex items-center justify-center gap-2"
                                >
                                    <XCircle size={16} /> FALSA ALARMA
                                </button>
                            </div>

                            <div className="w-48 flex flex-col gap-2 border-l border-slate-100 pl-6">
                                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest text-center mb-1">Evidencia</p>
                                <div className="flex flex-wrap gap-2 overflow-y-auto max-h-32">
                                    {selectedAlert.evidence_urls && selectedAlert.evidence_urls.length > 0 ? (
                                        selectedAlert.evidence_urls.map((url, i) => {
                                            // El backend devuelve rutas relativas del tipo /static/uploads/...
                                            // Necesitamos apuntar al servidor de la API
                                            const fullUrl = `${API_BASE_URL.replace('/api', '')}${url}`;
                                            const isVideo = url.match(/\.(mp4|mov|webm)$/i);
                                            
                                            return (
                                                <a 
                                                    key={i} 
                                                    href={fullUrl} 
                                                    target="_blank" 
                                                    rel="noopener noreferrer"
                                                    className="w-14 h-14 bg-slate-100 rounded-xl border border-slate-200 flex items-center justify-center hover:bg-slate-200 transition-all overflow-hidden relative group"
                                                >
                                                    {isVideo ? (
                                                        <Video size={18} className="text-indigo-600" />
                                                    ) : (
                                                        <img 
                                                            src={fullUrl} 
                                                            alt="Evidencia" 
                                                            className="w-full h-full object-cover" 
                                                            onError={(e) => {
                                                                e.target.style.display = 'none';
                                                                e.target.parentElement.innerHTML = '🖼️';
                                                            }}
                                                        />
                                                    )}
                                                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                                                        <ExternalLink size={14} className="text-white" />
                                                    </div>
                                                </a>
                                            );
                                        })
                                    ) : (
                                        <div className="w-full h-14 bg-slate-50 border border-slate-100 border-dashed rounded-xl flex items-center justify-center italic text-[9px] text-slate-300">
                                            Sin archivos
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-center bg-white rounded-3xl border border-slate-100 border-dashed">
                        <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                            <ShieldAlert className="text-slate-200" size={40} />
                        </div>
                        <h3 className="text-xl font-black text-slate-900 tracking-tight">Consola de Control</h3>
                        <p className="text-sm text-slate-400 font-medium mt-1">Haga clic en una alerta activa <br/>para ver su ubicación y gestionarla</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PanicMonitoring;
