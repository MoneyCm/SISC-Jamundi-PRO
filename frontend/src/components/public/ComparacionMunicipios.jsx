import React, { useEffect, useState } from 'react';
import { API_BASE_URL } from '../../utils/apiConfig';
import { fechaCorta, textoPuesto } from '../../utils/metasPublicas';

const numero = (valor, decimales = 1) => (valor == null ? '—'
    : Number(valor).toLocaleString('es-CO', { maximumFractionDigits: decimales, minimumFractionDigits: decimales }));

// Jamundí frente a vecinos y municipios grandes del Valle, el Valle y Colombia (tasa por 100.000 habitantes).
const ComparacionMunicipios = () => {
    const [delito, setDelito] = useState('homicidio');
    const [anio, setAnio] = useState('');
    const [data, setData] = useState(null);
    const [cargando, setCargando] = useState(false);

    useEffect(() => {
        let vigente = true;
        setCargando(true);
        const query = new URLSearchParams({ delito, ...(anio ? { anio } : {}) });
        fetch(`${API_BASE_URL}/analitica/public/comparacion?${query}`)
            .then((r) => (r.ok ? r.json() : null))
            .then((d) => { if (vigente) setData(d); })
            .catch(() => { if (vigente) setData(null); })
            .finally(() => { if (vigente) setCargando(false); });
        return () => { vigente = false; };
    }, [delito, anio]);

    if (!data?.available && !cargando) return null;
    const filas = data?.municipios || [];
    const referencias = data ? [data.valle, data.colombia].filter((r) => r?.tasa != null) : [];
    const maximo = Math.max(1, ...filas.map((f) => f.tasa || 0), ...referencias.map((r) => r.tasa || 0));

    return (
        <section id="comparar" className="scroll-mt-24 border-y border-slate-200 py-8" aria-labelledby="comparar-title">
            <div className="mb-5 grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
                <div className="max-w-3xl">
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">Contexto regional</p>
                    <h2 id="comparar-title" className="mt-1 text-3xl font-black tracking-normal text-slate-950">Jamundí frente a otros municipios</h2>
                    <p className="mt-3 text-sm font-semibold leading-6 text-slate-600">
                        Tasa por cada 100.000 habitantes: así se pueden comparar municipios de distinto tamaño.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <label className="text-xs font-black uppercase text-slate-500">Delito
                        <select value={delito} onChange={(e) => setDelito(e.target.value)} className="mt-1 block min-h-11 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold text-slate-800">
                            {(data?.delitos || [{ id: 'homicidio', nombre: 'Homicidio' }]).map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
                        </select>
                    </label>
                    <label className="text-xs font-black uppercase text-slate-500">Año
                        <select value={anio || data?.anio || ''} onChange={(e) => setAnio(e.target.value)} className="mt-1 block min-h-11 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold text-slate-800">
                            {(data?.anios || []).map((a) => <option key={a} value={a}>{a}</option>)}
                        </select>
                    </label>
                </div>
            </div>
            {data?.available && (
                <>
                    <p className="mb-4 text-sm font-black text-slate-800">
                        {data.delito_nombre}, {data.periodo}. {textoPuesto(data.puesto_valle)}
                    </p>
                    <ul className={`space-y-2 ${cargando ? 'opacity-50' : ''}`} aria-label={`Tasa de ${data.delito_nombre.toLowerCase()} por municipio`}>
                        {filas.map((f) => (
                            <li key={f.codigo} className="grid grid-cols-[minmax(7rem,11rem)_1fr_auto] items-center gap-3 text-sm">
                                <span className={`truncate ${f.es_jamundi ? 'font-black text-[#281FD0]' : 'font-bold text-slate-700'}`}>
                                    {f.municipio}{f.departamento && !f.departamento.startsWith('Valle') ? ` (${f.departamento})` : ''}
                                </span>
                                <span className="h-3 bg-slate-100" aria-hidden="true">
                                    <span className={`block h-3 ${f.es_jamundi ? 'bg-[#281FD0]' : 'bg-slate-400'}`} style={{ width: `${Math.max(2, ((f.tasa || 0) / maximo) * 100)}%` }} />
                                </span>
                                <span className={`tabular-nums ${f.es_jamundi ? 'font-black text-[#281FD0]' : 'font-bold text-slate-700'}`} title={`${f.casos} casos`}>{numero(f.tasa)}</span>
                            </li>
                        ))}
                        {referencias.map((r) => (
                            <li key={r.nombre} className="grid grid-cols-[minmax(7rem,11rem)_1fr_auto] items-center gap-3 border-t border-dashed border-slate-200 pt-2 text-sm">
                                <span className="font-black text-slate-900">{r.nombre}</span>
                                <span className="h-3 bg-slate-100" aria-hidden="true">
                                    <span className="block h-3 bg-[#FFB600]" style={{ width: `${Math.max(2, ((r.tasa || 0) / maximo) * 100)}%` }} />
                                </span>
                                <span className="font-black tabular-nums text-slate-900">{numero(r.tasa)}</span>
                            </li>
                        ))}
                    </ul>
                    <p className="mt-4 text-xs font-semibold leading-5 text-slate-500">
                        Fuente: {data.fuente}{data.corte ? `, corte ${fechaCorta(data.corte)}` : ''}. {data.nota}
                    </p>
                </>
            )}
        </section>
    );
};

export default ComparacionMunicipios;
