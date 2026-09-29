import React, { useState, useEffect, useRef } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import {
    Search, Filter, Calendar, FileText, TrendingUp, AlertCircle,
    MapPin, Clock, CheckCircle2, DollarSign, ChevronRight, List,
    History as HistoryIcon, Info, Download, Loader2, ArrowRight, Upload, X
} from 'lucide-react';

import { API_BASE_URL } from '../utils/apiConfig';
import TendenciaConvivencia from '../components/TendenciaConvivencia';

const COLORS = ['#281FD0', '#34D399', '#FBBF24', '#EF4444', '#8B5CF6'];

// Barrio vacío o de relleno en el reporte del RNMC ("NONE", "SIN DATO", "NO APLICA...").
const SIN_BARRIO = /^(|NONE|NAN|NULL|0|-|SIN DATO|SIN BARRIO|NO APLICA.*)$/i;
const barrio = (valor) => (SIN_BARRIO.test(String(valor ?? '').trim()) ? 'Sin barrio' : valor);
const textoActuacion = (valor) => (!valor || /^(none|nan|null)$/i.test(String(valor).trim()) ? 'Registro en el RNMC' : valor);

const ROLES_OPERATIVOS = ['ANALYST', 'SOURCE_UPLOADER', 'FUNC_ADMIN', 'TI_ADMIN'];

const InspeccionesModule = ({ userRoles = [] }) => {
    const opera = userRoles.some((rol) => ROLES_OPERATIVOS.includes(rol));
    const [activeTab, setActiveTab] = useState(opera ? 'operativo' : 'analitico');
    const [loading, setLoading] = useState(false);
    const [stats, setStats] = useState(null);
    const [expedientes, setExpedientes] = useState({ items: [], total: 0 });
    const [filters, setFilters] = useState({ localidad: '' });
    const [selectedExp, setSelectedExp] = useState(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState(null);
    const [convivencia, setConvivencia] = useState(null);
    const fileInputRef = useRef(null);

    const fetchConvivencia = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/inspecciones/stats/convivencia`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) setConvivencia(await res.json());
        } catch (err) {
            console.error("Error convivencia:", err);
        }
    };

    const fetchStats = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/inspecciones/stats/summary`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setStats(data);
        } catch (err) {
            console.error("Error stats:", err);
        }
    };

    const fetchExpedientes = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const params = new URLSearchParams(filters);
            const res = await fetch(`${API_BASE_URL}/inspecciones/expedientes?${params.toString()}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setExpedientes(data);
        } catch (err) {
            console.error("Error list:", err);
        } finally {
            setLoading(false);
        }
    };

    const fetchDetail = async (numero) => {
        setLoadingDetail(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/inspecciones/expedientes/${numero}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setSelectedExp(data);
        } catch (err) {
            console.error("Error detail:", err);
        } finally {
            setLoadingDetail(false);
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setUploading(true);
        setUploadStatus({ text: "Analizando calidad de datos...", type: "info" });

        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/inspecciones/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            const result = await res.json();

            if (res.ok) {
                const quality = result.quality;
                const qualityLabel = quality?.semaforo ? ` Calidad ${quality.semaforo.toLowerCase()}.` : '';
                setUploadStatus({
                    text: `Carga terminada: ${result.inserted} nuevos, ${result.skipped} ignorados.${qualityLabel}`,
                    type: quality?.semaforo === 'AMARILLO' ? "warning" : "success",
                    quality,
                });
                fetchExpedientes();
                fetchStats();
                fetchConvivencia();
            } else {
                const detail = result.detail;
                const message = typeof detail === 'object' ? detail?.message : detail;
                setUploadStatus({
                    text: message || 'No fue posible procesar el archivo.',
                    type: "error",
                    quality: typeof detail === 'object' ? detail : null,
                });
            }
        } catch (err) {
            setUploadStatus({ text: "Error de conexión", type: "error" });
        } finally {
            setUploading(false);
            e.target.value = null;
        }
    };

    useEffect(() => {
        fetchStats();
        fetchExpedientes();
    }, [filters]);

    useEffect(() => {
        fetchConvivencia();
    }, []);

    const numero = (valor) => new Intl.NumberFormat('es-CO').format(Number(valor || 0));
    const porcentaje = (valor) => `${String(valor ?? 0).replace('.', ',')}%`;
    const minuscula = (texto) => (texto ? texto.charAt(0).toLowerCase() + texto.slice(1) : '');
    const anio = stats?.anio ? ` ${stats.anio}` : '';

    // Las cuatro cifras son del mismo año (el del último comparendo cargado).
    const kpis = [
        { label: `Comparendos${anio}`, value: numero(stats?.comparendos), icon: Folder, color: 'bg-indigo-50 text-indigo-600' },
        { label: `Medidas${anio}`, value: numero(stats?.medidas), icon: List, color: 'bg-emerald-50 text-emerald-600' },
        { label: `Ratificadas${anio}`, value: numero(stats?.ratificadas), icon: CheckCircle2, color: 'bg-blue-50 text-blue-600' },
        { label: `Pagadas${anio}`, value: numero(stats?.pagadas), icon: DollarSign, color: 'bg-amber-50 text-amber-600' }
    ];

    // Lectura automática: solo describe lo que dicen las cifras, sin adivinar causas.
    const lectura = (() => {
        if (!convivencia?.total) return null;
        const partes = [];
        const primero = convivencia.comportamientos?.[0];
        if (primero) partes.push(`${porcentaje(primero.porcentaje)} de los comparendos del año son por ${minuscula(primero.etiqueta)}.`);
        const barrio = convivencia.barrios?.[0];
        if (barrio) {
            let texto = `El barrio con más comparendos es ${barrio.barrio} (${numero(barrio.total)}, ${porcentaje(barrio.porcentaje)} del total)`;
            if (barrio.principal) texto += `, sobre todo por ${minuscula(barrio.principal.etiqueta)} (${porcentaje(barrio.principal.porcentaje)})`;
            partes.push(texto + '.');
        }
        const dias = [...(convivencia.dias || [])].sort((x, y) => y.total - x.total);
        if (dias[0]?.total) partes.push(`El día con más comparendos es el ${dias[0].dia.toLowerCase()} (${numero(dias[0].total)}).`);
        return partes.join(' ');
    })();
    const sinArticulo = convivencia
        ? Math.max(0, convivencia.total - (convivencia.comportamientos || []).reduce((total, item) => total + item.total, 0))
        : 0;

    return (
        <div className="space-y-8 pb-20 p-6 max-w-7xl mx-auto">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                    <h1 className="text-4xl font-black tracking-tighter text-slate-900 uppercase">Inspecciones de Policía</h1>
                    <p className="text-slate-500 font-bold tracking-tight">Comparendos y medidas correctivas del RNMC</p>
                    <p className="text-slate-400 text-sm font-semibold mt-1">Cada mes suba los dos reportes del RNMC: medidas pendientes (comparendos) y medidas gestionadas.</p>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={() => fileInputRef.current.click()}
                        disabled={uploading}
                        className="bg-[#281FD0] text-white px-8 py-4 rounded-3xl font-black uppercase text-xs tracking-widest shadow-2xl shadow-indigo-200 flex items-center gap-3 hover:scale-105 transition-transform disabled:opacity-50"
                    >
                        {uploading ? <Loader2 className="animate-spin" size={20} /> : <Upload size={20} />}
                        Cargar reportes del RNMC
                    </button>
                    <input type="file" ref={fileInputRef} onChange={handleUpload} className="hidden" accept=".xlsx,.xls" />
                </div>
            </div>

            {uploadStatus && (
                <div className={`p-6 rounded-[2rem] border-2 flex items-center justify-between ${
                    uploadStatus.type === 'error' ? 'bg-red-50 border-red-100 text-red-700' :
                    uploadStatus.type === 'success' ? 'bg-emerald-50 border-emerald-100 text-emerald-700' :
                    uploadStatus.type === 'warning' ? 'bg-amber-50 border-amber-100 text-amber-700' :
                    'bg-indigo-50 border-indigo-100 text-indigo-700'
                }`}>
                    <div className="flex items-center gap-4">
                        {uploadStatus.type === 'info' && <Loader2 className="animate-spin" />}
                        {uploadStatus.type === 'success' && <CheckCircle2 />}
                        {uploadStatus.type === 'warning' && <AlertCircle />}
                        {uploadStatus.type === 'error' && <AlertCircle />}
                        <p className="font-black text-sm uppercase tracking-widest">{uploadStatus.text}</p>
                    </div>
                    <button onClick={() => setUploadStatus(null)}><X size={20} /></button>
                </div>
            )}

            {/* KPIs */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                {kpis.map((k, i) => (
                    <div key={i} className="bg-white p-8 rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50 transition-all hover:translate-y-[-4px]">
                        <div className={`p-4 rounded-2xl w-fit mb-6 ${k.color}`}>
                            <k.icon size={28} />
                        </div>
                        <p className="text-slate-400 text-xs font-black uppercase tracking-widest">{k.label}</p>
                        <p className="text-4xl font-black text-slate-900 mt-2">{k.value}</p>
                    </div>
                ))}
            </div>
            {stats?.corte && <p className="-mt-4 text-xs font-semibold text-slate-500">Cifras de {stats.anio} hasta el {stats.corte}. Cada comparendo se cuenta una vez; una medida es lo que se impuso en cada comparendo.</p>}

            {/* Tabs */}
            <div className="flex gap-4 p-1.5 bg-slate-100 w-fit rounded-[2rem] border border-slate-200">
                <button
                    onClick={() => setActiveTab('operativo')}
                    className={`px-10 py-3 rounded-full text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'operativo' ? 'bg-[#281FD0] text-white shadow-lg' : 'text-slate-500 hover:bg-white'}`}
                >
                    Módulo Operativo
                </button>
                <button
                    onClick={() => setActiveTab('analitico')}
                    className={`px-10 py-3 rounded-full text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'analitico' ? 'bg-[#281FD0] text-white shadow-lg' : 'text-slate-500 hover:bg-white'}`}
                >
                    Convivencia: qué y dónde
                </button>
            </div>

            {activeTab === 'operativo' ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                    {/* List */}
                    <div className={`${selectedExp ? 'lg:col-span-2' : 'lg:col-span-3'} bg-white rounded-[3rem] shadow-2xl shadow-slate-100 overflow-hidden border border-slate-50`}>
                        <div className="p-8 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                            <div>
                                <h3 className="font-black text-slate-900 uppercase tracking-tighter text-xl">Comparendos más recientes</h3>
                                <p className="text-xs font-semibold text-slate-500">{numero(expedientes.total)} expedientes · los más recientes primero</p>
                            </div>
                            <div className="flex items-center bg-white rounded-2xl px-4 py-2 border border-slate-200">
                                <Search size={16} className="text-slate-400 mr-2" />
                                <input
                                    placeholder="Barrio o expediente..."
                                    className="text-sm font-bold outline-none w-32"
                                    onChange={e => setFilters({localidad: e.target.value})}
                                />
                            </div>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="bg-slate-50/50 border-b border-slate-50">
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Fecha</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Expediente</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Barrio</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Comportamiento</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Estado</th>
                                        <th className="px-6 py-4" aria-label="Detalle" />
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {expedientes.items && expedientes.items.map(exp => (
                                        <tr key={exp.id} onClick={() => fetchDetail(exp.numero_expediente)}
                                            className={`group cursor-pointer transition-colors ${selectedExp?.expediente?.numero_expediente === exp.numero_expediente ? 'bg-indigo-50' : 'hover:bg-indigo-50/30'}`}>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-slate-700 tabular-nums">{exp.fecha || '—'}</td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-black text-slate-900">{exp.numero_expediente}</td>
                                            <td className="px-6 py-4 text-sm font-bold text-slate-600">{barrio(exp.localidad)}</td>
                                            <td className="px-6 py-4 text-sm font-semibold text-slate-600">{exp.comportamiento || 'Sin artículo'}</td>
                                            <td className="px-6 py-4 text-xs font-black uppercase text-slate-500">{exp.estados || '—'}</td>
                                            <td className="px-6 py-4 text-[#281FD0]"><ChevronRight size={16} /></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Detalle: solo aparece al escoger un expediente */}
                    {selectedExp && (
                    <div className="bg-slate-900 rounded-[3.5rem] p-10 text-white shadow-2xl shadow-indigo-100 relative overflow-hidden lg:sticky lg:top-6">
                        <div className="absolute top-0 right-0 p-20 bg-indigo-500/10 blur-[100px] rounded-full"></div>
                            <div className="relative z-10 space-y-8">
                                <button onClick={() => setSelectedExp(null)} className="absolute right-0 top-0 text-white/60 hover:text-white" aria-label="Cerrar detalle"><X size={20} /></button>
                                <div>
                                    <span className="text-[10px] font-black uppercase tracking-[0.3em] text-indigo-400">Detalle de Actuación</span>
                                    <h2 className="text-4xl font-black mt-2 tracking-tighter">{selectedExp.expediente.numero_expediente}</h2>
                                    <p className="flex items-center gap-2 text-indigo-200/60 font-bold mt-2">
                                        <MapPin size={16} /> {barrio(selectedExp.expediente.localidad)}
                                    </p>
                                </div>

                                <div className="space-y-6">
                                    <h4 className="text-xs font-black uppercase tracking-widest text-indigo-400 border-b border-white/10 pb-4">Medidas Aplicadas</h4>
                                    {selectedExp.medidas.map(m => (
                                        <div key={m.id} className="bg-white/5 p-6 rounded-3xl border border-white/5 space-y-4">
                                            <div className="flex justify-between items-start">
                                                <div className="w-2/3">
                                                    <p className="font-black text-lg leading-tight">{m.nombre}</p>
                                                    {m.articulo && <p className="mt-1 text-xs font-semibold text-indigo-200/80">{m.articulo}</p>}
                                                </div>
                                                <span className="bg-indigo-500 text-[10px] px-3 py-1.5 rounded-full font-black uppercase">{m.estado}</span>
                                            </div>

                                            {m.finanzas && (
                                                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/5">
                                                    <div>
                                                        <p className="text-[10px] font-black text-white/40 uppercase">Multa Total</p>
                                                        <p className="font-black text-xl">${m.finanzas.valor_neto?.toLocaleString()}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-[10px] font-black text-white/40 uppercase">Pagado</p>
                                                        <p className="font-black text-xl text-emerald-400">${m.finanzas.valor_pagado?.toLocaleString()}</p>
                                                    </div>
                                                </div>
                                            )}

                                            <div className="space-y-3">
                                                <p className="text-[10px] font-black text-white/40 uppercase">Línea de Tiempo</p>
                                                {m.actuaciones.map((a, idx) => (
                                                    <div key={idx} className="flex gap-3 items-start">
                                                        <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-1.5"></div>
                                                        <div>
                                                            <p className="text-xs font-bold text-white/90">{textoActuacion(a.anotacion)}</p>
                                                            <p className="text-[10px] text-white/40 mt-0.5">{new Date(a.fecha_actuacion).toLocaleDateString()}</p>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                    </div>
                    )}
                </div>
            ) : (
                <div className="space-y-8">
                    {!convivencia?.total ? (
                        <div className="bg-white p-10 rounded-[2.5rem] border border-slate-100 text-slate-500 font-bold">
                            Todavía no hay comparendos cargados. Suba los reportes del RNMC con el botón de arriba.
                        </div>
                    ) : (
                        <>
                            <div className="bg-[#281FD0] text-white p-8 rounded-[2.5rem] shadow-xl shadow-indigo-100">
                                <p className="text-xs font-black uppercase tracking-widest text-indigo-200">Lectura del Observatorio · corte {convivencia.corte}</p>
                                <p className="mt-3 text-lg font-bold leading-relaxed">{lectura}</p>
                                <p className="mt-3 text-xs text-indigo-200 font-semibold">Cada comparendo se cuenta una vez. Fuente: RNMC, Policía Nacional (reportes de medidas pendientes y gestionadas).</p>
                            </div>

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
                                <div className="bg-white p-8 rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50">
                                    <h3 className="text-xl font-black text-slate-900 mb-6 flex items-center gap-3">
                                        <TrendingUp className="text-indigo-600" /> Comportamientos que más originan comparendos
                                    </h3>
                                    <div className="space-y-4">
                                        {convivencia.comportamientos.map(item => (
                                            <div key={item.articulo} title={item.texto_oficial}>
                                                <div className="flex justify-between gap-4 text-sm">
                                                    <p className="font-bold text-slate-800">{item.etiqueta} <span className="text-slate-400 font-semibold">(art. {item.articulo})</span></p>
                                                    <p className="font-black text-slate-900 tabular-nums whitespace-nowrap">{numero(item.total)} · {porcentaje(item.porcentaje)}</p>
                                                </div>
                                                <div className="mt-1.5 h-2.5 rounded-full bg-slate-100 overflow-hidden">
                                                    <div className="h-full rounded-full bg-[#281FD0]" style={{ width: `${Math.max(item.porcentaje, 1)}%` }} />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                    {sinArticulo > 0 && (
                                        <p className="mt-6 text-xs text-slate-500 font-semibold">{numero(sinArticulo)} comparendos vienen solo del reporte de medidas gestionadas, que no trae el artículo.</p>
                                    )}
                                </div>

                                <div className="bg-white p-8 rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50">
                                    <h3 className="text-xl font-black text-slate-900 mb-6 flex items-center gap-3">
                                        <MapPin className="text-indigo-600" /> Barrios con más comparendos
                                    </h3>
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left text-sm">
                                            <thead>
                                                <tr className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100">
                                                    <th className="py-2 pr-3">Barrio</th>
                                                    <th className="py-2 pr-3 text-right">Comparendos</th>
                                                    <th className="py-2 pr-3">Comportamiento principal</th>
                                                    <th className="py-2 text-right">Fin de semana</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-50">
                                                {convivencia.barrios.map(item => (
                                                    <tr key={item.barrio}>
                                                        <td className="py-3 pr-3 font-black text-slate-900">{item.barrio}</td>
                                                        <td className="py-3 pr-3 text-right font-black tabular-nums">{numero(item.total)}</td>
                                                        <td className="py-3 pr-3 text-slate-600 font-semibold">
                                                            {item.principal ? `${item.principal.etiqueta} (${porcentaje(item.principal.porcentaje)})` : 'Sin artículo'}
                                                        </td>
                                                        <td className="py-3 text-right font-bold tabular-nums">{porcentaje(item.fin_de_semana_pct)}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                    <p className="mt-4 text-xs text-slate-500 font-semibold">Fin de semana: parte de los comparendos del barrio que fueron sábado o domingo. Si se repartieran parejo en la semana, sería cerca del 29%.</p>
                                </div>

                                <div className="bg-white p-8 rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50">
                                    <h3 className="text-xl font-black text-slate-900 mb-6 flex items-center gap-3">
                                        <Calendar className="text-indigo-600" /> Por día de la semana
                                    </h3>
                                    <ResponsiveContainer width="100%" height={260}>
                                        <BarChart data={convivencia.dias}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                            <XAxis dataKey="dia" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11, fontWeight: 700 }} />
                                            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                                            <Tooltip formatter={(valor) => [numero(valor), 'Comparendos']} cursor={{ fill: '#f8fafc' }} />
                                            <Bar dataKey="total" fill="#281FD0" radius={[8, 8, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>

                                <div className="bg-white p-8 rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50">
                                    <h3 className="text-xl font-black text-slate-900 mb-6 flex items-center gap-3">
                                        <Clock className="text-indigo-600" /> Por mes
                                    </h3>
                                    <ResponsiveContainer width="100%" height={260}>
                                        <BarChart data={convivencia.meses}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                            <XAxis dataKey="mes" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11, fontWeight: 700 }} />
                                            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                                            <Tooltip formatter={(valor) => [numero(valor), 'Comparendos']} cursor={{ fill: '#f8fafc' }} />
                                            <Bar dataKey="total" fill="#34D399" radius={[8, 8, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                    <p className="mt-2 text-xs text-slate-500 font-semibold">El último mes puede estar incompleto: llega hasta el corte.</p>
                                </div>
                            </div>
                            <TendenciaConvivencia />
                        </>
                    )}
                </div>
            )}
        </div>
    );
};

// Simple icon fallbacks since I don't have all lucide-react in mind
const Folder = ({size, className}) => <FileText size={size} className={className} />;

export default InspeccionesModule;
