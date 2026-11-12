import React, { useEffect, useState } from 'react';
import { API_BASE_URL } from '../../utils/apiConfig';
import { fechaCorta, semaforoMeta, textoMeta } from '../../utils/metasPublicas';

const TONOS = {
    verde: 'border-emerald-300 bg-emerald-50 text-emerald-900',
    amarillo: 'border-amber-300 bg-amber-50 text-amber-950',
    rojo: 'border-red-300 bg-red-50 text-red-900',
    gris: 'border-slate-200 bg-slate-50 text-slate-700',
};
const PUNTOS = { verde: 'bg-emerald-500', amarillo: 'bg-amber-500', rojo: 'bg-red-600', gris: 'bg-slate-400' };
const ANIO_COLOR = { VERDE: 'bg-emerald-500', AMARILLO: 'bg-amber-500', ROJO: 'bg-red-600' };

// Rendición de cuentas: las metas de resultado del PISCC 2024-2027 y cómo van.
const MetasPiscc = () => {
    const [data, setData] = useState(null);
    const [error, setError] = useState(false);
    useEffect(() => {
        let vigente = true;
        fetch(`${API_BASE_URL}/analitica/public/piscc`)
            .then((r) => (r.ok ? r.json() : Promise.reject()))
            .then((d) => { if (vigente) setData(d); })
            .catch(() => { if (vigente) setError(true); });
        return () => { vigente = false; };
    }, []);
    if (error || !data?.indicators?.length) return null;
    return (
        <section id="metas" className="scroll-mt-24" aria-labelledby="metas-title">
            <div className="mb-5 max-w-3xl">
                <p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Rendición de cuentas</p>
                <h2 id="metas-title" className="mt-1 text-3xl font-black tracking-normal text-slate-950">¿Se está cumpliendo el plan de seguridad?</h2>
                <p className="mt-3 text-sm font-semibold leading-6 text-slate-600">
                    Metas del Plan Integral de Seguridad y Convivencia Ciudadana (PISCC) 2024–2027: el máximo de casos al año que el plan se propone no superar en 2027, y cómo va este año.
                </p>
            </div>
            {/* Tarjeta compacta: estado, cifra y meta a la vista; la explicación se abre con "Ver detalle". */}
            <div className="grid grid-cols-2 items-start gap-3 lg:grid-cols-4">
                {data.indicators.map((meta) => {
                    const tono = semaforoMeta(meta.status);
                    return (
                        <article key={meta.id} className={`min-w-0 rounded-lg border p-3 sm:p-4 ${TONOS[tono]}`}>
                            <h3 className="text-base font-black leading-5">{meta.label}</h3>
                            <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-black">
                                <span className={`h-2.5 w-2.5 rounded-full ${PUNTOS[tono]}`} aria-hidden="true" />{meta.status_label}
                            </span>
                            <p className="mt-2 text-3xl font-black tabular-nums">{meta.count ?? '—'}</p>
                            <p className="text-xs font-bold opacity-80">{textoMeta(meta)}</p>
                            <details className="mt-2">
                                <summary className="inline-flex min-h-9 cursor-pointer items-center text-xs font-black underline underline-offset-2">Ver detalle</summary>
                                {meta.previous != null && meta.cutoff && (
                                    <p className="mt-1 inline-flex w-fit items-center gap-1.5 rounded bg-white/70 px-2 py-0.5 text-[11px] font-bold" title={meta.previous_status_label || ''}>
                                        <span className={`h-2 w-2 shrink-0 rounded-full ${PUNTOS[semaforoMeta(meta.previous_status)]}`} aria-hidden="true" />
                                        Mismo periodo de {Number(String(meta.cutoff).slice(0, 4)) - 1}: {meta.previous}{meta.previous_status_label ? ` · ${meta.previous_status_label}` : ''}
                                    </p>
                                )}
                                <p className="mt-2 text-sm font-semibold leading-5">{meta.detail}</p>
                                {meta.closed_years?.some((a) => a.completo) && (
                                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-bold">
                                        {meta.closed_years.filter((a) => a.completo).map((a) => (
                                            <span key={a.anio} className="inline-flex items-center gap-1 rounded bg-white/70 px-2 py-0.5" title={a.semaforo_label}>
                                                <span className={`h-2 w-2 rounded-full ${ANIO_COLOR[a.semaforo] || 'bg-slate-400'}`} aria-hidden="true" />
                                                {a.anio}: {a.total}
                                            </span>
                                        ))}
                                    </div>
                                )}
                                <p className="pt-3 text-[11px] font-semibold opacity-75">
                                    Fuente: {meta.source || 'sin fuente'}{meta.cutoff ? ` · hasta el ${fechaCorta(meta.cutoff)}` : ''}
                                </p>
                            </details>
                        </article>
                    );
                })}
            </div>
            <p className="mt-4 text-xs font-semibold leading-5 text-slate-500">
                La meta 2027 es un límite: los casos del año no deberían pasar de esa cifra. Estas cifras son de MinDefensa, que cuenta víctimas; por eso pueden diferir de los casos (hechos) de la Policía que se muestran arriba. Verde: dentro de la meta; amarillo: a este ritmo pasaría el límite; rojo: ya pasó el límite anual.
                Línea base 2023 y metas: {data.source}. Años cerrados: {data.closed_years_source}. {data.note}
            </p>
        </section>
    );
};

export default MetasPiscc;
