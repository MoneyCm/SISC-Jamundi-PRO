import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, ShieldCheck, XCircle } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const LEVEL_STYLES = {
    BLOQUEA: { icon: XCircle, box: 'border-red-200 bg-red-50', title: 'text-red-900', text: 'text-red-800', iconClass: 'text-red-600', label: 'Bloquea' },
    REVISAR: { icon: AlertTriangle, box: 'border-amber-200 bg-amber-50', title: 'text-amber-950', text: 'text-amber-900', iconClass: 'text-amber-600', label: 'Revisar' },
    OK: { icon: CheckCircle2, box: 'border-slate-200 bg-white', title: 'text-slate-800', text: 'text-slate-500', iconClass: 'text-emerald-600', label: 'Verificado' },
};

const formatDateTime = (value) => {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('es-CO', { dateStyle: 'long', timeStyle: 'short' });
};

/**
 * Revisión editorial antes de publicar: muestra qué comprobó el sistema, qué debe mirar
 * una persona y, si no hay bloqueos, permite aprobar y publicar dejando constancia.
 */
const EditorialReview = ({ publication, authHeaders, canApprove, onPublished, showActions = true }) => {
    const [acknowledged, setAcknowledged] = useState(false);
    const [working, setWorking] = useState(false);
    const [error, setError] = useState('');

    const governance = publication?.governance || {};
    const review = governance.editorial_review;
    if (!review) return null;

    const checks = review.checks || [];
    const ordered = ['BLOQUEA', 'REVISAR', 'OK'].flatMap((level) => checks.filter((check) => check.level === level));
    const published = publication.status === 'PUBLISHED';
    const approval = governance.approval;
    const isSavedDraft = publication.status === 'DRAFT' && governance.history_saved;
    const needsAck = review.warnings > 0;

    const approve = async () => {
        setWorking(true);
        setError('');
        try {
            const response = await fetch(`${API_BASE_URL}/sisc-cifras/publications/${publication.id}/approve`, {
                method: 'POST',
                headers: { ...authHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ warnings_acknowledged: acknowledged }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || `No se pudo publicar (${response.status}).`);
            onPublished?.(data);
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setWorking(false);
        }
    };

    return (
        <section className="rounded-lg border border-slate-200 bg-white p-5" aria-labelledby="editorial-review-title">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                    <ShieldCheck size={18} className="text-[#281FD0]" />
                    <h2 id="editorial-review-title" className="text-sm font-black uppercase tracking-wide text-slate-900">Revisión antes de publicar</h2>
                </div>
                <p className="text-xs font-bold text-slate-500">
                    {review.blocking > 0 ? `${review.blocking} bloqueo(s)` : 'Sin bloqueos'} · {review.warnings} advertencia(s)
                </p>
            </div>

            <ul className="mt-4 space-y-2">
                {ordered.map((check, index) => {
                    const style = LEVEL_STYLES[check.level] || LEVEL_STYLES.OK;
                    const Icon = style.icon;
                    return (
                        <li key={`${check.code}-${index}`} className={`flex gap-3 rounded-md border p-3 ${style.box}`}>
                            <Icon size={17} className={`mt-0.5 shrink-0 ${style.iconClass}`} />
                            <div className="min-w-0">
                                <p className={`text-sm font-black ${style.title}`}>
                                    <span className="mr-2 text-[10px] uppercase tracking-wide opacity-70">{style.label}</span>{check.title}
                                </p>
                                <p className={`mt-0.5 text-xs font-semibold leading-5 ${style.text}`}>{check.detail}</p>
                            </div>
                        </li>
                    );
                })}
            </ul>

            {showActions && <div className="mt-4 border-t border-slate-100 pt-4">
                {published ? (
                    <p className="flex items-center gap-2 text-sm font-black text-emerald-700">
                        <CheckCircle2 size={18} />
                        {approval?.approved_by
                            ? `Publicado por ${approval.approved_by} el ${formatDateTime(approval.approved_at).replace(/\.$/, '')}.`
                            : 'Publicado sin aprobación registrada (publicación automática anterior).'}
                    </p>
                ) : !isSavedDraft ? (
                    <p className="text-xs font-semibold text-slate-500">Vista previa: este boletín no se guardó y no se publicará.</p>
                ) : review.blocking > 0 ? (
                    <p className="text-sm font-bold text-red-800">Resuelva los bloqueos y genere el boletín de nuevo para poder publicarlo.</p>
                ) : !canApprove ? (
                    <p className="text-sm font-bold text-slate-600">Borrador guardado. Una persona con rol de publicación debe aprobarlo.</p>
                ) : (
                    <div className="space-y-3">
                        {needsAck && (
                            <label className="flex items-start gap-3 text-sm font-semibold text-slate-700">
                                <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} className="mt-1" />
                                Revisé las {review.warnings} advertencia(s) y el boletín las presenta de forma que no induce a error.
                            </label>
                        )}
                        <button
                            onClick={approve}
                            disabled={working || (needsAck && !acknowledged)}
                            className="inline-flex min-h-11 items-center gap-2 rounded-md bg-emerald-600 px-4 text-sm font-black text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                            {working ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Aprobar y publicar en el portal
                        </button>
                        <p className="text-xs font-semibold text-slate-500">Quedará registrado quién aprobó, cuándo y qué advertencias aceptó.</p>
                    </div>
                )}
                {error && <p className="mt-3 text-sm font-bold text-red-700" role="alert">{error}</p>}
            </div>}
        </section>
    );
};

export default EditorialReview;
