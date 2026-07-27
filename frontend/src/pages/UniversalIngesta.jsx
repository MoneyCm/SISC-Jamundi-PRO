import React, { useState, useRef, useEffect } from 'react';
import {
    Upload,
    ShieldCheck,
    ShieldAlert,
    ShieldEllipsis,
    Loader2,
    CheckCircle2,
    XCircle,
    ArrowRight,
    FileSearch,
    RefreshCcw,
    AlertTriangle
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const DATASETS_CONFIG = [
    { code: 'HOMICIDIO_INTENCIONAL', label: 'Homicidio Intencional' },
    { code: 'LESIONES_COMUNES', label: 'Lesiones Comunes' },
    { code: 'VIOLENCIA_INTRAFAMILIAR', label: 'Violencia Intrafamiliar' },
    { code: 'DELITOS_SEXUALES', label: 'Delitos Sexuales' },
    { code: 'SECUESTRO', label: 'Secuestro' },
    { code: 'EXTORSIÓN', label: 'Extorsión' },
    { code: 'TERRORISMO', label: 'Terrorismo' },
    { code: 'MASACRES', label: 'Masacres' },
    { code: 'AFECTACIÓN_FUERZA_PUBLICA', label: 'Afectación Fuerza Pública' },
    { code: 'HURTO_PERSONAS', label: 'Hurto a Personas' },
    { code: 'HURTO_RESIDENCIAS', label: 'Hurto a Residencias' },
    { code: 'HURTO_VEHÍCULOS', label: 'Hurto de Vehículos' },
    { code: 'HURTO_COMERCIO', label: 'Hurto a Comercio' },
    { code: 'INCAUTACIÓN_COCAINA', label: 'Incautación Cocaína' },
    { code: 'INCAUTACIÓN_MARIHUANA', label: 'Incautación Marihuana' },
    { code: 'POLICIA_SEMANAL', label: 'Policía Jamundí - Base Semanal' },
    { code: 'POLICIA_PORTAL', label: 'SIEDCO (Público)' },
];

const UniversalIngesta = ({ setActivePage, setReportId, datasetCode = "SECUESTRO", label = "Secuestro" }) => {
    const [currentDataset, setCurrentDataset] = useState({ code: datasetCode, label: label });
    const [status, setStatus] = useState('idle'); // idle, uploading, rejected, success
    const [reportInfo, setReportInfo] = useState(null);
    const [error, setError] = useState(null);
    const [assetStatus, setAssetStatus] = useState(null);
    const [forcing, setForcing] = useState(false);
    const [sabanaHistory, setSabanaHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const fileInputRef = useRef(null);
    const forceInputRef = useRef(null);

    const safeDatasetCode = currentDataset.code;

    useEffect(() => {
        checkAssetStatus();
    }, [safeDatasetCode]);

    useEffect(() => {
        if (safeDatasetCode === 'POLICIA_SEMANAL') loadSabanaHistory();
        else setSabanaHistory([]);
    }, [safeDatasetCode]);

    const loadSabanaHistory = async () => {
        setHistoryLoading(true);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/ingesta/policia/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error('No fue posible consultar el historial SABANA');
            const data = await response.json();
            setSabanaHistory(data.items || []);
        } catch (err) {
            console.error('Error loading SABANA history:', err);
        } finally {
            setHistoryLoading(false);
        }
    };

    const handleDatasetChange = (e) => {
        const selected = DATASETS_CONFIG.find(d => d.code === e.target.value);
        if (selected) {
            setCurrentDataset(selected);
            setStatus('idle');
            setReportInfo(null);
        }
    };

    const checkAssetStatus = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/mindefensa/assets/${safeDatasetCode}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setAssetStatus(data);
            } else {
                setAssetStatus(null);
            }
        } catch (err) {
            console.error("Error checking asset status:", err);
            setAssetStatus(null);
        }
    };

    const handleFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        await startUpload(file);
    };

    const startUpload = async (file, force = false) => {
        if (force) setForcing(true);
        else setForcing(false);
        setStatus('uploading');
        setError(null);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('source_name', `${safeDatasetCode}_MINDEFENSA`);

        const forceParam = force ? '?force=true' : '';

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/ingesta/gate/${safeDatasetCode.toLowerCase()}${forceParam}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });

            const data = await response.json();

            if (response.status === 409) {
                setStatus('rejected');
                setReportInfo({
                    type: 'OUTDATED_SOURCE',
                    message: data.detail.message,
                    last_change: data.detail.last_change,
                    issues_count: "BLOQUEO"
                });
            } else if (response.status === 422) {
                setStatus('rejected');
                const detail = data.detail;
                if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
                    setReportInfo(detail);
                } else {
                    setReportInfo({
                        message: "Error de validación en los datos del archivo.",
                        issues_count: Array.isArray(detail) ? detail.length : 1,
                        report_id: null
                    });
                }
            } else if (!response.ok) {
                throw new Error(data.detail || 'Error en la comunicación con el servidor');
            } else {
                setStatus('success');
                setReportInfo(data);
                if (safeDatasetCode === 'POLICIA_SEMANAL') await loadSabanaHistory();
            }
        } catch (err) {
            setError(err.message);
            setStatus('idle');
        } finally {
            if (fileInputRef.current) fileInputRef.current.value = '';
            if (forceInputRef.current) forceInputRef.current.value = '';
            setForcing(false);
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-8 animate-fade-in py-12">
            <div className="text-center space-y-4">
                <div className="inline-block p-3 bg-indigo-100 rounded-2xl text-indigo-600 mb-2">
                    <ShieldCheck size={48} />
                </div>
                <h1 className="text-4xl font-black text-slate-800 tracking-tight">Gate de Ingesta Inteligente</h1>
                <p className="text-slate-500 max-w-xl mx-auto font-medium">Validación automática de calidad para <strong>{currentDataset.label}</strong> antes de la persistencia definitiva.</p>

                {/* Selector de Delito */}
                <div className="flex justify-center mt-6">
                    <div className="relative w-full max-w-md">
                        <select
                            value={currentDataset.code}
                            onChange={handleDatasetChange}
                            className="w-full bg-white border-2 border-slate-200 rounded-2xl px-6 py-4 font-black text-slate-700 appearance-none focus:border-indigo-500 outline-none transition-all shadow-lg text-sm uppercase tracking-widest cursor-pointer"
                        >
                            {DATASETS_CONFIG.map(d => (
                                <option key={d.code} value={d.code}>{d.label}</option>
                            ))}
                        </select>
                        <div className="absolute right-6 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                            <ArrowRight size={20} className="rotate-90" />
                        </div>
                    </div>
                </div>

                {assetStatus?.status === 'UPDATED' && (
                    <div className="inline-flex items-center gap-3 px-6 py-3 bg-amber-50 border border-amber-200 rounded-2xl text-amber-700 animate-pulse mt-4">
                        <AlertTriangle size={20} className="shrink-0" />
                        <div className="text-left">
                            <p className="text-xs font-black uppercase tracking-widest">Fuente Oficial Actualizada</p>
                            <p className="text-[10px] font-bold opacity-80">Se detectó una nueva versión de {currentDataset.label} en el portal oficial.</p>
                        </div>
                        <button
                            onClick={() => setActivePage('monitoring')}
                            className="ml-4 px-3 py-1 bg-amber-600 text-white rounded-lg text-[10px] font-black uppercase"
                        >
                            Ver Monitor
                        </button>
                    </div>
                )}
            </div>

            {status === 'idle' && (
                <div
                    onClick={() => fileInputRef.current?.click()}
                    className="bg-white p-12 rounded-3xl shadow-xl border border-slate-200 flex flex-col items-center border-dashed border-2 hover:border-indigo-400 transition-all cursor-pointer relative group"
                >
                    <input
                        type="file"
                        ref={fileInputRef}
                        className="hidden"
                        accept=".xlsx,.xls"
                        onChange={handleFileChange}
                    />
                    {/* Input oculto para forzar ingesta */}
                    <input
                        type="file"
                        ref={forceInputRef}
                        className="hidden"
                        accept=".xlsx,.xls"
                        onChange={(e) => { const f = e.target.files[0]; if (f) startUpload(f, true); }}
                    />
                    <div className="bg-slate-100 p-8 rounded-full mb-6 group-hover:bg-indigo-600 transition-all duration-500 group-hover:scale-110 shadow-inner">
                        <Upload className="h-12 w-12 text-slate-400 group-hover:text-white" />
                    </div>
                    <h3 className="text-2xl font-black text-slate-800 mb-2">Subir registros de {currentDataset.label}</h3>
                    <p className="text-slate-400 font-bold uppercase tracking-tight text-sm">Formato oficial (Abierto/Cerrado)</p>

                    <div className="mt-8 flex gap-6 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
                        <span className="flex items-center gap-2 px-3 py-1 bg-slate-50 rounded-full border border-slate-100"><ShieldCheck size={14} className="text-emerald-500" /> Esquema</span>
                        <span className="flex items-center gap-2 px-3 py-1 bg-slate-50 rounded-full border border-slate-100"><ShieldCheck size={14} className="text-emerald-500" /> Duplicados</span>
                        <span className="flex items-center gap-2 px-3 py-1 bg-slate-50 rounded-full border border-slate-100"><ShieldCheck size={14} className="text-emerald-500" /> Fechas</span>
                    </div>
                </div>
            )}

            {status === 'uploading' && (
                <div className="bg-white p-20 rounded-3xl shadow-xl border border-slate-200 flex flex-col items-center text-center space-y-8">
                    <div className="relative">
                        <div className="h-28 w-28 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin"></div>
                        <ShieldEllipsis className="absolute inset-0 m-auto h-12 w-12 text-indigo-400 animate-pulse" />
                    </div>
                    <div className="space-y-3">
                        <h3 className="text-3xl font-black text-slate-800 tracking-tighter uppercase">Validando Gate de Calidad</h3>
                        <p className="text-slate-400 font-black tracking-widest text-xs uppercase animate-pulse">Analizando inconsistencias geográficas y lógicas...</p>
                    </div>
                </div>
            )}

            {status === 'rejected' && (
                <div className="bg-white p-12 rounded-3xl shadow-2xl border-2 border-red-500 flex flex-col items-center text-center space-y-8 animate-shake">
                    <div className="bg-red-100 p-8 rounded-full text-red-600 shadow-lg shadow-red-100">
                        <ShieldAlert size={64} />
                    </div>
                    <div className="space-y-3">
                        <h3 className="text-4xl font-black text-slate-800 tracking-tighter uppercase">Ingesta Bloqueada</h3>
                        <p className="text-red-500 font-black uppercase tracking-[0.2em] text-xs leading-relaxed">{reportInfo.message}</p>
                    </div>

                    <div className="bg-slate-50 p-8 rounded-[2.5rem] border border-slate-200 w-full max-md relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-4">
                            <span className={`px-4 py-1.5 ${reportInfo.type === 'OUTDATED_SOURCE' ? 'bg-amber-600' : 'bg-red-600'} text-white rounded-full text-[10px] font-black uppercase tracking-widest shadow-lg self-end`}>
                                {reportInfo.type === 'OUTDATED_SOURCE' ? 'ACTUALIZAR' : 'ROJO'}
                            </span>
                        </div>
                        <div className="text-left space-y-4">
                            <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b pb-2 mb-4">Evidencia del Hallazgo</div>
                            {reportInfo.type === 'OUTDATED_SOURCE' ? (
                                <div className="space-y-4">
                                    <div className="text-xs font-bold text-slate-700 flex justify-between items-center bg-white p-3 rounded-xl border border-slate-100">
                                        Origen: <span className="text-amber-600 font-black">{currentDataset.code.includes('POLICIA') ? 'Policía Nacional' : 'MinDefensa'} {currentDataset.label}</span>
                                    </div>
                                    <div className="text-xs font-bold text-slate-700 flex justify-between items-center bg-white p-3 rounded-xl border border-slate-100">
                                        Último Cambio: <span className="text-slate-900 font-black">{new Date(reportInfo.last_change).toLocaleDateString()}</span>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-xs font-bold text-slate-700 flex justify-between items-center bg-white p-3 rounded-xl border border-slate-100">
                                    Errores Críticos Detectados: <span className="text-red-600 font-black text-lg">{reportInfo.issues_count}</span>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="flex gap-4 flex-wrap justify-center">
                        <button
                            onClick={() => setStatus('idle')}
                            className="px-10 py-4 bg-slate-100 text-slate-600 rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-slate-200 transition-all active:scale-95"
                        >
                            Intentar otro
                        </button>
                        {reportInfo.type === 'OUTDATED_SOURCE' ? (
                            <button
                                onClick={() => setActivePage('monitoring')}
                                className="px-10 py-4 bg-amber-600 text-white rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-amber-700 transition-all flex items-center gap-2 shadow-xl active:scale-95"
                            >
                                <RefreshCcw size={16} /> Ir al Monitor
                            </button>
                        ) : (
                            <>
                                {reportInfo.report_id && (
                                    <button
                                        onClick={() => { 
                                            setReportId(reportInfo.report_id); 
                                            setActivePage(safeDatasetCode === 'POLICIA_SEMANAL' ? 'police_audit' : 'dq'); 
                                        }}
                                        className="px-8 py-4 bg-red-600 text-white rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-red-700 transition-all flex items-center gap-2 shadow-xl shadow-red-200 active:scale-95"
                                    >
                                        <FileSearch size={16} /> Auditoría
                                    </button>
                                )}
                                <button
                                    onClick={() => forceInputRef.current?.click()}
                                    title="Salta el gate de calidad e ingesta el archivo tal como está"
                                    className="px-8 py-4 bg-orange-500 text-white rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-orange-600 transition-all flex items-center gap-2 shadow-xl shadow-orange-200 active:scale-95"
                                >
                                    <ShieldAlert size={16} /> Forzar Ingesta
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}

            {status === 'success' && (
                <div className="bg-white p-12 rounded-3xl shadow-2xl border-2 border-emerald-500 flex flex-col items-center text-center space-y-8">
                    <div className="bg-emerald-100 p-8 rounded-full text-emerald-600 animate-bounce shadow-lg shadow-emerald-100">
                        <CheckCircle2 size={64} />
                    </div>
                    <div className="space-y-3">
                        <h3 className="text-4xl font-black text-slate-800 tracking-tighter uppercase">Ingesta Exitosa</h3>
                        <p className="text-emerald-600 font-black uppercase tracking-[0.2em] text-xs leading-relaxed">{reportInfo.message}</p>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 w-full">
                        <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 flex flex-col items-center">
                            <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">
                                {reportInfo.stats ? 'Aprobados' : 'Registros'}
                            </div>
                            <div className="text-xl font-black text-emerald-600">
                                {reportInfo.stats ? reportInfo.stats.aprobadas : (reportInfo.message.match(/\d+/) ? reportInfo.message.match(/\d+/)[0] : 'OK')}
                            </div>
                        </div>
                        {reportInfo.stats && (
                            <>
                                <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 flex flex-col items-center">
                                    <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Rechazados</div>
                                    <div className="text-xl font-black text-red-600">
                                        {reportInfo.stats.rechazadas}
                                    </div>
                                </div>
                                <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 flex flex-col items-center">
                                    <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Ya existentes</div>
                                    <div className="text-xl font-black text-amber-600">
                                        {reportInfo.stats.duplicadas}
                                    </div>
                                </div>
                                <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 flex flex-col items-center">
                                    <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Fuera Jamundí</div>
                                    <div className="text-xl font-black text-slate-600">
                                        {reportInfo.stats.fuera_territorio}
                                    </div>
                                </div>
                                <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 flex flex-col items-center">
                                    <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Ubicados</div>
                                    <div className="text-xl font-black text-indigo-600">
                                        {reportInfo.stats.georreferenciadas}
                                    </div>
                                </div>
                            </>
                        )}
                        <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 flex flex-col items-center">
                            <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">ID Proceso</div>
                            <div className="text-[10px] font-mono font-bold text-slate-400 truncate w-full text-center">
                                {reportInfo.ingestion_id?.slice(0, 8)}...
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-4">
                        <button
                            onClick={() => setStatus('idle')}
                            className="px-10 py-4 bg-slate-100 text-slate-600 rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-slate-200 transition-all active:scale-95"
                        >
                            Cargar más
                        </button>
                        <button
                            onClick={() => setActivePage('data')}
                            className="px-10 py-4 bg-indigo-600 text-white rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-indigo-700 transition-all flex items-center gap-2 shadow-xl shadow-indigo-100 active:scale-95"
                        >
                            Ver en Bodega <ArrowRight size={16} />
                        </button>
                    </div>
                </div>
            )}

            {safeDatasetCode === 'POLICIA_SEMANAL' && (
                <section className="border-t border-slate-200 pt-8">
                    <div className="flex items-end justify-between gap-4 mb-4">
                        <div>
                            <h2 className="text-xl font-black text-slate-800">Historial central de entregas SABANA</h2>
                            <p className="text-sm text-slate-500">Cada archivo es una foto semanal inmutable; el consolidado solo suma novedades.</p>
                        </div>
                        <button
                            onClick={loadSabanaHistory}
                            disabled={historyLoading}
                            title="Actualizar historial"
                            className="p-2 text-slate-500 hover:text-indigo-600 disabled:opacity-50"
                        >
                            <RefreshCcw size={18} className={historyLoading ? 'animate-spin' : ''} />
                        </button>
                    </div>
                    <div className="overflow-x-auto border border-slate-200 bg-white">
                        <table className="w-full min-w-[760px] text-left text-sm">
                            <thead className="bg-slate-800 text-white text-[10px] uppercase tracking-wider">
                                <tr>
                                    <th className="px-4 py-3">Entrega</th>
                                    <th className="px-4 py-3">Cobertura</th>
                                    <th className="px-4 py-3 text-right">Filas únicas</th>
                                    <th className="px-4 py-3 text-right">Novedades</th>
                                    <th className="px-4 py-3 text-right">Ya existentes</th>
                                    <th className="px-4 py-3">Responsable</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {sabanaHistory.map((run) => {
                                    const snapshot = run.resumen?.snapshot || {};
                                    const coverage = snapshot.coverage || {};
                                    return (
                                        <tr key={run.id} className="text-slate-700">
                                            <td className="px-4 py-3">
                                                <div className="font-bold text-slate-900">{run.filename}</div>
                                                <div className="text-xs text-slate-400">{run.fecha_fin ? new Date(run.fecha_fin).toLocaleString() : 'Sin fecha'}</div>
                                            </td>
                                            <td className="px-4 py-3">
                                                <div>{(coverage.years || []).join(' / ') || 'Sin identificar'}</div>
                                                <div className="text-xs text-slate-400">{coverage.min_date || 'N/D'} a {coverage.max_date || 'N/D'}</div>
                                            </td>
                                            <td className="px-4 py-3 text-right font-bold">{snapshot.filas ?? run.aprobadas ?? 0}</td>
                                            <td className="px-4 py-3 text-right font-bold text-emerald-700">{snapshot.nuevas_consolidadas ?? 0}</td>
                                            <td className="px-4 py-3 text-right font-bold text-amber-700">{snapshot.existentes_historico ?? run.duplicadas ?? 0}</td>
                                            <td className="px-4 py-3">{run.usuario_carga || 'Sistema'}</td>
                                        </tr>
                                    );
                                })}
                                {!historyLoading && sabanaHistory.length === 0 && (
                                    <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-400">La primera entrega registrada aparecerá aquí.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
            {error && (
                <div className="p-5 bg-red-50 text-red-700 rounded-2xl border border-red-200 flex items-center gap-4 animate-shake">
                    <XCircle size={24} className="shrink-0" />
                    <span className="text-xs font-black uppercase tracking-tight">{error}</span>
                </div>
            )}
        </div>
    );
};

export default UniversalIngesta;
