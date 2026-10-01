import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, FileClock, Loader2, Trash2 } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';
import { puedePublicar } from '../utils/permisos';
import { etiquetaEdicion, textoBorrador } from '../utils/borradores';

/**
 * Borradores guardados que esperan aprobación. "Revisar" los abre tal como se generaron;
 * "Descartar" (solo quien publica) los deja como reemplazados, sin borrarlos.
 */
const BorradoresPendientes = ({ authHeaders, onOpen, refreshKey, openId }) => {
    const [drafts, setDrafts] = useState([]);
    const [working, setWorking] = useState(null);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/sisc-cifras/publications/drafts`, { headers: authHeaders() });
            setDrafts(response.ok ? await response.json() : []);
        } catch {
            setDrafts([]);
        }
    }, [authHeaders]);

    useEffect(() => { load(); }, [load, refreshKey]);

    const discard = async (draft) => {
        if (!window.confirm(`¿Descartar el borrador ${textoBorrador(draft)}? No se borra: queda registrado como descartado.`)) return;
        setWorking(draft.id);
        setError('');
        try {
            const response = await fetch(`${API_BASE_URL}/sisc-cifras/publications/${draft.id}/discard`, {
                method: 'POST', headers: authHeaders(),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || `No se pudo descartar (${response.status}).`);
            await load();
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setWorking(null);
        }
    };

    if (!drafts.length) return null;
    const publica = puedePublicar();
    return (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-4" aria-labelledby="borradores-title">
            <h2 id="borradores-title" className="flex items-center gap-2 text-xs font-black uppercase tracking-wide text-amber-950">
                <FileClock size={15} /> Borradores pendientes ({drafts.length})
            </h2>
            <ul className="mt-3 space-y-2">
                {drafts.map((draft) => (
                    <li key={draft.id} className={`rounded-md border bg-white p-3 ${draft.id === openId ? 'border-[#281FD0]' : 'border-amber-200'}`}>
                        <p className="text-sm font-black text-slate-900">{etiquetaEdicion(draft.edition_type)} · {draft.period_start} al {draft.period_end}</p>
                        <p className="text-xs text-slate-500">Generado por {draft.created_by || 'sin registro'}{draft.created_at ? ` el ${draft.created_at.slice(0, 10)}` : ''}</p>
                        {draft.stale && (
                            <p className="mt-1 flex items-start gap-1 text-xs font-bold text-amber-800">
                                <AlertTriangle size={13} className="mt-0.5 shrink-0" /> Se armó con una sábana anterior: no se puede publicar. Descártelo y genere uno nuevo.
                            </p>
                        )}
                        <div className="mt-2 flex flex-wrap gap-2">
                            {!draft.stale && (
                                <button type="button" onClick={() => onOpen(draft)} className="min-h-9 rounded-md bg-[#281FD0] px-3 text-xs font-black text-white hover:bg-[#1f18a8]">
                                    {publica ? 'Revisar y publicar' : 'Revisar'}
                                </button>
                            )}
                            {publica && (
                                <button type="button" onClick={() => discard(draft)} disabled={working === draft.id}
                                    className="inline-flex min-h-9 items-center gap-1 rounded-md border border-slate-300 bg-white px-3 text-xs font-black text-slate-700 hover:bg-slate-50 disabled:opacity-40">
                                    {working === draft.id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />} Descartar
                                </button>
                            )}
                        </div>
                    </li>
                ))}
            </ul>
            {error && <p className="mt-2 text-xs font-bold text-red-700" role="alert">{error}</p>}
        </section>
    );
};

export default BorradoresPendientes;
