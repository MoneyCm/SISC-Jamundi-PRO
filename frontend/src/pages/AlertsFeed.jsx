import React, { useState, useEffect } from 'react';
import {
    Bell,
    AlertTriangle,
    Info,
    CheckCircle2,
    Eye,
    Trash2,
    Filter,
    RefreshCw,
    ArrowRight,
    Search,
    Clock,
    DollarSign,
    MapPin,
    Zap,
    Globe,
    Download,
    FileText,
    Hash
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const AlertsFeed = ({ onPageChange, setExternalFilters }) => {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
        status: 'OPEN',
        tier: '',
        severity: ''
    });
    const [error, setError] = useState(null);
    const [exporting, setExporting] = useState(false);
    const [snapshotInfo, setSnapshotInfo] = useState(null);
    const [scoringConfig, setScoringConfig] = useState(null);
    const [scoringLoading, setScoringLoading] = useState(false);

    const fetchAlerts = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const cleanFilters = {};
            Object.keys(filters).forEach(k => { if (filters[k]) cleanFilters[k] = filters[k]; });
            const query = new URLSearchParams(cleanFilters).toString();
            const response = await fetch(`${API_BASE_URL}/intelligence/alerts?${query}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error('Error al cargar alertas');
            const data = await response.json();
            setAlerts(data.items || []);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAlerts();
    }, [filters]);

    // Config de scoring (solo lectura)
    useEffect(() => {
        const fetchConfig = async () => {
            setScoringLoading(true);
            try {
                const token = localStorage.getItem('token');
                const response = await fetch(`${API_BASE_URL}/intelligence/alerts/scoring-config`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (response.ok) {
                    const data = await response.json();
                    setScoringConfig(data);
                }
            } catch (err) {
                console.error('Error al cargar configuración de scoring:', err);
            } finally {
                setScoringLoading(false);
            }
        };
        fetchConfig();
    }, []);

    const handleAction = async (id, action) => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/intelligence/alerts/${id}/${action}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                fetchAlerts();
            }
        } catch (err) {
            console.error(`Error en ${action}:`, err);
        }
    };

    const handleGenerate = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            // Primero generamos/actualizamos datos
            await fetch(`${API_BASE_URL}/intelligence/alerts/rnmc/generate`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            // Luego forzamos recalcular prioridad con IA
            await fetch(`${API_BASE_URL}/intelligence/alerts/prioritize?source=RNMC&ai=true`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            fetchAlerts();
        } catch (err) {
            console.error('Error al generar:', err);
        } finally {
            setLoading(false);
        }
    };

    const buildCommonFilters = () => {
        const cleanFilters = {};
        Object.keys(filters).forEach(k => { if (filters[k]) cleanFilters[k] = filters[k]; });
        cleanFilters.source = 'RNMC';
        return cleanFilters;
    };

    const handleExportExcel = async () => {
        try {
            setExporting(true);
            const token = localStorage.getItem('token');
            const params = new URLSearchParams(buildCommonFilters());
            params.set('limit', '500');
            const response = await fetch(`${API_BASE_URL}/intelligence/alerts/export/excel?${params.toString()}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error('Error al exportar Excel');
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `RNMC_Alerts_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Error exportando Excel:', err);
            setError('No se pudo exportar el Excel del ranking.');
        } finally {
            setExporting(false);
        }
    };

    const handleExportPdf = async () => {
        try {
            setExporting(true);
            const token = localStorage.getItem('token');
            const body = {
                source: 'RNMC',
                status: filters.status || 'OPEN',
                tiers: filters.tier ? [filters.tier] : null,
                severity: filters.severity || null,
                limit: 500
            };
            const response = await fetch(`${API_BASE_URL}/intelligence/alerts/export/pdf`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });
            if (!response.ok) throw new Error('Error al exportar PDF');
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `RNMC_Alerts_Ejecutivo_${new Date().toISOString().slice(0, 10)}.pdf`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Error exportando PDF:', err);
            setError('No se pudo generar el PDF ejecutivo.');
        } finally {
            setExporting(false);
        }
    };

    const handleCreateSnapshot = async () => {
        try {
            setExporting(true);
            const token = localStorage.getItem('token');
            const body = {
                source: 'RNMC',
                status: filters.status || 'OPEN',
                tiers: filters.tier ? [filters.tier] : null,
                severity: filters.severity || null,
                limit: 500
            };
            const response = await fetch(`${API_BASE_URL}/intelligence/alerts/snapshot`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });
            if (!response.ok) throw new Error('Error al crear snapshot');
            const data = await response.json();
            setSnapshotInfo(data);
            setError(null);
        } catch (err) {
            console.error('Error creando snapshot:', err);
            setError('No se pudo crear el snapshot del ranking.');
        } finally {
            setExporting(false);
        }
    };

    const navigateToSource = (alert) => {
        if (alert.source === 'RNMC') {
            // Pasar filtros externos al modulo RNMC
            if (alert.entity_ref && alert.entity_ref.event_fingerprint) {
                setExternalFilters({
                    event_fingerprint: alert.entity_ref.event_fingerprint,
                    source_id: alert.entity_ref.source_id
                });
            }
            onPageChange('rnmc');
        }
    };

    const getSeverityStyles = (severity) => {
        switch (severity) {
            case 'HIGH': return 'bg-red-100 text-red-700 border-red-200';
            case 'MEDIUM': return 'bg-amber-100 text-amber-700 border-amber-200';
            case 'LOW': return 'bg-blue-100 text-blue-700 border-blue-200';
            default: return 'bg-slate-100 text-slate-700 border-slate-200';
        }
    };

    const getTierStyles = (tier) => {
        switch (tier) {
            case 'P1': return 'bg-red-600 text-white border-red-700 shadow-sm shadow-red-100';
            case 'P2': return 'bg-amber-500 text-white border-amber-600 shadow-sm shadow-amber-100';
            case 'P3': return 'bg-indigo-400 text-white border-indigo-500 shadow-sm shadow-indigo-100';
            default: return 'bg-slate-500 text-white border-slate-600';
        }
    };

    return (
        <div className="max-w-6xl mx-auto p-6 space-y-8 animate-fade-in pb-40">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                        <Bell className="text-[#281FD0]" /> Muro de Priorización
                    </h1>
                    <p className="text-slate-500 font-medium mt-1">Inteligencia Operativa y Ranking de Acción (Fase 3)</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <button
                        onClick={handleGenerate}
                        disabled={loading}
                        className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-xl font-bold text-sm hover:bg-slate-50 transition-all flex items-center gap-2"
                    >
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                        Recalcular Prioridad
                    </button>
                    <button
                        onClick={fetchAlerts}
                        className="bg-[#281FD0] text-white px-6 py-2 rounded-xl font-bold text-sm hover:bg-blue-700 transition-all shadow-lg shadow-blue-200"
                    >
                        Sincronizar Feed
                    </button>
                    <button
                        onClick={handleExportExcel}
                        disabled={exporting}
                        className="bg-emerald-600 text-white px-4 py-2 rounded-xl font-bold text-sm hover:bg-emerald-700 transition-all shadow-md shadow-emerald-200 flex items-center gap-2"
                    >
                        <Download size={16} />
                        Exportar Excel
                    </button>
                    <button
                        onClick={handleExportPdf}
                        disabled={exporting}
                        className="bg-slate-900 text-white px-4 py-2 rounded-xl font-bold text-sm hover:bg-black transition-all shadow-md shadow-slate-300 flex items-center gap-2"
                    >
                        <FileText size={16} />
                        PDF Ejecutivo
                    </button>
                    <button
                        onClick={handleCreateSnapshot}
                        disabled={exporting}
                        className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-xl font-bold text-xs hover:bg-slate-50 transition-all flex items-center gap-2"
                    >
                        <Hash size={14} />
                        Crear Snapshot
                    </button>
                </div>
            </div>

            {snapshotInfo && (
                <div className="mt-4 bg-slate-900 text-slate-50 p-4 rounded-2xl flex flex-col md:flex-row md:items-center md:justify-between gap-3 text-xs">
                    <div className="flex items-center gap-2">
                        <Hash size={14} className="text-emerald-400" />
                        <span className="font-black uppercase tracking-widest text-[10px]">Snapshot creado</span>
                    </div>
                    <div className="space-y-1 md:text-right">
                        <div>
                            <span className="font-semibold mr-1">ID:</span>
                            <code className="bg-slate-800 px-2 py-0.5 rounded">{snapshotInfo.snapshot_id}</code>
                        </div>
                        <div>
                            <span className="font-semibold mr-1">SHA256:</span>
                            <code className="bg-slate-800 px-2 py-0.5 rounded break-all">{snapshotInfo.sha256}</code>
                        </div>
                        <div className="text-[10px] text-slate-400">
                            {snapshotInfo.created_at && `Creado: ${new Date(snapshotInfo.created_at).toLocaleString()}`}
                        </div>
                    </div>
                </div>
            )}

            {/* Filters */}
            <div className="bg-white p-4 rounded-2xl border border-slate-100 shadow-sm flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2 text-slate-400">
                    <Filter size={18} />
                    <span className="text-xs font-black uppercase tracking-widest">Filtros</span>
                </div>

                <select
                    value={filters.status}
                    onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                    className="bg-slate-50 border-none rounded-xl px-4 py-2 font-bold text-sm text-slate-700 focus:ring-2 focus:ring-blue-500 transition-all"
                >
                    <option value="OPEN">Abiertas</option>
                    <option value="ACK">Reconocidas</option>
                    <option value="DISMISSED">Descartadas</option>
                </select>

                <select
                    value={filters.tier}
                    onChange={(e) => setFilters({ ...filters, tier: e.target.value })}
                    className="bg-slate-50 border-none rounded-xl px-4 py-2 font-bold text-sm text-slate-700 focus:ring-2 focus:ring-blue-500 transition-all"
                >
                    <option value="">Cualquier Prioridad</option>
                    <option value="P1">P1 - Inmediata</option>
                    <option value="P2">P2 - Semanal</option>
                    <option value="P3">P3 - Monitoreo</option>
                </select>

                <select
                    value={filters.severity}
                    onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
                    className="bg-slate-50 border-none rounded-xl px-4 py-2 font-bold text-sm text-slate-700 focus:ring-2 focus:ring-blue-500 transition-all"
                >
                    <option value="">Cualquier Severidad</option>
                    <option value="HIGH">Crítica</option>
                    <option value="MEDIUM">Advertencia</option>
                    <option value="LOW">Informativa</option>
                </select>
            </div>

            {/* Content */}
            {loading && alerts.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 bg-white rounded-3xl border border-slate-100 border-dashed">
                    <RefreshCw className="text-blue-500 animate-spin mb-4" size={32} />
                    <p className="text-slate-500 font-bold">Calculando Action Scores (IA Prioritization)...</p>
                </div>
            ) : alerts.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 bg-white rounded-3xl border border-slate-100 border-dashed">
                    <CheckCircle2 className="text-emerald-500 mb-4" size={32} />
                    <p className="text-slate-900 font-black text-xl">¡Todo bajo control!</p>
                    <p className="text-slate-500 font-medium">No hay alertas abiertas para los criterios seleccionados.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-6">
                    {alerts.map((alert) => (
                        <div
                            key={alert.id}
                            className={`group bg-white rounded-[32px] border-2 transition-all hover:shadow-xl hover:shadow-indigo-50 flex flex-col overflow-hidden ${alert.priority_tier === 'P1' ? 'border-red-100 hover:border-red-300' :
                                'border-slate-50 hover:border-indigo-300'
                                }`}
                        >
                            <div className="p-6 flex gap-6">
                                {/* Score Circle */}
                                <div className="flex-shrink-0 flex flex-col items-center justify-center space-y-2">
                                    <div className={`w-20 h-20 rounded-full border-8 flex flex-col items-center justify-center shadow-inner ${alert.priority_tier === 'P1' ? 'border-red-50 text-red-600' :
                                        alert.priority_tier === 'P2' ? 'border-amber-50 text-amber-600' :
                                            'border-indigo-50 text-indigo-600'
                                        }`}>
                                        <span className="text-xl font-black">{Math.round(alert.action_score || 0)}</span>
                                        <span className="text-[10px] font-bold uppercase leading-none">Score</span>
                                    </div>
                                    <span className={`px-4 py-1 rounded-full text-[10px] font-black tracking-widest border ${getTierStyles(alert.priority_tier)}`}>
                                        {alert.priority_tier}
                                    </span>
                                </div>

                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                            <span className="text-[10px] font-black uppercase tracking-widest text-white bg-slate-900 px-3 py-1 rounded-lg">
                                                {alert.source}
                                            </span>
                                            <span className={`text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-lg border ${getSeverityStyles(alert.severity)}`}>
                                                {alert.severity}
                                            </span>
                                        </div>
                                        <span className="text-xs font-bold text-slate-400 flex items-center gap-1">
                                            <Clock size={12} /> {new Date(alert.updated_at).toLocaleDateString()}
                                        </span>
                                    </div>

                                    <h3 className="text-xl font-black text-slate-900 mb-2 leading-tight">{alert.title}</h3>

                                    <div className="bg-slate-50 p-4 rounded-2xl mb-4 border border-slate-100 italic text-slate-700 text-sm font-medium leading-relaxed">
                                        "{alert.recommended_action}"
                                    </div>

                                    {/* Rationale and AI Rationale */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                                        <div className="bg-indigo-50/50 p-4 rounded-2xl border border-indigo-50">
                                            <div className="flex items-center gap-2 mb-2 text-indigo-600">
                                                <Info size={14} />
                                                <span className="text-[10px] font-black uppercase tracking-widest">Sustento Determinista</span>
                                            </div>
                                            <div className="text-xs text-indigo-900 font-bold whitespace-pre-wrap leading-relaxed opacity-80">
                                                {alert.rationale_md}
                                            </div>
                                        </div>
                                        {alert.ai_rationale_md ? (
                                            <div className="bg-emerald-50/50 p-4 rounded-2xl border border-emerald-50 relative overflow-hidden">
                                                <div className="absolute top-2 right-2 flex items-center gap-1 opacity-20">
                                                    <Zap size={10} className="text-emerald-600 fill-emerald-600" />
                                                    <span className="text-[8px] font-black uppercase">{alert.ai_provider}</span>
                                                </div>
                                                <div className="flex items-center gap-2 mb-2 text-emerald-600">
                                                    <Globe size={14} />
                                                    <span className="text-[10px] font-black uppercase tracking-widest">Análisis del Asistente (IA)</span>
                                                </div>
                                                <div className="text-xs text-emerald-900 font-bold leading-relaxed italic">
                                                    {alert.ai_rationale_md}
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100 flex items-center justify-center">
                                                <p className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">Análisis IA pendiente...</p>
                                            </div>
                                        )}
                                    </div>

                                    {/* Bottom Info & Buttons */}
                                    <div className="flex items-center justify-between pt-4 border-t border-slate-50">
                                        <div className="flex gap-2">
                                            {alert.status === 'OPEN' && (
                                                <button
                                                    onClick={() => handleAction(alert.id, 'ack')}
                                                    className="px-4 py-2 rounded-xl text-xs font-black text-white bg-slate-900 hover:bg-slate-800 transition-all shadow-md shadow-slate-200"
                                                >
                                                    RECONOCER Y GESTIONAR
                                                </button>
                                            )}
                                            <button
                                                onClick={() => navigateToSource(alert)}
                                                className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-black flex items-center gap-2 hover:bg-indigo-700 shadow-md shadow-indigo-200 transition-all"
                                            >
                                                TRAZABILIDAD RNMC <ArrowRight size={14} />
                                            </button>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <div className="flex flex-col items-end">
                                                <span className="text-[10px] font-black text-slate-300 uppercase leading-none mb-1">Localidad</span>
                                                <span className="text-xs font-black text-slate-600">{alert.metrics.localidad || 'N/A'}</span>
                                            </div>
                                            <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                                                <MapPin size={16} />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {error && (
                <div className="bg-red-50 text-red-600 p-4 rounded-2xl border border-red-100 font-bold text-sm">
                    {error}
                </div>
            )}

            {scoringConfig && (
                <div className="mt-6 bg-white p-4 rounded-2xl border border-slate-100 shadow-sm">
                    <div className="flex items-center gap-2 mb-3">
                        <Info size={14} className="text-slate-500" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                            Config de scoring (solo lectura)
                        </span>
                        {scoringLoading && (
                            <RefreshCw size={12} className="animate-spin text-slate-400" />
                        )}
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs text-slate-700">
                        {Object.entries(scoringConfig).map(([key, value]) => (
                            <div key={key} className="flex items-center justify-between bg-slate-50 rounded-xl px-3 py-2">
                                <span className="font-semibold">{key}</span>
                                <span className="font-mono text-[11px] text-slate-600">{String(value)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default AlertsFeed;
