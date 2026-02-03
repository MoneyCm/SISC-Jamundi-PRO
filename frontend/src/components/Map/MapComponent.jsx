import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default marker icon in React Leaflet
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

const MapComponent = ({ incidents = [] }) => {
    const jamundiPosition = [3.2606, -76.5364];

    return (
        <MapContainer center={jamundiPosition} zoom={14} style={{ height: '100%', width: '100%', borderRadius: '0.5rem' }}>
            <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
            {incidents.map((incident) => {
                // El GeoJSON del backend devuelve [lng, lat] en coordinates
                const position = incident.geometry.coordinates.slice().reverse();
                return (
                    <Marker key={incident.properties.id} position={position}>
                        <Popup>
                            <div className="p-2">
                                <h3 className="font-bold text-sm text-primary">{incident.properties.categoria}</h3>
                                <p className="text-xs text-slate-500 font-medium">{incident.properties.fecha}</p>
                                <p className="text-sm mt-2 text-slate-700"><strong>Barrio:</strong> {incident.properties.barrio}</p>
                                <p className="text-sm mt-1 text-slate-600">{incident.properties.descripcion}</p>
                            </div>
                        </Popup>
                    </Marker>
                );
            })}
        </MapContainer>
    );
};

export default MapComponent;
