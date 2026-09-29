import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

const fecha = (value) => (value ? new Date(`${value}T00:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' }) : '');

// Aviso cuando los reportes del RNMC (comparendos) tienen más de 35 días sin datos nuevos.
const AvisoRNMC = () => {
    const [estado, setEstado] = useState(null);
    useEffect(() => {
        let vigente = true;
        apiJson('/inspecciones/estado-carga').then((data) => { if (vigente) setEstado(data); }).catch(() => {});
        return () => { vigente = false; };
    }, []);
    if (!estado?.atrasado) return null;
    return (
        <section role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950">
            <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 shrink-0 text-amber-600" size={20} />
                <div className="min-w-0 flex-1">
                    <p className="font-black">
                        {estado.corte
                            ? `Los comparendos del RNMC no se actualizan desde hace ${estado.dias_desde_corte} días (último dato: ${fecha(estado.corte)}).`
                            : 'Todavía no hay comparendos del RNMC cargados.'}
                    </p>
                    <p className="mt-1 text-sm">
                        Pida los dos reportes del mes (medidas pendientes y gestionadas) y súbalos en Inspecciones de Policía.
                        Mientras tanto, la meta de convivencia del PISCC sigue en ese corte.
                    </p>
                </div>
            </div>
        </section>
    );
};

export default AvisoRNMC;
