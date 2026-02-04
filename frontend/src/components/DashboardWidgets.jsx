import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { ArrowUpRight, ArrowDownRight, AlertTriangle, Skull, Briefcase, Home, Activity, Clock, CheckCircle, AlertCircle } from 'lucide-react';

const iconMap = {
    AlertTriangle: AlertTriangle,
    Skull: Skull,
    Briefcase: Briefcase,
    Home: Home,
};

export const KPICard = ({ data }) => {
    const Icon = iconMap[data.icon] || AlertTriangle;
    const isUp = data.trend === 'up';
    const isNeutral = data.trend === 'neutral';

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 hover:shadow-md transition-all duration-300 group">
            <div className="flex justify-between items-start mb-4">
                <div className={`p-3 rounded-xl transition-colors ${isUp ? 'bg-red-50 text-red-600 group-hover:bg-red-100' : 'bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100'}`}>
                    <Icon size={24} strokeWidth={2} />
                </div>
                <div className={`flex items-center space-x-1 text-sm font-bold px-2 py-1 rounded-full ${isUp ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}>
                    <span>{data.change}</span>
                    {isUp ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                </div>
            </div>
            <h3 className="text-slate-500 text-sm font-medium tracking-wide uppercase">{data.title}</h3>
            <p className="text-3xl font-bold text-slate-800 mt-1 tracking-tight">{data.value}</p>
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

export const TrendChart = ({ data }) => {
    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-96 flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Activity size={20} className="text-primary" />
                    Tendencia Delictiva
                </h3>
                <span className="text-xs font-medium text-slate-400 bg-slate-50 px-2 py-1 rounded-md">{new Date().getFullYear()}</span>
            </div>
            <div className="flex-1 w-full min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <defs>
                            <linearGradient id="colorHurtos" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="colorVif" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="colorHomicidios" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="colorLesiones" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} dy={10} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                        <Tooltip content={<CustomTooltip />} />
                        <Area type="monotone" dataKey="homicidios" stroke="#ef4444" strokeWidth={3} fillOpacity={1} fill="url(#colorHomicidios)" name="Homicidios" activeDot={{ r: 6, strokeWidth: 0 }} />
                        <Area type="monotone" dataKey="hurtos" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorHurtos)" name="Hurtos" activeDot={{ r: 6, strokeWidth: 0 }} />
                        <Area type="monotone" dataKey="vif" stroke="#f59e0b" strokeWidth={3} fillOpacity={1} fill="url(#colorVif)" name="Violencia Intrafamiliar" activeDot={{ r: 6, strokeWidth: 0 }} />
                        <Area type="monotone" dataKey="lesiones" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill="url(#colorLesiones)" name="Lesiones Personales" activeDot={{ r: 6, strokeWidth: 0 }} />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export const DistributionChart = ({ data }) => {
    const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-96 flex flex-col">
            <h3 className="text-lg font-bold text-slate-800 mb-2">Distribución por Delito</h3>
            <div className="flex-1 w-full min-h-0">
                <ResponsiveContainer width="100%" height="100%">
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
