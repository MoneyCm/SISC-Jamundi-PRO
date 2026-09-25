import { bulletinFetch as fetch } from '../lib/bulletinApi';
"use client";
import React, { useEffect, useState } from 'react';

interface CentralPub {
  id: string;
  title: string;
  edition_type: string;
  period_start: string;
  period_end: string;
  created_at?: string | null;
  published_at?: string | null;
  source_codes?: string[];
}

const IMPORTED_KEY = 'sisc_replica_legacy_imported_hashes'; // protección contra duplicados (preferencia local)

/** Historial central + conciliación + importación explícita de borradores locales. */
export default function CentralHistoryPanel({ localDrafts }: { localDrafts: Array<{ id: string; anio: number; semana: number; totalYTD: number; totalSemana: number; nombreArchivo: string; hashArchivo: string }> }) {
  const [pubs, setPubs] = useState<CentralPub[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [newDelivery, setNewDelivery] = useState('');
  const [reconcilePending, setReconcilePending] = useState(false);
  const [reconcileResult, setReconcileResult] = useState<string | null>(null);
  const [imported, setImported] = useState<string[]>([]);

  useEffect(() => {
    try {
      setImported(JSON.parse(window.localStorage.getItem(IMPORTED_KEY) || '[]'));
    } catch { /* noop */ }
  }, []);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/central-history', { cache: 'no-store' });
      const data: unknown = await res.json();
      if (!res.ok) throw new Error((data as { error?: string })?.error || 'Error consultando historial central.');
      setPubs(Array.isArray(data) ? (data as CentralPub[]) : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error de conexión.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const reconcile = async () => {
    if (!selectedId || !newDelivery) return;
    setReconcilePending(true);
    setReconcileResult(null);
    try {
      const res = await fetch('/api/central-reconcile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ publication_id: selectedId, new_source_version_id: newDelivery.trim() }),
      });
      const data: unknown = await res.json();
      if (!res.ok) throw new Error((data as { detail?: string; error?: string })?.detail || (data as { error?: string })?.error || 'No se pudo conciliar.');
      const r = data as { diferencia?: number | null; nota_boletin?: string };
      setReconcileResult(`Diferencia: ${r.diferencia ?? '—'}. ${r.nota_boletin || ''}`);
    } catch (e: unknown) {
      setReconcileResult(`Error: ${e instanceof Error ? e.message : 'fallo'}`);
    } finally {
      setReconcilePending(false);
    }
  };

  return (
    <section className="border border-ui-border bg-black/20 p-4 text-xs">
      <div className="font-semibold text-white">Historial central (servidor — oficial)</div>
      <p className="mt-1 text-ui-text-secondary">El historial local del navegador es solo borrador y no alimenta cifras oficiales.</p>
      <button onClick={load} disabled={loading} className="mt-2 border border-ui-border px-3 py-2 text-white disabled:opacity-40">{loading ? 'Cargando…' : 'Recargar historial central'}</button>
      {error && <div className="mt-2 border border-red-400/40 bg-red-400/10 p-2 text-red-200">{error}</div>}
      <div className="mt-2 grid max-h-40 gap-1 overflow-y-auto">
        {pubs.map((p) => (
          <button key={p.id} onClick={() => setSelectedId(p.id)} className={`border p-2 text-left ${selectedId === p.id ? 'border-emerald-400 bg-emerald-400/10 text-white' : 'border-ui-border text-ui-text-secondary'}`}>
            <div className="font-bold">{p.period_start} a {p.period_end} · {p.edition_type}</div>
            <div className="break-all">{p.id}</div>
          </button>
        ))}
        {pubs.length === 0 && !loading && <div className="text-ui-text-secondary">Sin publicaciones centrales.</div>}
      </div>
      <div className="mt-3 grid gap-2">
        <label className="grid gap-1"><span className="text-ui-text-secondary">Publicación seleccionada (id)</span>
          <input value={selectedId} onChange={(e) => setSelectedId(e.target.value.trim())} className="border border-ui-border bg-black/30 p-2 text-white" placeholder="UUID publicación" /></label>
        <label className="grid gap-1"><span className="text-ui-text-secondary">Conciliar contra entrega (UUID)</span>
          <input value={newDelivery} onChange={(e) => setNewDelivery(e.target.value.trim())} className="border border-ui-border bg-black/30 p-2 text-white" placeholder="UUID entrega B" /></label>
        <p className="text-ui-text-secondary">La conciliación utiliza los permisos de su sesión del SISC.</p>
        <button onClick={reconcile} disabled={reconcilePending || !selectedId || !newDelivery} className="bg-ui-accent px-3 py-2 font-bold text-white disabled:opacity-40">{reconcilePending ? 'Conciliando…' : 'Solicitar conciliación central'}</button>
        {reconcileResult && <div className="border border-ui-border bg-white/5 p-2 text-white">{reconcileResult}</div>}
      </div>
      <div className="mt-3 border-t border-ui-border pt-2">
        <div className="font-semibold text-white">Importación explícita de borradores locales</div>
        <div className="text-ui-text-secondary">Acción explícita, visible y sin duplicados. Solo marca reproducible si el backend lo demuestra.</div>
        <div className="mt-1 grid gap-1">
          {localDrafts.slice(0, 5).map((d) => {
            const done = imported.includes(d.hashArchivo);
            return (
              <div key={d.id} className="flex items-center justify-between gap-2 border border-ui-border p-2">
                <span className="text-ui-text-secondary">{d.anio}-S{d.semana} · YTD {d.totalYTD} · {d.hashArchivo.slice(0, 10)}</span>
                <span className="text-ui-text-secondary">{done ? 'importado' : 'borrador local'}</span>
              </div>
            );
          })}
          {localDrafts.length === 0 && <div className="text-ui-text-secondary">Sin borradores locales.</div>}
        </div>
      </div>
    </section>
  );
}
