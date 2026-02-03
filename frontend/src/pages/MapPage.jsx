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
    const [startDate, setStartDate] = useState('2024-01-01');
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
        <div className="flex h-full gap-4">
            {/* Sidebar de Filtros */}
            <div className="w-80 bg-white rounded-lg shadow-sm p-4 flex flex-col h-full overflow-y-auto">
                <div className="flex items-center space-x-2 mb-6 text-slate-700 border-b pb-4">
                    <Filter size={20} />
                    <h2 className="font-bold text-lg">Filtros</h2>
                </div>

                <div className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2 flex items-center">
                            <AlertTriangle size={16} className="mr-2 text-primary" />
                            Tipo de Delito
                        </label>
                        <div className="space-y-2">
                            {CATEGORIES.map((type) => (
                                <label key={type} className="flex items-center space-x-2 text-sm text-slate-600 cursor-pointer hover:text-slate-900 capitalize">
                                    <input
                                        type="checkbox"
                                        className="rounded border-slate-300 text-primary focus:ring-primary"
                                        checked={selectedCategories.includes(type)}
                                        onChange={() => handleCategoryToggle(type)}
                                    />
                                    <span>{type.toLowerCase()}</span>
                                </label>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2 flex items-center">
                            <Calendar size={16} className="mr-2 text-primary" />
                            Rango de Fechas
                        </label>
                        <div className="space-y-3">
                            <div>
                                <span className="text-[10px] uppercase font-bold text-slate-400">Desde</span>
                                <input
                                    type="date"
                                    value={startDate}
                                    onChange={(e) => setStartDate(e.target.value)}
                                    className="w-full border-slate-200 rounded-md text-sm focus:ring-primary focus:border-primary"
                                />
                            </div>
                            <div>
                                <span className="text-[10px] uppercase font-bold text-slate-400">Hasta</span>
                                <input
                                    type="date"
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    className="w-full border-slate-200 rounded-md text-sm focus:ring-primary focus:border-primary"
                                />
                            </div>
                        </div>
                    </div>

                    <button
                        onClick={fetchIncidents}
                        disabled={loading}
                        className="w-full bg-primary text-white py-2 px-4 rounded-md hover:bg-primary/90 transition-colors text-sm font-medium shadow-sm flex items-center justify-center space-x-2 disabled:opacity-50"
                    >
                        {loading && <Loader2 size={16} className="animate-spin" />}
                        <span>Aplicar Filtros</span>
                    </button>

                    {error && (
                        <p className="text-xs text-red-500 bg-red-50 p-2 rounded border border-red-100 italic">
                            {error}
                        </p>
                    )}
                </div>
            </div>

            {/* Área del Mapa */}
            <div className="flex-1 bg-white rounded-lg shadow-sm p-1 border border-slate-200 relative z-0 min-h-[500px]">
                <MapComponent incidents={incidents} />
            </div>
        </div>
    );
};

export default MapPage;
