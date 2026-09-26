'use client';
import { useEffect } from 'react';
import { useOfficialIndicator, OfficialResult } from '../hooks/useOfficialIndicator';
interface Props {
  periodStart: string; periodEnd: string; sourceVersionId: string;
  onOfficialChange: (r: OfficialResult | null) => void;
  onPendingChange?: (pending: boolean, error: string | null) => void;
  onSelectionChange?: (s: { sourceVersionId: string; indicator: string }) => void;
}
export default function OfficialQueryPanel({ periodStart, periodEnd, sourceVersionId, onOfficialChange, onPendingChange, onSelectionChange }: Props) {
  const official = useOfficialIndicator();
  const { query, invalidate } = official;
  useEffect(() => {
    invalidate(); onOfficialChange(null);
    onSelectionChange?.({ sourceVersionId, indicator: 'SEGURIDAD_TOTAL' });
    if (sourceVersionId) void query({ indicator: 'SEGURIDAD_TOTAL', periodStart, periodEnd, territory: 'JAMUNDI', sourceVersionId, methodologyVersion: '1' });
  }, [periodStart, periodEnd, sourceVersionId, query, invalidate, onOfficialChange, onSelectionChange]);
  useEffect(() => { onOfficialChange(official.data); }, [official.data, onOfficialChange]);
  useEffect(() => { onPendingChange?.(official.pending, official.error); }, [official.pending, official.error, onPendingChange]);
  return <section className="rounded border border-ui-border bg-black/20 p-4 text-sm">
    <h3 className="font-bold text-white">Cifras para el boletín</h3>
    {!sourceVersionId && <p className="mt-2 text-ui-text-secondary">Se calcularán automáticamente cuando la sábana esté validada.</p>}
    {official.pending && <p role="status" className="mt-2">Calculando el período seleccionado…</p>}
    {official.error && <div role="alert" className="mt-2 text-red-200"><p>{official.error}</p><button className="underline" onClick={() => void query({ indicator: 'SEGURIDAD_TOTAL', periodStart, periodEnd, territory: 'JAMUNDI', sourceVersionId, methodologyVersion: '1' })}>Reintentar consulta</button></div>}
    {official.data && <div className="mt-2 rounded border border-emerald-400/30 bg-emerald-400/10 p-3">
      <p className="text-2xl font-bold text-white">{official.data.value} <span className="text-sm font-normal">{official.data.unit}</span></p>
      <p className="text-emerald-200">Jamundí · {periodStart} a {periodEnd}</p>
      <p className="mt-1 text-ui-text-secondary">Cifra calculada con la entrega cargada. Revise el borrador antes de publicar.</p>
      <details className="mt-2 text-xs text-ui-text-secondary"><summary>Ver trazabilidad</summary><p className="break-all">Entrega: {sourceVersionId}</p><p>Metodología: {official.data.methodology_version}</p><p className="break-all">Consulta: {official.data.query_hash}</p></details>
    </div>}
  </section>;
}
