import { bulletinFetch as fetch } from '../lib/bulletinApi';
"use client";
import { useCallback, useEffect, useRef, useState } from 'react';

export interface OfficialQuery {
  indicator: string;
  periodStart: string;
  periodEnd: string;
  territory: string;
  sourceVersionId: string | null;
  methodologyVersion: string;
}

export interface OfficialResult {
  value: number;
  unit: string;
  unit_code: string;
  indicator: string;
  source_version_id: string | null;
  methodology_version: string;
  query_hash: string;
  quality_status: string;
  period: { start: string; end: string };
  territory: string;
  reproducible?: boolean;
  exploratory?: boolean;
  publication_note?: string;
}

interface State {
  data: OfficialResult | null;
  pending: boolean;
  error: string | null;
  requestId: number;
}

/**
 * Consulta oficial única con stale-guard:
 * - Cada cambio de filtros invalida el resultado anterior (data=null hasta nueva respuesta).
 * - Respuestas atrasadas se ignoran por requestId + AbortController.
 * - Ante error del backend se muestra el error; NUNCA se sustituye por conteo Excel.
 */
export function useOfficialIndicator() {
  const [state, setState] = useState<State>({ data: null, pending: false, error: null, requestId: 0 });
  const reqRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const query = useCallback(async (q: OfficialQuery) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const id = ++reqRef.current;
    setState((s) => ({ ...s, data: null, pending: true, error: null, requestId: id }));
    try {
      const res = await fetch('/api/official-indicator', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          indicator: q.indicator,
          period: { start: q.periodStart, end: q.periodEnd },
          territory: q.territory,
          source_version_id: q.sourceVersionId,
          methodology_version: q.methodologyVersion,
        }),
      });
      const data: unknown = await res.json();
      if (reqRef.current !== id || controller.signal.aborted) return;
      if (!res.ok) {
        const msg = (data as { detail?: string; error?: string })?.detail
          || (data as { error?: string })?.error
          || 'El backend no pudo calcular el indicador.';
        setState({ data: null, pending: false, error: String(msg), requestId: id });
        return;
      }
      setState({ data: data as OfficialResult, pending: false, error: null, requestId: id });
    } catch (e: unknown) {
      if (reqRef.current !== id) return;
      if (e instanceof Error && e.name === 'AbortError') return;
      setState({ data: null, pending: false, error: e instanceof Error ? e.message : 'Error de conexión con el SISC.', requestId: id });
    }
  }, []);

  const invalidate = useCallback(() => {
    abortRef.current?.abort();
    reqRef.current += 1;
    setState((s) => ({ ...s, data: null, pending: false, error: null, requestId: reqRef.current }));
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { ...state, query, invalidate };
}
