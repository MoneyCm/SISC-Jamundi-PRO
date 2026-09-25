import { bulletinFetch as fetch } from '../lib/bulletinApi';
'use client';
import { useEffect, useRef, useState } from 'react';

type Run = { id: string; status: string; total_filas: number; aprobadas: number; rechazadas: number; duplicadas: number;
  resumen?: { snapshot?: { coverage?: { max_date?: string; max_week_by_year?: Record<string, number> }; nuevas_consolidadas?: number; actualizadas_consolidadas?: number }; dq?: { semaforo?: string } } };
type Props = { onStart: () => void; onReady: (file: File, run: Run) => void };
const field = 'w-full rounded border border-ui-border bg-black/30 p-2 text-white';

export default function SabanaUploadFlow({ onStart, onReady }: Props) {
  const [user, setUser] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [phase, setPhase] = useState(''); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(''); const [issues, setIssues] = useState<string[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [pendingRun, setPendingRun] = useState('');
  const [reconciliation, setReconciliation] = useState('');
  const fileRef = useRef<File | null>(null);
  const controller = useRef<AbortController | null>(null);
  const serial = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    fetch('/api/generator/session', { signal: abort.signal, cache: 'no-store' }).then(r => r.json()).then(d => { if (d.authenticated) setUser(d.full_name || d.username); })
      .catch(() => {}).finally(() => setChecking(false));
    return () => { abort.abort(); controller.current?.abort(); serial.current++; if (timer.current) clearTimeout(timer.current); };
  }, []);
  async function request(url: string, options: RequestInit = {}) {
    const r = await fetch(url, options); const d = await r.json();
    if (!r.ok) {
      if (r.status === 401) setUser(null);
      const detail = d.detail;
      throw new Error(typeof detail === 'string' ? detail : detail?.message || d.error || 'No se pudo completar la operación.');
    }
    return d;
  }
  async function poll(id: string, file: File, seq: number, signal: AbortSignal, attempts = 0) {
    try {
      const result: Run = await request(`/api/generator/ingestion/${id}`, { signal, cache: 'no-store' });
      if (seq !== serial.current) return;
      if (result.status === 'COMPLETED') {
        setRun(result); setBusy(false); setPendingRun('');
        if (result.rechazadas > 0 || result.aprobadas === 0) { setError('La carga tiene registros rechazados o ningún registro aprobado. Revise el archivo antes de preparar cifras oficiales.'); setPhase('Requiere corrección'); return; }
        setPhase('Entrega lista. Elija el período del boletín.'); onReady(file, result);
        setReconciliation('Comprobando cambios frente a boletines anteriores…');
        try {
          const summary = await request(`/api/generator/summary/${id}`, { signal, cache: 'no-store' });
          if (seq === serial.current) setReconciliation([summary.publication, summary.note, summary.caveat].filter(Boolean).join(' · '));
        } catch { if (seq === serial.current) setReconciliation('No se pudo conciliar el historial. La carga está guardada; revise el antecedente desde Historial.'); }
        return;
      }
      if (result.status === 'FAILED') throw new Error('El procesamiento falló. Puede volver a cargar el archivo; el sistema reconoce entregas repetidas.');
      if (attempts >= 100) throw new Error('El procesamiento continúa. Pulse Consultar avance; no es necesario volver a subir el archivo.');
      timer.current = setTimeout(() => void poll(id, file, seq, signal, attempts + 1), 3000);
    } catch (e) { if (seq !== serial.current || signal.aborted) return; setBusy(false); setError((e as Error).message); }
  }
  async function upload(file: File) {
    controller.current?.abort(); if (timer.current) clearTimeout(timer.current);
    const abort = new AbortController(); controller.current = abort; const seq = ++serial.current;
    fileRef.current = file; setRun(null); setPendingRun(''); setError(''); setIssues([]); setReconciliation(''); setBusy(true); onStart();
    try {
      if (!file.size || file.size > 25 * 1024 * 1024) throw new Error('Seleccione un archivo no vacío de hasta 25 MB.');
      const form = new FormData(); form.set('file', file);
      setPhase('1 de 3 · Revisando estructura y calidad…');
      const check = await request('/api/generator/ingestion/preflight', { method: 'POST', body: form, signal: abort.signal });
      if (seq !== serial.current) return;
      setIssues((check.issues || []).map((i: { message: string }) => i.message));
      if (check.status === 'BLOCKED') throw new Error('El archivo contiene errores que impiden incorporarlo. Corrija los hallazgos y vuelva a cargarlo.');
      setPhase('2 de 3 · Incorporando la entrega al histórico…');
      const accepted = await request('/api/generator/ingestion/upload', { method: 'POST', body: form, signal: abort.signal });
      if (seq !== serial.current) return;
      if (!accepted.ingestion_id) throw new Error('El servidor no devolvió una entrega. No se habilitarán cifras oficiales.');
      setPendingRun(accepted.ingestion_id); setPhase(accepted.status === 'skipped' ? 'Archivo reconocido. Recuperando su entrega…' : '3 de 3 · Procesando y verificando registros…');
      await poll(accepted.ingestion_id, file, seq, abort.signal);
    } catch (e) { if (seq !== serial.current || abort.signal.aborted) return; setBusy(false); setPhase('Carga detenida'); setError((e as Error).message); }
  }
  return <section className="rounded border border-ui-border bg-black/20 p-4 text-sm" aria-label="Carga de sábana">
    <h3 className="font-bold text-white">Cargar → validar → preparar boletín</h3>
    <p className="mt-1 text-ui-text-secondary">Seleccione la sábana una vez. La entrega y las cifras se vinculan automáticamente.</p>
    {checking ? <p>Comprobando sesión…</p> : !user ? <p role="alert" className="mt-3 text-amber-200">No se pudo verificar la sesión del SISC. Compruebe la conexión y vuelva a abrir esta sección.</p> : <>
      <div className="my-3"><span>Sesión del SISC: {user}</span></div>
      <label className="block">Sábana policial (Excel o CSV, hasta 25 MB)<input type="file" accept=".xlsx,.xls,.csv" disabled={busy} className={`${field} mt-1`} onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) void upload(f); }} /></label>
    </>}
    {phase && <p role="status" className="mt-3 text-white">{phase}</p>}
    {issues.length > 0 && <ul className="mt-2 list-disc pl-4 text-amber-200">{issues.map((i, n) => <li key={n}>{i}</li>)}</ul>}
    {error && <p role="alert" className="mt-2 border-l-2 border-red-400 p-2 text-red-200">{error}</p>}
    {reconciliation && <p className="mt-2 rounded border border-ui-border p-2 text-ui-text-secondary">{reconciliation}</p>}
    {pendingRun && !busy && user && <button className="mt-2 underline" onClick={() => { if (fileRef.current && controller.current) { setBusy(true); setError(''); void poll(pendingRun, fileRef.current, serial.current, controller.current.signal); } }}>Consultar avance</button>}
    {run && <div className="mt-3 rounded border border-white/15 p-3 text-ui-text-secondary"><p>{run.total_filas} registros recibidos · {run.aprobadas} aprobados · {run.duplicadas} duplicados · {run.rechazadas} rechazados.</p><p>Los registros recibidos no equivalen necesariamente a hechos únicos.</p><p>{run.resumen?.snapshot?.nuevas_consolidadas ?? 0} incorporaciones · {run.resumen?.snapshot?.actualizadas_consolidadas ?? 0} actualizaciones en el histórico.</p><p>Última fecha con registros: {run.resumen?.snapshot?.coverage?.max_date || 'no disponible'}. No demuestra por sí sola cobertura de días sin hechos.</p></div>}
  </section>;
}
