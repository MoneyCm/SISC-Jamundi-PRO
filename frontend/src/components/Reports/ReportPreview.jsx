import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../utils/apiConfig';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, Legend } from 'recharts';
import { Activity, Shield, TrendingDown, TrendingUp, Minus, SearchX } from 'lucide-react';

const ReportPreview = ({ fuente, fechaInicio, fechaFin }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchPreviewData = async () => {
            setLoading(true);
            try {
                const token = localStorage.getItem('token');
                // Llama al mismo endpoint que usa el dashboard para estadísticas en lugar de generar un PDF
                const base = `${API_BASE_URL}/analitica/estadisticas`;

                const [kpiRes, distRes, compRes] = await Promise.all([
                    fetch(`${base}/kpis?start_date=${fechaInicio}&end_date=${fechaFin}&fuente=${fuente}`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    }),
                    fetch(`${base}/distribucion?start_date=${fechaInicio}&end_date=${fechaFin}&fuente=${fuente}`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    }),
                    fetch(`${base}/comparativa?start1=${fechaInicio}&end1=${fechaFin}&start2=2024-01-01&end2=2024-12-31&fuente=${fuente}`, { // Comparativa provisional
                        headers: { 'Authorization': `Bearer ${token}` }
                    }).catch(() => null)
                ]);

                if (kpiRes.ok && distRes.ok) {
                    const kpis = await kpiRes.json();
                    let distribucion = await distRes.json();
                    // Limpiar etiquetas largas de MinDefensa
                    distribucion = distribucion.map(d => ({
                        ...d,
                        name: d.name.replace("Carga Directa: ", "").replace("Local Sync: ", "").replace("HURTO ", "HURTO A ")
                    }));

                    let comparativa = null;
                    if (compRes && compRes.ok) {
                        comparativa = await compRes.json();
                    }

                    setData({ kpis, distribucion, comparativa });
                } else {
                    setData(null);
                }
            } catch (err) {
                console.error("Error preview:", err);
                setData(null);
            } finally {
                setLoading(false);
            }
        };

        fetchPreviewData();
    }, [fuente, fechaInicio, fechaFin]);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center bg-slate-50 rounded-3xl animate-pulse">
                <div className="text-center text-slate-400">
                    <Activity size={32} className="mx-auto mb-3 animate-spin" />
                    <p className="font-bold text-xs uppercase tracking-widest">Calculando Análisis...</p>
                </div>
            </div>
        );
    }

    if (!data || !data.distribucion || data.distribucion.length === 0) {
        return (
            <div className="h-full flex flex-col items-center justify-center bg-white rounded-3xl border border-dashed border-slate-200">
                <div className="p-4 bg-slate-50 rounded-full mb-4">
                    <SearchX size={32} className="text-slate-300" />
                </div>
                <h4 className="text-lg font-black text-slate-800">Sin Datos para Mostrar</h4>
                <p className="text-sm font-medium text-slate-500 max-w-xs text-center mt-2">
                    La fuente <span className="font-bold">{fuente.replace('_', ' ')}</span> no tiene registros en el rango de fechas seleccionado.
                </p>
            </div>
        );
    }

    const { kpis, distribucion, comparativa } = data;
    const COLORS = ['#281FD0', '#384CF5', '#FFB600', '#F97316', '#FFE000', '#10B981', '#3B82F6', '#8B5CF6'];

    return (
        <div className="bg-white rounded-[2rem] shadow-xl border border-slate-100 overflow-hidden flex flex-col h-full animate-in fade-in slide-in-from-bottom-5 duration-700">
            {/* Header de la Vista Previa */}
            <div className="bg-[#281FD0] text-white p-6 relative overflow-hidden shrink-0">
                <div className="absolute -right-10 -top-10 w-40 h-40 bg-white/10 rounded-full blur-3xl mix-blend-overlay"></div>
                <div className="relative z-10 flex justify-between items-start">
                    <div>
                        <div className="flex items-center gap-2 text-[#FFE000] mb-2">
                            <Shield size={16} />
                            <span className="text-[10px] font-black uppercase tracking-[0.2em]">Inteligencia Estratégica</span>
                        </div>
                        <h3 className="text-2xl font-black tracking-tighter leading-none mb-1">Previsualización del Boletín</h3>
                        <p className="text-xs text-white/70 font-medium">Radiografía delictiva antes de exportar</p>
                    </div>
                </div>
            </div>

            <div className="p-6 overflow-y-auto flex-1 custom-scrollbar space-y-6">
                {/* KPIs */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Total Incidentes</p>
                        <p className="text-3xl font-black text-[#281FD0]">{kpis.total_incidentes}</p>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Tasa Homicidios</p>
                        <p className="text-3xl font-black text-slate-800">{kpis.tasa_homicidios}<span className="text-sm text-slate-400 ml-1 font-bold">/100k</span></p>
                    </div>
                </div>

                {/* Tendencia Comparativa (si existe) */}
                {comparativa && comparativa.cambios_porcentaje && (
                    <div className="p-4 bg-indigo-50/50 rounded-2xl border border-indigo-100/50 flex flex-col gap-3">
                        <div className="flex justify-between items-center">
                            <p className="text-xs font-black text-indigo-900 uppercase tracking-widest">Variación Total</p>
                            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-black ${comparativa.cambios_porcentaje.total > 0 ? 'bg-red-100 text-red-700' :
                                comparativa.cambios_porcentaje.total < 0 ? 'bg-emerald-100 text-emerald-700' :
                                    'bg-slate-200 text-slate-600'
                                }`}>
                                {comparativa.cambios_porcentaje.total > 0 ? <TrendingUp size={14} /> :
                                    comparativa.cambios_porcentaje.total < 0 ? <TrendingDown size={14} /> :
                                        <Minus size={14} />}
                                {Math.abs(comparativa.cambios_porcentaje.total)}%
                            </div>
                        </div>
                        <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${comparativa.cambios_porcentaje.total > 0 ? 'bg-red-500' : 'bg-emerald-500'}`} style={{ width: '40%' }}></div>
                        </div>
                    </div>
                )}

                {/* Gráfico de Distribución */}
                <div className="pt-2">
                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4">Composición del Mapa Criminal</p>
                    <div className="h-64 w-full relative">
                        {/* Círculo decorativo de fondo */}
                        <div className="absolute inset-0 m-auto w-32 h-32 rounded-full border-[10px] border-slate-50 -z-10"></div>

                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={distribucion}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={55}
                                    outerRadius={80}
                                    paddingAngle={3}
                                    dataKey="value"
                                    stroke="none"
                                >
                                    {distribucion.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <RechartsTooltip
                                    contentStyle={{ borderRadius: '1rem', border: 'none', boxShadow: '0 10px 25px rgba(0,0,0,0.1)', fontWeight: 'bold' }}
                                    itemStyle={{ color: '#3A3A44', fontSize: '14px' }}
                                />
                                <Legend
                                    layout="vertical"
                                    verticalAlign="middle"
                                    align="right"
                                    iconType="circle"
                                    iconSize={8}
                                    wrapperStyle={{ fontSize: '10px', fontWeight: '800', textTransform: 'uppercase', color: '#94a3b8' }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ReportPreview;
