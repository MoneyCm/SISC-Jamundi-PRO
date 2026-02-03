import { MapContainer, TileLayer, CircleMarker, Popup, LayersControl } from 'react-leaflet';
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
    const validIncidents = incidents.filter(i => i.geometry.coordinates[0] && i.geometry.coordinates[1]);

    return (
        <MapContainer center={jamundiPosition} zoom={14} style={{ height: '100%', width: '100%', borderRadius: '0.5rem' }}>
            {/* Capa Base - Siempre Visible */}
            <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            />

            <LayersControl position="topright">
                {/* Capa de Calor como Overlay */}
                <LayersControl.Overlay checked name="Mapa de Calor (Densidad)">
                    <HeatmapLayer points={validIncidents} />
                </LayersControl.Overlay>

                {/* Marcadores como Overlay */}
                <LayersControl.Overlay checked name="Mostrar Marcadores">
                    <>
                        {validIncidents.map((incident) => {
                            const [lng, lat] = incident.geometry.coordinates;
                            const position = [lat, lng];

                            return (
                                <CircleMarker
                                    key={incident.properties.id}
                                    center={position}
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
                    </>
                </LayersControl.Overlay>
            </LayersControl>
        </MapContainer>
    );
};

export default MapComponent;
