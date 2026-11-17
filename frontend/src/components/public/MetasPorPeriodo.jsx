import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, Download, RefreshCw } from 'lucide-react';
import { API_BASE_URL } from '../../utils/apiConfig';
import {
    csvMetasPeriodo, mesesResaltados, nombreArchivoMetas, opcionesDeTipo, textoAcumulado, textoCambio, TIPOS_PERIODO,
    tonoCambio, tonoRitmo,
} from '../../utils/metasPeriodo';

const INICIALES = ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
const RITMO = {
    ambar: 'border-amber-300 bg-amber-50 text-amber-900',
    verde: 'border-emerald-300 bg-emerald-50 text-emerald-900',
    rojo: 'border-red-300 bg-red-50 text-red-900',
    gris: 'border-slate-200 bg-slate-50 text-slate-700',
};
const CAMBIO = { verde: 'text-emerald-700', rojo: 'text-red-700', gris: 'text-slate-600' };
const CAMPO = 'mt-1 block min-h-11 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold text-slate-800';

const numero = (valor) => (valor == null ? '—' : Number(valor).toLocaleString('es-CO', { maximumFractionDigits: 1 }));

// Doce barras del año: las del periodo consultado van en azul; un mes sin publicar queda vacío.
const BarrasDelAnio = ({ item }) => {
    const serie = item.series?.[item.series.length - 1];
    if (!serie) return null;
    const resaltados = mesesResaltados(item);
    const preliminares = serie.preliminares || [];
    const maximo = Math.max(1, ...serie.valores.map((v) => v || 0));
    return (
        <div className="flex h-12 items-end gap-0.5" role="img"
            aria-label={`${item.label} por mes en ${serie.anio}: ${serie.valores.map((v, i) => `${INICIALES[i]} ${v ?? 'sin dato'}`).join(', ')}`}>
            {serie.valores.map((valor, i) => (
                <span key={i} className="flex w-3 flex-col items-center justify-end" title={`${INICIALES[i]}: ${valor ?? 'sin publicar'}${preliminares.includes(i) ? ' (sábana, preliminar)' : ''}`}>
                    <span className={`block w-full ${valor == null ? 'border-b border-dashed border-slate-300' : preliminares.includes(i) ? 'bg-amber-500' : resaltados.includes(i) ? 'bg-[#281FD0]' : 'bg-slate-300'}`}
                        style={{ height: valor == null ? 1 : `${Math.max(2, (valor / maximo) * 36)}px` }} />
                    <span className="mt-0.5 text-[8px] font-bold leading-none text-slate-400" aria-hidden="true">{INICIALES[i]}</span>
                </span>
            ))}
        </div>
    );
};

// Seguimiento de las metas del PISCC en el periodo que se necesite: mes, trimestre, semestre, año o rango.
const MetasPorPeriodo = () => {
    const [tipo, setTipo] = useState('mes');
    const [periodo, setPeriodo] = useState(null); // { desde, hasta } o null = último mes publicado
    const [rango, setRango] = useState({ desde: '', hasta: '' });
    const [data, setData] = useState(null);
    // Plegado al abrir la página: es una consulta detallada y alarga mucho la portada, sobre todo en celular.
    const [abierto, setAbierto] = useState(false);
    const [cargando, setCargando] = useState(false);
    const [error, setError] = useState('');
    const [intento, setIntento] = useState(0);

    useEffect(() => {
        if (!abierto) return undefined;
        let vigente = true;
        setCargando(true);
        setError('');
        const query = periodo ? `?${new URLSearchParams(periodo)}` : '';
        fetch(`${API_BASE_URL}/analitica/public/piscc/periodo${query}`)
            .then(async (r) => {
                if (r.ok) return r.json();
                const detalle = await r.json().catch(() => ({}));
                throw new Error(r.status === 400 && detalle.detail ? detalle.detail : 'No fue posible consultar el periodo.');
            })
            .then((d) => { if (vigente) setData(d); })
            .catch((e) => { if (vigente) setError(e.message || 'No fue posible consultar el periodo.'); })
            .finally(() => { if (vigente) setCargando(false); });
        return () => { vigente = false; };
    }, [abierto, periodo, intento]);

    const opciones = data?.opciones?.periodos || [];
    const lista = useMemo(() => opcionesDeTipo(opciones, tipo), [opciones, tipo]);
    const seleccion = periodo ? `${periodo.desde}|${periodo.hasta}` : (data ? `${data.desde}|${data.hasta}` : '');

    const cambiarTipo = (nuevo) => {
        setTipo(nuevo);
        if (nuevo === 'rango') {
            setRango({ desde: data?.desde || '', hasta: data?.hasta || '' });
            return;
        }
        const primera = opcionesDeTipo(opciones, nuevo)[0];
        if (primera) setPeriodo({ desde: primera.desde, hasta: primera.hasta });
    };

    const descargar = () => {
        // El BOM hace que Excel lea bien las tildes.
        const blob = new Blob(['﻿', csvMetasPeriodo(data)], { type: 'text/csv;charset=utf-8' });
        const enlace = document.createElement('a');
        enlace.href = URL.createObjectURL(blob);
        enlace.download = nombreArchivoMetas(data);
        enlace.click();
        URL.revokeObjectURL(enlace.href);
    };

    if (!abierto) {
        return (
            <button type="button" onClick={() => setAbierto(true)} aria-expanded="false" aria-controls="metas-periodo"
                className="mt-6 flex min-h-14 w-full items-center gap-3 border border-slate-200 bg-white px-4 py-3 text-left transition-colors hover:border-[#281FD0]">
                <span className="min-w-0 flex-1">
                    <strong className="block text-base font-black text-slate-950">Seguimiento por periodo</strong>
                    <span className="block text-sm font-semibold text-slate-600">Ver las metas por mes, trimestre, semestre o rango, frente al año anterior.</span>
                </span>
                <ChevronDown size={20} className="shrink-0 text-[#281FD0]" />
            </button>
        );
    }
    return (
        <div id="metas-periodo" className="mt-6 scroll-mt-24 border border-slate-200 bg-white p-4 sm:p-6" aria-labelledby="metas-periodo-title">
            <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
                <div className="max-w-3xl">
                    <h3 id="metas-periodo-title" className="flex items-center gap-2 text-xl font-black text-slate-950">
                        Seguimiento por periodo
                        <button type="button" onClick={() => setAbierto(false)} aria-expanded="true" className="ml-1 inline-flex min-h-9 items-center gap-1 text-xs font-black text-[#281FD0] underline underline-offset-2">Ocultar</button>
                    </h3>
                    <p className="mt-2 text-sm font-semibold leading-6 text-slate-600">
                        Las mismas metas, en el mes, trimestre, semestre o rango que necesite, frente a los mismos meses del año anterior.
                    </p>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                    <label className="text-xs font-black uppercase text-slate-500">Ver por
                        <select value={tipo} onChange={(e) => cambiarTipo(e.target.value)} className={CAMPO}>
                            {TIPOS_PERIODO.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                        </select>
                    </label>
                    {tipo === 'rango' ? (
                        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); if (rango.desde && rango.hasta) setPeriodo({ ...rango }); }}>
                            <label className="text-xs font-black uppercase text-slate-500">Desde
                                <input type="month" required value={rango.desde} min={data?.opciones?.primer_mes} max={data?.opciones?.ultimo_mes}
                                    onChange={(e) => setRango((r) => ({ ...r, desde: e.target.value }))} className={CAMPO} />
                            </label>
                            <label className="text-xs font-black uppercase text-slate-500">Hasta
                                <input type="month" required value={rango.hasta} min={rango.desde || data?.opciones?.primer_mes} max={data?.opciones?.ultimo_mes}
                                    onChange={(e) => setRango((r) => ({ ...r, hasta: e.target.value }))} className={CAMPO} />
                            </label>
                            <button type="submit" className="min-h-11 bg-[#281FD0] px-4 text-sm font-black text-white transition-colors hover:bg-[#1c159c]">Consultar</button>
                        </form>
                    ) : (
                        <label className="text-xs font-black uppercase text-slate-500">Periodo
                            <select value={seleccion} onChange={(e) => { const [desde, hasta] = e.target.value.split('|'); setPeriodo({ desde, hasta }); }} className={CAMPO}>
                                {!lista.some((o) => `${o.desde}|${o.hasta}` === seleccion) && <option value={seleccion}>{data?.periodo || 'Seleccione'}</option>}
                                {lista.map((o) => <option key={`${o.tipo}-${o.desde}-${o.hasta}`} value={`${o.desde}|${o.hasta}`}>{o.label}</option>)}
                            </select>
                        </label>
                    )}
                </div>
            </div>

            {error && (
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-l-4 border-red-600 bg-red-50 p-4 text-sm font-semibold text-red-900" role="alert">
                    <span>{error}</span>
                    <button onClick={() => setIntento((n) => n + 1)} className="inline-flex min-h-10 items-center gap-2 border border-red-700 px-3 font-black"><RefreshCw size={16} /> Reintentar</button>
                </div>
            )}
            {cargando && !data && <p className="mt-6 text-sm font-bold text-slate-500" role="status">Consultando el periodo…</p>}

            {data && (
                <div className={cargando ? 'opacity-50' : ''}>
                    <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                        <p className="text-sm font-black text-slate-900">Periodo consultado: {data.periodo}</p>
                        <button onClick={descargar} className="inline-flex min-h-10 items-center gap-2 border border-slate-300 px-3 text-xs font-black text-[#281FD0] transition-colors hover:border-[#281FD0]"><Download size={16} /> Descargar tabla (CSV)</button>
                    </div>
                    <div className="mt-3 overflow-x-auto">
                        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                            <caption className="sr-only">Metas del PISCC en {data.periodo}</caption>
                            <thead>
                                <tr className="border-b-2 border-slate-300 text-[11px] font-black uppercase tracking-wide text-slate-500">
                                    <th scope="col" className="py-2 pr-3">Indicador</th>
                                    <th scope="col" className="px-3 py-2 text-right">En el periodo</th>
                                    <th scope="col" className="px-3 py-2 text-right">Mismos meses, año anterior</th>
                                    <th scope="col" className="px-3 py-2">Cambio</th>
                                    <th scope="col" className="px-3 py-2">Acumulado del año / meta anual</th>
                                    <th scope="col" className="px-3 py-2">Ritmo frente a la meta</th>
                                    <th scope="col" className="py-2 pl-3">Mes a mes</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.indicators.map((item) => (
                                    <tr key={item.id} className="border-b border-slate-200 align-middle">
                                        <th scope="row" className="py-3 pr-3 font-black text-slate-900">
                                            {item.label}
                                            {item.preliminary && <span className="mt-1 block text-[11px] font-semibold text-amber-800">Fuente: {item.source}</span>}
                                            {!item.preliminary && item.months_counted > 0 && item.months_counted < item.months_requested && (
                                                <span className="mt-1 block text-[11px] font-semibold text-amber-800">Publicado hasta {item.published_until}: {item.months_counted} de {item.months_requested} meses</span>
                                            )}
                                        </th>
                                        <td className="px-3 py-3 text-right text-lg font-black tabular-nums text-slate-950">{numero(item.value)}</td>
                                        <td className="px-3 py-3 text-right font-bold tabular-nums text-slate-700">{numero(item.previous)}</td>
                                        <td className={`px-3 py-3 font-bold ${CAMBIO[tonoCambio(item)]}`}>{textoCambio(item)}</td>
                                        <td className="px-3 py-3 font-bold tabular-nums text-slate-800">
                                            {textoAcumulado(item)}
                                        </td>
                                        <td className="px-3 py-3">
                                            <span className={`inline-block rounded border px-2 py-1 text-[11px] font-black ${RITMO[item.preliminary ? 'ambar' : tonoRitmo(item.status)]}`}>{item.status_label}</span>
                                            {item.year_to_date_reference != null && <span className="mt-1 block text-[11px] font-semibold text-slate-500">Acumulado {numero(item.year_to_date)} frente a {numero(item.year_to_date_reference)} de referencia</span>}
                                        </td>
                                        <td className="py-3 pl-3"><BarrasDelAnio item={item} /></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <p className="mt-4 text-xs font-semibold leading-5 text-slate-500">
                        {data.note} Fuentes: MinDefensa / Policía Nacional (datos.gov.co) y RNMC para convivencia. En la gráfica, las barras azules son los meses del periodo consultado y las naranjas, meses preliminares de la sábana de la Policía.
                    </p>
                </div>
            )}
        </div>
    );
};

export default MetasPorPeriodo;
