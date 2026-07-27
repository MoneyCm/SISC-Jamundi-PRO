import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { ArrowUpRight, ArrowDownRight, AlertTriangle, Skull, Briefcase, Home, Activity, Clock, CheckCircle, AlertCircle, Brain, Info, Users, X, FileText, UserMinus, Car, PhoneForwarded, ShieldCheck, Zap, ArrowRight } from 'lucide-react';

const iconMap = {
    AlertTriangle: AlertTriangle,
    Skull: Skull,
    Briefcase: Briefcase,
    Home: Home,
    Users: Users,
    Activity: Activity,
    UserMinus: UserMinus,
    Car: Car,
    PhoneForwarded: PhoneForwarded,
};

export const KPICard = ({ data }) => {
    const Icon = iconMap[data.icon] || AlertTriangle;
    const isNegative = data.trend === 'up' || data.trend === 'negative';
    const isNeutral = data.trend === 'neutral';

    return (
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 hover:shadow-xl hover:border-primary/20 transition-all duration-500 group relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-slate-50 rounded-full -mr-10 -mt-10 group-hover:bg-primary/5 transition-colors duration-500" />

            <div className="relative z-10">
                <div className="flex justify-between items-start mb-5">
                    <div className={`p-3 rounded-2xl transition-all duration-500 ${isNegative ? 'bg-red-50 text-red-600 group-hover:bg-red-600 group-hover:text-white' : 'bg-primary/5 text-primary group-hover:bg-primary group-hover:text-white'}`}>
                        <Icon size={24} strokeWidth={2.5} />
                    </div>
                    <div className={`flex items-center space-x-1 text-[10px] font-black px-2.5 py-1 rounded-lg border ${isNegative ? 'bg-red-50 text-red-600 border-red-100' : 'bg-emerald-50 text-emerald-600 border-emerald-100'}`}>
                        <span>{data.change}</span>
                        {isNeutral ? null : isNegative ? <ArrowUpRight size={12} strokeWidth={3} /> : <ArrowDownRight size={12} strokeWidth={3} />}
                    </div>
                </div>
                <h3 className="text-slate-400 text-[10px] font-black tracking-[0.15em] uppercase mb-1">{data.title}</h3>
                <p className="text-3xl font-black text-slate-800 tracking-tighter">{data.value}</p>
            </div>
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
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 h-96 flex flex-col transition-all hover:shadow-lg">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-black text-slate-800 flex items-center gap-2 font-titles uppercase tracking-tight">
                    <Activity size={20} className="text-primary" />
                    Tendencia Delictiva
                </h3>
                <span className="text-[10px] font-black text-slate-400 bg-slate-50 border border-slate-100 px-3 py-1 rounded-full uppercase tracking-widest">{year || new Date().getFullYear()}</span>
            </div>
            <div className="flex-1 w-full min-h-[300px]">
                {(!data || data.length === 0) ? (
                    <div className="w-full h-full flex flex-col items-center justify-center text-slate-400 italic">
                        <Activity size={32} className="text-slate-200 mb-3" />
                        <p className="text-xs font-bold uppercase tracking-widest">Sin datos de tendencia</p>
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%" debounce={100}>
                        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorHurtos" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#281FD0" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#281FD0" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="colorVif" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#FFB600" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#FFB600" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="colorHomicidios" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3A3A44" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#3A3A44" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="colorLesiones" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#FFE000" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#FFE000" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10, fontWeight: 700 }} dy={10} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10, fontWeight: 700 }} />
                            <Tooltip content={<CustomTooltip />} />
                            <Area type="monotone" dataKey="homicidios" stroke="#3A3A44" strokeWidth={3} fillOpacity={1} fill="url(#colorHomicidios)" name="Homicidios" activeDot={{ r: 6, strokeWidth: 0 }} />
                            <Area type="monotone" dataKey="hurtos" stroke="#281FD0" strokeWidth={3} fillOpacity={1} fill="url(#colorHurtos)" name="Hurtos" activeDot={{ r: 6, strokeWidth: 0 }} />
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
    if (!status) return 'bg-slate-50 text-slate-600 border-slate-100';
    switch (status.toLowerCase()) {
        case 'atendido': return 'bg-emerald-50 text-emerald-600 border-emerald-100';
        case 'en proceso': return 'bg-blue-50 text-blue-600 border-blue-100';
        case 'remitido': return 'bg-amber-50 text-amber-600 border-amber-100';
        default: return 'bg-slate-50 text-slate-600 border-slate-100';
    }
};

const getStatusIcon = (status) => {
    if (!status) return <Activity size={14} />;
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
    const [chatOpen, setChatOpen] = React.useState(false);
    const [messages, setMessages] = React.useState([]);
    const [input, setInput] = React.useState('');
    const [chatLoading, setChatLoading] = React.useState(false);
    const scrollRef = React.useRef(null);

    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, chatOpen]);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim() || chatLoading) return;

        const userMsg = { id: Date.now(), text: input, sender: 'user' };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setChatLoading(true);

        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/ia/chat_ciudadano`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: input })
            });

            if (!response.ok) throw new Error('Error de conexión');
            const data = await response.json();

            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                text: data.response || 'Error al procesar consulta.',
                sender: 'ai'
            }]);
        } catch (err) {
            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                text: 'Error de conexión con el servicio de IA.',
                sender: 'ai'
            }]);
        } finally {
            setChatLoading(false);
        }
    };

    return (
        <div className={`bg-white rounded-[2.5rem] shadow-sm border border-slate-100 relative overflow-hidden transition-all duration-700 ${chatOpen ? 'h-[550px]' : 'p-8'}`}>
            <div className="relative z-10 h-full flex flex-col">
                <div className={`flex items-center justify-between mb-6 ${chatOpen ? 'p-8 pb-2' : ''}`}>
                    <div className="flex items-center space-x-4">
                        <div className="p-3 bg-primary/10 rounded-2xl border border-primary/10">
                            <Brain className="text-primary w-6 h-6" />
                        </div>
                        <div>
                            <h3 className="text-xl font-black text-slate-800 tracking-tight font-titles uppercase">Análisis Estratégico IA</h3>
                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mt-1">SISC Cognition Engine</p>
                        </div>
                    </div>
                    {chatOpen && (
                        <button
                            onClick={() => setChatOpen(false)}
                            className="bg-slate-100 hover:bg-slate-200 p-2 rounded-xl text-slate-500 transition-all"
                        >
                            <X size={20} />
                        </button>
                    )}
                </div>

                {!chatOpen ? (
                    <>
                        <div className="bg-slate-50 border border-slate-100 rounded-2xl p-6 mb-6">
                            {loading ? (
                                <div className="flex flex-col gap-3">
                                    <div className="h-4 w-3/4 bg-slate-200 animate-pulse rounded"></div>
                                    <div className="h-4 w-1/2 bg-slate-200 animate-pulse rounded"></div>
                                    <p className="text-[10px] font-bold text-primary animate-pulse uppercase tracking-widest mt-2">Sintetizando Patrones Regionales...</p>
                                </div>
                            ) : (
                                <p className="text-slate-700 text-base leading-relaxed font-bold italic">
                                    <span className="text-primary font-black text-2xl mr-2">“</span>
                                    {insight}
                                    <span className="text-primary font-black text-2xl ml-1">”</span>
                                </p>
                            )}
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="flex flex-col">
                                    <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Motor de Análisis</span>
                                    <span className="text-xs font-bold text-slate-600">{provider || 'SISC Intelligence'}</span>
                                </div>
                                <div className="h-8 w-px bg-slate-200"></div>
                                <button
                                    onClick={() => setChatOpen(true)}
                                    className="flex items-center gap-2 text-xs font-black text-white hover:opacity-90 transition-all bg-primary px-4 py-2.5 rounded-xl shadow-md"
                                >
                                    <Activity size={14} className="animate-pulse" />
                                    CONSULTAR ANALISTA
                                </button>
                            </div>
                            <button
                                onClick={onTechnicalReport}
                                className="flex items-center gap-2 text-xs text-slate-400 font-bold hover:text-primary transition-colors group"
                            >
                                <FileText size={14} />
                                Descargar Análisis Detallado
                            </button>
                        </div>
                    </>
                ) : (
                    <>
                        <div ref={scrollRef} className="flex-1 overflow-y-auto px-8 py-4 space-y-6 scrollbar-thin scrollbar-thumb-slate-200">
                            <div className="flex justify-start">
                                <div className="max-w-[90%] p-4 rounded-3xl text-sm leading-relaxed bg-slate-100 text-slate-700 border border-slate-200 rounded-bl-none">
                                    <p className="font-bold text-primary text-[10px] uppercase tracking-widest mb-1">IA Institucional</p>
                                    Hola analista. He procesado las tendencias delictivas y medidas de convivencia del periodo actual. ¿En qué hallazgo específico desea profundizar?
                                </div>
                            </div>
                            {messages.map(msg => (
                                <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    <div className={`max-w-[90%] p-4 rounded-3xl text-sm leading-relaxed shadow-sm ${msg.sender === 'user'
                                        ? 'bg-primary text-white rounded-br-none font-bold'
                                        : 'bg-white text-slate-700 border border-slate-200 rounded-bl-none'}`}>
                                        {msg.text}
                                    </div>
                                </div>
                            ))}
                            {chatLoading && (
                                <div className="flex items-center gap-2 px-4 py-2 bg-slate-50 rounded-full w-fit">
                                    <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce"></div>
                                    <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce [animation-delay:0.2s]"></div>
                                    <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce [animation-delay:0.4s]"></div>
                                    <span className="text-[9px] text-slate-400 font-black uppercase tracking-widest ml-1">Procesando...</span>
                                </div>
                            )}
                        </div>
                        <form onSubmit={handleSend} className="p-6 bg-slate-50 border-t border-slate-200">
                            <div className="relative">
                                <input
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder="Interactuar con la inteligencia del SISC..."
                                    className="w-full bg-white border border-slate-200 text-slate-800 rounded-2xl px-6 py-4 text-sm focus:ring-2 focus:ring-primary outline-none transition-all pr-12 placeholder:text-slate-400 shadow-sm"
                                    disabled={chatLoading}
                                />
                                <button
                                    type="submit"
                                    disabled={!input.trim() || chatLoading}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 bg-primary p-2 rounded-xl text-white hover:opacity-90 disabled:bg-slate-300 transition-all"
                                >
                                    <ArrowUpRight size={18} strokeWidth={3} />
                                </button>
                            </div>
                        </form>
                    </>
                )}
            </div>
        </div>
    );
};

export const EarlyWarningWidget = ({ alerts = [] }) => {
    if (alerts.length === 0) return (
        <div className="bg-emerald-50/30 border border-emerald-100 p-6 rounded-[2rem] flex flex-col items-center justify-center text-center">
            <ShieldCheck className="text-emerald-500 mb-2 opacity-40" size={32} />
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-600">Sistema de Alertas Tempranas</p>
            <p className="text-xs text-emerald-800 font-bold mt-1">Situación Territorial Estable - Sin anomalías detectadas</p>
        </div>
    );

    const getTierConfig = (nivel) => {
        switch (nivel) {
            case 'P1': return {
                bg: 'bg-red-50', border: 'border-red-500/30', text: 'text-red-700',
                label: 'bg-red-600 text-white', icon: <Skull size={18} />, pulse: true
            };
            case 'P2': return {
                bg: 'bg-amber-50', border: 'border-amber-500/30', text: 'text-amber-800',
                label: 'bg-amber-500 text-white', icon: <AlertTriangle size={18} />, pulse: false
            };
            case 'P3': return {
                bg: 'bg-blue-50', border: 'border-blue-500/30', text: 'text-blue-800',
                label: 'bg-blue-500 text-white', icon: <Activity size={18} />, pulse: false
            };
            default: return {
                bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-700',
                label: 'bg-slate-500 text-white', icon: <Info size={18} />, pulse: false
            };
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                <div className="flex items-center gap-3">
                    <div className="bg-red-600 p-2 rounded-xl shadow-lg shadow-red-200 animate-pulse">
                        <Zap size={20} className="text-white fill-white" />
                    </div>
                    <div>
                        <h3 className="text-lg font-black text-slate-900 tracking-tight leading-none uppercase italic">S.A.T.</h3>
                        <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mt-1">Secretaría de Seguridad - Jamundí</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-emerald-500 rounded-full animate-ping"></span>
                    <span className="text-[9px] font-black text-emerald-600 uppercase tracking-widest">En Tiempo Real</span>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {alerts.map((alert, idx) => {
                    const config = getTierConfig(alert.nivel);
                    return (
                        <div key={idx} className={`relative overflow-hidden group p-5 rounded-[2rem] border ${config.border} ${config.bg} transition-all hover:scale-[1.02] hover:shadow-xl`}>
                            {config.pulse && <div className="absolute top-0 right-0 w-24 h-24 bg-red-400/10 rounded-full -mr-12 -mt-12 animate-ping"></div>}

                            <div className="flex items-start gap-4">
                                <div className={`p-3 rounded-2xl ${config.label} shadow-lg transition-transform group-hover:rotate-12`}>
                                    {config.icon}
                                </div>
                                <div className="flex-1">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full ${config.label}`}>
                                            Prioridad {alert.nivel}
                                        </span>
                                        {alert.variacion !== 'N/A' && (
                                            <span className="text-[10px] font-black text-red-600 flex items-center gap-0.5">
                                                <ArrowUpRight size={12} strokeWidth={3} /> {alert.variacion}
                                            </span>
                                        )}
                                    </div>
                                    <h4 className={`text-sm font-black ${config.text} uppercase tracking-tight`}>{alert.titulo}</h4>
                                    <p className="text-xs text-slate-600 font-medium mt-1 leading-relaxed">{alert.mensaje}</p>

                                    <div className="mt-4 flex items-center gap-4">
                                        <div className="flex flex-col">
                                            <span className="text-[8px] font-bold text-slate-400 uppercase tracking-widest">Actual</span>
                                            <span className={`text-sm font-black ${config.text}`}>{alert.valor_actual}</span>
                                        </div>
                                        <div className="w-px h-6 bg-slate-200"></div>
                                        <div className="flex flex-col">
                                            <span className="text-[8px] font-bold text-slate-400 uppercase tracking-widest">Histórico</span>
                                            <span className="text-sm font-black text-slate-400">{alert.valor_previo}</span>
                                        </div>
                                        <button className="ml-auto bg-white/50 backdrop-blur-sm p-2 rounded-xl border border-white opacity-0 group-hover:opacity-100 transition-all hover:bg-white hover:shadow-md">
                                            <ArrowRight size={14} className={config.text} />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export const CommunityInboxWidget = ({ items = [], loading }) => {
    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Users size={20} className="text-emerald-600" />
                    Bandeja de Participación
                </h3>
                <span className="text-[10px] font-bold bg-emerald-50 text-emerald-600 px-2 py-1 rounded-md uppercase tracking-wider">Ciudadanía</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin">
                {loading ? (
                    <div className="flex justify-center py-10 italic text-slate-400 text-sm">Cargando solicitudes...</div>
                ) : items.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10 text-slate-300">
                        <Users size={32} className="mb-2 opacity-20" />
                        <p className="text-xs font-medium uppercase tracking-widest">Sin solicitudes pendientes</p>
                    </div>
                ) : (
                    items.map((item) => (
                        <div key={item.id} className="p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-emerald-200 transition-all group">
                            <div className="flex justify-between items-start mb-2">
                                <span className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-tighter ${item.tipo === 'PROPUESTA' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
                                    }`}>
                                    {item.tipo}
                                </span>
                                <span className="text-[10px] text-slate-400">{new Date(item.fecha).toLocaleDateString()}</span>
                            </div>
                            <h4 className="text-sm font-bold text-slate-800 group-hover:text-emerald-700 transition-colors uppercase tracking-tight">{item.titulo}</h4>
                            <p className="text-[11px] text-slate-500 mt-1 font-medium italic">{item.subtitulo}</p>
                            <div className="mt-3 p-2 bg-white/50 rounded-lg border border-slate-200/50">
                                <p className="text-[11px] text-slate-600 leading-relaxed line-clamp-2">{item.descripcion}</p>
                            </div>
                        </div>
                    ))
                )}
            </div>

            <button className="mt-4 w-full py-2 text-xs font-bold text-slate-400 hover:text-emerald-600 border-t border-slate-50 transition-colors uppercase tracking-widest">
                Gestionar en Módulo Social
            </button>
        </div>
    );
};
