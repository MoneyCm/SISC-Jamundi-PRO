import React, { useMemo, useState } from 'react';
import { Search, MapPinned, Maximize2, Minimize2, Download } from 'lucide-react';
import TerritoryMap from './TerritoryMap';
import { territoryKind, visibleTerritories, reviewableTerritories } from '../../utils/territoryExplorer';

const number = (value) => Number(value || 0).toLocaleString('es-CO');
export default function TerritoryExplorer({ map, selectedTerritory, onSelect }) {
    const [scope, setScope] = useState('all');
    const [query, setQuery] = useState('');
    const [expanded, setExpanded] = useState(false);
    const points = map.points || [];
    const scoped = useMemo(() => visibleTerritories(points, scope, ''), [points, scope]);
    const matches = useMemo(() => visibleTerritories(points, scope, query), [points, scope, query]);
    const pending = reviewableTerritories(map);
    const total = scoped.reduce((sum, item) => sum + Number(item.total || 0), 0);
    const selected = points.find((point) => point.name === selectedTerritory);
    const exportPending = () => {
        const cell = (value) => `"${String(value || '').replace(/^[=+@-]/, "'$&").replace(/"/g, '""')}"`;
        const csv = '\uFEFF' + [['Territorio', 'Registros', 'Motivo'], ...pending.map((item) => [item.name, item.total, item.reason])].map((row) => row.map(cell).join(',')).join('\r\n');
        const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
        const link = document.createElement('a'); link.href = url; link.download = 'Revision_territorial_SISC.csv'; link.click(); URL.revokeObjectURL(url);
    };
    return <div className={expanded ? 'fixed inset-0 z-[1000] overflow-y-auto bg-slate-50 p-3 md:p-6' : ''}>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-950 p-4 text-white">
            <div><p className="text-xs font-bold uppercase tracking-widest text-indigo-300">Explorador territorial</p><p className="mt-1 text-sm">{number(scoped.length)} territorios · {number(total)} casos representados</p></div>
            <button type="button" onClick={() => setExpanded(!expanded)} className="inline-flex items-center gap-2 rounded-lg border border-white/30 px-3 py-2 text-xs font-bold">{expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}{expanded ? 'Cerrar vista ampliada' : 'Ampliar mapa'}</button>
        </div>
        <div className="flex flex-wrap gap-2 border-b border-slate-200 bg-white p-3" aria-label="Ámbito territorial">
            {[['all', 'Todo el municipio'], ['urban', 'Barrios urbanos'], ['rural', 'Veredas'], ['unknown', 'Sin clasificación']].map(([key, label]) => <button key={key} type="button" aria-pressed={scope === key} onClick={() => { setScope(key); setQuery(''); onSelect(''); }} className={`rounded-lg px-3 py-2 text-xs font-bold ${scope === key ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>{label} <span className="ml-1 opacity-70">{points.filter((point) => key === 'all' || territoryKind(point) === key).length}</span></button>)}
        </div>
        <div className="grid min-w-0 lg:grid-cols-[240px_minmax(0,1fr)]">
            <aside className="min-w-0 border-b border-slate-200 bg-white lg:border-b-0 lg:border-r">
                <label className="m-3 flex items-center gap-2 rounded-lg border border-slate-200 px-3"><Search size={16} className="text-slate-400" /><input aria-label="Buscar barrio o vereda" placeholder="Buscar territorio…" value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 w-full bg-transparent py-3 text-sm outline-none" /></label>
                <p className="px-4 pb-2 text-[11px] text-slate-500">Mayor cantidad de casos · pulsa para acercar</p>
                <div className="max-h-48 overflow-y-auto lg:max-h-[490px]">
                    {matches.map((point) => <button key={point.name} onClick={() => onSelect(point.name)} className={`block w-full border-t border-slate-100 px-4 py-3 text-left hover:bg-indigo-50 ${selectedTerritory === point.name ? 'bg-indigo-50 ring-1 ring-inset ring-indigo-200' : ''}`}><span className="flex items-start justify-between gap-3"><span className="text-xs font-bold text-slate-800">{point.name}</span><span className="text-sm font-black text-primary">{number(point.total)}</span></span><span className="mt-2 block h-1 overflow-hidden rounded bg-slate-100"><span className="block h-full rounded bg-indigo-400" style={{ width: `${Math.max(3, point.total / Math.max(1, scoped[0]?.total || 1) * 100)}%` }} /></span></button>)}
                    {!matches.length && <p className="p-4 text-sm text-slate-500">No hay territorios para esta búsqueda o ámbito.</p>}
                </div>
            </aside>
            <div className="min-w-0"><TerritoryMap map={{ ...map, points: scoped }} selectedTerritory={selectedTerritory} onSelect={onSelect} focusSelection className={expanded ? 'h-[70vh] min-h-[440px]' : 'h-[600px]'} /></div>
        </div>
        <div className="border-t border-slate-200 bg-white p-4">
            {selected ? <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold text-primary">Territorio seleccionado</p><h3 className="mt-1 text-lg font-black text-slate-900">{selected.name}</h3><p className="mt-1 text-xs text-slate-500">Cartografía: {selected.source || 'Sin fuente declarada'}</p></div><p className="text-2xl font-black text-slate-900">{number(selected.total)} <span className="text-xs font-normal">casos</span></p></div> : <p className="flex items-center gap-2 text-sm text-slate-600"><MapPinned size={18} />Selecciona un territorio en la lista o en el mapa para ver su detalle.</p>}
            <p className="mt-3 text-xs leading-5 text-slate-500">El color compara cantidades dentro del ámbito visible; no representa una tasa de riesgo. La búsqueda filtra la lista. Los territorios sin casos publicables no aparecen coloreados.</p>
        </div>
        <details className="border-t border-amber-200 bg-amber-50/60 p-4">
            <summary className="cursor-pointer text-sm font-bold text-slate-800">Revisión territorial · {pending.length} nombres sin polígono</summary>
            <p className="mt-3 text-xs leading-5 text-slate-600">Estos registros no tienen una correspondencia cartográfica verificada. La bandeja permite revisar y exportar; no asigna ubicaciones automáticamente. Los nombres de baja frecuencia se mantienen ocultos.</p>
            {pending.length > 0 ? <><button onClick={exportPending} className="my-3 inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs font-bold"><Download size={15} />Exportar pendientes</button><div className="max-h-72 overflow-auto rounded-lg border border-amber-100 bg-white"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-slate-100"><tr><th className="p-3">Nombre en datos</th><th className="p-3">Registros</th><th className="p-3">Por revisar</th></tr></thead><tbody>{pending.map((item) => <tr key={item.name} className="border-t border-slate-100"><td className="p-3 font-bold">{item.name}</td><td className="p-3">{number(item.total)}</td><td className="p-3">{item.reason}</td></tr>)}</tbody></table></div></> : <p className="mt-3 text-sm text-slate-600">No hay pendientes cartográficos publicables para este periodo.</p>}
        </details>
    </div>;
}
