import React from 'react';
import { GeoJSON, MapContainer, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const formatNumber = (value) => new Intl.NumberFormat('es-CO').format(Number(value) || 0);

const territoryStyle = (point, max, selectedTerritory) => {
  const ratio = Number(point.total || 0) / Math.max(1, max);
  const selected = selectedTerritory === point.name;
  return {
    color: selected ? '#0F172A' : '#281FD0',
    fillColor: ratio > 0.66 ? '#FFB600' : '#384CF5',
    fillOpacity: selected ? 0.72 : 0.24 + ratio * 0.44,
    weight: selected ? 3 : 2,
  };
};

const TerritoryMap = ({ map, onSelect, selectedTerritory, className = 'h-full' }) => {
  const points = map?.points || [];
  const max = Math.max(1, ...points.map((point) => Number(point.total || 0)));

  if (!points.length) {
    return <div className={`flex items-center justify-center bg-slate-100 px-6 text-center text-sm font-bold text-slate-500 ${className}`}>No hay territorios con poligono oficial para los filtros seleccionados.</div>;
  }

  return (
    <div className={className}>
      <MapContainer center={[3.2606, -76.5364]} zoom={12} preferCanvas style={{ height: '100%', width: '100%', background: '#F8FAFC' }}>
        <TileLayer attribution="&copy; OpenStreetMap contributors &copy; CARTO" url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" maxZoom={19} />
        {points.map((point) => (
          <GeoJSON
            key={point.name}
            data={point.geometry}
            eventHandlers={{ click: () => onSelect?.(point.name) }}
            style={() => territoryStyle(point, max, selectedTerritory)}
          >
            <Popup>
              <div className="min-w-44 text-slate-800">
                <strong>{point.name}</strong>
                <p className="mt-1 text-sm">{formatNumber(point.total)} casos agregados</p>
                {point.conductas?.length > 0 && <p className="mt-2 text-xs text-slate-600">{point.conductas.slice(0, 3).join(', ')}</p>}
              </div>
            </Popup>
          </GeoJSON>
        ))}
      </MapContainer>
    </div>
  );
};

export default TerritoryMap;
