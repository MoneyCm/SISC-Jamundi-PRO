import React, { useEffect, useState } from 'react';
import { Building2, UserCog, Plus, Loader2, AlertCircle } from 'lucide-react';

import { API_BASE_URL } from '../utils/apiConfig';
import { localToday } from '../utils/localDate';
import { etiquetaInspeccion, porcentajeResuelto, millones } from '../utils/inspecciones';

const numero = (valor) => new Intl.NumberFormat('es-CO').format(Number(valor || 0));
const autorizacion = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const FORMULARIO_VACIO = { documento: '', nombre: '', inspeccion: 'SEGUNDA', desde: '' };

// Gestión del año por inspección (despacho) y, para quien carga los reportes, la tabla de
// funcionarios que dice en qué inspección registra cada documento del RNMC.
const GestionPorInspeccion = ({ opera = false, recargar = 0, onCambio }) => {
    const [gestion, setGestion] = useState(null);
    const [funcionarios, setFuncionarios] = useState({ items: [], inspecciones: [] });
    const [formulario, setFormulario] = useState(FORMULARIO_VACIO);
    const [cierre, setCierre] = useState({});
    const [guardando, setGuardando] = useState(false);
    const [error, setError] = useState(null);

    const cargarGestion = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/inspecciones/stats/por-inspeccion`, { headers: autorizacion() });
            if (res.ok) setGestion(await res.json());
        } catch (err) {
            console.error('Error gestión por inspección:', err);
        }
    };

    const cargarFuncionarios = async () => {
        if (!opera) return;
        try {
            const res = await fetch(`${API_BASE_URL}/inspecciones/funcionarios`, { headers: autorizacion() });
            if (res.ok) setFuncionarios(await res.json());
        } catch (err) {
            console.error('Error funcionarios:', err);
        }
    };

    useEffect(() => { cargarGestion(); }, [recargar]);
    useEffect(() => { cargarFuncionarios(); }, [opera]);

    const enviar = async (url, metodo, cuerpo) => {
        setGuardando(true);
        setError(null);
        try {
            const res = await fetch(url, {
                method: metodo,
                headers: { ...autorizacion(), 'Content-Type': 'application/json' },
                body: JSON.stringify(cuerpo),
            });
            const datos = await res.json().catch(() => ({}));
            if (!res.ok) {
                setError(typeof datos.detail === 'string' ? datos.detail : 'No fue posible guardar el cambio.');
                return false;
            }
            await Promise.all([cargarFuncionarios(), cargarGestion()]);
            onCambio?.();
            return true;
        } catch (err) {
            setError('Error de conexión.');
            return false;
        } finally {
            setGuardando(false);
        }
    };

    const agregar = async (e) => {
        e.preventDefault();
        const ok = await enviar(`${API_BASE_URL}/inspecciones/funcionarios`, 'POST', formulario);
        if (ok) setFormulario(FORMULARIO_VACIO);
    };

    const cerrar = async (funcionario) => {
        const hasta = cierre[funcionario.id] || localToday();
        const ok = await enviar(`${API_BASE_URL}/inspecciones/funcionarios/${funcionario.id}`, 'PATCH', { hasta });
        if (ok) setCierre((actual) => ({ ...actual, [funcionario.id]: '' }));
    };

    const filas = gestion?.inspecciones || [];

    return (
        <div className="space-y-6">
            <div className="bg-white p-5 md:p-8 rounded-3xl md:rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50">
                <h3 className="text-xl font-black text-slate-900 flex items-center gap-3">
                    <Building2 className="text-indigo-600" /> Gestión {gestion?.anio || ''} por inspección
                </h3>
                <p className="mt-1 text-xs font-semibold text-slate-500">
                    Expedientes con actuaciones de la Inspección en el año (incluye expedientes de años anteriores) y estado actual de sus medidas.
                </p>
                {filas.length === 0 ? (
                    <p className="mt-6 text-sm font-bold text-slate-500">Todavía no hay medidas gestionadas cargadas para este año.</p>
                ) : (
                    <div className="mt-6 overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead>
                                <tr className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100">
                                    <th className="py-2 pr-3">Inspección</th>
                                    <th className="py-2 pr-3 text-right">Expedientes</th>
                                    <th className="py-2 pr-3 text-right">Actuaciones</th>
                                    <th className="py-2 pr-3 text-right">Pagadas</th>
                                    <th className="py-2 pr-3 text-right">Ratificadas</th>
                                    <th className="py-2 pr-3 text-right">No impuestas</th>
                                    <th className="py-2 pr-3 text-right">En proceso</th>
                                    <th className="py-2 pr-3 text-right">Resuelto</th>
                                    <th className="py-2 text-right">Recaudo</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                                {filas.map((fila) => (
                                    <tr key={fila.inspeccion}>
                                        <td className="py-3 pr-3 font-black text-slate-900">{etiquetaInspeccion(fila.inspeccion)}</td>
                                        <td className="py-3 pr-3 text-right font-black tabular-nums">{numero(fila.expedientes)}</td>
                                        <td className="py-3 pr-3 text-right font-bold tabular-nums">{numero(fila.actuaciones)}</td>
                                        <td className="py-3 pr-3 text-right font-bold tabular-nums">{numero(fila.pagadas)}</td>
                                        <td className="py-3 pr-3 text-right font-bold tabular-nums">{numero(fila.ratificadas)}</td>
                                        <td className="py-3 pr-3 text-right font-bold tabular-nums">{numero(fila.no_impuestas)}</td>
                                        <td className="py-3 pr-3 text-right font-bold tabular-nums">{numero(fila.en_proceso)}</td>
                                        <td className="py-3 pr-3 text-right font-bold tabular-nums">{porcentajeResuelto(fila)}%</td>
                                        <td className="py-3 text-right font-bold tabular-nums whitespace-nowrap">{millones(fila.recaudo)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
                {gestion?.pendientes_sin_repartir > 0 && (
                    <p className="mt-4 text-xs font-semibold text-slate-500">
                        Además hay {numero(gestion.pendientes_sin_repartir)} medidas pendientes de {gestion.anio} que no se pueden repartir por inspección: el RNMC no dice a cuál se asignaron.
                    </p>
                )}
                <p className="mt-2 text-xs font-semibold text-slate-500">
                    La inspección sale de las anotaciones del RNMC o, si no la nombran, de quién registró la actuación. Recaudo: pagos con fecha en el año.
                </p>
            </div>

            {opera && (
                <div className="bg-white p-5 md:p-8 rounded-3xl md:rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50">
                    <h3 className="text-xl font-black text-slate-900 flex items-center gap-3">
                        <UserCog className="text-indigo-600" /> Funcionarios por inspección
                    </h3>
                    <p className="mt-1 text-xs font-semibold text-slate-500">
                        El reporte del RNMC solo trae el documento de quien registra. Si trasladan a alguien, póngale fecha final y regístrelo de nuevo en su nueva inspección.
                    </p>

                    {error && (
                        <p className="mt-4 flex items-center gap-2 text-sm font-bold text-red-600"><AlertCircle size={16} /> {error}</p>
                    )}

                    <div className="mt-6 overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead>
                                <tr className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100">
                                    <th className="py-2 pr-3">Nombre</th>
                                    <th className="py-2 pr-3">Documento</th>
                                    <th className="py-2 pr-3">Inspección</th>
                                    <th className="py-2 pr-3">Desde</th>
                                    <th className="py-2">Hasta</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                                {funcionarios.items.map((funcionario) => (
                                    <tr key={funcionario.id} className={funcionario.hasta ? 'text-slate-400' : ''}>
                                        <td className="py-3 pr-3 font-black">{funcionario.nombre || '—'}</td>
                                        <td className="py-3 pr-3 font-bold tabular-nums">{funcionario.documento}</td>
                                        <td className="py-3 pr-3 font-bold">{etiquetaInspeccion(funcionario.inspeccion)}</td>
                                        <td className="py-3 pr-3 font-bold tabular-nums">{funcionario.desde}</td>
                                        <td className="py-3">
                                            {funcionario.hasta ? (
                                                <span className="font-bold tabular-nums">{funcionario.hasta}</span>
                                            ) : (
                                                <div className="flex items-center gap-2">
                                                    <input
                                                        type="date"
                                                        aria-label={`Fecha final de ${funcionario.nombre || funcionario.documento}`}
                                                        value={cierre[funcionario.id] || ''}
                                                        onChange={(e) => setCierre((actual) => ({ ...actual, [funcionario.id]: e.target.value }))}
                                                        className="rounded-xl border border-slate-200 px-2 py-1 text-xs font-bold"
                                                    />
                                                    <button
                                                        type="button"
                                                        disabled={guardando}
                                                        onClick={() => cerrar(funcionario)}
                                                        className="rounded-xl bg-slate-100 px-3 py-1 text-[11px] font-black uppercase text-slate-600 hover:bg-slate-200 disabled:opacity-50"
                                                    >
                                                        Terminar
                                                    </button>
                                                </div>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {funcionarios.items.length === 0 && (
                                    <tr><td colSpan={5} className="py-4 text-sm font-bold text-slate-500">Todavía no hay funcionarios registrados.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    <form onSubmit={agregar} className="mt-6 grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
                        <label className="text-xs font-black uppercase text-slate-500">Nombre
                            <input value={formulario.nombre} onChange={(e) => setFormulario({ ...formulario, nombre: e.target.value })}
                                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold normal-case text-slate-900" />
                        </label>
                        <label className="text-xs font-black uppercase text-slate-500">Documento
                            <input required inputMode="numeric" value={formulario.documento}
                                onChange={(e) => setFormulario({ ...formulario, documento: e.target.value })}
                                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold text-slate-900" />
                        </label>
                        <label className="text-xs font-black uppercase text-slate-500">Inspección
                            <select value={formulario.inspeccion} onChange={(e) => setFormulario({ ...formulario, inspeccion: e.target.value })}
                                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold normal-case text-slate-900">
                                {(funcionarios.inspecciones.length ? funcionarios.inspecciones : ['PRIMERA', 'SEGUNDA', 'TERCERA']).map((nombre) => (
                                    <option key={nombre} value={nombre}>{etiquetaInspeccion(nombre)}</option>
                                ))}
                            </select>
                        </label>
                        <label className="text-xs font-black uppercase text-slate-500">Desde
                            <input required type="date" value={formulario.desde} onChange={(e) => setFormulario({ ...formulario, desde: e.target.value })}
                                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold text-slate-900" />
                        </label>
                        <button type="submit" disabled={guardando}
                            className="flex items-center justify-center gap-2 rounded-2xl bg-[#281FD0] px-4 py-2.5 text-xs font-black uppercase tracking-widest text-white disabled:opacity-50">
                            {guardando ? <Loader2 className="animate-spin" size={16} /> : <Plus size={16} />} Agregar
                        </button>
                    </form>
                    <p className="mt-2 text-xs font-semibold text-slate-500">
                        «Desde» es desde cuándo registra en esa inspección. Para que cubra los reportes anteriores, ponga la fecha en que empezó, no la de hoy.
                    </p>
                </div>
            )}
        </div>
    );
};

export default GestionPorInspeccion;
