import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Archive, Download, FileText, Loader2, Paperclip, RefreshCw, Upload } from 'lucide-react';
import { apiFetch, apiJson, readApiError } from '../utils/apiClient';
import { ESTADOS_ACTA, anioActa, fechaActa, filtrarActas, resumenPorInstancia, sinActaOficial, tamanoArchivo } from '../utils/archivoActas';

// Archivo de actas: todas las actas digitalizadas de las reuniones (Consejo, comités, planeación), con su original.
const ArchivoActas = ({ onNavigate }) => {
    const [actas, setActas] = useState([]);
    const [cargando, setCargando] = useState(true);
    const [error, setError] = useState('');
    const [aviso, setAviso] = useState('');
    const [filtros, setFiltros] = useState({ instancia: '', anio: '', estado: '' });
    const [trabajando, setTrabajando] = useState(null);
    const archivoRef = useRef(null);
    const destino = useRef(null);

    const cargar = useCallback(async () => {
        setCargando(true);
        setError('');
        try {
            setActas(await apiJson('/council-commitments/acts/archive'));
        } catch (requestError) {
            setError(requestError.message || 'No se pudo consultar el archivo de actas.');
        } finally {
            setCargando(false);
        }
    }, []);
    useEffect(() => { cargar(); }, [cargar]);

    const resumen = useMemo(() => resumenPorInstancia(actas), [actas]);
    const anios = useMemo(() => [...new Set(actas.map(anioActa).filter(Boolean))].sort((a, b) => b - a), [actas]);
    const visibles = useMemo(() => filtrarActas(actas, filtros), [actas, filtros]);

    const descargar = async (acta) => {
        setTrabajando(acta.read_id);
        setAviso('');
        try {
            const response = await apiFetch(`/council-commitments/acts/${acta.read_id}/file`);
            if (!response.ok) throw new Error(await readApiError(response));
            const url = URL.createObjectURL(await response.blob());
            const enlace = document.createElement('a');
            enlace.href = url;
            enlace.download = acta.filename || 'acta';
            enlace.click();
            setTimeout(() => URL.revokeObjectURL(url), 10000);
        } catch (requestError) {
            setAviso(requestError.message);
        } finally {
            setTrabajando(null);
        }
    };

    const elegirOriginal = (acta) => {
        destino.current = acta;
        archivoRef.current?.click();
    };

    const adjuntar = async (event) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        const acta = destino.current;
        if (!file || !acta) return;
        setTrabajando(acta.read_id);
        setAviso('');
        try {
            const body = new FormData();
            body.append('file', file);
            const response = await apiFetch(`/council-commitments/acts/${acta.read_id}/file`, { method: 'POST', body });
            if (!response.ok) throw new Error(await readApiError(response));
            setAviso(`Archivo original guardado para el acta del ${fechaActa(acta.act_date)}.`);
            await cargar();
        } catch (requestError) {
            setAviso(requestError.message);
        } finally {
            setTrabajando(null);
        }
    };

    const filtro = (clave) => (event) => setFiltros({ ...filtros, [clave]: event.target.value });

    return (
        <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-6">
            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Gestión documental</p>
                    <h1 className="mt-1 flex items-center gap-2 text-3xl font-black text-slate-950"><Archive size={28} /> Archivo de actas</h1>
                    <p className="mt-2 max-w-3xl text-sm font-semibold text-slate-600">
                        Todas las actas digitalizadas de las reuniones: Consejo de Seguridad, comités y planeación. Para subir un acta nueva use «Leer acta» en Compromisos y acuerdos; aquí queda archivada con su original.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    {onNavigate && (
                        <button type="button" onClick={() => onNavigate('council_commitments')} className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8]">
                            <Upload size={17} /> Subir un acta nueva
                        </button>
                    )}
                    <button type="button" onClick={cargar} aria-label="Recargar" className="inline-flex min-h-11 items-center border border-slate-300 bg-white px-3 text-slate-700 hover:bg-slate-50">
                        <RefreshCw size={17} />
                    </button>
                </div>
            </header>

            {error && <p role="alert" className="border-l-4 border-red-500 bg-red-50 p-4 text-sm font-bold text-red-800">{error}</p>}
            {aviso && <p role="status" className="border-l-4 border-[#281FD0] bg-indigo-50 p-4 text-sm font-bold text-indigo-950">{aviso}</p>}

            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Resumen por instancia">
                {resumen.map((g) => (
                    <button type="button" key={g.instancia} onClick={() => setFiltros({ ...filtros, instancia: filtros.instancia === g.instancia ? '' : g.instancia })}
                        className={`border bg-white p-4 text-left hover:border-[#281FD0] ${filtros.instancia === g.instancia ? 'border-[#281FD0] ring-2 ring-[#281FD0]/20' : 'border-slate-200'}`}>
                        <p className="text-sm font-black text-slate-900">{g.nombre}</p>
                        <p className="mt-1 text-3xl font-black tabular-nums text-[#281FD0]">{g.total}</p>
                        <p className="text-xs font-semibold text-slate-500">actas · la más reciente: {g.ultima ? fechaActa(g.ultima) : '—'}</p>
                        <div className="mt-2 flex flex-wrap gap-1 text-[11px] font-bold">
                            {g.pendientes > 0 && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-900">{g.pendientes} por revisar</span>}
                            {g.sinArchivo > 0 && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-700">{g.sinArchivo} sin original</span>}
                            {g.sinOficial > 0 && <span className="rounded bg-red-50 px-1.5 py-0.5 text-red-800">{g.sinOficial} sin acta oficial</span>}
                        </div>
                    </button>
                ))}
            </section>

            <section className="flex flex-wrap gap-3 border border-slate-200 bg-white p-4" aria-label="Filtros">
                <label className="text-xs font-black uppercase text-slate-500">Instancia
                    <select value={filtros.instancia} onChange={filtro('instancia')} className="mt-1 block min-h-10 border border-slate-300 px-2 text-sm font-bold text-slate-800">
                        <option value="">Todas</option>
                        {resumen.map((g) => <option key={g.instancia} value={g.instancia}>{g.nombre}</option>)}
                    </select>
                </label>
                <label className="text-xs font-black uppercase text-slate-500">Año
                    <select value={filtros.anio} onChange={filtro('anio')} className="mt-1 block min-h-10 border border-slate-300 px-2 text-sm font-bold text-slate-800">
                        <option value="">Todos</option>
                        {anios.map((anio) => <option key={anio} value={anio}>{anio}</option>)}
                    </select>
                </label>
                <label className="text-xs font-black uppercase text-slate-500">Estado
                    <select value={filtros.estado} onChange={filtro('estado')} className="mt-1 block min-h-10 border border-slate-300 px-2 text-sm font-bold text-slate-800">
                        <option value="">Todos</option>
                        {Object.entries(ESTADOS_ACTA).map(([codigo, info]) => <option key={codigo} value={codigo}>{info.etiqueta}</option>)}
                    </select>
                </label>
                <p className="ml-auto self-end text-sm font-bold text-slate-500">{visibles.length} de {actas.length} actas</p>
            </section>

            <input ref={archivoRef} type="file" accept=".pdf,.docx,.doc,.txt" onChange={adjuntar} className="hidden" />

            {cargando ? (
                <p className="flex items-center justify-center gap-2 p-10 text-sm font-bold text-slate-500"><Loader2 size={18} className="animate-spin" /> Consultando el archivo…</p>
            ) : (
                <div className="overflow-x-auto border border-slate-200 bg-white">
                    <table className="w-full min-w-[860px] text-left text-sm">
                        <thead className="bg-slate-100 text-xs uppercase text-slate-600">
                            <tr>
                                <th className="px-3 py-2">Fecha</th><th className="px-3 py-2">Instancia</th><th className="px-3 py-2">Acta</th>
                                <th className="px-3 py-2">Estado</th><th className="px-3 py-2 text-right">Compromisos</th>
                                <th className="px-3 py-2">Cargada</th><th className="px-3 py-2">Original</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {visibles.map((acta) => {
                                const estado = ESTADOS_ACTA[acta.status] || ESTADOS_ACTA.HISTORICA;
                                return (
                                    <tr key={acta.read_id} className="align-top">
                                        <td className="px-3 py-2 font-bold text-slate-900">{fechaActa(acta.act_date)}</td>
                                        <td className="px-3 py-2 text-slate-700">{acta.instance_label}</td>
                                        <td className="px-3 py-2">
                                            <p className="flex items-start gap-1.5 font-semibold text-slate-800"><FileText size={15} className="mt-0.5 shrink-0 text-slate-400" />{acta.act_number ? `Acta ${acta.act_number}` : acta.filename}</p>
                                            {sinActaOficial(acta) && <p className="mt-1 flex items-center gap-1 text-xs font-bold text-red-700"><AlertTriangle size={13} /> Sin acta oficial: conviene pedirla</p>}
                                        </td>
                                        <td className="px-3 py-2"><span className={`inline-block border px-2 py-0.5 text-xs font-black ${estado.clase}`}>{estado.etiqueta}</span></td>
                                        <td className="px-3 py-2 text-right font-bold tabular-nums text-slate-800">{acta.commitments}</td>
                                        <td className="px-3 py-2 text-xs font-semibold text-slate-500">{acta.created_by}<br />{acta.created_at ? fechaActa(acta.created_at) : ''}</td>
                                        <td className="px-3 py-2">
                                            {acta.has_file ? (
                                                <button type="button" disabled={trabajando === acta.read_id} onClick={() => descargar(acta)}
                                                    className="inline-flex min-h-9 items-center gap-1.5 border border-slate-300 px-2.5 text-xs font-black text-slate-700 hover:bg-slate-50 disabled:opacity-40">
                                                    {trabajando === acta.read_id ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} Descargar ({tamanoArchivo(acta.file_size)})
                                                </button>
                                            ) : (
                                                <button type="button" disabled={trabajando === acta.read_id} onClick={() => elegirOriginal(acta)} title="Debe ser exactamente el mismo archivo que se leyó"
                                                    className="inline-flex min-h-9 items-center gap-1.5 border border-dashed border-slate-400 px-2.5 text-xs font-black text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                                                    {trabajando === acta.read_id ? <Loader2 size={14} className="animate-spin" /> : <Paperclip size={14} />} Adjuntar original
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                            {!visibles.length && <tr><td colSpan={7} className="px-3 py-8 text-center text-sm font-bold text-slate-500">No hay actas para este filtro.</td></tr>}
                        </tbody>
                    </table>
                </div>
            )}
            <p className="text-xs font-semibold text-slate-500">
                «Adjuntar original» acepta solo el mismo archivo que se leyó (el SISC lo comprueba). Las actas nuevas guardan su original automáticamente. Cada descarga queda registrada en la auditoría.
            </p>
        </div>
    );
};

export default ArchivoActas;
