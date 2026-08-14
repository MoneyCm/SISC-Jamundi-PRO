import React, { useState, useEffect, useMemo } from 'react';
import MapComponent from '../components/Map/MapComponent';
import { Filter, Calendar, AlertTriangle, CalendarDays, Layers3, Loader2, MapPinned, RefreshCw, ShieldCheck } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';
import TerritoryMap from '../components/Map/TerritoryMap';
import { loadPublicDashboard } from '../utils/publicDashboardCache';

const CATEGORIES = [
    'HOMICIDIO',
    'HURTO A PERSONAS',
    'HURTO A COMERCIO',
    'LESIONES PERSONALES',
    'VIOLENCIA INTRAFAMILIAR',
    'INSPECCIONES POLICÍA'
];

const LegacyPointMap = () => {
    const [startDate, setStartDate] = useState('2023-01-01');
    const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
    const [selectedCategories, setSelectedCategories] = useState(CATEGORIES);
    const [incidents, setIncidents] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchIncidents = async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);
            selectedCategories.forEach(cat => params.append('categories', cat));

            const token = localStorage.getItem('token');
            const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
            const response = await fetch(`${API_BASE_URL}/analitica/eventos/geojson?${params.toString()}`, { headers });
            const data = await response.json();
            let allFeatures = data.features || [];

            // Si se selecciona inspecciones, cargar datos de la nueva API
            if (selectedCategories.includes('INSPECCIONES POLICÍA')) {
                const resIns = await fetch(`${API_BASE_URL}/inspecciones/geojson`, { headers });
                if (resIns.ok) {
                    const dataIns = await resIns.json();
                    const insFeatures = (dataIns.features || []).map(f => ({
                        ...f,
                        properties: {
                            ...f.properties,
                            categoria: 'INSPECCION POLICÍA',
                            descripcion: `Expediente: ${f.properties.expediente}`,
                            fecha: 'Activo'
                        }
                    }));
                    allFeatures = [...allFeatures, ...insFeatures];
                }
            }

            setIncidents(allFeatures);
        } catch (err) {
            console.error(err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchIncidents();
    }, []);

    const handleCategoryToggle = (category) => {
        setSelectedCategories(prev =>
            prev.includes(category)
                ? prev.filter(c => c !== category)
                : [...prev, category]
        );
    };

    return (
        <div className="flex flex-col lg:flex-row h-full gap-4 lg:gap-6 animate-fade-in">
            {/* Sidebar de Filtros */}
            <div className="w-full lg:w-80 bg-white rounded-xl shadow-sm p-4 lg:p-6 flex flex-col border border-slate-100 divide-y lg:divide-y-0 divide-slate-50">
                <div className="flex items-center space-x-2 mb-4 lg:mb-6 text-slate-700 border-b border-slate-50 pb-4">
                    <Filter size={20} className="text-primary" />
                    <h2 className="font-bold text-lg">Filtros Avanzados</h2>
                </div>

                <div className="py-4 lg:py-0">
                    <label className="block text-sm font-semibold text-slate-700 mb-3 flex items-center">
                        <AlertTriangle size={16} className="mr-2 text-primary" />
                        Tipificación del Delito
                    </label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2">
                        {CATEGORIES.map((type) => (
                            <label key={type} className="flex items-center space-x-3 text-sm text-slate-600 cursor-pointer hover:text-primary transition-colors capitalize bg-slate-50/50 p-2 rounded-lg border border-transparent hover:border-primary/20">
                                <input
                                    type="checkbox"
                                    className="rounded border-slate-300 text-primary focus:ring-primary w-4 h-4"
                                    checked={selectedCategories.includes(type)}
                                    onChange={() => handleCategoryToggle(type)}
                                />
                                <span className="font-medium">{type.toLowerCase()}</span>
                            </label>
                        ))}
                    </div>
                </div>

                <div className="py-4 lg:py-6 space-y-4">
                    <label className="block text-sm font-semibold text-slate-700 mb-1 flex items-center">
                        <Calendar size={16} className="mr-2 text-primary" />
                        Rango Temporal
                    </label>
                    <div className="flex flex-col sm:flex-row lg:flex-col gap-3">
                        <div className="flex-1">
                            <span className="text-[10px] uppercase font-black text-slate-400 tracking-wider mb-1 block">Fecha Inicial</span>
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                className="w-full border-slate-200 rounded-lg text-sm focus:ring-primary focus:border-primary shadow-sm"
                            />
                        </div>
                        <div className="flex-1">
                            <span className="text-[10px] uppercase font-black text-slate-400 tracking-wider mb-1 block">Fecha Final</span>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="w-full border-slate-200 rounded-lg text-sm focus:ring-primary focus:border-primary shadow-sm"
                            />
                        </div>
                    </div>
                </div>

                <button
                    onClick={fetchIncidents}
                    disabled={loading}
                    className="w-full mt-6 bg-primary text-white py-3 px-4 rounded-xl hover:bg-emphasis transition-all text-sm font-bold shadow-md hover:shadow-lg flex items-center justify-center space-x-2 disabled:opacity-50 active:scale-[0.98]"
                >
                    {loading ? <Loader2 size={18} className="animate-spin" /> : <Filter size={18} />}
                    <span>Actualizar Visualización</span>
                </button>

                {error && (
                    <p className="mt-4 text-xs text-red-500 bg-red-50 p-3 rounded-lg border border-red-100 italic">
                        {error}
                    </p>
                )}
            </div>

            {/* Área del Mapa */}
            <div className="flex-1 bg-white rounded-xl shadow-sm p-1 border border-slate-100 relative z-0 min-h-[400px] lg:min-h-0 overflow-hidden">
                <MapComponent incidents={incidents} />
            </div>
        </div>
    );
};

const numberFormat = new Intl.NumberFormat('es-CO');
const formatNumber = (value) => numberFormat.format(Number(value) || 0);
const formatDate = (value) => value
  ? new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`))
  : 'Sin corte';

const PERIOD_OPTIONS = [
  { value: 'last_7_days', label: 'Ultimos 7 dias' },
  { value: 'last_30_days', label: 'Ultimos 30 dias' },
  { value: 'year_to_date', label: 'Ano a la fecha' },
  { value: 'custom', label: 'Rango personalizado' },
];

const INITIAL_FILTERS = { periodMode: 'last_30_days', startDate: '', endDate: '', conducta: '' };

const OperationalTerritoryMap = () => {
  const [draftFilters, setDraftFilters] = useState(INITIAL_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(INITIAL_FILTERS);
  const [data, setData] = useState(null);
  const [selectedTerritory, setSelectedTerritory] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadMap = async (filters, force = false) => {
    setLoading(true);
    setError('');
    try {
      const response = await loadPublicDashboard({
        periodMode: filters.periodMode,
        startDate: filters.startDate,
        endDate: filters.endDate,
        conducta: filters.conducta,
        comparison: 'none',
        includeMap: true,
        minLocationCount: 3,
        force,
      });
      setData(response);
      setSelectedTerritory('');
    } catch (requestError) {
      setError(requestError.message || 'No fue posible consultar el mapa territorial.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMap(appliedFilters);
    // The map reloads only when the analyst applies the selected filters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedFilters]);

  const conductas = data?.filters?.available?.conductas || [];
  const map = data?.map || {};
  const territories = data?.territories || [];
  const territory = useMemo(
    () => territories.find((item) => item.name === selectedTerritory) || null,
    [territories, selectedTerritory]
  );
  const latestCutoff = data?.metadata?.latest_event_date;

  const applyFilters = () => {
    if (draftFilters.periodMode === 'custom' && (!draftFilters.startDate || !draftFilters.endDate)) {
      setError('Selecciona fecha inicial y fecha final para el rango personalizado.');
      return;
    }
    setAppliedFilters({ ...draftFilters });
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <section className="border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="flex items-center gap-2 text-[#281FD0]"><MapPinned size={18} /><p className="text-xs font-black uppercase tracking-wide">Centro de mando SISC</p></div>
            <h1 className="mt-2 text-2xl font-black text-slate-950">Mapa operativo territorial</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-600">Concentracion agregada por territorio oficial. No representa direcciones ni ubicaciones exactas de hechos.</p>
          </div>
          <div className="flex items-center gap-2 border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-black text-emerald-800"><ShieldCheck size={16} /> Base maestra consolidada</div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[300px_1fr]">
        <aside className="space-y-4">
          <section className="border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-slate-900"><Filter size={18} /><h2 className="text-sm font-black uppercase tracking-wide">Consulta territorial</h2></div>
            <label className="mt-5 block text-[11px] font-black uppercase tracking-wide text-slate-500">Periodo
              <select value={draftFilters.periodMode} onChange={(event) => setDraftFilters((current) => ({ ...current, periodMode: event.target.value }))} className="mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold normal-case text-slate-800 outline-none focus:border-[#281FD0]">
                {PERIOD_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            {draftFilters.periodMode === 'custom' && <div className="mt-4 grid gap-3">
              <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Inicio
                <input type="date" value={draftFilters.startDate} max={latestCutoff} onChange={(event) => setDraftFilters((current) => ({ ...current, startDate: event.target.value }))} className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-bold text-slate-800 outline-none focus:border-[#281FD0]" />
              </label>
              <label className="text-[11px] font-black uppercase tracking-wide text-slate-500">Corte
                <input type="date" value={draftFilters.endDate} max={latestCutoff} onChange={(event) => setDraftFilters((current) => ({ ...current, endDate: event.target.value }))} className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-bold text-slate-800 outline-none focus:border-[#281FD0]" />
              </label>
            </div>}
            <label className="mt-5 block text-[11px] font-black uppercase tracking-wide text-slate-500">Conducta
              <select value={draftFilters.conducta} onChange={(event) => setDraftFilters((current) => ({ ...current, conducta: event.target.value }))} className="mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold normal-case text-slate-800 outline-none focus:border-[#281FD0]">
                <option value="">Todas las conductas</option>
                {conductas.map((conducta) => <option key={conducta.code} value={conducta.code}>{conducta.name}</option>)}
              </select>
            </label>
            <button onClick={applyFilters} disabled={loading} className="mt-6 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8] disabled:cursor-not-allowed disabled:opacity-50">
              {loading ? <Loader2 size={17} className="animate-spin" /> : <RefreshCw size={17} />} Actualizar mapa
            </button>
          </section>

          <section className="border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-slate-900"><Layers3 size={18} /><h2 className="text-sm font-black uppercase tracking-wide">Cobertura</h2></div>
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3"><dt className="font-semibold text-slate-600">Territorios en mapa</dt><dd className="font-black text-slate-950">{formatNumber(map.points?.length)}</dd></div>
              <div className="flex items-center justify-between gap-3"><dt className="font-semibold text-slate-600">Omitidos por privacidad</dt><dd className="font-black text-slate-950">{formatNumber(map.suppressed_count)}</dd></div>
              <div className="flex items-center justify-between gap-3"><dt className="font-semibold text-slate-600">Sin poligono oficial</dt><dd className="font-black text-slate-950">{formatNumber(map.unmapped_count)}</dd></div>
            </dl>
          </section>
        </aside>

        <main className="space-y-4">
          {error && <div className="flex items-start gap-3 border border-amber-200 bg-amber-50 p-4 text-sm font-bold text-amber-900"><AlertTriangle className="mt-0.5 shrink-0" size={18} />{error}</div>}
          <section className="border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-col gap-3 border-b border-slate-200 p-5 lg:flex-row lg:items-center lg:justify-between">
              <div><h2 className="text-lg font-black text-slate-950">Distribucion por territorio oficial</h2><p className="mt-1 text-sm font-semibold text-slate-500">{formatDate(data?.metadata?.period_start)} - {formatDate(data?.metadata?.period_end)} | Corte disponible: {formatDate(latestCutoff)}</p></div>
              <div className="border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700">{data?.metadata?.source || 'Fuente en consulta'}</div>
            </div>
            <TerritoryMap map={map} selectedTerritory={selectedTerritory} onSelect={setSelectedTerritory} className="h-[560px]" />
            <div className="grid gap-3 border-t border-slate-200 bg-slate-50 p-4 text-xs font-semibold leading-5 text-slate-600 md:grid-cols-3"><p><strong className="text-slate-900">Metodo:</strong> el color indica volumen agregado, no riesgo individual.</p><p><strong className="text-slate-900">Privacidad:</strong> minimo {formatNumber(map.min_location_count || 3)} casos por territorio.</p><p><strong className="text-slate-900">Cartografia:</strong> solo poligonos oficiales verificados.</p></div>
          </section>

          {territory && <section className="border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-black uppercase tracking-wide text-[#281FD0]">Territorio seleccionado</p>
            <div className="mt-2 flex flex-col gap-2 md:flex-row md:items-end md:justify-between"><div><h2 className="text-2xl font-black text-slate-950">{territory.name}</h2><p className="mt-1 text-sm font-semibold text-slate-600">Concentracion de registros agregados en el periodo consultado.</p></div><p className="text-3xl font-black text-slate-950">{formatNumber(territory.total)} <span className="text-sm text-slate-500">casos</span></p></div>
            {territory.conductas?.length > 0 && <p className="mt-4 text-sm font-semibold text-slate-700">Conductas registradas: {territory.conductas.slice(0, 4).join(', ')}.</p>}
          </section>}

          <section className="border border-slate-200 bg-white p-5 text-sm font-semibold leading-6 text-slate-600 shadow-sm"><div className="flex items-start gap-3"><CalendarDays className="mt-0.5 shrink-0 text-[#281FD0]" size={19} /><p><strong className="text-slate-900">Fuentes institucionales separadas:</strong> Inspecciones de Policia y Comisarias de Familia conservan sus propios cortes y se consultan en sus modulos. No se mezclan ni se suman con los registros de Policia Nacional en este mapa.</p></div></section>
        </main>
      </div>
    </div>
  );
};

export default OperationalTerritoryMap;
