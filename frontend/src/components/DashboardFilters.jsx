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

    const [showCustom, setShowCustom] = useState(false);
    const [tempCustom, setTempCustom] = useState({
        start: currentRange?.start || '',
        end: currentRange?.end || ''
    });

    const handlePresetSelect = (preset) => {
        setSelectedPreset(preset.name);
        onFilterChange(preset.getValue());
        setIsOpen(false);
        setShowCustom(false);
    };

    const handleApplyCustom = () => {
        if (!tempCustom.start || !tempCustom.end) return;
        setSelectedPreset('Rango Personalizado');
        onFilterChange({
            start: tempCustom.start,
            end: tempCustom.end
        });
        setIsOpen(false);
    };

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-4 bg-white/5 hover:bg-white/10 border border-white/10 px-5 py-2.5 rounded-2xl text-sm font-semibold text-white transition-all shadow-inner backdrop-blur-sm group active:scale-95"
            >
                <div className="bg-primary/20 p-1.5 rounded-lg group-hover:bg-primary/30 transition-colors">
                    <Calendar size={16} className="text-primary" />
                </div>
                <div className="flex flex-col items-start leading-tight">
                    <span className="text-[9px] text-white/40 uppercase font-black tracking-[0.2em]">{selectedPreset}</span>
                    <span className="text-white font-black tracking-tight text-sm">{rangeLabel}</span>
                </div>
                <div className="h-6 w-px bg-white/10 ml-2 mr-1"></div>
                <ChevronDown size={16} className={`text-white/30 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && (
                <>
                    <div className="fixed inset-0 z-40 transition-opacity" onClick={() => setIsOpen(false)}></div>
                    <div className="absolute top-full right-0 mt-4 w-72 bg-slate-900/95 border border-white/10 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-200 backdrop-blur-2xl">
                        <div className="p-3">
                            <div className="flex items-center gap-2 px-3 py-3 mb-1 border-b border-white/5">
                                <Filter size={12} className="text-primary" />
                                <p className="text-[10px] font-black text-white/40 uppercase tracking-[0.2em]">Seleccionar Inteligencia</p>
                            </div>
                            <div className="space-y-1">
                                {presets.map((preset) => (
                                    <button
                                        key={preset.name}
                                        onClick={() => handlePresetSelect(preset)}
                                        className={`w-full text-left px-4 py-3 text-sm rounded-2xl transition-all flex items-center justify-between group ${selectedPreset === preset.name && !showCustom
                                            ? 'bg-primary text-white font-bold shadow-lg shadow-primary/20'
                                            : 'text-white/60 hover:bg-white/5 hover:text-white'
                                            }`}
                                    >
                                        <span className="tracking-tight">{preset.name}</span>
                                        {selectedPreset === preset.name && !showCustom ? (
                                            <div className="w-2 h-2 rounded-full bg-white shadow-[0_0_8px_white]" />
                                        ) : (
                                            <div className="w-1.5 h-1.5 rounded-full bg-white/10 group-hover:bg-white/30 transition-colors" />
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="bg-white/[0.02] p-4 border-t border-white/5 flex flex-col gap-3">
                            <button
                                onClick={() => setShowCustom(!showCustom)}
                                className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl text-[10px] font-black transition-all uppercase tracking-widest border ${showCustom
                                    ? 'bg-white/10 border-white/20 text-white'
                                    : 'bg-white/5 border-white/5 text-white/50 hover:text-white'}`}
                            >
                                <Calendar size={14} />
                                Rango Personalizado
                            </button>

                            {showCustom && (
                                <div className="space-y-3 pt-1 animate-in slide-in-from-top-2 duration-300">
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="flex flex-col gap-1">
                                            <label className="text-[9px] font-bold text-white/30 uppercase tracking-widest pl-1">Inicio</label>
                                            <input
                                                type="date"
                                                value={tempCustom.start}
                                                onChange={(e) => setTempCustom({...tempCustom, start: e.target.value})}
                                                className="bg-white/10 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-primary transition-colors"
                                            />
                                        </div>
                                        <div className="flex flex-col gap-1">
                                            <label className="text-[9px] font-bold text-white/30 uppercase tracking-widest pl-1">Fin</label>
                                            <input
                                                type="date"
                                                value={tempCustom.end}
                                                onChange={(e) => setTempCustom({...tempCustom, end: e.target.value})}
                                                className="bg-white/10 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-primary transition-colors"
                                            />
                                        </div>
                                    </div>
                                    <button
                                        onClick={handleApplyCustom}
                                        disabled={!tempCustom.start || !tempCustom.end}
                                        className="w-full bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed text-white text-[10px] font-black py-3 rounded-xl transition-all shadow-lg shadow-primary/20 uppercase tracking-widest"
                                    >
                                        Aplicar Filtro
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default DashboardFilters;
