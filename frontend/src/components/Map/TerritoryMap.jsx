import React from 'react';
import { GeoJSON, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const formatNumber = (value) => new Intl.NumberFormat('es-CO').format(Number(value) || 0);

// Escala secuencial de 5 clases por cuantiles: evita que un solo barrio con muchos casos
// deje al resto del municipio en el mismo tono.
const CLASS_COLORS = ['#DDE3FF', '#AAB6FB', '#6F7FF3', '#3B45D6', '#FFB600'];

const buildClasses = (points) => {
  const values = [...new Set(points.map((point) => Number(point.total || 0)))].sort((a, b) => a - b);
  if (!values.length) return [];
  const breaks = [];
  for (let index = 1; index < CLASS_COLORS.length; index += 1) {
    const value = values[Math.min(values.length - 1, Math.floor((index * values.length) / CLASS_COLORS.length))];
    if (!breaks.length || value > breaks[breaks.length - 1]) breaks.push(value);
  }
  const classes = [];
  let from = values[0];
  breaks.forEach((limit) => {
    if (limit > from) {
      classes.push({ from, to: limit - 1 });
      from = limit;
    }
  });
  classes.push({ from, to: values[values.length - 1] });
  const offset = CLASS_COLORS.length - classes.length;
  return classes.map((item, index) => ({ ...item, color: CLASS_COLORS[index + offset] }));
};

const classFor = (value, classes) => classes.find((item) => value >= item.from && value <= item.to) || classes[classes.length - 1];

const territoryStyle = (point, classes, selectedTerritory) => {
  const selected = selectedTerritory === point.name;
  return {
    color: selected ? '#0F172A' : '#281FD0',
    fillColor: classFor(Number(point.total || 0), classes)?.color || CLASS_COLORS[0],
    fillOpacity: selected ? 0.9 : 0.72,
    weight: selected ? 3 : 1,
    opacity: 0.85,
  };
};

// Área aproximada (grados²) para dibujar primero los polígonos grandes (veredas) y encima los barrios.
const ringArea = (ring = []) => Math.abs(ring.reduce((sum, [x1, y1], index) => {
  const [x2, y2] = ring[(index + 1) % ring.length];
  return sum + (x1 * y2 - x2 * y1);
}, 0) / 2);
const geometryArea = (geometry) => {
  if (!geometry) return 0;
  if (geometry.type === 'Polygon') return ringArea(geometry.coordinates?.[0]);
  if (geometry.type === 'MultiPolygon') return (geometry.coordinates || []).reduce((sum, polygon) => sum + ringArea(polygon?.[0]), 0);
  return 0;
};

// Las etiquetas del mapa base van en un pane propio por encima de los polígonos.
const LabelsPane = () => {
  const map = useMap();
  if (!map.getPane('basemapLabels')) {
    const pane = map.createPane('basemapLabels');
    pane.style.zIndex = 650;
    pane.style.pointerEvents = 'none';
  }
  return <TileLayer url={BASEMAP.labelsUrl} maxZoom={16} pane="basemapLabels" />;
};

// Mapa base sin API key (CARTO ahora exige clave y muestra la marca "API KEY REQUIRED").
export const BASEMAP = {
  url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  labelsUrl: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
  attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors',
};

// Ajusta la vista a los polígonos visibles en lugar de un zoom fijo.
const FitToTerritories = ({ points }) => {
  const map = useMap();
  const key = points.map((p) => p.name).join('|');
  React.useEffect(() => {
    try {
      const bounds = L.geoJSON(points.map((p) => p.geometry)).getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    } catch (e) { /* geometría inválida: se conserva la vista por defecto */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return null;
};

const formatRange = ({ from, to }) => (from === to ? formatNumber(from) : `${formatNumber(from)} – ${formatNumber(to)}`);

const Legend = ({ classes }) => (
  <div className="leaflet-bottom leaflet-left">
    <div className="leaflet-control m-3 rounded-md border border-slate-200 bg-white/95 px-3 py-2 text-[11px] font-semibold text-slate-700 shadow-sm">
      <p className="mb-1 font-black uppercase tracking-wide text-slate-900">Casos agregados</p>
      {[...classes].reverse().map((item) => (
        <div key={`${item.from}-${item.to}`} className="flex items-center gap-2">
          <span className="inline-block h-3 w-5 rounded-sm border border-[#281FD0]/60" style={{ background: item.color }} /> {formatRange(item)}
        </div>
      ))}
    </div>
  </div>
);

// react-leaflet no reaplica `style` al cambiar props: se actualiza la capa directamente
// para que la selección se resalte sin desmontar el polígono (y sin cerrar su popup).
const TerritoryLayer = ({ point, pathStyle, onSelect }) => {
  const layerRef = React.useRef(null);
  const styleKey = JSON.stringify(pathStyle);
  React.useEffect(() => {
    layerRef.current?.setStyle(pathStyle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [styleKey]);
  return (
    <GeoJSON
      ref={layerRef}
      data={point.geometry}
      eventHandlers={{ click: () => onSelect?.(point.name) }}
      style={() => pathStyle}
    >
      <Popup>
        <div className="min-w-44 text-slate-800">
          <strong>{point.name}</strong>
          <p className="mt-1 text-sm">{formatNumber(point.total)} casos agregados</p>
          {point.aliases?.length > 1 && <p className="mt-1 text-xs text-slate-500">Incluye: {point.aliases.join(', ')}</p>}
          {point.conductas?.length > 0 && <p className="mt-2 text-xs text-slate-600">{point.conductas.slice(0, 3).join(', ')}</p>}
        </div>
      </Popup>
    </GeoJSON>
  );
};

const TerritoryMap = ({ map, onSelect, selectedTerritory, className = 'h-full' }) => {
  const points = map?.points || [];
  const classes = React.useMemo(() => buildClasses(points), [points]);
  const orderedPoints = React.useMemo(
    () => [...points].sort((a, b) => geometryArea(b.geometry) - geometryArea(a.geometry)),
    [points]
  );

  if (!points.length) {
    return <div className={`flex items-center justify-center bg-slate-100 px-6 text-center text-sm font-bold text-slate-500 ${className}`}>No hay territorios con polígono oficial para los filtros seleccionados.</div>;
  }

  return (
    <div className={className}>
      <MapContainer center={[3.2606, -76.5364]} zoom={12} preferCanvas style={{ height: '100%', width: '100%', background: '#F8FAFC' }}>
        <TileLayer attribution={BASEMAP.attribution} url={BASEMAP.url} maxZoom={16} />
        <LabelsPane />
        <FitToTerritories points={points} />
        {orderedPoints.map((point) => (
          <TerritoryLayer
            key={point.name}
            point={point}
            pathStyle={territoryStyle(point, classes, selectedTerritory)}
            onSelect={onSelect}
          />
        ))}
        <Legend classes={classes} />
      </MapContainer>
    </div>
  );
};

export default TerritoryMap;
