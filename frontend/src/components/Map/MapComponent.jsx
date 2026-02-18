import React, { useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import HeatmapLayer from './HeatmapLayer';

const createCustomIcon = (color, isSatellite) => {
    return L.divIcon({
        className: 'custom-marker-icon',
        html: `<div style="
            background-color: ${color};
            width: 14px;
            height: 14px;
            border-radius: 50%;
            border: ${isSatellite ? '2px solid white' : '1px solid white'};
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            transition: all 0.2s ease;
        "></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
        popupAnchor: [0, -8]
    });
};

const getColor = (category) => {
    const cat = (category || '').toUpperCase();
    if (cat.includes('HOMICIDIO')) return '#d32f2f'; // Rojo Oscuro Pro
    if (cat.includes('HURTO')) return '#1976d2'; // Azul Pro
    if (cat.includes('VIOLENCIA')) return '#fbc02d'; // Amarillo Oscuro
    if (cat.includes('LESIONES')) return '#388e3c'; // Verde Pro
    return '#7b1fa2'; // Púrpura Pro
};

const MapComponent = ({ incidents = [] }) => {
    const jamundiPosition = [3.2606, -76.5364];
    const [showHeatmap, setShowHeatmap] = useState(true);
    const [showMarkers, setShowMarkers] = useState(true);
    const [isSatellite, setIsSatellite] = useState(false);

    const validIncidents = incidents.filter(i =>
        i.geometry &&
        i.geometry.coordinates &&
        i.geometry.coordinates[0] !== undefined &&
        i.geometry.coordinates[1] !== undefined
    );

    const categories = [
        { name: 'Homicidio', color: '#d32f2f' },
        { name: 'Hurto', color: '#1976d2' },
        { name: 'Violencia', color: '#fbc02d' },
        { name: 'Lesiones', color: '#388e3c' },
        { name: 'Otros', color: '#7b1fa2' }
    ];

    return (
        <div className="relative w-full h-full flex flex-col group">
            {/* Controles del Mapa Personalizados */}
            <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-2">
                <button
                    onClick={() => setIsSatellite(!isSatellite)}
                    className={`p-3 rounded-xl shadow-xl border backdrop-blur-md transition-all duration-300 transform hover:scale-110 ${isSatellite ? 'bg-indigo-600 text-white border-indigo-400' : 'bg-white/90 text-slate-600 border-slate-200'}`}
                    title={isSatellite ? "Cambiar a Vista de Calles" : "Cambiar a Vista Satelital"}
                >
                    <span className="text-xl">🛰️</span>
                </button>
                <button
                    onClick={() => setShowHeatmap(!showHeatmap)}
                    className={`p-3 rounded-xl shadow-xl border backdrop-blur-md transition-all duration-300 transform hover:scale-110 ${showHeatmap ? 'bg-orange-500 text-white border-orange-400' : 'bg-white/90 text-slate-600 border-slate-200'}`}
                    title="Alternar Mapa de Calor"
                >
                    <span className="text-xl">🔥</span>
                </button>
                <button
                    onClick={() => setShowMarkers(!showMarkers)}
                    className={`p-3 rounded-xl shadow-xl border backdrop-blur-md transition-all duration-300 transform hover:scale-110 ${showMarkers ? 'bg-blue-600 text-white border-blue-400' : 'bg-white/90 text-slate-600 border-slate-200'}`}
                    title="Alternar Marcadores"
                >
                    <span className="text-xl">📍</span>
                </button>
            </div>

            {/* Leyenda Glassmorphism Claro */}
            <div className="absolute bottom-6 left-6 z-[1000] bg-white/80 backdrop-blur-lg border border-slate-200 p-4 rounded-2xl shadow-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none">
                <h4 className="text-slate-800 text-xs font-bold mb-3 tracking-widest uppercase opacity-70">Leyenda de Incidentes</h4>
                <div className="grid grid-cols-1 gap-2">
                    {categories.map((cat) => (
                        <div key={cat.name} className="flex items-center gap-3">
                            <div className="w-3 h-3 rounded-full shadow-sm" style={{ backgroundColor: cat.color }}></div>
                            <span className="text-slate-600 text-[11px] font-semibold">{cat.name}</span>
                        </div>
                    ))}
                </div>
            </div>

            <MapContainer
                center={jamundiPosition}
                zoom={14}
                zoomControl={false}
                preferCanvas={true}
                style={{ height: '100%', width: '100%', borderRadius: '1rem', background: '#f8fafc' }}
            >
                {isSatellite ? (
                    <TileLayer
                        attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
                        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                    />
                ) : (
                    <TileLayer
                        attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
                        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                    />
                )}

                {showHeatmap && <HeatmapLayer points={validIncidents} />}

                {showMarkers && (
                    <MarkerClusterGroup
                        chunkedLoading
                        maxClusterRadius={50}
                        spiderfyOnMaxZoom={true}
                        showCoverageOnHover={false}
                        disableClusteringAtZoom={18}
                    >
                        {validIncidents.map((incident) => {
                            const [lng, lat] = incident.geometry.coordinates;
                            const color = getColor(incident.properties.categoria);
                            const markerId = incident.properties.id || `inc-${lat}-${lng}-${Math.random()}`;

                            return (
                                <Marker
                                    key={markerId}
                                    position={[lat, lng]}
                                    icon={createCustomIcon(color, isSatellite)}
                                >
                                    <Popup>
                                        <div className="p-3 min-w-[180px] bg-white text-slate-800 rounded-lg shadow-2xl border border-slate-100">
                                            <h3 className="font-bold text-sm border-b border-slate-100 pb-2 mb-2 uppercase tracking-tight" style={{ color: color }}>
                                                {incident.properties.categoria}
                                            </h3>
                                            <div className="space-y-2">
                                                <div className="flex justify-between items-center text-[10px] font-bold text-slate-400">
                                                    <span>{incident.properties.fecha}</span>
                                                    <span className="px-2 py-0.5 bg-slate-50 rounded-full">{incident.properties.barrio}</span>
                                                </div>
                                                <p className="text-xs text-slate-600 leading-relaxed italic">"{incident.properties.descripcion}"</p>
                                            </div>
                                        </div>
                                    </Popup>
                                </Marker>
                            );
                        })}
                    </MarkerClusterGroup>
                )}
            </MapContainer>
        </div>
    );
};

export default MapComponent;
