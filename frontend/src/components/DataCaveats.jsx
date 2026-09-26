import React from 'react';
import { AlertTriangle, ArrowRight } from 'lucide-react';

/** Aviso del Inicio: la sábana del periodo puede estar incompleta, así que una baja no es necesariamente mejora. */
const DataCaveats = ({ caveats, onOpen }) => (
    <section role="status" className="flex gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950">
        <AlertTriangle size={20} className="mt-0.5 shrink-0 text-amber-700" />
        <div className="min-w-0 space-y-1">
            <p className="text-sm font-black">Lea estas cifras con cuidado: el periodo tiene datos incompletos</p>
            <ul className="list-disc space-y-0.5 pl-5 text-xs font-semibold leading-5">
                {caveats.items.map((item) => <li key={item}>{item}</li>)}
            </ul>
            {caveats.reading && <p className="text-xs font-bold">{caveats.reading}</p>}
            {onOpen && (
                <button onClick={onOpen} className="inline-flex items-center gap-1 text-xs font-black text-amber-900 hover:underline">
                    Ver en el Centro de análisis <ArrowRight size={13} />
                </button>
            )}
        </div>
    </section>
);

export default DataCaveats;
