import React, { useCallback, useEffect, useState } from 'react';
import { ArrowRight, CalendarDays, Loader2 } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import { CALENDAR_STATUS, councilText } from '../utils/operatingCalendar';

/** Calendario operativo: qué toca esta semana y cuándo es el próximo Consejo (uso interno). */
const WeekCalendar = ({ onTab, onNavigate }) => {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [editing, setEditing] = useState(false);
    const [day, setDay] = useState('');

    const load = useCallback(async () => {
        try {
            setData(await apiJson('/observatory/calendar'));
            setError('');
        } catch (loadError) {
            setError(loadError.message);
        }
    }, []);
    useEffect(() => { load(); }, [load]);

    const setSession = async (event) => {
        event.preventDefault();
        setError('');
        try {
            await apiJson('/observatory/council-sessions', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_date: day }),
            });
            setEditing(false);
            load();
        } catch (saveError) {
            setError(saveError.message);
        }
    };
    const clearSession = async () => {
        setError('');
        try {
            await apiJson(`/observatory/council-sessions/${data.council.session_id}`, { method: 'DELETE' });
            load();
        } catch (saveError) {
            setError(saveError.message);
        }
    };

    if (!data) {
        return error
            ? <p role="alert" className="bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>
            : <p className="flex items-center gap-2 text-sm font-bold text-slate-500"><Loader2 size={16} className="animate-spin" /> Armando la semana…</p>;
    }

    const go = (target) => (target.tab ? onTab?.(target.tab) : onNavigate?.(target.page));
    return (
        <section className="bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-3 border-b border-slate-200 pb-3 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-sm font-black uppercase tracking-wide text-slate-700">Esta semana</h2>
                    <p className="mt-1 flex items-center gap-2 text-sm font-semibold text-slate-700">
                        <CalendarDays size={16} className="text-[#281FD0]" /> {councilText(data.council)}
                    </p>
                </div>
                {!editing && (
                    <div className="flex gap-3 text-sm font-black">
                        <button onClick={() => { setDay(data.council.start); setEditing(true); }} className="text-[#281FD0] hover:underline">
                            {data.council.source === 'REGISTRADA' ? 'Cambiar fecha' : 'Fijar fecha del Consejo'}
                        </button>
                        {data.council.session_id && <button onClick={clearSession} className="text-slate-500 hover:text-slate-900">Quitar fecha</button>}
                    </div>
                )}
                {editing && (
                    <form onSubmit={setSession} className="flex flex-wrap items-center gap-2">
                        <input type="date" required value={day} onChange={(event) => setDay(event.target.value)} aria-label="Fecha de la sesión del Consejo"
                            className="border border-slate-300 px-2 py-1.5 text-sm font-semibold" />
                        <button type="submit" className="bg-[#281FD0] px-3 py-1.5 text-sm font-black text-white">Guardar</button>
                        <button type="button" onClick={() => setEditing(false)} className="border border-slate-300 px-3 py-1.5 text-sm font-bold text-slate-700">Cancelar</button>
                    </form>
                )}
            </div>
            {error && <p role="alert" className="mt-2 bg-red-50 p-2 text-sm font-bold text-red-800">{error}</p>}
            <ul className="divide-y divide-slate-100">
                {data.items.map((row) => {
                    const status = CALENDAR_STATUS[row.status];
                    return (
                        <li key={row.key} className="grid gap-1 py-2.5 md:grid-cols-[120px_minmax(0,1fr)_auto] md:items-center">
                            <span className={`w-fit px-2 py-0.5 text-[11px] font-black uppercase ${status.chip}`}>{status.label}</span>
                            <div className="min-w-0">
                                <p className={`text-sm font-black ${row.status === 'HECHO' ? 'text-slate-500' : 'text-slate-900'}`}>
                                    {row.title} <span className="font-semibold text-slate-500">· {row.when}</span>
                                </p>
                                <p className="text-xs font-semibold text-slate-500">{row.detail}</p>
                            </div>
                            {row.status !== 'HECHO' && (
                                <button onClick={() => go(row.target)} className="inline-flex items-center gap-1 text-sm font-black text-[#281FD0] hover:underline">
                                    Ir <ArrowRight size={14} />
                                </button>
                            )}
                        </li>
                    );
                })}
            </ul>
        </section>
    );
};

export default WeekCalendar;
