import React, { useEffect, useState } from 'react';
import {
    FileText, CalendarDays, AlertTriangle, CheckCircle2, XCircle,
    ArrowRight, MapPin, Clock, Search, Loader2
} from 'lucide-react';
import { apiJson } from '../utils/apiClient';

const fmt = (v) => Number(v || 0).toLocaleString('es-CO');

const TriFuenteDisplay = ({ tri }) => {
    if (!tri) return null;
    const estado = tri.estado || '—';
    const isWarning = estado === 'WARNING';
    const hfp = tri.hechos_por_fuente || {};
    const spoa = hfp['FISCALIA_SPOA_V3'] || {};
    const ml = hfp['MEDICINA_LEGAL'] || {};
    const pol = hfp['POLICIA_SEMANAL'] || {};
    const arb = tri.arbitraje_forense || {};
    const evidencias = tri.evidencias || [];
    const nota = tri.nota_metodologica || '';

    return (
        <div className="mt-4 space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-black uppercase tracking-wide ${
                    isWarning ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                }`}>
                    {isWarning ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
                    {estado}
                </span>
                {arb.desempate && (
                    <span className="text-xs text-slate-600">
                        Arbitraje: <strong>{arb.desempate.fuente_final}</strong>
                    </span>
                )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div className="bg-slate-50 rounded-lg p-2">
                    <span className="text-slate-500 uppercase tracking-wider">POLICIA</span>
                    <p className="font-black text-lg">{fmt(pol.hechos)}</p>
                    <p className="text-slate-400">hechos</p>
                </div>
                <div className="bg-amber-50 rounded-lg p-2">
                    <span className="text-amber-700 uppercase tracking-wider">SPOA</span>
                    <p className="font-black text-lg">{fmt(spoa.hechos)}</p>
                    <p className="text-amber-400">hechos</p>
                </div>
                <div className="bg-blue-50 rounded-lg p-2">
                    <span className="text-blue-700 uppercase tracking-wider">MEDICINA LEGAL</span>
                    <p className="font-black text-lg">{fmt(ml.hechos)}</p>
                    <p className="text-blue-400">hechos</p>
                </div>
            </div>

            {evidencias.length > 0 && (
                <div className="text-xs space-y-1">
                    <p className="font-bold text-slate-700 uppercase tracking-wider">Evidencias</p>
                    {evidencias.map((e, i) => (
                        <p key={i} className="text-slate-600 flex items-start gap-1">
                            <span className="text-slate-400">•</span> {e}
                        </p>
                    ))}
                </div>
            )}

            {nota && (
                <p className="text-xs text-slate-500 italic mt-2">{nota}</p>
            )}
        </div>
    );
};

const ObservatoryBulletins = () => {
    const [bulletins, setBulletins] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const data = await apiJson('/sisc-cifras/publications/public');
                if (!cancelled) setBulletins(Array.isArray(data) ? data : []);
            } catch (e) {
                if (!cancelled) setError(e?.message || 'Error al cargar boletines');
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        load();
        return () => { cancelled = true; };
    }, []);

    if (loading) {
        return (
            <div className="flex min-h-[50vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex min-h-[50vh] items-center justify-center">
                <div className="text-center text-red-600">
                    <XCircle className="h-10 w-10 mx-auto mb-2" />
                    <p className="font-bold">{error}</p>
                </div>
            </div>
        );
    }

    return (
        <section className="space-y-6">
            <div className="flex items-center gap-3 mb-2">
                <div className="bg-primary/10 p-2.5 rounded-xl">
                    <FileText className="h-6 w-6 text-primary" />
                </div>
                <div>
                    <h2 className="text-xl font-black text-slate-900">Boletines del Observatorio</h2>
                    <p className="text-xs text-slate-500">Conciliación tri-fuente de homicidios</p>
                </div>
            </div>

            {bulletins.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                    <Search className="h-12 w-12 mb-3" />
                    <p className="font-bold">Sin boletines publicados</p>
                    <p className="text-xs">Genera un boletín con las 3 fuentes para ver la conciliación.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {bulletins.map((b) => {
                        const tri = b?.publication_json?.governance?.integrity?.tri_fuente_homicidios;
                        return (
                            <article key={b.id} className="bg-white rounded-2xl shadow-lg border border-slate-100 p-5 hover:shadow-xl transition-shadow">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="space-y-1">
                                        <h3 className="font-black text-slate-900">{b.title}</h3>
                                        <div className="flex items-center gap-2 text-xs text-slate-500">
                                            <CalendarDays size={14} />
                                            <span>{b.period_start} → {b.period_end}</span>
                                        </div>
                                        <div className="flex items-center gap-2 text-xs text-slate-400">
                                            <Clock size={14} />
                                            <span>{b.edition_type}</span>
                                            {b.source_codes?.includes('FISCALIA_SPOA_V3') && (
                                                <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">SPOA</span>
                                            )}
                                            {b.source_codes?.includes('MEDICINA_LEGAL') && (
                                                <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">ML</span>
                                            )}
                                        </div>
                                    </div>
                                    <ArrowRight className="h-5 w-5 text-slate-300 flex-shrink-0" />
                                </div>

                                {tri ? (
                                    <TriFuenteDisplay tri={tri} />
                                ) : (
                                    <div className="mt-4 flex items-center gap-2 text-xs text-amber-700 bg-amber-50 rounded-lg p-3">
                                        <AlertTriangle size={16} />
                                        <span>Sin conciliación tri-fuente: faltan entregas fijas (SPOA/ML).</span>
                                    </div>
                                )}
                            </article>
                        );
                    })}
                </div>
            )}
        </section>
    );
};

export default ObservatoryBulletins;
