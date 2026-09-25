import React, { useEffect, useState } from 'react';
import { ArrowRight, ShieldCheck, Users, Database, Activity, RefreshCw, ClipboardCheck } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

const attentionStatuses = new Set(['ERROR', 'NOT_CONNECTED', 'UPDATE_AVAILABLE', 'NEEDS_REVIEW', 'EXPIRED', 'LAGGED']);

export default function AdminWorkspace({ userRoles, onNavigate }) {
    const [state, setState] = useState({});
    const [revision, setRevision] = useState(0);
    useEffect(() => {
        let cancelled = false;
        setState({});
        const queries = [
            ['access', '/users/access-requests/pending', (data) => {
                if (!Array.isArray(data)) throw new Error('Respuesta no válida');
                return data.length;
            }],
            ['sources', '/source-center', (data) => {
                if (!Array.isArray(data?.connectors)) throw new Error('Respuesta no válida');
                return data.connectors.filter((item) => attentionStatuses.has(item.status)).length;
            }],
        ];
        queries.forEach(async ([key, endpoint, select]) => {
            try {
                const value = select(await apiJson(endpoint));
                if (!cancelled) setState((previous) => ({ ...previous, [key]: { value } }));
            } catch {
                if (!cancelled) setState((previous) => ({ ...previous, [key]: { error: true } }));
            }
        });
        return () => { cancelled = true; };
    }, [revision]);

    const cards = [
        { key: 'access', label: 'Solicitudes de acceso', detail: 'Autorizaciones pendientes de revisión', page: 'access_requests', icon: ClipboardCheck },
        { key: 'sources', label: 'Fuentes por atender', detail: 'Actualizaciones, rezagos o incidencias', page: 'sources', icon: Database },
    ];
    return (
        <section aria-label="Centro de administración" className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="relative overflow-hidden bg-slate-950 px-6 py-7 text-white md:px-8">
                <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-28 h-80 w-80 rounded-full border-[40px] border-indigo-500/10" />
                <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                    <div className="max-w-xl">
                        <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-indigo-300"><ShieldCheck size={16} /> {userRoles.includes('TI_ADMIN') ? 'Administración TI' : 'Administración funcional'}</p>
                        <h1 className="mt-3 text-3xl font-black tracking-tight md:text-4xl">Tu centro de trabajo</h1>
                        <p className="mt-3 text-sm leading-6 text-slate-300">Gestiona los accesos, revisa tus fuentes y mantén la información lista para decidir.</p>
                    </div>
                    <button onClick={() => onNavigate('sources')} className="inline-flex items-center justify-center gap-3 self-start rounded-xl bg-white px-5 py-3 text-sm font-bold text-slate-900 hover:bg-indigo-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white">Abrir centro de fuentes <ArrowRight size={17} /></button>
                </div>
            </div>
            <div className="p-5 md:p-6">
                <div className="mb-4 flex items-center justify-between gap-3"><div><h2 className="font-bold text-slate-900">Tu agenda de gestión</h2><p className="mt-1 text-xs text-slate-500">Estado actual · independiente del periodo estadístico</p></div><button onClick={() => setRevision((value) => value + 1)} aria-label="Actualizar pendientes administrativos" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><RefreshCw size={17} /></button></div>
                <div className="grid gap-3 sm:grid-cols-2" aria-live="polite">
                    {cards.map(({ key, label, detail, page, icon: Icon }) => {
                        const result = state[key];
                        const pending = result?.value > 0;
                        return <button key={key} onClick={() => onNavigate(page)} className={`group flex items-center gap-4 rounded-xl border p-4 text-left transition-colors focus-visible:outline-primary ${pending ? 'border-amber-200 bg-amber-50 hover:bg-amber-100' : 'border-slate-200 bg-slate-50 hover:bg-indigo-50'}`}>
                            <span className="rounded-xl bg-white p-3 text-primary"><Icon size={21} /></span>
                            <span className="flex-1"><span className="block text-sm font-bold text-slate-900">{label}</span><span className="mt-1 block text-xs text-slate-500">{result?.error ? 'No se pudo consultar. Abre el módulo o reintenta.' : detail}</span></span>
                            <span className="text-3xl font-black text-slate-900" aria-label={!result ? 'Consultando' : result.error ? 'No disponible' : `${result.value}`}>{!result ? '…' : result.error ? '—' : result.value}</span><ArrowRight size={16} className="text-slate-400 group-hover:text-primary" />
                        </button>;
                    })}
                </div>
                <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
                    {[['users', 'Gestionar usuarios', Users], ['audit', 'Consultar auditoría', Activity], ['boletin_replica', 'Cargar sábana en Boletín', Database]].map(([page, label, Icon]) => <button key={page} onClick={() => onNavigate(page)} className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 hover:text-primary"><Icon size={15} />{label}<ArrowRight size={13} /></button>)}
                </div>
            </div>
        </section>
    );
}
