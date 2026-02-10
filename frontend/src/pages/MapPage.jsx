import React, { useState, useEffect } from 'react';
import MapComponent from '../components/Map/MapComponent';
import { Filter, Calendar, AlertTriangle, Loader2 } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const CATEGORIES = [
    'HOMICIDIO',
    'HURTO A PERSONAS',
    'HURTO A COMERCIO',
    'LESIONES PERSONALES',
    'VIOLENCIA INTRAFAMILIAR'
];

const MapPage = () => {
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

            const response = await fetch(`${API_BASE_URL}/analitica/eventos/geojson?${params.toString()}`);
            if (!response.ok) throw new Error('Error al cargar datos del mapa');

            const data = await response.json();
            setIncidents(data.features || []);
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

export default MapPage;
