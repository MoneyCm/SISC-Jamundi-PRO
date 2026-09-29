import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Loader2, RefreshCw, ShieldCheck, Upload, XCircle } from 'lucide-react';
import { apiFetch, apiJson, readApiError } from '../utils/apiClient';
import { formatDays, formatPct, monthLabel, reincidenceSummary } from '../utils/vifCases';

const TABS = [
    { id: 'analysis', label: 'Análisis' },
    { id: 'upload', label: 'Cargar base' },
    { id: 'deliveries', label: 'Entregas' },
];
const STATUS_STYLES = {
    PREVISUALIZADA: 'bg-amber-100 text-amber-800',
    CONFIRMADA: 'bg-emerald-100 text-emerald-800',
    DESCARTADA: 'bg-slate-200 text-slate-500',
};
const COMPLETENESS_LABELS = {
    lugar: 'Barrio o sector', sexo: 'Sexo', rango_edad: 'Rango de edad', tipos_violencia: 'Tipo de violencia',
    relacion: 'Relación con el agresor', antecedentes: 'Antecedentes', nivel_riesgo: 'Nivel de riesgo',
    medidas: 'Medida de protección', fecha_medida: 'Fecha de la medida', seguimiento: 'Seguimiento',
    reincidencia: 'Nuevos episodios',
};

const formatDate = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value.slice(0, 10)}T12:00:00`))
    : '');

const Tile = ({ label, value, helper }) => (
    <div className="border-t-4 border-[#281FD0] bg-white p-4 shadow-sm">
        <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-1 text-3xl font-black tabular-nums text-slate-950">{value}</p>
        {helper && <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">{helper}</p>}
    </div>
);

const Panel = ({ title, note, children }) => (
    <section className="border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-slate-700">{title}</h3>
        {note && <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">{note}</p>}
        <div className="mt-3">{children}</div>
    </section>
);

// Barras horizontales de un solo color: la cifra siempre visible, sin depender del color.
const Bars = ({ rows, valueKey = 'count', labelKey = 'label', suffix }) => {
    const max = Math.max(1, ...rows.map((row) => row[valueKey] || 0));
    if (!rows.length) return <p className="text-sm font-semibold text-slate-500">Sin datos.</p>;
    return (
        <ul className="space-y-2">
            {rows.map((row) => (
                <li key={row.code || row[labelKey]} title={`${row[labelKey]}: ${row[valueKey]}${row.pct != null ? ` (${formatPct(row.pct)})` : ''}`}>
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                        <span className="min-w-0 truncate font-bold text-slate-800">{row[labelKey]}</span>
                        <span className="shrink-0 font-black tabular-nums text-slate-900">
                            {row.display ?? row[valueKey]}{row.pct != null && <span className="ml-1 font-semibold text-slate-500">· {formatPct(row.pct)}</span>}{suffix ? suffix(row) : null}
                        </span>
                    </div>
                    <div className="mt-1 h-2 bg-slate-100">
                        <div className="h-2 rounded-r bg-[#281FD0]" style={{ width: `${((row[valueKey] || 0) / max) * 100}%` }} />
                    </div>
                </li>
            ))}
        </ul>
    );
};

const MonthlyChart = ({ series }) => {
    const max = Math.max(1, ...series.map((point) => point.total));
    return (
        <div>
            <div className="flex h-40 items-end gap-[2px]" role="img" aria-label="Casos atendidos por mes">
                {series.map((point) => (
                    <div key={point.month} className="group relative flex h-full flex-1 flex-col justify-end">
                        <div className="rounded-t bg-[#281FD0] group-hover:bg-[#1F18A8]" style={{ height: `${(point.total / max) * 100}%`, minHeight: point.total ? 2 : 0 }} />
                        <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap bg-slate-900 px-2 py-1 text-xs font-bold text-white group-hover:block">
                            {monthLabel(point.month)}: {point.total}
                            {Object.entries(point.by_entity).map(([entity, count]) => <span key={entity} className="block font-semibold text-slate-300">{entity.replace(' de Familia', '')}: {count}</span>)}
                        </div>
                    </div>
                ))}
            </div>
            <div className="mt-1 flex gap-[2px] text-[10px] font-bold text-slate-500">
                {series.map((point) => <span key={point.month} className="flex-1 truncate text-center">{monthLabel(point.month, true)}</span>)}
            </div>
            <details className="mt-2 text-xs">
                <summary className="cursor-pointer font-bold text-slate-600">Ver como tabla</summary>
                <table className="mt-2 w-full text-left">
                    <thead><tr className="text-slate-500"><th className="py-1">Mes</th><th className="py-1 text-right">Casos</th></tr></thead>
                    <tbody>{series.map((point) => <tr key={point.month} className="border-t border-slate-100"><td className="py-1">{monthLabel(point.month)}</td><td className="py-1 text-right tabular-nums">{point.total}</td></tr>)}</tbody>
                </table>
            </details>
        </div>
    );
};

const FactorTable = ({ title, rows }) => (
    <div>
        <p className="text-xs font-black uppercase tracking-wide text-slate-500">{title}</p>
        <table className="mt-1 w-full text-sm">
            <tbody>
                {rows.map((row) => (
                    <tr key={row.code} className="border-t border-slate-100">
                        <td className="py-1.5 font-bold text-slate-800">{row.label}</td>
                        <td className="py-1.5 text-right tabular-nums text-slate-600">{row.cases} casos</td>
                        <td className="py-1.5 text-right font-black tabular-nums text-slate-900">{row.small ? 'pocos casos' : formatPct(row.rate)}</td>
                    </tr>
                ))}
                {!rows.length && <tr><td className="py-1.5 text-slate-500">Sin datos suficientes.</td></tr>}
            </tbody>
        </table>
    </div>
);

// Informes de gestión aprobados (cifras agregadas que ya usa el boletín): se ven aunque no haya base caso a caso.
const periodoLargo = (periodo) => {
    if (!periodo) return '';
    const [anio, mes] = periodo.split('-');
    return `${['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'][Number(mes) - 1]} de ${anio}`;
};

const InformesComisarias = () => {
    const [datos, setDatos] = useState(null);
    useEffect(() => {
        let vigente = true;
        apiJson('/comisarias/informes').then((resultado) => { if (vigente) setDatos(resultado); }).catch(() => {});
        return () => { vigente = false; };
    }, []);
    if (!datos || (!datos.informes.length && !datos.pendientes)) return null;
    return (
        <section className="space-y-3">
            <div>
                <h3 className="text-lg font-black text-slate-900">Lo que ya reportaron las Comisarías</h3>
                <p className="text-sm font-semibold text-slate-600">Último informe de gestión aprobado de cada una. Son cifras del mes que reporta la Comisaría, las mismas del boletín.</p>
            </div>
            {datos.pendientes > 0 && (
                <p className="flex gap-2 bg-amber-50 p-3 text-sm font-semibold text-amber-900">
                    <AlertTriangle size={18} className="shrink-0" />
                    Hay {datos.pendientes} {datos.pendientes === 1 ? 'informe pendiente' : 'informes pendientes'} de aprobar: no se muestran hasta revisarlos en Centro de fuentes → Entregas.
                </p>
            )}
            <div className="grid gap-4 lg:grid-cols-2">
                {datos.informes.map((informe) => (
                    <Panel key={informe.entidad} title={informe.entidad} note={`Informe de ${periodoLargo(informe.periodo)} · corte ${formatDate(informe.corte)}`}>
                        <table className="w-full text-sm">
                            <tbody>
                                {informe.cifras.map((cifra) => (
                                    <tr key={cifra.indicador} className="border-t border-slate-100 first:border-t-0">
                                        <td className="py-1.5 pr-3 font-semibold text-slate-800">{cifra.indicador}</td>
                                        <td className="py-1.5 text-right font-black tabular-nums text-slate-950">
                                            {cifra.valor === null ? '—' : Number(cifra.valor).toLocaleString('es-CO')}
                                            {cifra.unidad && <span className="ml-1 text-xs font-semibold text-slate-500">{cifra.unidad}</span>}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {informe.cifras.length < 3 && <p className="mt-2 text-xs font-semibold text-amber-800">Este informe trae muy pocas cifras; conviene pedir el informe completo.</p>}
                    </Panel>
                ))}
            </div>
        </section>
    );
};

const Analysis = ({ catalog, onUpload, onTemplate }) => {
    const [entity, setEntity] = useState('');
    const [start, setStart] = useState('');
    const [end, setEnd] = useState('');
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        const params = new URLSearchParams();
        if (entity) params.set('entity', entity);
        if (start) params.set('start', start);
        if (end) params.set('end', end);
        try {
            setData(await apiJson(`/comisarias/analysis?${params}`));
        } catch (loadError) {
            setError(loadError.message);
        } finally {
            setLoading(false);
        }
    }, [entity, start, end]);
    useEffect(() => { load(); }, [load]);

    if (error) return <p className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-semibold text-slate-500"><Loader2 size={16} className="animate-spin" /> Cargando…</p>;
    if (data.status === 'SIN_DATOS' && !data.data_last) {
        return (
            <div className="space-y-6">
            <InformesComisarias />
            <section className="space-y-3 border border-dashed border-slate-300 bg-white p-6">
                <h3 className="text-lg font-black text-slate-900">Análisis caso a caso: aún no hay bases cargadas</h3>
                <p className="max-w-3xl text-sm font-semibold leading-6 text-slate-600">
                    Cuando las Comisarías respondan la solicitud del Observatorio, cargue aquí su base (Excel o CSV) en el formato que usen.
                    Si no tienen formato propio, envíeles la plantilla: trae los 11 datos solicitados y la explicación de cada columna.
                </p>
                <div className="flex flex-wrap gap-2">
                    <button onClick={onTemplate} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50"><Download size={17} /> Descargar plantilla</button>
                    <button onClick={onUpload} className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8]"><Upload size={17} /> Cargar base</button>
                </div>
            </section>
            </div>
        );
    }

    const reinc = data.reincidence ? reincidenceSummary(data.reincidence) : null;
    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-end gap-3 border border-slate-200 bg-white p-3">
                <label className="text-xs font-bold text-slate-600">Comisaría
                    <select value={entity} onChange={(event) => setEntity(event.target.value)} className="mt-1 block min-h-10 border border-slate-300 px-2 text-sm">
                        <option value="">Ambas</option>
                        {(catalog?.entities || []).map((name) => <option key={name} value={name}>{name}</option>)}
                    </select>
                </label>
                <label className="text-xs font-bold text-slate-600">Desde
                    <input type="date" value={start} onChange={(event) => setStart(event.target.value)} className="mt-1 block min-h-10 border border-slate-300 px-2 text-sm" />
                </label>
                <label className="text-xs font-bold text-slate-600">Hasta
                    <input type="date" value={end} onChange={(event) => setEnd(event.target.value)} className="mt-1 block min-h-10 border border-slate-300 px-2 text-sm" />
                </label>
                {(start || end || entity) && <button onClick={() => { setEntity(''); setStart(''); setEnd(''); }} className="min-h-10 px-2 text-sm font-bold text-[#281FD0]">Limpiar</button>}
                {loading && <Loader2 size={16} className="mb-3 animate-spin text-slate-500" />}
                <p className="ml-auto text-xs font-semibold text-slate-500">
                    {data.status === 'OK' ? `${formatDate(data.start)} a ${formatDate(data.end)}` : 'Sin casos en ese periodo'} · datos del {formatDate(data.data_first)} al {formatDate(data.data_last)}
                </p>
            </div>

            {data.status !== 'OK' ? (
                <p className="bg-slate-100 p-3 text-sm font-bold text-slate-700">No hay casos en el periodo elegido.</p>
            ) : (
                <>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        <Tile label="Casos atendidos" value={data.total.toLocaleString('es-CO')}
                            helper={Object.entries(data.by_entity).map(([name, count]) => `${name.replace('Comisaría ', '').replace(' de Familia', '')}: ${count}`).join(' · ')} />
                        <Tile label="Víctimas mujeres" value={formatPct(data.women_pct)} helper="De los casos con sexo registrado." />
                        <Tile label="Reincidencia" value={reinc.value} helper={reinc.helper} />
                        <Tile label="Días hasta la medida" value={formatDays(data.response.median_days)}
                            helper={data.response.with_both_dates ? `Mediana, en ${data.response.with_both_dates} casos con ambas fechas. Más de 7 días: ${formatPct(data.response.over_7_days_pct)}.` : 'Sin fechas de medida.'} />
                        <Tile label="Con seguimiento" value={formatPct(data.response.followup_pct)} helper={`De ${data.response.followup_known} casos con el dato.`} />
                    </div>

                    <Panel title="Tendencia" note="Casos atendidos por mes. Pase el cursor sobre una barra para ver cada comisaría.">
                        <MonthlyChart series={data.series} />
                    </Panel>

                    <div className="grid gap-4 lg:grid-cols-2">
                        <Panel title="Concentración territorial"
                            note={`Barrios y sectores con más casos. «Últimos 90 días» frente a los 90 anteriores. ${data.territory_unlocated ? `${data.territory_unlocated} casos sin barrio.` : ''}`}>
                            <Bars rows={data.territory.map((row) => ({ ...row, label: row.recognized ? row.lugar : `${row.lugar} (no reconocido)` }))}
                                suffix={(row) => <span className={`ml-2 text-xs font-bold ${row.recent > row.prior ? 'text-red-700' : 'text-slate-500'}`}>{row.prior}→{row.recent}</span>} />
                        </Panel>
                        <Panel title="Tipo de violencia" note="Un caso puede tener más de un tipo.">
                            <Bars rows={data.violence} />
                        </Panel>
                        <Panel title="Relación con el presunto agresor"><Bars rows={data.relationship} /></Panel>
                        <Panel title="Víctimas por edad" note="Ciclo vital. Entre paréntesis: mujeres / hombres.">
                            <Bars rows={data.age.filter((row) => row.count)} suffix={(row) => <span className="ml-2 text-xs font-semibold text-slate-500">({row.mujer} / {row.hombre})</span>} />
                        </Panel>
                        <Panel title="Nivel de riesgo"><Bars rows={data.risk} /></Panel>
                        <Panel title="Medidas de protección" note={`${data.response.with_measure} casos (${formatPct(data.response.with_measure_pct)}) con al menos una medida.`}>
                            <Bars rows={data.measures} />
                        </Panel>
                    </div>

                    <Panel title="Reincidencia y factores de riesgo"
                        note={`Porcentaje de casos que reinciden según cada característica. Con menos de ${data.min_cell} casos no se calcula el porcentaje.`}>
                        <div className="grid gap-4 md:grid-cols-3">
                            <FactorTable title="Antecedentes previos" rows={data.factors.antecedentes} />
                            <FactorTable title="Nivel de riesgo" rows={data.factors.nivel_riesgo} />
                            <FactorTable title="Relación con el agresor" rows={data.factors.relacion} />
                        </div>
                        <p className="mt-3 text-xs font-semibold leading-5 text-slate-500">{reinc.method}</p>
                    </Panel>

                    <div className="grid gap-4 lg:grid-cols-2">
                        <Panel title="Comisarías frente a denuncias ante la Policía"
                            note="Denuncias de violencia intrafamiliar en Jamundí según Mindefensa (solo hay total municipal anual y puede estar incompleto para el año en curso).">
                            <table className="w-full text-sm">
                                <thead><tr className="text-left text-xs text-slate-500"><th className="py-1">Año</th><th className="py-1 text-right">Casos en Comisarías</th><th className="py-1 text-right">Denuncias (Policía)</th></tr></thead>
                                <tbody>{data.police.map((row) => (
                                    <tr key={row.year} className="border-t border-slate-100">
                                        <td className="py-1.5 font-bold">{row.year}</td>
                                        <td className="py-1.5 text-right tabular-nums">{row.comisarias}</td>
                                        <td className="py-1.5 text-right tabular-nums">{row.policia ?? 'sin dato'}</td>
                                    </tr>
                                ))}</tbody>
                            </table>
                        </Panel>
                        <Panel title="Qué tan completa viene la información" note="Porcentaje de casos con cada dato diligenciado. Úselo para retroalimentar a las Comisarías.">
                            <Bars rows={Object.entries(data.completeness).map(([code, pct]) => ({ code, label: COMPLETENESS_LABELS[code] || code, count: pct ?? 0, display: formatPct(pct) }))} />
                        </Panel>
                    </div>
                    <InformesComisarias />
                    <p className="text-xs font-semibold text-slate-500">Uso interno y reservado. Solo se muestran cifras agregadas; el SISC no guarda nombres, documentos, teléfonos ni direcciones.</p>
                </>
            )}
        </div>
    );
};

const MappingEditor = ({ delivery, catalog, onChange, busy }) => {
    const [mapping, setMapping] = useState(delivery.mapping);
    useEffect(() => setMapping(delivery.mapping), [delivery.id, delivery.mapping]);
    const dirty = JSON.stringify(mapping) !== JSON.stringify(delivery.mapping);
    const columns = delivery.columns || [];
    return (
        <Panel title="Columnas del archivo" note="El SISC reconoció estas columnas. Corrija la que no corresponda y aplique los cambios antes de confirmar.">
            <div className="grid gap-2 md:grid-cols-2">
                {(catalog?.fields || []).map((field) => (
                    <label key={field.code} className="text-xs font-bold text-slate-600">
                        {field.label}{field.required ? ' *' : ''}
                        <select value={mapping[field.code] || ''} disabled={busy}
                            onChange={(event) => setMapping({ ...mapping, [field.code]: event.target.value || undefined })}
                            className={`mt-1 block min-h-10 w-full border px-2 text-sm ${mapping[field.code] ? 'border-slate-300' : 'border-amber-400 bg-amber-50'}`}>
                            <option value="">— No viene en el archivo —</option>
                            {columns.map((column) => <option key={column} value={column}>{column}{delivery.samples?.[column]?.length ? ` (ej.: ${delivery.samples[column].slice(0, 2).join(', ')})` : ''}</option>)}
                        </select>
                    </label>
                ))}
            </div>
            {dirty && (
                <button disabled={busy} onClick={() => onChange(Object.fromEntries(Object.entries(mapping).filter(([, value]) => value)))}
                    className="mt-3 inline-flex min-h-10 items-center gap-2 bg-slate-900 px-3 text-sm font-black text-white disabled:opacity-50">
                    Aplicar cambios y revisar de nuevo
                </button>
            )}
        </Panel>
    );
};

const DeliveryReview = ({ delivery, catalog, onDone }) => {
    const [current, setCurrent] = useState(delivery);
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    useEffect(() => setCurrent(delivery), [delivery]);
    const s = current.summary;
    const pending = current.status === 'PREVISUALIZADA';

    const run = async (label, path, options) => {
        setBusy(label);
        setError('');
        try {
            const updated = await apiJson(`/comisarias/deliveries/${current.id}${path}`, options);
            setCurrent({ ...current, ...updated });
            if (label !== 'remap') onDone(updated);
        } catch (runError) {
            setError(runError.message);
        } finally {
            setBusy('');
        }
    };

    return (
        <div className="space-y-4">
            <section className="border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-center gap-2">
                    <FileSpreadsheet size={18} className="text-[#281FD0]" />
                    <h3 className="font-black text-slate-900">{current.filename}</h3>
                    <span className={`px-2 py-0.5 text-[11px] font-black uppercase ${STATUS_STYLES[current.status]}`}>{current.status.toLowerCase()}</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-slate-600">{current.entity} · hoja «{current.sheet}» · {s.period_start ? `atenciones del ${formatDate(s.period_start)} al ${formatDate(s.period_end)}` : 'sin fechas válidas'}</p>
                <div className="mt-3 grid gap-2 text-sm sm:grid-cols-4">
                    <p><span className="block text-2xl font-black tabular-nums">{s.total_rows}</span>filas leídas</p>
                    <p><span className="block text-2xl font-black tabular-nums text-emerald-700">{s.accepted}</span>casos válidos</p>
                    <p><span className="block text-2xl font-black tabular-nums text-red-700">{s.rejected}</span>filas rechazadas</p>
                    <p><span className="block text-2xl font-black tabular-nums">{s.duplicates}</span>repetidas en el archivo</p>
                </div>
                {s.created != null && <p className="mt-2 text-sm font-bold text-emerald-800">Cargado: {s.created} casos nuevos y {s.updated} actualizados.</p>}
                {s.already_loaded && <p className="mt-2 bg-amber-50 p-2 text-sm font-bold text-amber-900">Este mismo archivo ya se cargó el {formatDate(s.already_loaded)}. Si lo confirma, no se duplican casos: solo se actualizan.</p>}
            </section>

            {current.dropped_columns?.length > 0 && (
                <section className="flex gap-3 border border-emerald-200 bg-emerald-50 p-4 text-sm">
                    <ShieldCheck size={20} className="shrink-0 text-emerald-700" />
                    <div>
                        <p className="font-black text-emerald-900">Columnas descartadas para proteger a las personas (no se guardan):</p>
                        <p className="font-semibold text-emerald-800">{current.dropped_columns.map((item) => `${item.column} (${item.reason === 'PERSONAL' ? 'dato personal' : 'texto libre'})`).join(' · ')}</p>
                    </div>
                </section>
            )}
            {s.has_case_code ? null : (
                <p className="flex gap-2 bg-slate-100 p-3 text-sm font-semibold text-slate-700"><AlertTriangle size={18} className="shrink-0" /> El archivo no trae código interno de caso: la reincidencia se medirá solo con la columna de nuevos episodios.</p>
            )}
            {s.missing_fields?.length > 0 && (
                <p className="bg-amber-50 p-3 text-sm font-semibold text-amber-900">
                    No se encontraron: {s.missing_fields.map((code) => catalog?.fields.find((field) => field.code === code)?.label || code).join(', ')}. Si vienen con otro nombre, asígnelos abajo.
                </p>
            )}
            {s.errors?.length > 0 && (
                <Panel title="Filas rechazadas" note={s.rejected > s.errors.length ? `Se muestran las primeras ${s.errors.length} de ${s.rejected}.` : undefined}>
                    <ul className="text-sm">{s.errors.map((item) => <li key={item.fila} className="border-t border-slate-100 py-1"><b>Fila {item.fila}:</b> {item.motivo}</li>)}</ul>
                </Panel>
            )}
            {s.unknown_places?.length > 0 && (
                <Panel title="Barrios o sectores no reconocidos" note="Se cargan con el nombre que traen, pero no se ubican en el mapa oficial. Revise la escritura con la comisaría.">
                    <p className="text-sm font-semibold text-slate-700">{s.unknown_places.map((item) => `${item.lugar} (${item.casos})`).join(' · ')}</p>
                </Panel>
            )}

            {pending && <MappingEditor delivery={current} catalog={catalog} busy={!!busy}
                onChange={(mapping) => run('remap', '/mapping', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mapping }) })} />}

            {error && <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}
            {pending && (
                <div className="flex flex-wrap gap-2">
                    <button disabled={!!busy || !s.accepted || !current.mapping.fecha_atencion} onClick={() => run('confirm', '/confirm', { method: 'POST' })}
                        className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8] disabled:opacity-40">
                        {busy === 'confirm' ? <Loader2 size={17} className="animate-spin" /> : <CheckCircle2 size={17} />} Confirmar carga de {s.accepted} casos
                    </button>
                    <button disabled={!!busy} onClick={() => run('discard', '/discard', { method: 'POST' })}
                        className="inline-flex min-h-11 items-center gap-2 border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50">
                        <XCircle size={17} /> Descartar
                    </button>
                </div>
            )}
        </div>
    );
};

const UploadTab = ({ catalog, onLoaded }) => {
    const [entity, setEntity] = useState('');
    const [delivery, setDelivery] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const fileRef = useRef(null);

    const upload = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        setBusy(true);
        setError('');
        const form = new FormData();
        form.append('file', file);
        form.append('entity', entity);
        try {
            const response = await apiFetch('/comisarias/deliveries/preview', { method: 'POST', body: form });
            if (!response.ok) throw new Error(await readApiError(response));
            setDelivery(await response.json());
        } catch (uploadError) {
            setError(uploadError.message);
        } finally {
            setBusy(false);
            if (fileRef.current) fileRef.current.value = '';
        }
    };

    if (delivery) {
        return (
            <div className="space-y-3">
                <button onClick={() => setDelivery(null)} className="text-sm font-bold text-[#281FD0]">← Cargar otro archivo</button>
                <DeliveryReview delivery={delivery} catalog={catalog} onDone={(updated) => { setDelivery({ ...delivery, ...updated }); onLoaded(); }} />
            </div>
        );
    }
    return (
        <section className="space-y-4 border border-slate-200 bg-white p-5">
            <div>
                <h3 className="text-lg font-black text-slate-900">Cargar la base de una Comisaría</h3>
                <p className="mt-1 max-w-3xl text-sm font-semibold leading-6 text-slate-600">
                    Suba el archivo tal como lo envió la comisaría (Excel o CSV, una fila por atención). Antes de guardar nada verá qué columnas reconoció el SISC,
                    qué filas tienen problemas y qué columnas con datos personales se descartan.
                </p>
            </div>
            <label className="block max-w-sm text-xs font-bold text-slate-600">Comisaría que envía
                <select value={entity} onChange={(event) => setEntity(event.target.value)} className="mt-1 block min-h-11 w-full border border-slate-300 px-2 text-sm">
                    <option value="">Elija una…</option>
                    {(catalog?.entities || []).map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
            </label>
            <button disabled={!entity || busy} onClick={() => fileRef.current?.click()}
                className="inline-flex min-h-11 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white hover:bg-[#1F18A8] disabled:opacity-40">
                {busy ? <Loader2 size={17} className="animate-spin" /> : <Upload size={17} />} Elegir archivo
            </button>
            <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={upload} />
            {error && <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}
        </section>
    );
};

const DeliveriesTab = ({ catalog, refreshKey }) => {
    const [rows, setRows] = useState([]);
    const [open, setOpen] = useState(null);
    const [error, setError] = useState('');
    const load = useCallback(() => apiJson('/comisarias/deliveries').then(setRows).catch((loadError) => setError(loadError.message)), []);
    useEffect(() => { load(); }, [load, refreshKey]);

    if (open) {
        return (
            <div className="space-y-3">
                <button onClick={() => { setOpen(null); load(); }} className="text-sm font-bold text-[#281FD0]">← Volver a las entregas</button>
                <DeliveryReview delivery={open} catalog={catalog} onDone={() => load()} />
            </div>
        );
    }
    return (
        <section className="border border-slate-200 bg-white">
            {error && <p className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}
            {!rows.length && !error && <p className="p-4 text-sm font-semibold text-slate-500">Todavía no hay entregas.</p>}
            <ul>
                {rows.map((row) => (
                    <li key={row.id} className="border-t border-slate-100 first:border-t-0">
                        <button onClick={async () => setOpen(await apiJson(`/comisarias/deliveries/${row.id}`))} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 p-3 text-left hover:bg-slate-50">
                            <span className={`px-2 py-0.5 text-[11px] font-black uppercase ${STATUS_STYLES[row.status]}`}>{row.status.toLowerCase()}</span>
                            <span className="font-black text-slate-900">{row.entity}</span>
                            <span className="text-sm font-semibold text-slate-600">{row.filename}</span>
                            <span className="text-sm font-semibold text-slate-500">{row.summary.accepted} casos · {row.period_start ? `${formatDate(row.period_start)} a ${formatDate(row.period_end)}` : ''}</span>
                            <span className="ml-auto text-xs font-semibold text-slate-500">{row.created_by} · {formatDate(row.created_at)}</span>
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
};

const ComisariasModule = () => {
    const [tab, setTab] = useState('analysis');
    const [catalog, setCatalog] = useState(null);
    const [refreshKey, setRefreshKey] = useState(0);
    const [message, setMessage] = useState('');

    useEffect(() => { apiJson('/comisarias/catalog').then(setCatalog).catch((error) => setMessage(error.message)); }, []);

    const downloadTemplate = async () => {
        try {
            const response = await apiFetch('/comisarias/template');
            if (!response.ok) throw new Error(await readApiError(response));
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement('a');
            link.href = url;
            link.download = 'plantilla_casos_vif_comisarias.xlsx';
            link.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            setMessage(error.message);
        }
    };

    return (
        <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
            <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-[#281FD0]">Gestión institucional</p>
                    <h1 className="mt-1 text-3xl font-black text-slate-950">Comisarías de Familia</h1>
                    <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-600">
                        Casos de violencia intrafamiliar atendidos por las Comisarías, anonimizados: tendencia, barrios donde se concentran, reincidencia,
                        factores de riesgo y oportunidad de las medidas de protección. Uso interno y reservado.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button onClick={downloadTemplate} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50">
                        <Download size={17} /> Plantilla para las Comisarías
                    </button>
                    <button onClick={() => setRefreshKey((key) => key + 1)} aria-label="Recargar" className="inline-flex min-h-11 items-center border border-slate-300 bg-white px-3 text-slate-700 hover:bg-slate-50">
                        <RefreshCw size={17} />
                    </button>
                </div>
            </header>
            {message && <p role="status" className="bg-red-50 p-3 text-sm font-bold text-red-800">{message}</p>}
            <div className="flex gap-1 border-b border-slate-200" role="tablist">
                {TABS.map((item) => (
                    <button key={item.id} role="tab" aria-selected={tab === item.id} onClick={() => setTab(item.id)}
                        className={`min-h-11 px-4 text-sm font-black ${tab === item.id ? 'border-b-4 border-[#281FD0] text-slate-950' : 'text-slate-500 hover:text-slate-800'}`}>
                        {item.label}
                    </button>
                ))}
            </div>
            {tab === 'analysis' && <Analysis key={refreshKey} catalog={catalog} onUpload={() => setTab('upload')} onTemplate={downloadTemplate} />}
            {tab === 'upload' && <UploadTab catalog={catalog} onLoaded={() => setRefreshKey((key) => key + 1)} />}
            {tab === 'deliveries' && <DeliveriesTab catalog={catalog} refreshKey={refreshKey} />}
        </div>
    );
};

export default ComisariasModule;
