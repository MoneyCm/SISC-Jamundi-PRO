import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    AlertTriangle,
    Building2,
    CalendarDays,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Database,
    ExternalLink,
    FileSpreadsheet,
    Globe2,
    Loader2,
    RefreshCw,
    Search,
    ShieldCheck,
    Upload,
    WifiOff,
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const STATUS_STYLES = {
    CURRENT: {
        icon: CheckCircle2,
        className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    },
    LAGGED: {
        icon: CalendarDays,
        className: 'border-amber-200 bg-amber-50 text-amber-800',
    },
    EXPIRED: {
        icon: AlertTriangle,
        className: 'border-red-200 bg-red-50 text-red-700',
    },
    UPDATE_AVAILABLE: {
        icon: RefreshCw,
        className: 'border-blue-200 bg-blue-50 text-blue-700',
    },
    ERROR: {
        icon: AlertTriangle,
        className: 'border-red-200 bg-red-50 text-red-700',
    },
    NEEDS_REVIEW: {
        icon: AlertTriangle,
        className: 'border-amber-200 bg-amber-50 text-amber-800',
    },
    NOT_CONNECTED: {
        icon: WifiOff,
        className: 'border-slate-200 bg-slate-100 text-slate-600',
    },
};

const ASSET_STATUS = {
    UPDATED: { label: 'Nueva versión', className: 'text-blue-700 bg-blue-50 border-blue-200' },
    ERROR: { label: 'Error', className: 'text-red-700 bg-red-50 border-red-200' },
    UNCHANGED: { label: 'Sin cambios', className: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
    UNKNOWN: { label: 'Sin revisar', className: 'text-slate-600 bg-slate-50 border-slate-200' },
};

const FILTERS = [
    { code: 'ALL', label: 'Todas' },
    { code: 'ATTENTION', label: 'Por atender' },
    { code: 'AUTOMATIC', label: 'Automáticas' },
    { code: 'MANUAL', label: 'Manual' },
];

const OPERATOR_ROLES = new Set(['SOURCE_UPLOADER', 'STEWARD', 'ANALYST', 'FUNC_ADMIN', 'TI_ADMIN']);
const UPLOAD_ROLES = new Set(['SOURCE_UPLOADER', 'STEWARD', 'FUNC_ADMIN', 'TI_ADMIN']);
const ATTENTION_STATUSES = new Set(['ERROR', 'NOT_CONNECTED', 'UPDATE_AVAILABLE', 'NEEDS_REVIEW', 'EXPIRED']);

const formatDate = (value) => {
    if (!value) return 'Sin corte reportado';
    const date = /^\d{4}-\d{2}-\d{2}$/.test(String(value))
        ? new Date(`${value}T12:00:00`)
        : new Date(value);
    if (Number.isNaN(date.getTime())) return 'Sin corte reportado';
    return new Intl.DateTimeFormat('es-CO', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
    }).format(date);
};

const formatDateTime = (value) => {
    if (!value) return 'Nunca';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Nunca';
    return new Intl.DateTimeFormat('es-CO', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/Bogota',
    }).format(date);
};

const formatNumber = (value) => new Intl.NumberFormat('es-CO').format(Number(value || 0));

const StatusBadge = ({ connector }) => {
    const style = STATUS_STYLES[connector.status] || STATUS_STYLES.NEEDS_REVIEW;
    const Icon = style.icon;
    return (
        <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-bold ${style.className}`}>
            <Icon size={13} aria-hidden="true" />
            {connector.status_label || 'Por revisar'}
        </span>
    );
};

const SourceCenter = ({ onIngest, userRoles = [] }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [search, setSearch] = useState('');
    const [filter, setFilter] = useState('ALL');
    const [expanded, setExpanded] = useState({});
    const [checking, setChecking] = useState('');

    const canOperate = userRoles.some((role) => OPERATOR_ROLES.has(role));
    const canUpload = userRoles.some((role) => UPLOAD_ROLES.has(role));

    const loadSources = useCallback(async ({ quiet = false } = {}) => {
        if (!quiet) setLoading(true);
        setError('');
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/source-center`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.detail || 'No fue posible consultar las fuentes.');
            }
            setData(payload);
        } catch (requestError) {
            setError(requestError.message || 'No fue posible consultar las fuentes.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadSources();
    }, [loadSources]);

    const connectors = data?.connectors || [];
    const filteredConnectors = useMemo(() => {
        const term = search.trim().toLocaleLowerCase('es');
        return connectors.filter((connector) => {
            const searchable = [
                connector.name,
                connector.institution,
                connector.scope,
                connector.purpose,
                connector.code,
            ].join(' ').toLocaleLowerCase('es');
            const matchesSearch = !term || searchable.includes(term);
            const matchesFilter = filter === 'ALL'
                || (filter === 'ATTENTION' && ATTENTION_STATUSES.has(connector.status))
                || (filter === 'AUTOMATIC' && connector.update_mode !== 'MANUAL')
                || (filter === 'MANUAL' && connector.update_mode === 'MANUAL');
            return matchesSearch && matchesFilter;
        });
    }, [connectors, filter, search]);

    const checkConnector = async (connectorCode, datasetCode = null) => {
        if (!canOperate) return;
        const operationKey = datasetCode ? `${connectorCode}:${datasetCode}` : connectorCode;
        setChecking(operationKey);
        setError('');
        try {
            const token = localStorage.getItem('token');
            const query = datasetCode ? `?dataset_code=${encodeURIComponent(datasetCode)}` : '';
            const response = await fetch(`${API_BASE_URL}/source-center/check/${connectorCode}${query}`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.detail || 'No fue posible revisar la fuente.');
            }
            setData(payload.summary);
        } catch (requestError) {
            setError(requestError.message || 'No fue posible revisar la fuente.');
        } finally {
            setChecking('');
        }
    };

    const runAction = (connector) => {
        if (connector.action?.type === 'UPLOAD') {
            if (canUpload) onIngest?.(connector.action.dataset_code, connector.name);
            return;
        }
        if (connector.action?.type === 'CHECK') {
            checkConnector(connector.code);
            return;
        }
        if (connector.action?.type === 'OPEN' && connector.source_url) {
            window.open(connector.source_url, '_blank', 'noopener,noreferrer');
        }
    };

    const actionIcon = (type) => {
        if (type === 'UPLOAD') return Upload;
        if (type === 'CHECK') return RefreshCw;
        return ExternalLink;
    };

    const actionLabel = (type) => {
        if (type === 'UPLOAD') return 'Cargar';
        if (type === 'CHECK') return 'Revisar';
        return 'Abrir';
    };

    const actionDisabled = (connector) => {
        if (connector.action?.type === 'UPLOAD') return !canUpload;
        if (connector.action?.type === 'CHECK') return !canOperate || Boolean(checking);
        return !connector.source_url;
    };

    if (loading) {
        return (
            <div className="flex min-h-[55vh] items-center justify-center">
                <div className="text-center">
                    <Loader2 className="mx-auto mb-3 animate-spin text-[#3026D9]" size={32} />
                    <p className="text-sm font-semibold text-slate-600">Consultando estado de las fuentes</p>
                </div>
            </div>
        );
    }

    return (
        <div className="mx-auto w-full max-w-[1500px] space-y-5 pb-10">
            <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase text-[#3026D9]">
                        <Database size={16} aria-hidden="true" />
                        Operación de datos
                    </div>
                    <h1 className="text-2xl font-black text-slate-900 sm:text-3xl">Centro de fuentes</h1>
                    <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
                        Vigencia, calidad y actualización de las fuentes que alimentan el SISC.
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="hidden text-right sm:block">
                        <p className="text-[10px] font-bold uppercase text-slate-400">Última consulta</p>
                        <p className="text-sm font-semibold text-slate-700">{formatDateTime(data?.generated_at)}</p>
                    </div>
                    <button
                        type="button"
                        onClick={() => loadSources()}
                        title="Actualizar estado"
                        className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#3026D9] px-4 text-sm font-bold text-white shadow-sm transition-colors hover:bg-[#251DB8] focus:outline-none focus:ring-2 focus:ring-[#3026D9]/30"
                    >
                        <RefreshCw size={16} aria-hidden="true" />
                        Actualizar vista
                    </button>
                </div>
            </header>

            {error && (
                <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
                    <AlertTriangle className="mt-0.5 shrink-0" size={18} aria-hidden="true" />
                    <div className="flex-1">
                        <p className="font-bold">No se completó la operación</p>
                        <p>{error}</p>
                    </div>
                    <button type="button" onClick={() => setError('')} className="font-bold" aria-label="Cerrar mensaje">×</button>
                </div>
            )}

            <section className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 lg:grid-cols-4" aria-label="Resumen de fuentes">
                <div className="bg-white p-4">
                    <p className="text-[10px] font-bold uppercase text-slate-500">Fuentes registradas</p>
                    <p className="mt-1 text-2xl font-black text-slate-900">{data?.totals?.total || 0}</p>
                </div>
                <div className="bg-white p-4">
                    <p className="text-[10px] font-bold uppercase text-slate-500">Conectadas</p>
                    <p className="mt-1 text-2xl font-black text-emerald-700">{data?.totals?.connected || 0}</p>
                </div>
                <div className="bg-white p-4">
                    <p className="text-[10px] font-bold uppercase text-slate-500">Automáticas</p>
                    <p className="mt-1 text-2xl font-black text-[#3026D9]">{data?.totals?.automatic || 0}</p>
                </div>
                <div className="bg-white p-4">
                    <p className="text-[10px] font-bold uppercase text-slate-500">Por atender</p>
                    <p className={`mt-1 text-2xl font-black ${data?.totals?.attention ? 'text-amber-700' : 'text-slate-900'}`}>
                        {data?.totals?.attention || 0}
                    </p>
                </div>
            </section>

            <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                <div className="flex flex-col gap-3 border-b border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="relative min-w-0 flex-1 lg:max-w-md">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} aria-hidden="true" />
                        <input
                            type="search"
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Buscar fuente o institución"
                            className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-3 text-sm text-slate-800 outline-none transition focus:border-[#3026D9] focus:bg-white focus:ring-2 focus:ring-[#3026D9]/10"
                        />
                    </div>
                    <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-slate-200 sm:grid-cols-4" aria-label="Filtrar fuentes">
                        {FILTERS.map((item) => (
                            <button
                                key={item.code}
                                type="button"
                                onClick={() => setFilter(item.code)}
                                className={`min-h-9 border-slate-200 px-3 text-xs font-bold transition-colors [&:not(:last-child)]:border-r ${filter === item.code ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                            >
                                {item.label}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="divide-y divide-slate-100 xl:hidden">
                    {filteredConnectors.map((connector) => {
                        const isExpanded = Boolean(expanded[connector.code]);
                        const ActionIcon = actionIcon(connector.action?.type);
                        const isChecking = checking === connector.code;
                        return (
                            <article key={connector.code} className="p-4">
                                <div className="flex items-start gap-3">
                                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#3026D9]/10 text-[#3026D9]">
                                        {connector.update_mode === 'MANUAL' ? <Building2 size={18} /> : <Globe2 size={18} />}
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <p className="font-bold text-slate-900">{connector.name}</p>
                                        <p className="mt-0.5 text-xs leading-5 text-slate-500">{connector.purpose} · {connector.expected_frequency}</p>
                                    </div>
                                    <StatusBadge connector={connector} />
                                </div>

                                <div className="mt-4 grid grid-cols-2 gap-3 border-y border-slate-100 py-3">
                                    <div>
                                        <p className="text-[10px] font-bold uppercase text-slate-400">Corte</p>
                                        <p className="mt-1 text-sm font-bold text-slate-800">{formatDate(connector.source_cutoff_date)}</p>
                                    </div>
                                    <div>
                                        <p className="text-[10px] font-bold uppercase text-slate-400">Última revisión</p>
                                        <p className="mt-1 text-sm font-bold text-slate-800">{formatDateTime(connector.last_checked_at)}</p>
                                    </div>
                                </div>

                                <div className="mt-3 flex items-center justify-between gap-3">
                                    <button
                                        type="button"
                                        onClick={() => setExpanded((current) => ({ ...current, [connector.code]: !current[connector.code] }))}
                                        className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2 text-xs font-bold text-slate-600 hover:bg-slate-100"
                                    >
                                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                        Detalles
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => runAction(connector)}
                                        disabled={actionDisabled(connector)}
                                        title={actionDisabled(connector) ? 'No tiene permisos para esta acción' : connector.action?.label}
                                        className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-xs font-bold text-slate-800 hover:border-[#3026D9] hover:text-[#3026D9] disabled:cursor-not-allowed disabled:opacity-45"
                                    >
                                        {isChecking ? <Loader2 className="animate-spin" size={15} /> : <ActionIcon size={15} />}
                                        {actionLabel(connector.action?.type)}
                                    </button>
                                </div>

                                {isExpanded && (
                                    <div className="mt-4 border-t border-slate-200 pt-4">
                                        <p className="text-[10px] font-bold uppercase text-slate-500">Institución responsable</p>
                                        <p className="mt-1 text-sm font-bold text-slate-900">{connector.institution}</p>
                                        <p className="mt-1 text-xs leading-5 text-slate-600">{connector.scope}</p>
                                        <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                                            <div>
                                                <p className="text-[10px] font-bold uppercase text-slate-400">Registros cargados</p>
                                                <p className="mt-1 font-black text-slate-900">{formatNumber(connector.record_count)}</p>
                                            </div>
                                            <div>
                                                <p className="text-[10px] font-bold uppercase text-slate-400">Calidad</p>
                                                <p className="mt-1 font-black text-slate-900">{connector.quality_label}</p>
                                            </div>
                                        </div>
                                        {connector.source_url && (
                                            <a href={connector.source_url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-2 text-xs font-bold text-[#3026D9] hover:underline">
                                                Publicación oficial <ExternalLink size={14} />
                                            </a>
                                        )}
                                        {connector.assets?.length > 0 && (
                                            <div className="mt-4 border-t border-slate-200">
                                                {connector.assets.map((asset) => {
                                                    const assetStyle = ASSET_STATUS[asset.status] || ASSET_STATUS.UNKNOWN;
                                                    const assetKey = `${connector.code}:${asset.code}`;
                                                    return (
                                                        <div key={asset.code} className="flex items-center justify-between gap-3 border-b border-slate-100 py-3 last:border-b-0">
                                                            <div className="min-w-0">
                                                                <p className="truncate text-xs font-bold text-slate-800">{asset.name}</p>
                                                                <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold ${assetStyle.className}`}>{assetStyle.label}</span>
                                                            </div>
                                                            <div className="flex shrink-0 items-center gap-1">
                                                                {asset.file_url && (
                                                                    <a href={asset.file_url} target="_blank" rel="noopener noreferrer" title="Abrir archivo oficial" className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-[#3026D9]">
                                                                        <ExternalLink size={15} />
                                                                    </a>
                                                                )}
                                                                <button type="button" onClick={() => checkConnector(connector.code, asset.code)} disabled={!canOperate || Boolean(checking)} title="Revisar este archivo" className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-[#3026D9] disabled:opacity-40">
                                                                    {checking === assetKey ? <Loader2 className="animate-spin" size={15} /> : <RefreshCw size={15} />}
                                                                </button>
                                                                <button type="button" onClick={() => onIngest?.(asset.code, asset.name)} disabled={!canUpload} title="Cargar archivo" className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-[#3026D9] disabled:opacity-40">
                                                                    <FileSpreadsheet size={15} />
                                                                </button>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </article>
                        );
                    })}
                </div>

                <div className="hidden overflow-x-auto xl:block">
                    <table className="min-w-[900px] w-full border-collapse text-left">
                        <thead className="bg-slate-50 text-[10px] font-bold uppercase text-slate-500">
                            <tr>
                                <th className="w-12 px-4 py-3"><span className="sr-only">Detalle</span></th>
                                <th className="px-3 py-3">Fuente y uso</th>
                                <th className="px-3 py-3">Estado</th>
                                <th className="px-3 py-3">Corte de la fuente</th>
                                <th className="px-3 py-3">Última revisión</th>
                                <th className="px-3 py-3 text-right">Acción</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {filteredConnectors.map((connector) => {
                                const isExpanded = Boolean(expanded[connector.code]);
                                const ActionIcon = actionIcon(connector.action?.type);
                                const isChecking = checking === connector.code;
                                return (
                                    <React.Fragment key={connector.code}>
                                        <tr className="align-middle hover:bg-slate-50/70">
                                            <td className="px-4 py-4">
                                                <button
                                                    type="button"
                                                    onClick={() => setExpanded((current) => ({ ...current, [connector.code]: !current[connector.code] }))}
                                                    title={isExpanded ? 'Ocultar detalle' : 'Ver detalle'}
                                                    className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-200 hover:text-slate-900"
                                                >
                                                    {isExpanded ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
                                                </button>
                                            </td>
                                            <td className="px-3 py-4">
                                                <div className="flex items-start gap-3">
                                                    <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#3026D9]/10 text-[#3026D9]">
                                                        {connector.update_mode === 'MANUAL' ? <Building2 size={18} /> : <Globe2 size={18} />}
                                                    </div>
                                                    <div className="min-w-0">
                                                        <p className="font-bold text-slate-900">{connector.name}</p>
                                                        <p className="mt-0.5 text-xs text-slate-500">{connector.purpose} · {connector.expected_frequency}</p>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-3 py-4"><StatusBadge connector={connector} /></td>
                                            <td className="px-3 py-4">
                                                <p className="text-sm font-bold text-slate-800">{formatDate(connector.source_cutoff_date)}</p>
                                                <p className="mt-0.5 text-xs text-slate-500">{connector.period_label || connector.quality_label}</p>
                                            </td>
                                            <td className="px-3 py-4">
                                                <p className="text-sm font-semibold text-slate-700">{formatDateTime(connector.last_checked_at)}</p>
                                                <p className="mt-0.5 text-xs text-slate-500">{connector.asset_count ? `${connector.asset_count} archivos vigilados` : connector.update_mode === 'MANUAL' ? 'Carga institucional' : 'Monitor externo'}</p>
                                            </td>
                                            <td className="px-3 py-4 text-right">
                                                <button
                                                    type="button"
                                                    onClick={() => runAction(connector)}
                                                    disabled={actionDisabled(connector)}
                                                    title={actionDisabled(connector) ? 'No tiene permisos para esta acción' : connector.action?.label}
                                                    className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-xs font-bold text-slate-800 transition hover:border-[#3026D9] hover:text-[#3026D9] disabled:cursor-not-allowed disabled:opacity-45"
                                                >
                                                    {isChecking ? <Loader2 className="animate-spin" size={15} /> : <ActionIcon size={15} />}
                                                    {actionLabel(connector.action?.type)}
                                                </button>
                                            </td>
                                        </tr>
                                        {isExpanded && (
                                            <tr className="bg-slate-50/80">
                                                <td colSpan="6" className="px-6 py-5">
                                                    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(320px,1.4fr)]">
                                                        <div>
                                                            <p className="text-[10px] font-bold uppercase text-slate-500">Institución responsable</p>
                                                            <p className="mt-1 text-sm font-bold text-slate-900">{connector.institution}</p>
                                                            <p className="mt-1 text-sm text-slate-600">{connector.scope}</p>
                                                            <div className="mt-4 grid grid-cols-2 gap-3">
                                                                <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                                    <p className="text-[10px] font-bold uppercase text-slate-400">Registros cargados</p>
                                                                    <p className="mt-1 text-xl font-black text-slate-900">{formatNumber(connector.record_count)}</p>
                                                                </div>
                                                                <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                                    <p className="text-[10px] font-bold uppercase text-slate-400">Calidad</p>
                                                                    <p className="mt-1 text-sm font-black text-slate-900">{connector.quality_label}</p>
                                                                </div>
                                                            </div>
                                                            {connector.source_url && (
                                                                <a
                                                                    href={connector.source_url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="mt-4 inline-flex items-center gap-2 text-xs font-bold text-[#3026D9] hover:underline"
                                                                >
                                                                    Consultar publicación oficial <ExternalLink size={14} />
                                                                </a>
                                                            )}
                                                            {connector.warnings?.length > 0 && (
                                                                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                                                                    <p className="font-bold">Advertencias del monitor</p>
                                                                    {connector.warnings.slice(0, 3).map((warning) => <p key={warning} className="mt-1">{warning}</p>)}
                                                                </div>
                                                            )}
                                                        </div>

                                                        <div>
                                                            <div className="mb-2 flex items-center justify-between">
                                                                <p className="text-[10px] font-bold uppercase text-slate-500">Archivos de esta fuente</p>
                                                                {connector.updated_assets > 0 && <span className="text-xs font-bold text-blue-700">{connector.updated_assets} por actualizar</span>}
                                                            </div>
                                                            {connector.assets?.length > 0 ? (
                                                                <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                                                                    {connector.assets.map((asset) => {
                                                                        const assetStyle = ASSET_STATUS[asset.status] || ASSET_STATUS.UNKNOWN;
                                                                        const assetKey = `${connector.code}:${asset.code}`;
                                                                        return (
                                                                            <div key={asset.code} className="flex flex-col gap-3 border-b border-slate-100 p-3 last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
                                                                                <div className="min-w-0">
                                                                                    <p className="truncate text-sm font-bold text-slate-800">{asset.name}</p>
                                                                                    <div className="mt-1 flex items-center gap-2">
                                                                                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${assetStyle.className}`}>{assetStyle.label}</span>
                                                                                        <span className="text-[10px] text-slate-400">{formatDateTime(asset.last_checked_at)}</span>
                                                                                    </div>
                                                                                </div>
                                                                                <div className="flex shrink-0 items-center gap-1">
                                                                                    {asset.file_url && (
                                                                                        <a href={asset.file_url} target="_blank" rel="noopener noreferrer" title="Abrir archivo oficial" className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-[#3026D9]">
                                                                                            <ExternalLink size={15} />
                                                                                        </a>
                                                                                    )}
                                                                                    <button
                                                                                        type="button"
                                                                                        onClick={() => checkConnector(connector.code, asset.code)}
                                                                                        disabled={!canOperate || Boolean(checking)}
                                                                                        title="Revisar este archivo"
                                                                                        className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-[#3026D9] disabled:opacity-40"
                                                                                    >
                                                                                        {checking === assetKey ? <Loader2 className="animate-spin" size={15} /> : <RefreshCw size={15} />}
                                                                                    </button>
                                                                                    <button
                                                                                        type="button"
                                                                                        onClick={() => onIngest?.(asset.code, asset.name)}
                                                                                        disabled={!canUpload}
                                                                                        title="Cargar archivo"
                                                                                        className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-[#3026D9] disabled:opacity-40"
                                                                                    >
                                                                                        <FileSpreadsheet size={15} />
                                                                                    </button>
                                                                                </div>
                                                                            </div>
                                                                        );
                                                                    })}
                                                                </div>
                                                            ) : (
                                                                <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">
                                                                    Esta fuente reporta un corte consolidado; no publica una lista de archivos dentro del SISC.
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {filteredConnectors.length === 0 && (
                    <div className="px-6 py-12 text-center">
                        <ShieldCheck className="mx-auto text-slate-300" size={30} />
                        <p className="mt-3 font-bold text-slate-700">No hay fuentes con esos criterios</p>
                        <p className="mt-1 text-sm text-slate-500">Cambie el filtro o el término de búsqueda.</p>
                    </div>
                )}
            </section>

            <div className="flex items-start gap-2 border-l-2 border-amber-400 pl-3 text-xs leading-5 text-slate-600">
                <AlertTriangle className="mt-0.5 shrink-0 text-amber-600" size={15} aria-hidden="true" />
                <p><strong className="text-slate-800">Lectura correcta:</strong> cada fuente conserva su metodología y fecha de corte. Sus conteos sirven para control y contraste, pero no deben sumarse entre sí.</p>
            </div>
        </div>
    );
};

export default SourceCenter;
