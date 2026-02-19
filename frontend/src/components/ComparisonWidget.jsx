import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus, Activity, TrendingUp, TrendingDown } from 'lucide-react';

const ComparisonWidget = ({ comparisonData }) => {
    if (!comparisonData) return null;

    const { periodo_actual, periodo_anterior, cambios_porcentaje } = comparisonData;

    const renderMetric = (label, current, last, change, icon) => {
        const isNegative = change > 0; // En seguridad, que suba es malo
        const isNeutral = change === 0;

        return (
            <div className="flex flex-col p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-slate-200 transition-all">
                <div className="flex justify-between items-start mb-2">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{label}</span>
                    <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${isNeutral ? 'bg-slate-100 text-slate-500' :
                            isNegative ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-600'
                        }`}>
                        {isNeutral ? <Minus size={10} /> : isNegative ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                        {Math.abs(change)}%
                    </div>
                </div>
                <div className="flex items-baseline gap-2">
                    <span className="text-xl font-black text-slate-800">{current}</span>
                    <span className="text-xs text-slate-400 font-medium">vs {last}</span>
                </div>
            </div>
        );
    };

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 mb-6 animate-in slide-in-from-right duration-500">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-lg">
                        <Activity className="text-primary w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-slate-800 tracking-tight">Análisis Comparativo</h3>
                        <p className="text-[10px] text-slate-500 font-medium uppercase tracking-tight">Comparativa de periodos seleccionados</p>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {renderMetric("Homicidios", periodo_actual.homicidios, periodo_anterior.homicidios, cambios_porcentaje.homicidios)}
                {renderMetric("Otros Delitos", periodo_actual.otros, periodo_anterior.otros, cambios_porcentaje.otros)}
                {renderMetric("Total Incidentes", periodo_actual.total, periodo_anterior.total, cambios_porcentaje.total)}
            </div>

            <div className="mt-4 p-3 bg-primary/5 rounded-lg border border-primary/10 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center shadow-sm">
                    <Activity size={16} className="text-primary" />
                </div>
                <p className="text-xs text-slate-600 font-medium leading-relaxed">
                    El sistema detecta una {cambios_porcentaje.total > 0 ? 'tendencia al alza' : 'reducción'} del <span className="font-bold text-primary">{Math.abs(cambios_porcentaje.total)}%</span> en la criminalidad general comparado con el periodo anterior seleccionado.
                </p>
            </div>
        </div>
    );
};

export default ComparisonWidget;
