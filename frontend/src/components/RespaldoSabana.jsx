import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

const fecha = (value) => (value ? new Date(`${value}T00:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' }) : '');

// Aviso cuando la sábana de la Policía tiene más de 3 semanas, con las cifras de MinDefensa mientras tanto.
const RespaldoSabana = () => {
    const [estado, setEstado] = useState(null);
    useEffect(() => {
        let vigente = true;
        apiJson('/analitica/estadisticas/respaldo-sabana').then((data) => { if (vigente) setEstado(data); }).catch(() => {});
        return () => { vigente = false; };
    }, []);
    if (!estado?.atrasada) return null;
    return (
        <section role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950">
            <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 shrink-0 text-amber-600" size={20} />
                <div className="min-w-0 flex-1">
                    <p className="font-black">
                        {estado.sabana_corte
                            ? `La sábana de la Policía no llega desde hace ${estado.dias_retraso} días (último dato: ${fecha(estado.sabana_corte)}).`
                            : 'Todavía no hay sábana de la Policía cargada.'}
                    </p>
                    <p className="mt-1 text-sm">Conviene pedirla a la Policía: es la única fuente con barrio y hora. Las cifras de esta página siguen en ese corte.</p>
                    {estado.respaldo_disponible && (
                        <div className="mt-3 overflow-hidden rounded-lg border border-amber-200 bg-white">
                            <p className="border-b border-amber-100 px-3 py-2 text-xs font-bold text-amber-900">
                                Mientras tanto: cifras oficiales de MinDefensa al {fecha(estado.respaldo_corte)} (sin barrios ni horas)
                            </p>
                            <table className="w-full text-sm">
                                <thead className="text-left text-xs text-slate-500">
                                    <tr><th className="px-3 py-1.5">Delito</th><th className="px-3 py-1.5 text-right">Este año</th><th className="px-3 py-1.5 text-right">Mismo periodo anterior</th></tr>
                                </thead>
                                <tbody>
                                    {estado.respaldo.map((fila) => (
                                        <tr key={fila.delito} className="border-t border-slate-100">
                                            <td className="px-3 py-1.5 font-semibold text-slate-800">{fila.delito}</td>
                                            <td className="px-3 py-1.5 text-right font-bold">{fila.actual}</td>
                                            <td className="px-3 py-1.5 text-right text-slate-500">{fila.anterior}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
};

export default RespaldoSabana;
