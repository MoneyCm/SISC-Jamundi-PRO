import React, { lazy, Suspense, useState } from 'react';
import { Database, ClipboardCheck } from 'lucide-react';

const SourceCenter = lazy(() => import('./SourceCenter'));
const InstitutionalAgents = lazy(() => import('./InstitutionalAgents'));

export default function SourceCenterHub({ userRoles = [], onOpenBulletin, initialSection = 'sources' }) {
    const canManageDeliveries = userRoles.some((role) => ['TI_ADMIN', 'FUNC_ADMIN', 'SOURCE_UPLOADER', 'STEWARD', 'DATA_OWNER'].includes(role));
    const [section, setSection] = useState(initialSection);
    const active = canManageDeliveries ? section : 'sources';
    return <div className="space-y-5">
        {canManageDeliveries && <nav aria-label="Secciones del centro de fuentes" className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-2">
            {[['sources', 'Fuentes y monitores', Database], ['deliveries', 'Entregas institucionales', ClipboardCheck]].map(([key, label, Icon]) => <button key={key} type="button" aria-pressed={active === key} onClick={() => setSection(key)} className={`inline-flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-bold ${active === key ? 'bg-primary text-white' : 'text-slate-600 hover:bg-slate-100'}`}><Icon size={17} />{label}</button>)}
        </nav>}
        {active === 'deliveries' && <div className="rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-sm text-slate-700"><strong className="block text-slate-900">Entregas de Comisarías e Inspecciones</strong><p className="mt-1">Recepción de archivos, revisión de hallazgos y aprobación para publicación. Los expedientes y actuaciones se consultan en Inspecciones de Policía.</p></div>}
        <Suspense fallback={<div role="status" className="p-8 text-center text-sm text-slate-500">Cargando sección…</div>}>
            {active === 'deliveries' ? <InstitutionalAgents /> : <SourceCenter userRoles={userRoles} onOpenBulletin={onOpenBulletin} />}
        </Suspense>
    </div>;
}
