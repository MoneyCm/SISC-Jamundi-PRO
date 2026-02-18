import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { ArrowUpRight, ArrowDownRight, AlertTriangle, Skull, Briefcase, Home, Activity, Clock, CheckCircle, AlertCircle, Brain } from 'lucide-react';

const iconMap = {
    AlertTriangle: AlertTriangle,
    Skull: Skull,
    Briefcase: Briefcase,
    Home: Home,
};

export const KPICard = ({ data }) => {
    const Icon = iconMap[data.icon] || AlertTriangle;
    // En contexto de seguridad: "up" o "negative" es MALO (Rojo)
    // "down" o "positive" es BUENO (Verde)
    const isNegative = data.trend === 'up' || data.trend === 'negative';
    const isNeutral = data.trend === 'neutral';

    return (
        <div className="bg-white p-4 md:p-6 rounded-xl shadow-sm border border-slate-100 hover:shadow-md transition-all duration-300 group">
            <div className="flex justify-between items-start mb-3 md:mb-4">
                <div className={`p-2 md:p-3 rounded-xl transition-colors ${isNegative ? 'bg-red-50 text-red-600 group-hover:bg-red-100' : 'bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100'}`}>
                    <Icon size={20} strokeWidth={2} className="md:w-6 md:h-6" />
                </div>
                <div className={`flex items-center space-x-1 text-[10px] md:text-sm font-bold px-2 py-1 rounded-full ${isNegative ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}>
                    <span>{data.change}</span>
                    {isNegative ? <ArrowUpRight size={12} className="md:w-3.5 md:h-3.5" /> : <ArrowDownRight size={12} className="md:w-3.5 md:h-3.5" />}
                </div>
            </div>
            <h3 className="text-slate-500 text-[10px] md:text-sm font-medium tracking-wide uppercase">{data.title}</h3>
            <p className="text-2xl md:text-3xl font-bold text-slate-800 mt-0.5 md:mt-1 tracking-tight">{data.value}</p>
        </div>
    );
};

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-white p-4 border border-slate-100 shadow-lg rounded-xl">
                <p className="text-sm font-bold text-slate-800 mb-2">{label}</p>
                {payload.map((entry, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm">
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                        <span className="text-slate-500 capitalize">{entry.name}:</span>
                        <span className="font-bold text-slate-800">{entry.value}</span>
                    </div>
                ))}
            </div>
        );
    }
    return null;
};

export const TrendChart = ({ data, year }) => {
    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-96 flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Activity size={20} className="text-primary" />
                    Tendencia Delictiva
                </h3>
                <span className="text-xs font-medium text-slate-400 bg-slate-50 px-2 py-1 rounded-md">{year || new Date().getFullYear()}</span>
            </div>
            <div className="flex-1 w-full min-h-[300px]">
                {(!data || data.length === 0) ? (
                    <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
                        <div className="p-4 bg-slate-50 rounded-full mb-3">
                            <Activity size={32} className="text-slate-300" />
                        </div>
                        <p className="text-sm font-medium">No hay datos de tendencia disponibles</p>
                        <p className="text-xs mt-1">Sube datos para visualizar el comportamiento.</p>
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%" debounce={100}>
                        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorHurtos" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#384CF5" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#384CF5" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="colorVif" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#FFB600" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#FFB600" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="colorHomicidios" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#281FD0" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#281FD0" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="colorLesiones" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#FFE000" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#FFE000" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} dy={10} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                            <Tooltip content={<CustomTooltip />} />
                            <Area type="monotone" dataKey="homicidios" stroke="#281FD0" strokeWidth={3} fillOpacity={1} fill="url(#colorHomicidios)" name="Homicidios" activeDot={{ r: 6, strokeWidth: 0 }} />
                            <Area type="monotone" dataKey="hurtos" stroke="#384CF5" strokeWidth={3} fillOpacity={1} fill="url(#colorHurtos)" name="Hurtos" activeDot={{ r: 6, strokeWidth: 0 }} />
                            <Area type="monotone" dataKey="vif" stroke="#FFB600" strokeWidth={3} fillOpacity={1} fill="url(#colorVif)" name="Violencia Intrafamiliar" activeDot={{ r: 6, strokeWidth: 0 }} />
                            <Area type="monotone" dataKey="lesiones" stroke="#FFE000" strokeWidth={3} fillOpacity={1} fill="url(#colorLesiones)" name="Lesiones Personales" activeDot={{ r: 6, strokeWidth: 0 }} />
                        </AreaChart>
                    </ResponsiveContainer>
                )}
            </div>
        </div>
    );
};

export const DistributionChart = ({ data }) => {
    const COLORS = ['#281FD0', '#384CF5', '#FFB600', '#FFE000', '#3A3A44'];

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-96 flex flex-col">
            <h3 className="text-lg font-bold text-slate-800 mb-2">Distribución por Delito</h3>
            <div className="flex-1 w-full min-h-[300px]">
                {(!data || data.length === 0) ? (
                    <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
                        <div className="p-4 bg-slate-50 rounded-full mb-3">
                            <Activity size={32} className="text-slate-300" />
                        </div>
                        <p className="text-sm font-medium">No hay distribución disponible</p>
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%" debounce={100}>
                        <PieChart>
                            <Pie
                                data={data}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={80}
                                paddingAngle={5}
                                dataKey="value"
                                stroke="none"
                            >
                                {data.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip content={<CustomTooltip />} />
                            <Legend
                                verticalAlign="bottom"
                                height={36}
                                iconType="circle"
                                iconSize={8}
                                formatter={(value) => <span className="text-xs text-slate-600 font-medium ml-1">{value}</span>}
                            />
                        </PieChart>
                    </ResponsiveContainer>
                )}
            </div>
        </div>
    );
};

const getStatusColor = (status) => {
    switch (status.toLowerCase()) {
        case 'atendido': return 'bg-emerald-50 text-emerald-600 border-emerald-100';
        case 'en proceso': return 'bg-blue-50 text-blue-600 border-blue-100';
        case 'remitido': return 'bg-amber-50 text-amber-600 border-amber-100';
        default: return 'bg-slate-50 text-slate-600 border-slate-100';
    }
};

const getStatusIcon = (status) => {
    switch (status.toLowerCase()) {
        case 'atendido': return <CheckCircle size={14} />;
        case 'en proceso': return <Clock size={14} />;
        case 'remitido': return <AlertCircle size={14} />;
        default: return <Activity size={14} />;
    }
};

export const RecentActivity = ({ data }) => {
    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-full">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-bold text-slate-800">Actividad Reciente</h3>
                <button className="text-xs font-medium text-primary hover:text-primary/80 transition-colors">Ver todo</button>
            </div>
            <div className="space-y-4">
                {data.map((item) => (
                    <div key={item.id} className="group flex items-start justify-between p-3 hover:bg-slate-50 rounded-xl transition-all border border-transparent hover:border-slate-100 cursor-default">
                        <div className="flex items-start space-x-3">
                            <div className="mt-1 w-2 h-2 rounded-full bg-primary ring-4 ring-primary/10"></div>
                            <div>
                                <p className="text-sm font-bold text-slate-800 group-hover:text-primary transition-colors">{item.type}</p>
                                <p className="text-xs text-slate-500 font-medium">{item.location}</p>
                            </div>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                            <span className={`flex items-center gap-1 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full border ${getStatusColor(item.status)}`}>
                                {getStatusIcon(item.status)}
                                {item.status}
                            </span>
                            <p className="text-[10px] text-slate-400 font-medium">{item.time}</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export const AIInsightWidget = ({ insight, loading, provider, onTechnicalReport }) => {
    return (
        <div className="bg-slate-900 p-6 rounded-xl shadow-xl border border-slate-800 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <Brain size={120} className="text-primary" />
            </div>
            <div className="relative z-10">
                <div className="flex items-center space-x-3 mb-4">
                    <div className="p-2 bg-primary/20 rounded-lg">
                        <Brain className="text-primary w-5 h-5" />
                    </div>
                    <h3 className="text-lg font-bold text-white">Perspectiva del SISC</h3>
                </div>
                {loading ? (
                    <div className="flex items-center space-x-3 text-slate-400">
                        <Activity className="animate-pulse w-4 h-4" />
                        <p className="text-sm italic">El SISC está sintetizando patrones...</p>
                    </div>
                ) : (
                    <p className="text-slate-300 text-sm leading-relaxed italic">
                        "{insight}"
                    </p>
                )}
                <div className="mt-4 flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-2 py-1 bg-white/5 rounded">
                        {provider || 'AI Analista'}
                    </span>
                    <button
                        onClick={onTechnicalReport}
                        className="text-xs text-primary font-bold hover:text-white transition-colors"
                    >
                        Ver reporte técnico
                    </button>
                </div>
            </div>
        </div>
    );
};

export const EarlyWarningWidget = ({ alerts = [] }) => {
    if (alerts.length === 0) return null;

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="text-red-500 animate-bounce" size={20} />
                <h3 className="text-lg font-bold text-slate-800">Alertas Tempranas Detectadas</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {alerts.map((alert, idx) => (
                    <div key={idx} className={`p-4 rounded-xl border-l-4 shadow-sm flex items-start gap-4 ${alert.nivel === 'CRÍTICO' ? 'bg-red-50 border-red-500' : 'bg-orange-50 border-orange-500'}`}>
                        <div className={`p-2 rounded-lg ${alert.nivel === 'CRÍTICO' ? 'bg-red-100 text-red-600' : 'bg-orange-100 text-orange-600'}`}>
                            <Activity size={20} />
                        </div>
                        <div>
                            <p className={`text-xs font-bold uppercase tracking-wider ${alert.nivel === 'CRÍTICO' ? 'text-red-600' : 'text-orange-600'}`}>{alert.nivel}</p>
                            <p className="text-sm text-slate-800 font-medium mt-1">{alert.mensaje}</p>
                            <p className="text-[10px] text-slate-500 mt-2">Tendencia: {alert.anterior} → {alert.actual} casos</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
