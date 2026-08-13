import React from 'react';
import {
    Activity,
    AlertTriangle,
    ArrowDownRight,
    ArrowRight,
    ArrowUpRight,
    Brain,
    CheckCircle2,
    FileText,
    MapPin,
    Minus,
    ShieldCheck,
} from 'lucide-react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    LabelList,
    Legend,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

const TERRITORY_PLACEHOLDERS = ['PENDIENTE', 'POR ASIGNAR', 'NO APLICA', 'SIN LOCALIDAD', 'SIN COMUNA', 'NAN'];

const cleanTerritory = (value) => {
    const normalized = String(value || '').trim();
    if (!normalized || TERRITORY_PLACEHOLDERS.some((item) => normalized.toUpperCase().includes(item))) {
        return 'Ubicación no clasificada';
    }
    return normalized;
};

export const MetricCard = ({ metric }) => {
    const Icon = metric.icon;
    const trendStyles = metric.trend === 'negative'
        ? 'text-red-700 bg-red-50'
        : metric.trend === 'positive'
            ? 'text-emerald-700 bg-emerald-50'
            : 'text-slate-600 bg-slate-100';
    const TrendIcon = metric.trend === 'negative' ? ArrowUpRight : metric.trend === 'positive' ? ArrowDownRight : Minus;

    return (
        <article className="bg-white border border-slate-200 rounded-lg p-4 min-h-[142px] flex flex-col justify-between">
            <div className="flex items-start justify-between gap-3">
                <div className="p-2 rounded-lg bg-primary/5 text-primary"><Icon size={20} /></div>
                <span className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-bold ${trendStyles}`}><TrendIcon size={12} />{metric.changeText}</span>
            </div>
            <div>
                <p className="text-[11px] font-bold uppercase text-slate-500 mt-4">{metric.label}</p>
                <div className="flex items-end justify-between gap-2"><p className="text-3xl font-black text-slate-900">{Number(metric.value || 0).toLocaleString('es-CO')}</p><p className="text-[10px] text-slate-500 text-right">Referencia: {Number(metric.previous || 0).toLocaleString('es-CO')}</p></div>
            </div>
        </article>
    );
};

const ChartTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
        <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs">
            <p className="font-bold text-slate-900 mb-2">{label}</p>
            {payload.map((item) => <p key={item.dataKey} className="flex justify-between gap-5 py-0.5"><span style={{ color: item.color }}>{item.name}</span><strong>{Number(item.value || 0).toLocaleString('es-CO')}</strong></p>)}
        </div>
    );
};

export const TrendChart = ({ data = [] }) => (
    <article className="bg-white border border-slate-200 rounded-lg p-4 md:p-5 h-[390px] flex flex-col">
        <div className="mb-4"><h3 className="font-black text-slate-900">Evolución durante el periodo</h3><p className="text-xs text-slate-500">Registros únicos por fecha, semana o mes según el rango seleccionado.</p></div>
        <div className="flex-1 min-h-0">
            {data.length === 0 ? <div className="h-full flex items-center justify-center text-sm text-slate-500">Sin datos de tendencia para este periodo.</div> : (
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}>
                        <CartesianGrid stroke="#e2e8f0" vertical={false} />
                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} minTickGap={24} />
                        <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
                        <Line isAnimationActive={false} type="monotone" dataKey="homicidios" name="Homicidios" stroke="#111827" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                        <Line isAnimationActive={false} type="monotone" dataKey="hurtos" name="Hurtos" stroke="#281FD0" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                        <Line isAnimationActive={false} type="monotone" dataKey="vif" name="V. intrafamiliar" stroke="#0f766e" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                        <Line isAnimationActive={false} type="monotone" dataKey="lesiones" name="Lesiones" stroke="#d97706" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                    </LineChart>
                </ResponsiveContainer>
            )}
        </div>
    </article>
);

export const DistributionChart = ({ data = [] }) => {
    const rows = data.slice(0, 6);
    const colors = ['#281FD0', '#0f766e', '#d97706', '#334155', '#475569', '#64748b'];
    return (
        <article className="bg-white border border-slate-200 rounded-lg p-4 md:p-5 h-[390px] flex flex-col">
            <div className="mb-4"><h3 className="font-black text-slate-900">Conductas con más registros</h3><p className="text-xs text-slate-500">Cantidad agregada en el periodo seleccionado.</p></div>
            <div className="flex-1 min-h-0">
                {rows.length === 0 ? <div className="h-full flex items-center justify-center text-sm text-slate-500">Sin distribución disponible.</div> : (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 36, left: 6, bottom: 0 }}>
                            <CartesianGrid stroke="#e2e8f0" horizontal={false} />
                            <XAxis type="number" hide />
                            <YAxis type="category" dataKey="name" width={132} axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 10, fontWeight: 600 }} />
                            <Tooltip content={<ChartTooltip />} cursor={{ fill: '#f8fafc' }} />
                            <Bar isAnimationActive={false} dataKey="value" name="Registros" radius={[0, 4, 4, 0]} barSize={18}>
                                {rows.map((row, index) => <Cell key={row.name} fill={colors[index % colors.length]} />)}
                                <LabelList dataKey="value" position="right" fill="#0f172a" fontSize={11} fontWeight={700} />
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                )}
            </div>
        </article>
    );
};

export const AlertsPanel = ({ alerts = [], updatedAt, onOpen }) => {
    const visibleAlerts = alerts
        .filter((alert) => !TERRITORY_PLACEHOLDERS.some((value) => `${alert.titulo || ''} ${alert.mensaje || ''}`.toUpperCase().includes(value)))
        .slice(0, 3);
    return (
        <article className="bg-white border border-slate-200 rounded-lg p-5 h-full">
            <div className="flex items-start justify-between gap-3 mb-4"><div><h3 className="font-black text-slate-900">Alertas estadísticas</h3><p className="text-xs text-slate-500">Cambios detectados frente al periodo de referencia.</p></div><AlertTriangle size={20} className="text-amber-600" /></div>
            {visibleAlerts.length === 0 ? (
                <div className="border border-emerald-100 bg-emerald-50 rounded-lg p-4 flex gap-3"><CheckCircle2 size={20} className="text-emerald-700 shrink-0" /><div><p className="text-sm font-bold text-emerald-900">Sin alertas priorizadas</p><p className="text-xs text-emerald-800 mt-1">No se generaron advertencias con los datos disponibles.</p></div></div>
            ) : <div className="divide-y divide-slate-100">{visibleAlerts.map((alert, index) => <div key={`${alert.titulo}-${index}`} className="py-3 first:pt-0"><div className="flex items-center justify-between gap-2"><span className={`text-[10px] font-bold rounded px-2 py-1 ${alert.nivel === 'P1' ? 'bg-red-50 text-red-700' : alert.nivel === 'P2' ? 'bg-amber-50 text-amber-800' : 'bg-blue-50 text-blue-700'}`}>{alert.nivel || 'Aviso'}</span><span className="text-xs font-bold text-slate-600">{alert.variacion && alert.variacion !== 'N/A' ? alert.variacion : ''}</span></div><p className="text-sm font-bold text-slate-900 mt-2">{alert.titulo || 'Cambio relevante'}</p><p className="text-xs text-slate-600 mt-1 leading-relaxed">{alert.mensaje}</p></div>)}</div>}
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between gap-3"><p className="text-[10px] text-slate-500">Actualizado: {updatedAt ? new Date(updatedAt).toLocaleString('es-CO') : 'según último cálculo'}</p>{onOpen && <button onClick={onOpen} className="text-xs font-bold text-primary inline-flex items-center gap-1">Ver alertas <ArrowRight size={14} /></button>}</div>
        </article>
    );
};

export const AIAnalysisPanel = ({ insight, provider, loading, onOpen, onDownload }) => {
    const cleanInsight = String(insight || '').replace(/\*\*/g, '').trim();
    return (
        <article className="bg-slate-900 text-white rounded-lg p-5 h-full flex flex-col">
            <div className="flex items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase text-yellow-300">Análisis asistido por IA</p><h3 className="font-black text-lg mt-1">Lectura ejecutiva</h3></div><div className="p-2 rounded-lg bg-white/10"><Brain size={20} /></div></div>
            <div className="flex-1 py-5">
                {loading ? <div className="space-y-2 animate-pulse"><div className="h-3 bg-white/10 rounded w-full" /><div className="h-3 bg-white/10 rounded w-5/6" /><div className="h-3 bg-white/10 rounded w-3/5" /></div> : <p className="text-sm leading-6 text-slate-200">{cleanInsight || 'No hay una lectura asistida disponible para este corte.'}</p>}
            </div>
            <div className="pt-4 border-t border-white/10 flex flex-wrap items-center justify-between gap-3"><div><p className="text-[9px] uppercase text-slate-400 font-bold">Proveedor</p><p className="text-xs font-semibold">{provider || 'No disponible'}</p></div><div className="flex gap-2"><button onClick={onDownload} title="Descargar resumen detallado" className="p-2 rounded-lg border border-white/20 hover:bg-white/10"><FileText size={17} /></button><button onClick={onOpen} className="px-3 py-2 rounded-lg bg-white text-slate-900 text-xs font-bold">Abrir análisis</button></div></div>
        </article>
    );
};

export const RecentRecords = ({ data = [], onOpen }) => (
    <article className="bg-white border border-slate-200 rounded-lg p-5 h-full">
        <div className="flex items-start justify-between gap-3 mb-4"><div><h3 className="font-black text-slate-900">Registros recientes</h3><p className="text-xs text-slate-500">Últimos hechos incluidos en el periodo.</p></div>{onOpen && <button onClick={onOpen} className="text-xs font-bold text-primary">Ver datos</button>}</div>
        {data.length === 0 ? <p className="text-sm text-slate-500 py-8 text-center">No hay registros para mostrar.</p> : <div className="divide-y divide-slate-100">{data.slice(0, 5).map((item) => <div key={item.id} className="py-3 first:pt-0 flex items-start gap-3"><div className="p-1.5 bg-slate-100 rounded text-slate-600 mt-0.5"><MapPin size={14} /></div><div className="min-w-0 flex-1"><p className="text-sm font-bold text-slate-900 truncate">{item.type}</p><p className="text-xs text-slate-500 truncate">{cleanTerritory(item.location)}</p></div><time className="text-[10px] text-slate-500 whitespace-nowrap">{item.time}</time></div>)}</div>}
    </article>
);

export const EmptyInstitutionalPanel = () => (
    <div className="bg-white border border-slate-200 rounded-lg p-6 flex items-start gap-3"><ShieldCheck className="text-primary shrink-0" size={22} /><div><p className="font-bold text-slate-900">Vista institucional limitada</p><p className="text-sm text-slate-600 mt-1">Su nivel actual permite consultar indicadores agregados. El mapa detallado, las alertas y la bandeja requieren acceso N2.</p></div></div>
);
