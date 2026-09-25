import React from 'react';
import { GeoJSON, MapContainer, Popup, Tooltip, ScaleControl, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const formatNumber = (value) => new Intl.NumberFormat('es-CO').format(Number(value) || 0);

// Escala secuencial de 5 clases por cuantiles: evita que un solo barrio con muchos casos
// deje al resto del municipio en el mismo tono.
const CLASS_COLORS = ['#dbeafe', '#93c5fd', '#60a5fa', '#2563eb', '#1e3a8a'];

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
    color: selected ? '#0F172A' : '#2563eb',
    fillColor: classFor(Number(point.total || 0), classes)?.color || CLASS_COLORS[0],
    fillOpacity: selected ? 0.65 : 0.42,
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
const FitToTerritories = ({ points, view, selectedTerritory, revision }) => {
  const map = useMap();
  React.useEffect(() => {
    const resize = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    resize.observe(map.getContainer());
    return () => resize.disconnect();
  }, [map]);
  React.useEffect(() => {
    map.invalidateSize({ pan: false });
    if (view === 'urban') {
      map.setView([3.2606, -76.5364], 14);
      return;
    }
    const selected = points.find((point) => point.name === selectedTerritory);
    const visible = view === 'selected' && selected ? [selected] : points;
    try {
      const bounds = L.geoJSON(visible.map((point) => point.geometry)).getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [35, 35], maxZoom: 16 });
    } catch { /* Mantener el encuadre si no hay geometrías válidas. */ }
  }, [map, points, view, selectedTerritory, revision]);
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
      <Tooltip sticky><strong>{point.name}</strong><br />{formatNumber(point.total)} casos agregados</Tooltip>
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

const TerritoryMap = ({ map, onSelect, selectedTerritory, className = 'h-full', explore = false, focusSelection = false }) => {
  const points = React.useMemo(() => map?.points || [], [map?.points]);
  const [view, setView] = React.useState(explore ? 'urban' : 'all');
  const [revision, setRevision] = React.useState(0);
  const chooseTerritory = (name) => { onSelect?.(name); if (explore) setView('selected'); };
  const changeView = (next) => { setView(next); setRevision((value) => value + 1); };
  const classes = React.useMemo(() => buildClasses(points), [points]);
  const orderedPoints = React.useMemo(
    () => [...points].sort((a, b) => geometryArea(b.geometry) - geometryArea(a.geometry)),
    [points]
  );

  if (!points.length) {
    return <div className={`flex items-center justify-center bg-slate-100 px-6 text-center text-sm font-bold text-slate-500 ${className}`}>No hay territorios con polígono oficial para los filtros seleccionados.</div>;
  }

  return (
    <div className={`flex min-w-0 flex-col ${className}`}>
      {explore && <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white p-3">
        <div className="flex rounded-lg bg-slate-100 p-1" aria-label="Encuadre del mapa">
          {[['urban', 'Casco urbano'], ['all', 'Todos los territorios']].map(([key, label]) => <button key={key} type="button" aria-pressed={view === key} onClick={() => changeView(key)} className={`rounded-md px-3 py-2 text-xs font-bold focus-visible:outline-primary ${view === key ? 'bg-white text-primary shadow-sm' : 'text-slate-600 hover:bg-white/70'}`}>{label}</button>)}
        </div>
        <label className="flex min-w-0 flex-1 items-center gap-2 text-xs font-bold text-slate-600"><span>Acercar a</span><select aria-label="Acercar a un territorio" value={view === 'selected' ? selectedTerritory || '' : ''} onChange={(event) => { if (event.target.value) chooseTerritory(event.target.value); }} className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white p-2 text-sm text-slate-900">
          <option value="">Selecciona un barrio o vereda</option>
          {[...points].sort((a, b) => a.name.localeCompare(b.name, 'es')).map((point) => <option key={point.name} value={point.name}>{point.name} · {formatNumber(point.total)} casos</option>)}
        </select></label>
        <p className="w-full text-[11px] text-slate-500">{view === 'urban' ? 'Encuadre urbano. Las veredas siguen disponibles en “Todos los territorios”.' : 'El encuadre cambia la vista; no modifica los filtros ni los conteos.'}</p>
      </div>}
      <div className="relative z-0 min-h-0 flex-1">
      <MapContainer center={[3.2606, -76.5364]} zoom={12} preferCanvas style={{ height: '100%', width: '100%', background: '#F8FAFC' }}>
        <TileLayer attribution={BASEMAP.attribution} url={BASEMAP.url} maxZoom={16} />
        <LabelsPane />
        <FitToTerritories points={points} view={focusSelection && selectedTerritory ? 'selected' : view} selectedTerritory={selectedTerritory} revision={revision} />
        <ScaleControl position="bottomright" imperial={false} />
        {orderedPoints.map((point) => (
          <TerritoryLayer
            key={point.name}
            point={point}
            pathStyle={territoryStyle(point, classes, selectedTerritory)}
            onSelect={chooseTerritory}
          />
        ))}
        <Legend classes={classes} />
      </MapContainer>
      </div>
    </div>
  );
};

export default TerritoryMap;
