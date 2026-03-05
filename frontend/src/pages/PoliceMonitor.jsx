import React, { useState, useEffect } from 'react';
import { RefreshCcw, ExternalLink, AlertCircle, CheckCircle2, AlertTriangle, Clock, Database, Search, Info, ShieldCheck } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const PoliceMonitor = ({ onIngest }) => {
    const [assets, setAssets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [checking, setChecking] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterStatus, setFilterStatus] = useState('ALL');

    useEffect(() => {
        fetchAssets();
    }, []);

    const fetchAssets = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_BASE_URL}/policia/assets`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const data = await response.json();
            if (!Array.isArray(data)) {
                throw new Error(data.detail || 'Respuesta del servidor no es válida');
            }
            if (data.length === 0) {
                // Si no hay assets, sembramos los iniciales
                await fetch(`${API_BASE_URL}/policia/assets/seed`, {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${token}` },
                });
                fetchAssets();
                return;
            }
            setAssets(data);
        } catch (err) {
            console.error('Error fetching police assets:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleCheckUpdates = async (datasetCode = null) => {
        setChecking(true);
        try {
            const token = localStorage.getItem('token');
            const url = datasetCode
                ? `${API_BASE_URL}/policia/assets/check?dataset_code=${datasetCode}`
                : `${API_BASE_URL}/policia/assets/check`;
            await fetch(url, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
            });
            await fetchAssets();
        } catch (err) {
            console.error('Error checking police updates:', err);
        } finally {
            setChecking(false);
        }
    };

    const getStatusBadge = (status) => {
        switch (status) {
            case 'UNCHANGED':
                return (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-600 rounded-full text-[10px] font-black border border-emerald-100 uppercase tracking-wider">
                        <CheckCircle2 size={12} /> Al Día
                    </span>
                );
            case 'UPDATED':
                return (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 text-amber-600 rounded-full text-[10px] font-black border border-amber-100 uppercase tracking-wider animate-pulse">
                        <AlertTriangle size={12} /> Actualizado
                    </span>
                );
            case 'ERROR':
                return (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 bg-red-50 text-red-600 rounded-full text-[10px] font-black border border-red-100 uppercase tracking-wider">
                        <AlertCircle size={12} /> Error
                    </span>
                );
            default:
                return (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 text-slate-500 rounded-full text-[10px] font-black border border-slate-100 uppercase tracking-wider">
                        <Clock size={12} /> Pendiente
                    </span>
                );
        }
    };

    const filteredAssets = assets.filter((a) => {
        const matchesSearch =
            a.display_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            a.dataset_code.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesStatus = filterStatus === 'ALL' || a.status === filterStatus;
        return matchesSearch && matchesStatus;
    });

    const updatedCount = assets.filter((a) => a.status === 'UPDATED').length;

    // Agrupar por categoría (si existe)
    const groupedAssets = filteredAssets.reduce((groups, asset) => {
        const category = asset.category || 'OTROS';
        if (!groups[category]) groups[category] = [];
        groups[category].push(asset);
        return groups;
    }, {});

    const categories = Object.keys(groupedAssets).sort();

    return (
        <div className="p-6 space-y-8 bg-slate-50 min-h-screen">
            <div className="bg-[#1A1A2E] text-white p-8 rounded-[2rem] shadow-2xl relative overflow-hidden">
                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="p-3 bg-indigo-500/20 rounded-2xl">
                            <ShieldCheck className="text-indigo-400" size={32} />
                        </div>
                        <div>
                            <h1 className="text-4xl font-black tracking-tighter uppercase">Monitor Policía Nacional</h1>
                            <p className="text-white/60 font-medium text-sm mt-1">
                                Seguimiento de activos locales (Boletín) y nacionales (SIEDCO).
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* TARJETA MANUAL - BOLETÍN SEMANAL */}
                <div className="bg-white p-6 rounded-2xl border-2 border-dashed border-indigo-200 shadow-sm hover:border-indigo-500 transition-all group flex flex-col justify-between">
                    <div>
                        <div className="flex justify-between items-start mb-2">
                            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                                <Database size={24} />
                            </div>
                            <span className="px-2 py-1 bg-amber-100 text-amber-700 text-[9px] font-black uppercase rounded-full tracking-widest">Requiere Acción Manual</span>
                        </div>
                        <h3 className="font-black text-slate-800 text-lg uppercase tracking-tight group-hover:text-indigo-600 transition-colors mt-2">
                            Base de Datos (Excel) Semanal
                        </h3>
                        <p className="text-xs text-slate-500 mt-2 font-medium">Sube aquí la base de datos completa en formato Excel (con todas sus columnas) entregada localmente por la Estación de Policía Jamundí.</p>
                    </div>
                    <button
                        onClick={() => onIngest('POLICIA_SEMANAL', 'Base de Datos Policía')}
                        className="mt-6 w-full py-3 bg-indigo-600 text-white rounded-xl text-xs font-black hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-200 flex items-center justify-center gap-2 uppercase tracking-widest"
                    >
                        <CheckCircle2 size={16} /> SUBIR EXCEL (BD)
                    </button>
                </div>

                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-center">
                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Activos Nacionales Monitoreados</div>
                    <div className="text-4xl font-black text-slate-800 tracking-tighter">{assets.length}</div>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-center">
                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Último Chequeo Automático</div>
                    <div className="text-sm font-bold text-slate-600 truncate mt-1">
                        {assets.length > 0 && assets[0].last_checked_at ? new Date(assets[0].last_checked_at).toLocaleString() : 'Nunca'}
                    </div>
                </div>
            </div>

            {/* Filters */}
            <div className="flex flex-col md:flex-row gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                    <input
                        type="text"
                        placeholder="Buscar por código o nombre..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-medium text-sm"
                    />
                </div>
                <div className="flex gap-2 bg-white p-1.5 border border-slate-200 rounded-2xl">
                    {['ALL', 'UPDATED', 'UNCHANGED', 'ERROR'].map((s) => (
                        <button
                            key={s}
                            onClick={() => setFilterStatus(s)}
                            className={`px-4 py-2 rounded-xl text-[10px] font-black transition-all ${filterStatus === s ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-50'}`}
                        >
                            {s === 'ALL' ? 'TODOS' : s}
                        </button>
                    ))}
                </div>
            </div>

            {/* Asset List Grouped */}
            <div className="space-y-8">
                {loading ? (
                    <div className="bg-white rounded-3xl p-20 text-center border border-slate-100 shadow-xl">
                        <RefreshCcw className="mx-auto h-10 w-10 text-slate-200 animate-spin" />
                    </div>
                ) : categories.length === 0 ? (
                    <div className="bg-white rounded-3xl p-20 text-center text-slate-400 italic border border-slate-100 shadow-xl">
                        No se encontraron activos con estos criterios
                    </div>
                ) : (
                    categories.map((category) => (
                        <div key={category} className="space-y-4">
                            <div className="flex items-center gap-3 px-2">
                                <div className="h-px w-8 bg-slate-200" />
                                <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-[0.3em]">{category}</h3>
                                <div className="h-px flex-1 bg-slate-100" />
                            </div>
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                {groupedAssets[category].map((asset) => (
                                    <div key={asset.id} className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-all group">
                                        <div className="flex justify-between items-start mb-4">
                                            <div>
                                                <div className="font-black text-slate-800 text-sm group-hover:text-indigo-600 transition-colors uppercase tracking-tight">
                                                    {asset.display_name}
                                                </div>
                                                <div className="font-mono text-[9px] text-slate-400 font-bold tracking-tighter">
                                                    ID: {asset.dataset_code}
                                                </div>
                                            </div>
                                            {getStatusBadge(asset.status)}
                                        </div>
                                        <div className="flex items-center justify-between mt-auto pt-4 border-t border-slate-50">
                                            <div className="flex gap-1">
                                                <a
                                                    href={asset.file_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    title="Descargar archivo original"
                                                    className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
                                                >
                                                    <ExternalLink size={16} />
                                                </a>
                                                <button
                                                    onClick={() => handleCheckUpdates(asset.dataset_code)}
                                                    title="Revisar actualizaciones"
                                                    className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
                                                >
                                                    <RefreshCcw size={16} className={checking ? 'animate-spin' : ''} />
                                                </button>
                                            </div>
                                            <button
                                                onClick={() => onIngest(asset.dataset_code, asset.display_name)}
                                                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-[10px] font-black hover:bg-indigo-600 transition-all shadow-lg active:scale-95 uppercase tracking-widest"
                                            >
                                                CARGAR DATOS
                                            </button>
                                        </div>
                                        {asset.last_checked_at && (
                                            <div className="mt-3 flex items-center gap-2 text-[9px] text-slate-400 font-bold uppercase tracking-tight">
                                                <Clock size={10} /> Vigencia: {new Date(asset.last_checked_at).toLocaleDateString()}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Info Footer */}
            <div className="bg-indigo-50 p-6 rounded-3xl border border-indigo-100 flex gap-4">
                <Info className="text-indigo-500 shrink-0" size={24} />
                <div>
                    <h4 className="font-black text-sm text-indigo-900 uppercase tracking-widest mb-1">¿Cómo funciona la detección?</h4>
                    <p className="text-xs text-indigo-700/80 font-medium leading-relaxed">
                        El sistema realiza peticiones de cabecera (HEAD) a los servidores de la Policía Nacional. Comparamos los valores de <strong>ETag</strong>, <strong>Last-Modified</strong> y <strong>Content-Length</strong>. Si cualquiera de estos valores cambia, el activo se marca como <strong>UPDATED</strong> y se bloquea su ingesta manual hasta que se confirme la carga del nuevo archivo.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default PoliceMonitor;
