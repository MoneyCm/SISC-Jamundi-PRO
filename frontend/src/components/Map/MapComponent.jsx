import React, { useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import HeatmapLayer from './HeatmapLayer';

const getColor = (category) => {
    const cat = (category || '').toUpperCase();
    if (cat.includes('HOMICIDIO')) return '#ef4444'; // Rojo
    if (cat.includes('HURTO')) return '#3b82f6'; // Azul
    if (cat.includes('VIOLENCIA')) return '#f59e0b'; // Naranja
    if (cat.includes('LESIONES')) return '#10b981'; // Verde
    return '#8b5cf6'; // Morado (otros)
};

const MapComponent = ({ incidents = [] }) => {
    const jamundiPosition = [3.2606, -76.5364];
    const [showHeatmap, setShowHeatmap] = useState(true);
    const [showMarkers, setShowMarkers] = useState(true);

    const validIncidents = incidents.filter(i =>
        i.geometry &&
        i.geometry.coordinates &&
        i.geometry.coordinates[0] !== undefined &&
        i.geometry.coordinates[1] !== undefined
    );

    return (
        <div className="relative w-full h-full flex flex-col">
            {/* Controles del Mapa Personalizados (Botones Flotantes) */}
            <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-2">
                <button
                    onClick={() => setShowHeatmap(!showHeatmap)}
                    className={`p-2 rounded-lg shadow-lg border transition-all ${showHeatmap ? 'bg-orange-500 text-white border-orange-600' : 'bg-white text-slate-600 border-slate-200'}`}
                    title="Alternar Mapa de Calor"
                >
                    🔥
                </button>
                <button
                    onClick={() => setShowMarkers(!showMarkers)}
                    className={`p-2 rounded-lg shadow-lg border transition-all ${showMarkers ? 'bg-blue-500 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200'}`}
                    title="Alternar Marcadores"
                >
                    📍
                </button>
            </div>

            <MapContainer
                center={jamundiPosition}
                zoom={14}
                style={{ height: '100%', width: '100%', borderRadius: '0.5rem' }}
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                    url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                />

                {showHeatmap && <HeatmapLayer points={validIncidents} />}

                {showMarkers && validIncidents.map((incident) => {
                    const [lng, lat] = incident.geometry.coordinates;
                    return (
                        <CircleMarker
                            key={incident.properties.id || Math.random()}
                            center={[lat, lng]}
                            radius={5}
                            fillColor={getColor(incident.properties.categoria)}
                            color="#ffffff"
                            weight={1}
                            opacity={0.8}
                            fillOpacity={0.6}
                        >
                            <Popup>
                                <div className="p-2 min-w-[150px]">
                                    <h3 className="font-bold text-sm border-b pb-1 mb-2" style={{ color: getColor(incident.properties.categoria) }}>
                                        {incident.properties.categoria}
                                    </h3>
                                    <div className="space-y-1">
                                        <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{incident.properties.fecha}</p>
                                        <p className="text-xs text-slate-700"><strong>Barrio:</strong> {incident.properties.barrio}</p>
                                        <p className="text-xs text-slate-600 italic">"{incident.properties.descripcion}"</p>
                                    </div>
                                </div>
                            </Popup>
                        </CircleMarker>
                    );
                })}
            </MapContainer>
        </div>
    );
};

export default MapComponent;
