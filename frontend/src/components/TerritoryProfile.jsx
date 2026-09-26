import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Search } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import { formatChange, searchText } from '../utils/territoryProfile';

const STATUS_LABELS = { SIN_INFORMACION: 'Sin información', PENDIENTE: 'Pendiente', EN_CURSO: 'En curso', CUMPLIDO: 'Cumplido', NO_CUMPLIDO: 'No cumplido', DESCARTADO: 'Descartado' };
const ALERT_LABELS = { RNMC_BACKLOG: 'medidas represadas', RNMC_RATIFICADA_SIN_PAGO: 'multas ratificadas sin pago', RNMC_GEO_MISSING: 'sin ubicación' };
const number = (value) => Number(value || 0).toLocaleString('es-CO');

const Section = ({ title, children }) => (
    <section className="bg-white p-4 shadow-sm">
        <h3 className="text-sm font-black uppercase tracking-wide text-[#281FD0]">{title}</h3>
        <div className="mt-3">{children}</div>
    </section>
);

const Monthly = ({ series }) => {
    const max = Math.max(1, ...series.map((item) => item.value));
    return (
        <div className="flex h-28 items-end gap-1" role="img" aria-label={`Hechos por mes: ${series.map((item) => `${item.label} ${item.value}`).join(', ')}`}>
            {series.map((item) => (
                <div key={item.label} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                    <span className="text-[10px] font-bold tabular-nums text-slate-600">{item.value}</span>
                    <span className={`w-full ${item.partial ? 'bg-slate-300' : 'bg-[#281FD0]'}`} style={{ height: `${Math.max(2, (item.value / max) * 72)}px` }} />
                    <span className="truncate text-[10px] font-semibold text-slate-500">{item.label}</span>
                </div>
            ))}
        </div>
    );
};

const Profile = ({ name, onOpenCommitments }) => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    useEffect(() => {
        let alive = true;
        setData(null);
        setError('');
        apiJson(`/observatory/territories/profile?name=${encodeURIComponent(name)}`)
            .then((result) => alive && setData(result)).catch((loadError) => alive && setError(loadError.message));
        return () => { alive = false; };
    }, [name]);

    if (error) return <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>;
    if (!data) return <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Armando la ficha…</p>;
    const { facts, comparendos, decisions } = data;
    const alerts = Object.entries(comparendos.open_alerts || {});
    return (
        <div className="space-y-4">
            <header>
                <p className="text-xs font-black uppercase tracking-wide text-slate-500">{data.group_label}</p>
                <h2 className="text-2xl font-black text-slate-950">{data.name}</h2>
                {data.defensoria.map((alert) => (
                    <p key={alert.id} className="mt-2 inline-block bg-amber-100 px-2 py-1 text-xs font-black text-amber-900">
                        Advertido por la Defensoría: {alert.title || alert.id}{alert.date ? ` (${alert.date.slice(0, 4)})` : ''}
                    </p>
                ))}
            </header>

            <div className="grid gap-4 lg:grid-cols-2">
                <Section title="Hechos registrados">
                    <p className="text-sm font-semibold text-slate-600">{facts.year_label}</p>
                    <p className="mt-1 text-2xl font-black tabular-nums text-slate-950">
                        {number(facts.total.current)} <span className="text-sm font-bold text-slate-500">(antes {number(facts.total.previous)}; {formatChange(facts.total)})</span>
                    </p>
                    <table className="mt-3 w-full text-sm">
                        <tbody>
                            {facts.by_conduct.map((row) => (
                                <tr key={row.conducta} className="border-t border-slate-100">
                                    <td className="py-1 font-bold text-slate-800">{row.label}</td>
                                    <td className="py-1 text-right tabular-nums text-slate-600">{row.previous} → {row.current}</td>
                                    <td className="py-1 pl-3 text-right font-black tabular-nums">{formatChange(row)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    <p className={`mt-3 text-sm font-semibold ${facts.recent.anomaly ? 'text-red-700' : 'text-slate-600'}`}>
                        Últimos 28 días: {facts.recent.observed} hechos; lo esperado según los 6 meses anteriores era {String(facts.recent.expected).replace('.', ',')}.
                        {facts.recent.anomaly ? ' El radar la marca como señal estadística.' : ''}
                    </p>
                </Section>
                <Section title="Últimos 12 meses">
                    <Monthly series={facts.monthly} />
                    <p className="mt-2 text-xs font-semibold text-slate-500">La barra gris es el mes en curso: todavía se está completando.</p>
                </Section>
                <Section title="Comparendos (Inspecciones)">
                    <p className="text-sm font-semibold text-slate-700">
                        {number(comparendos.last_12_months)} medidas en los últimos 12 meses{comparendos.last_date ? ` · dato más reciente del ${comparendos.last_date.split('-').reverse().join('/')}` : ''}.
                    </p>
                    {comparendos.top_measures.length > 0 && (
                        <ul className="mt-2 space-y-1 text-sm">
                            {comparendos.top_measures.map((item) => <li key={item.label} className="flex justify-between gap-3"><span className="text-slate-700">{item.label.toLowerCase()}</span><b className="tabular-nums">{item.count}</b></li>)}
                        </ul>
                    )}
                    {alerts.length > 0 && <p className="mt-2 text-sm font-bold text-amber-800">Alertas abiertas: {alerts.map(([key, n]) => `${n} ${ALERT_LABELS[key] || key}`).join(', ')}.</p>}
                </Section>
                <Section title="Decisiones y conocimiento">
                    {!decisions.commitments.length && !decisions.studies.length && (
                        <p className="text-sm font-semibold text-slate-600">Ningún compromiso del Consejo ni estudio del Observatorio menciona este territorio.</p>
                    )}
                    {decisions.commitments.length > 0 && (
                        <ul className="space-y-2 text-sm">
                            {decisions.commitments.map((item) => (
                                <li key={item.code}>
                                    <button onClick={onOpenCommitments} className="text-left font-black text-[#281FD0] hover:underline">{item.code}</button>{' '}
                                    <span className="text-slate-700">{item.text}</span>{' '}
                                    <span className="text-xs font-bold text-slate-500">· {STATUS_LABELS[item.status] || item.status}{item.flags.includes('ATRASADO') ? ' · atrasado' : ''}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                    {decisions.interventions.length > 0 && <p className="mt-2 text-sm font-semibold text-slate-700">{decisions.interventions.length} intervenciones documentadas.</p>}
                    {decisions.studies.map((study) => <p key={study.code} className="mt-2 text-sm font-semibold text-slate-700">Estudio {study.code}: {study.title}</p>)}
                </Section>
            </div>
            {data.notes.map((note) => <p key={note} className="text-xs font-semibold text-slate-500">{note}</p>)}
        </div>
    );
};

/** Buscador y ficha territorial (uso interno). La lista va en orden alfabético: no es un ranking. */
const TerritoryProfile = ({ initialName = '', onOpenCommitments }) => {
    const [territories, setTerritories] = useState([]);
    const [query, setQuery] = useState('');
    const [selected, setSelected] = useState(initialName);
    const [error, setError] = useState('');
    useEffect(() => { apiJson('/observatory/territories').then(setTerritories).catch((loadError) => setError(loadError.message)); }, []);
    useEffect(() => { if (initialName) setSelected(initialName); }, [initialName]);
    const visible = useMemo(() => territories.filter((item) => searchText(item.name).includes(searchText(query))), [territories, query]);

    return (
        <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
            <aside className="bg-white shadow-sm">
                <label className="m-3 flex items-center gap-2 border border-slate-300 px-3">
                    <Search size={16} className="text-slate-400" />
                    <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar barrio o vereda…" aria-label="Buscar barrio o vereda" className="w-full py-2 text-sm outline-none" />
                </label>
                {error && <p role="alert" className="px-3 pb-3 text-sm font-bold text-red-700">{error}</p>}
                <ul className="max-h-[520px] overflow-y-auto">
                    {visible.map((item) => (
                        <li key={item.name}>
                            <button onClick={() => setSelected(item.name)} aria-current={selected === item.name}
                                className={`block w-full border-t border-slate-100 px-4 py-2 text-left text-sm ${selected === item.name ? 'bg-indigo-50 font-black text-[#281FD0]' : 'font-semibold text-slate-700 hover:bg-slate-50'}`}>
                                {item.name}
                                {item.group === 'AT' && <span className="ml-2 text-[10px] font-black uppercase text-amber-700">advertido</span>}
                            </button>
                        </li>
                    ))}
                </ul>
            </aside>
            <div>
                {selected ? <Profile name={selected} onOpenCommitments={onOpenCommitments} />
                    : <p className="bg-slate-50 p-4 text-sm font-semibold text-slate-600">Elija un barrio, vereda o sector para ver su ficha.</p>}
            </div>
        </div>
    );
};

export default TerritoryProfile;
