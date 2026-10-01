import React, { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Clock, HeartHandshake, MapPin, Phone, ShieldCheck } from 'lucide-react';
import { useInstitutionalIndicators } from '../hooks/useInstitutionalIndicators';
import { agruparPorTema, conMayuscula, fechaLarga, rangoPeriodo, resumenComisaria } from '../utils/proteccionFamiliar';

// Líneas nacionales de atención y datos de las Comisarías de Familia de Jamundí.
const LINEAS = [
    { numero: '123', titulo: 'Emergencias', detalle: 'Si hay peligro en este momento.' },
    { numero: '155', titulo: 'Orientación a mujeres', detalle: 'Mujeres víctimas de violencia. Gratuita, las 24 horas.' },
    { numero: '141', titulo: 'ICBF', detalle: 'Niñas, niños y adolescentes en riesgo. Gratuita.' },
    { numero: '122', titulo: 'Fiscalía', detalle: 'Para denunciar un delito.' },
];
const COMISARIAS = {
    lugar: 'Centro Comercial Caña Dulce, Jamundí',
    horario: 'Lunes a viernes, 8:00 a. m. a 12:00 m. y 2:00 p. m. a 5:00 p. m.',
};

const PublicFamilyProtection = ({ onBack, onNavigate }) => {
    const { records, status } = useInstitutionalIndicators('COMISARIAS');
    const [entity, setEntity] = useState('ALL');
    const [period, setPeriod] = useState('');

    const entities = useMemo(() => [...new Set(records.map((item) => item.reporting_entity))].sort(), [records]);
    const periods = useMemo(() => [...new Set(records.map((item) => item.period))].sort().reverse(), [records]);
    // Por defecto, el último periodo informado por todas las comisarías, para poder compararlas.
    const defaultPeriod = useMemo(() => {
        const porPeriodo = {};
        records.forEach((item) => { (porPeriodo[item.period] = porPeriodo[item.period] || new Set()).add(item.reporting_entity); });
        return periods.find((item) => porPeriodo[item]?.size > 1) || periods[0] || '';
    }, [periods, records]);
    useEffect(() => { if (!period && defaultPeriod) setPeriod(defaultPeriod); }, [defaultPeriod, period]);

    const porComisaria = useMemo(() => {
        const result = {};
        records.filter((item) => item.period === period && (entity === 'ALL' || item.reporting_entity === entity))
            .forEach((item) => { (result[item.reporting_entity] = result[item.reporting_entity] || []).push(item); });
        // Primera antes que Segunda.
        return Object.fromEntries(Object.entries(result).sort(([a], [b]) => a.localeCompare(b, 'es')));
    }, [records, period, entity]);
    const resumen = Object.entries(porComisaria).map(([nombre, filas]) => resumenComisaria(nombre, filas)).filter(Boolean);
    const cortes = [...new Set(Object.values(porComisaria).flat().map((item) => item.cutoff_date).filter(Boolean))].sort();

    return (
        <main className="min-h-screen bg-[#F4F6FB] text-slate-900">
            <div className="mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-8">
                <button type="button" onClick={onBack} className="mb-5 inline-flex min-h-10 items-center gap-2 text-sm font-bold text-[#281FD0] hover:underline">
                    <ArrowLeft size={17} /> Volver al portal ciudadano
                </button>

                <header className="rounded-lg bg-[#281FD0] p-6 text-white md:p-10">
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-[#FFE000]">Comisarías de Familia</p>
                    <h1 className="mt-2 text-3xl font-black md:text-4xl">Protección familiar</h1>
                    <p className="mt-3 max-w-3xl text-base font-semibold leading-7 text-white/85">
                        Dónde pedir ayuda ante la violencia en la familia y qué atienden las comisarías de Jamundí, en cifras que no exponen a ninguna persona, familia ni expediente.
                    </p>
                </header>

                <section aria-labelledby="ayuda-title" className="mt-6 rounded-lg border-2 border-red-200 bg-white p-5 md:p-6">
                    <h2 id="ayuda-title" className="flex items-center gap-2 text-2xl font-black text-red-800"><Phone size={22} /> ¿Necesitas ayuda?</h2>
                    <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                        {LINEAS.map((linea) => (
                            <a key={linea.numero} href={`tel:${linea.numero}`} className="rounded-lg border border-slate-200 p-3 hover:border-red-300 hover:bg-red-50 md:p-4">
                                <p className="text-3xl font-black text-red-700">{linea.numero}</p>
                                <p className="mt-1 text-sm font-black text-slate-900">{linea.titulo}</p>
                                <p className="mt-1 text-xs font-semibold text-slate-600">{linea.detalle}</p>
                            </a>
                        ))}
                    </div>
                    <div className="mt-5 grid gap-4 border-t border-slate-100 pt-5 md:grid-cols-[1fr_auto] md:items-center">
                        <div className="space-y-2 text-sm font-semibold text-slate-700">
                            <p className="text-base font-black text-slate-900">Comisarías de Familia Primera y Segunda</p>
                            <p className="flex items-start gap-2"><MapPin size={17} className="mt-0.5 shrink-0 text-[#281FD0]" />{COMISARIAS.lugar}</p>
                            <p className="flex items-start gap-2"><Clock size={17} className="mt-0.5 shrink-0 text-[#281FD0]" />{COMISARIAS.horario}</p>
                            <p className="flex items-start gap-2"><ShieldCheck size={17} className="mt-0.5 shrink-0 text-[#281FD0]" />Puede acudir directamente, sin abogado y sin costo, para pedir una medida de protección.</p>
                        </div>
                        {onNavigate && (
                            <button type="button" onClick={() => onNavigate('victim-support')} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1f18a8]">
                                <HeartHandshake size={17} /> Ver rutas de atención
                            </button>
                        )}
                    </div>
                </section>

                <section aria-labelledby="cifras-title" className="mt-8">
                    <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
                        <div>
                            <p className="text-xs font-black uppercase tracking-[0.16em] text-[#281FD0]">En cifras</p>
                            <h2 id="cifras-title" className="mt-1 text-3xl font-black">Qué atienden las comisarías</h2>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <label className="text-xs font-black uppercase text-slate-500">Comisaría
                                <select value={entity} onChange={(event) => setEntity(event.target.value)} className="mt-1 block min-h-11 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold text-slate-800">
                                    <option value="ALL">Las dos, por separado</option>
                                    {entities.map((item) => <option key={item} value={item}>{item}</option>)}
                                </select>
                            </label>
                            <label className="text-xs font-black uppercase text-slate-500">Periodo
                                <select value={period} onChange={(event) => setPeriod(event.target.value)} className="mt-1 block min-h-11 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold text-slate-800">
                                    {periods.map((item) => <option key={item} value={item}>{conMayuscula(rangoPeriodo(item))}</option>)}
                                </select>
                            </label>
                        </div>
                    </div>

                    {status === 'loading' && <p className="mt-6 text-center text-sm font-bold text-slate-500">Consultando las cifras…</p>}
                    {status === 'fallback' && <p className="mt-6 rounded-lg bg-white p-5 text-sm font-bold">No fue posible consultar las cifras en este momento.</p>}

                    {resumen.length > 0 && (
                        <div className="mt-5 rounded-lg border border-slate-200 bg-white p-5">
                            <p className="text-xs font-black uppercase tracking-wide text-slate-500">En resumen</p>
                            <ul className="mt-2 space-y-2 text-base font-semibold leading-7 text-slate-800">
                                {resumen.map((texto) => <li key={texto}>{texto}</li>)}
                            </ul>
                            <p className="mt-3 text-xs font-semibold leading-5 text-slate-500">
                                Cada comisaría registra sus casos a su manera; por eso sus cifras se muestran por separado y no se suman.
                                {cortes.length ? ` Informes con corte al ${cortes.map(fechaLarga).join(' y al ')}.` : ''} Las cifras se actualizan cuando las comisarías entregan su informe.
                            </p>
                        </div>
                    )}

                    {status === 'ready' && !Object.keys(porComisaria).length && (
                        <p className="mt-6 rounded-lg bg-white p-5 text-sm font-bold">No hay cifras publicadas para esta selección.</p>
                    )}

                    {Object.entries(porComisaria).map(([nombre, filas]) => (
                        <section key={nombre} className="mt-8" aria-label={nombre}>
                            <h3 className="text-2xl font-black text-slate-950">{nombre}</h3>
                            <p className="text-sm font-semibold text-slate-500">
                                {filas[0]?.reporting_basis === 'CUMULATIVE' ? `Acumulado de ${rangoPeriodo(period)}` : rangoPeriodo(period, false)}
                            </p>
                            <div className="mt-4 space-y-5">
                                {agruparPorTema(filas).map((tema) => (
                                    <div key={tema.id}>
                                        <p className="text-xs font-black uppercase tracking-wide text-[#281FD0]">{tema.titulo}</p>
                                        {tema.nota && <p className="mt-1 text-xs font-semibold text-slate-500">{tema.nota}</p>}
                                        <div className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                            {tema.registros.map((item) => (
                                                <article key={item.indicator} className="rounded-lg border border-slate-200 bg-white p-4">
                                                    <p className="text-sm font-bold leading-5 text-slate-700">{item.nombre}</p>
                                                    <p className="mt-2 text-3xl font-black tabular-nums text-slate-950">{Number(item.value).toLocaleString('es-CO')}</p>
                                                    {item.explicacion && <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">{item.explicacion}</p>}
                                                </article>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    ))}
                </section>

                <section className="mt-10 rounded-lg border border-slate-200 bg-white p-5 text-sm font-semibold leading-6 text-slate-700">
                    <h2 className="text-base font-black text-slate-900">Privacidad</h2>
                    <p className="mt-1">
                        No se publican nombres, direcciones, expedientes, medidas individuales ni datos que permitan identificar a niñas, niños,
                        adolescentes o personas afectadas por violencias familiares. Solo se muestran totales de cada comisaría.
                    </p>
                </section>
            </div>
        </main>
    );
};

export default PublicFamilyProtection;
