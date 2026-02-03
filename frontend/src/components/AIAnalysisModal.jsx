import React, { useState, useEffect } from 'react';
import { Check, AlertTriangle, X, Brain, Loader } from 'lucide-react';
import { analyzeData } from '../utils/aiAnalysis';

const AIAnalysisModal = ({ isOpen, onClose, data, onConfirm }) => {
    const [isAnalyzing, setIsAnalyzing] = useState(true);
    const [analyzedData, setAnalyzedData] = useState([]);
    const [analysisSummary, setAnalysisSummary] = useState({
        total: 0,
        issues: 0,
        corrections: 0
    });

    useEffect(() => {
        if (isOpen) {
            const performAnalysis = async () => {
                try {
                    const results = await analyzeData(data);

                    const issuesCount = results.filter(r => r.status === 'error').length;
                    const correctionsCount = results.filter(r => r.status === 'warning' && r.message.includes('corregida')).length; // Simple heuristic

                    setAnalyzedData(results);
                    setAnalysisSummary({
                        total: results.length,
                        issues: issuesCount,
                        corrections: correctionsCount
                    });
                } catch (error) {
                    console.error("Analysis failed", error);
                } finally {
                    setIsAnalyzing(false);
                }
            };

            performAnalysis();
        }
    }, [isOpen, data]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
                {/* Header */}
                <div className="p-6 bg-slate-900 text-white flex justify-between items-center">
                    <div className="flex items-center space-x-3">
                        <div className="p-2 bg-primary/20 rounded-lg">
                            <Brain className="text-primary w-6 h-6" />
                        </div>
                        <div>
                            <h3 className="text-xl font-bold">Análisis de Datos IA</h3>
                            <p className="text-slate-400 text-sm">Validación y enriquecimiento automático</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
                        <X size={24} />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 bg-slate-50">
                    {isAnalyzing ? (
                        <div className="flex flex-col items-center justify-center h-64 space-y-4">
                            <Loader className="w-12 h-12 text-primary animate-spin" />
                            <p className="text-slate-600 font-medium animate-pulse">Analizando patrones y validando registros...</p>
                        </div>
                    ) : (
                        <div className="space-y-6">
                            {/* Summary Cards */}
                            <div className="grid grid-cols-3 gap-4">
                                <div className="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
                                    <p className="text-sm text-slate-500">Total Registros</p>
                                    <p className="text-2xl font-bold text-slate-800">{analysisSummary.total}</p>
                                </div>
                                <div className="bg-white p-4 rounded-lg shadow-sm border border-orange-200 bg-orange-50">
                                    <p className="text-sm text-orange-600">Correcciones Sugeridas</p>
                                    <p className="text-2xl font-bold text-orange-700">{analysisSummary.corrections}</p>
                                </div>
                                <div className="bg-white p-4 rounded-lg shadow-sm border border-red-200 bg-red-50">
                                    <p className="text-sm text-red-600">Problemas Detectados</p>
                                    <p className="text-2xl font-bold text-red-700">{analysisSummary.issues}</p>
                                </div>
                            </div>

                            {/* Results Table */}
                            <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                                <table className="w-full text-left text-sm">
                                    <thead className="bg-slate-50 border-b border-slate-200">
                                        <tr>
                                            <th className="p-3 font-semibold text-slate-600">Estado</th>
                                            <th className="p-3 font-semibold text-slate-600">Fecha</th>
                                            <th className="p-3 font-semibold text-slate-600">Tipo</th>
                                            <th className="p-3 font-semibold text-slate-600">Barrio</th>
                                            <th className="p-3 font-semibold text-slate-600">Análisis IA</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100">
                                        {analyzedData.map((item, idx) => (
                                            <tr key={idx} className="hover:bg-slate-50">
                                                <td className="p-3">
                                                    {item.status === 'ok' && <Check size={18} className="text-green-500" />}
                                                    {item.status === 'warning' && <AlertTriangle size={18} className="text-orange-500" />}
                                                    {item.status === 'error' && <X size={18} className="text-red-500" />}
                                                </td>
                                                <td className="p-3 text-slate-700">{item.corrected.fecha}</td>
                                                <td className="p-3">
                                                    <span className={item.original.tipo !== item.corrected.tipo ? 'text-orange-600 font-medium' : 'text-slate-700'}>
                                                        {item.corrected.tipo}
                                                    </span>
                                                </td>
                                                <td className="p-3">
                                                    <span className={item.original.barrio !== item.corrected.barrio ? 'text-orange-600 font-medium' : 'text-slate-700'}>
                                                        {item.corrected.barrio}
                                                    </span>
                                                </td>
                                                <td className="p-3 text-slate-500 italic">
                                                    {item.message || <span className="text-green-600 text-xs">Validado correctamente</span>}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-slate-200 bg-white flex justify-end space-x-3">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 font-medium"
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={() => onConfirm(analyzedData.map(a => a.corrected))}
                        disabled={isAnalyzing}
                        className="px-6 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center shadow-lg shadow-primary/20"
                    >
                        {isAnalyzing ? 'Procesando...' : 'Confirmar e Integrar'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AIAnalysisModal;
