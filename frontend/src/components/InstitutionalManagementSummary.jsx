import React, { useMemo } from 'react';
import {
    AlertTriangle,
    ArrowRight,
    CalendarClock,
    CheckCircle2,
    Gavel,
    HeartHandshake,
    LoaderCircle,
    RefreshCw,
} from 'lucide-react';

const SOURCE_CODES = {
    inspections: 'INSPECCIONES_RNMC',
    family: 'COMISARIAS_FAMILIA',
};

const STATUS_CONFIG = {
    aligned: { label: 'Corte completo', className: 'bg-emerald-50 text-emerald-800', Icon: CheckCircle2 },
    partial: { label: 'Corte parcial', className: 'bg-amber-50 text-amber-800', Icon: CalendarClock },
    stale: { label: 'Sin corte del periodo', className: 'bg-amber-50 text-amber-800', Icon: AlertTriangle },
    missing: { label: 'Sin datos', className: 'bg-slate-100 text-slate-700', Icon: AlertTriangle },
};

const formatNumber = (value) => Number(value || 0).toLocaleString('es-CO');

const formatDate = (value) => {
    if (!value) return 'No disponible';
    return new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })
        .format(new Date(`${value}T00:00:00`));
};

const formatMonth = (value) => {
    if (!value) return 'el último corte';
    const label = new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' })
        .format(new Date(`${value}T00:00:00`));
    return label.charAt(0).toUpperCase() + label.slice(1);
};

const comparisonText = (indicator) => {
    if (indicator?.comparison_value === null || indicator?.comparison_value === undefined) {
        return 'Sin base comparable';
    }
    if (Number(indicator.comparison_value) === 0) return 'Sin base comparable';
    if (indicator.variation_percentage === null || indicator.variation_percentage === undefined) {
        return `Referencia: ${formatNumber(indicator.comparison_value)}`;
    }
    const prefix = indicator.variation_percentage > 0 ? '+' : '';
    return `${prefix}${Number(indicator.variation_percentage).toFixed(1)}% · ref. ${formatNumber(indicator.comparison_value)}`;
};

const SourceStatus = ({ source }) => {
    const config = STATUS_CONFIG[source?.coverage_status] || STATUS_CONFIG.missing;
    const Icon = config.Icon;
    return (
        <span className={`inline-flex items-center gap-1.5 rounded px-2 py-1 text-[10px] font-black uppercase ${config.className}`}>
            <Icon size={12} />{config.label}
        </span>
    );
};

const IndicatorRows = ({ indicators, limit = 4 }) => (
    <div className="mt-4 border-t border-slate-100 divide-y divide-slate-100">
        {indicators.slice(0, limit).map((indicator) => {
            const context = indicator.metadata?.public_detail || indicator.metadata?.reporting_entity;
            const hasComparison = indicator.comparison_value !== null
                && indicator.comparison_value !== undefined
                && Number(indicator.comparison_value) !== 0;
            return (
                <div key={indicator.id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 py-3">
                    <div className="min-w-0">
                        <p className="text-sm font-bold leading-5 text-slate-900">{indicator.indicator_name}</p>
                        <p className="mt-0.5 text-[11px] leading-4 text-slate-500">{context || comparisonText(indicator)}</p>
                        {context && hasComparison && <p className="mt-1 text-[10px] font-bold text-primary">{comparisonText(indicator)}</p>}
                    </div>
                    <div className="text-right">
                        <p className="text-xl font-black tabular-nums text-slate-950">{formatNumber(indicator.value)}</p>
                        <p className="text-[10px] font-semibold text-slate-500">{indicator.unit}</p>
                    </div>
                </div>
            );
        })}
    </div>
);

const SourceUnavailable = ({ source, onUseCutoff }) => (
    <div className="mt-5 border-l-4 border-amber-400 bg-amber-50/70 px-4 py-3">
        <p className="text-sm font-bold text-slate-900">No hay cifras aprobadas para el periodo seleccionado.</p>
        <p className="mt-1 text-xs leading-5 text-slate-600">{source?.status_note || 'La fuente todavía no reporta este corte.'}</p>
        {source?.last_cutoff_date && onUseCutoff && (
            <button onClick={() => onUseCutoff(source.last_cutoff_date)} className="mt-3 inline-flex items-center gap-1.5 text-xs font-black text-primary">
                Ver {formatMonth(source.last_cutoff_date)} <ArrowRight size={14} />
            </button>
        )}
    </div>
);

const LoadingState = () => (
    <div className="min-h-56 flex items-center justify-center gap-3 text-sm font-semibold text-slate-600">
        <LoaderCircle size={20} className="animate-spin text-primary" /> Consultando cortes institucionales...
    </div>
);

const InstitutionalManagementSummary = ({
    summary,
    loading,
    error,
    onRetry,
    onNavigate,
    onUseCutoff,
}) => {
    const { sources, indicators } = useMemo(() => {
        const sourceMap = Object.fromEntries((summary?.sources || []).map((source) => [source.code, source]));
        const indicatorMap = (summary?.indicators || []).reduce((groups, indicator) => {
            groups[indicator.source_code] = [...(groups[indicator.source_code] || []), indicator];
            return groups;
        }, {});
        return { sources: sourceMap, indicators: indicatorMap };
    }, [summary]);

    const inspectionSource = sources[SOURCE_CODES.inspections];
    const familySource = sources[SOURCE_CODES.family];
    const inspectionIndicators = indicators[SOURCE_CODES.inspections] || [];
    const familyIndicators = indicators[SOURCE_CODES.family] || [];
    const inspectionTotal = inspectionIndicators.find((item) => item.indicator_code === 'convivencia.actuaciones');
    const inspectionMeasures = inspectionIndicators.filter((item) => item.category === 'Medida');

    return (
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white" aria-labelledby="institutional-management-title">
            <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <p className="text-[10px] font-black uppercase text-primary">Fuentes complementarias</p>
                    <h3 id="institutional-management-title" className="mt-1 text-lg font-black text-slate-950">Gestión institucional y convivencia</h3>
                    <p className="mt-1 text-xs leading-5 text-slate-500">Actuaciones de Inspecciones y cifras agregadas de protección familiar para el mismo periodo consultado.</p>
                </div>
                {summary?.period && (
                    <div className="shrink-0 text-left md:text-right">
                        <p className="text-[10px] font-bold uppercase text-slate-500">Periodo solicitado</p>
                        <p className="text-sm font-black text-slate-800">{formatDate(summary.period.start)} – {formatDate(summary.period.end)}</p>
                    </div>
                )}
            </div>

            {loading ? <LoadingState /> : error ? (
                <div className="m-5 flex items-start gap-3 border border-red-100 bg-red-50 p-4 text-sm text-red-800">
                    <AlertTriangle size={18} className="shrink-0" />
                    <div className="flex-1"><p className="font-bold">No fue posible consultar estas fuentes.</p><p className="mt-1 text-xs">{error}</p></div>
                    {onRetry && <button onClick={onRetry} title="Reintentar" className="p-2"><RefreshCw size={16} /></button>}
                </div>
            ) : (
                <div className="grid xl:grid-cols-2 xl:divide-x divide-slate-200">
                    <article className="p-5">
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex min-w-0 items-start gap-3">
                                <div className="shrink-0 rounded-lg bg-indigo-50 p-2.5 text-primary"><Gavel size={21} /></div>
                                <div className="min-w-0"><h4 className="font-black text-slate-950">Inspecciones de Policía</h4><p className="mt-0.5 text-xs text-slate-500">RNMC · corte {formatDate(inspectionSource?.last_cutoff_date)}</p></div>
                            </div>
                            <SourceStatus source={inspectionSource} />
                        </div>

                        {inspectionTotal ? (
                            <>
                                <div className="mt-5 flex flex-wrap items-end justify-between gap-3">
                                    <div><p className="text-4xl font-black tabular-nums text-slate-950">{formatNumber(inspectionTotal.value)}</p><p className="mt-1 text-sm font-bold text-slate-700">Actuaciones registradas</p></div>
                                    <div className="text-left sm:text-right"><p className="text-[10px] font-bold uppercase text-slate-500">Comparación</p><p className="mt-1 text-xs font-black text-slate-700">{comparisonText(inspectionTotal)}</p></div>
                                </div>
                                <IndicatorRows indicators={inspectionMeasures} limit={3} />
                            </>
                        ) : <SourceUnavailable source={inspectionSource} />}

                        <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-3">
                            <p className="text-[10px] leading-4 text-slate-500">Describe gestión institucional; no equivale a hechos delictivos.</p>
                            {onNavigate && <button onClick={() => onNavigate('inspecciones')} className="shrink-0 text-xs font-black text-primary">Abrir módulo</button>}
                        </div>
                    </article>

                    <article className="border-t border-slate-200 p-5 xl:border-t-0">
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex min-w-0 items-start gap-3">
                                <div className="shrink-0 rounded-lg bg-emerald-50 p-2.5 text-emerald-700"><HeartHandshake size={21} /></div>
                                <div className="min-w-0"><h4 className="font-black text-slate-950">Comisarías de Familia</h4><p className="mt-0.5 text-xs text-slate-500">Reporte mensual · corte {formatDate(familySource?.last_cutoff_date)}</p></div>
                            </div>
                            <SourceStatus source={familySource} />
                        </div>

                        {familyIndicators.length > 0 ? <IndicatorRows indicators={familyIndicators} limit={4} /> : (
                            <SourceUnavailable source={familySource} onUseCutoff={onUseCutoff} />
                        )}

                        <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-3">
                            <p className="text-[10px] leading-4 text-slate-500">Cifras agregadas y aprobadas; no muestra personas ni expedientes.</p>
                            {onNavigate && <button onClick={() => onNavigate('sources')} className="shrink-0 text-xs font-black text-primary">Ver fuente</button>}
                        </div>
                    </article>
                </div>
            )}

            <div className="border-t border-slate-200 bg-slate-50 px-5 py-3 text-[11px] font-semibold leading-5 text-slate-600">
                Cada fuente conserva su propia fecha de corte. Estas cifras no se suman entre sí ni con los indicadores de seguridad.
            </div>
        </section>
    );
};

export default InstitutionalManagementSummary;
