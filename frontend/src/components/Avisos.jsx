import React, { useEffect, useState } from 'react';
import { AlertTriangle, BellRing, ChevronRight } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

const ESTILOS = {
    alto: { borde: 'border-red-200 bg-red-50', icono: 'text-red-600', titulo: 'text-red-950' },
    medio: { borde: 'border-amber-200 bg-amber-50', icono: 'text-amber-600', titulo: 'text-amber-950' },
};

// Lo que está atrasado o se acerca (sábana, comparendos, solicitudes, Consejo, copia de seguridad).
const Avisos = ({ onNavigate }) => {
    const [avisos, setAvisos] = useState([]);
    useEffect(() => {
        let vigente = true;
        apiJson('/observatory/avisos').then((datos) => { if (vigente) setAvisos(datos.avisos || []); }).catch(() => {});
        return () => { vigente = false; };
    }, []);
    if (!avisos.length) return null;
    return (
        <section aria-label="Avisos" className="space-y-2">
            <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-wide text-slate-700">
                <BellRing size={16} className="text-[#281FD0]" /> Avisos ({avisos.length})
            </h3>
            <ul className="space-y-2">
                {avisos.map((aviso) => {
                    const estilo = ESTILOS[aviso.nivel] || ESTILOS.medio;
                    const puedeIr = aviso.destino?.page && onNavigate;
                    return (
                        <li key={aviso.clave}>
                            <button type="button" disabled={!puedeIr} onClick={() => puedeIr && onNavigate(aviso.destino.page)}
                                className={`flex w-full items-start gap-3 rounded-lg border p-3 text-left ${estilo.borde} ${puedeIr ? 'hover:brightness-95' : 'cursor-default'}`}>
                                <AlertTriangle size={18} className={`mt-0.5 shrink-0 ${estilo.icono}`} />
                                <span className="min-w-0 flex-1">
                                    <span className={`block text-sm font-black ${estilo.titulo}`}>{aviso.titulo}</span>
                                    <span className="mt-0.5 block text-sm text-slate-700">{aviso.detalle}</span>
                                </span>
                                {puedeIr && <ChevronRight size={18} className="mt-0.5 shrink-0 text-slate-400" />}
                            </button>
                        </li>
                    );
                })}
            </ul>
        </section>
    );
};

export default Avisos;
