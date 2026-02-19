import React, { useState } from 'react';
import { Calendar, ChevronDown, RefreshCcw, Filter } from 'lucide-react';

const DashboardFilters = ({ onFilterChange, referenceDate, currentRange }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [selectedPreset, setSelectedPreset] = useState('Este Mes');

    // Formatear fechas para mostrar en el botón
    const formatDate = (dateStr) => {
        if (!dateStr) return '';
        const d = new Date(dateStr + 'T00:00:00');
        const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
        return `${d.getDate()} ${months[d.getMonth()]}`;
    };

    const rangeLabel = currentRange
        ? `${formatDate(currentRange.start)} - ${formatDate(currentRange.end)}`
        : selectedPreset;

    // Default dates based on referenceDate
    const today = referenceDate || new Date();

    const presets = [
        { name: 'Hoy', getValue: () => ({ start: today.toISOString().split('T')[0], end: today.toISOString().split('T')[0] }) },
        {
            name: 'Este Mes', getValue: () => {
                const start = new Date(today.getFullYear(), today.getMonth(), 1);
                const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                return { start: start.toISOString().split('T')[0], end: end.toISOString().split('T')[0] };
            }
        },
        { name: 'Acumulado Anual', getValue: () => ({ start: `${today.getFullYear()}-01-01`, end: today.toISOString().split('T')[0] }) },
        {
            name: 'Últimos 12 Meses', getValue: () => {
                const start = new Date(today.getFullYear() - 1, today.getMonth() + 1, 1);
                return { start: start.toISOString().split('T')[0], end: today.toISOString().split('T')[0] };
            }
        },
        {
            name: 'Comparar vs Año Anterior', getValue: () => {
                const start = new Date(today.getFullYear(), today.getMonth(), 1);
                const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                const startPrev = new Date(today.getFullYear() - 1, today.getMonth(), 1);
                const endPrev = new Date(today.getFullYear() - 1, today.getMonth() + 1, 0);
                return {
                    start: start.toISOString().split('T')[0],
                    end: end.toISOString().split('T')[0],
                    compare: true,
                    startCompare: startPrev.toISOString().split('T')[0],
                    endCompare: endPrev.toISOString().split('T')[0]
                };
            }
        }
    ];

    const handlePresetSelect = (preset) => {
        setSelectedPreset(preset.name);
        onFilterChange(preset.getValue());
        setIsOpen(false);
    };

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 bg-white border border-slate-200 px-4 py-2.5 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
            >
                <Calendar size={16} className="text-primary" />
                <div className="flex flex-col items-start leading-none">
                    <span className="text-[10px] text-slate-400 uppercase font-black tracking-widest">{selectedPreset}</span>
                    <span className="text-primary font-black tracking-tight">{rangeLabel}</span>
                </div>
                <ChevronDown size={14} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && (
                <div className="absolute top-full right-0 mt-2 w-64 bg-white rounded-xl shadow-xl border border-slate-100 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="p-2">
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 py-2">Seleccionar Periodo</p>
                        {presets.map((preset) => (
                            <button
                                key={preset.name}
                                onClick={() => handlePresetSelect(preset)}
                                className={`w-full text-left px-3 py-2.5 text-sm rounded-lg transition-colors flex items-center justify-between group ${selectedPreset === preset.name
                                    ? 'bg-primary/10 text-primary font-bold'
                                    : 'text-slate-600 hover:bg-slate-50'
                                    }`}
                            >
                                {preset.name}
                                {selectedPreset === preset.name && <div className="w-1.5 h-1.5 rounded-full bg-primary" />}
                            </button>
                        ))}
                    </div>
                    <div className="bg-slate-50 p-3 border-t border-slate-100">
                        <button className="w-full flex items-center justify-center gap-2 text-xs font-bold text-slate-400 hover:text-slate-600 transition-colors uppercase tracking-tight">
                            <Filter size={12} />
                            Rango Personalizado
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DashboardFilters;
