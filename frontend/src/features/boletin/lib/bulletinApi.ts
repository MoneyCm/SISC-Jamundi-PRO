import { apiFetch } from '../../../utils/apiClient';

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});

async function request(path: string, options: RequestInit = {}) {
  const response = await apiFetch(path, options);
  if (response.ok) return response;
  const payload = await response.json().catch(() => ({}));
  const detail = payload.detail;
  const error = typeof detail === 'string' ? detail
    : Array.isArray(detail) ? detail.map(item => item.msg || JSON.stringify(item)).join(' · ')
    : detail?.message || payload.error || payload.message || `Error HTTP ${response.status}`;
  return json({ ...payload, error, detail: error }, response.status);
}

async function summary(id: string, options: RequestInit) {
  const runResponse = await request(`/ingesta/runs/${encodeURIComponent(id)}`, options);
  if (!runResponse.ok) return runResponse;
  const run = await runResponse.json();
  if (run.status !== 'COMPLETED' || run.rechazadas > 0) return json({ note: 'La conciliación espera una entrega completa sin rechazos.' });
  const list = await request('/sisc-cifras/publications/public?limit=100', options);
  if (!list.ok) return list;
  const publications = await list.json();
  const range = run.resumen?.snapshot?.coverage;
  const baseline = publications.find((p: {source_codes?: string[]; period_start: string; period_end: string}) =>
    p.source_codes?.includes('POLICIA_SEMANAL') && range?.min_date <= p.period_start && range?.max_date >= p.period_end);
  if (!baseline) return json({ note: 'No hay un boletín previo dentro del rango de esta entrega para comparar. No se presume ausencia de cambios.' });
  const response = await request('/sisc-cifras/reconcile', { signal: options.signal, method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ publication_id: baseline.id, new_source_version_id: id }) });
  if (!response.ok) return response;
  const result = await response.json();
  return json({ publication: baseline.title, note: result.nota_boletin || result.note || 'El antecedente no permite una conciliación reproducible.',
    caveat: 'La comparación describe cambios en la entrega; no supone que un registro ausente haya sido eliminado.' });
}

export async function bulletinFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const aliases: Record<string, string> = {
    '/api/official-indicator': '/sisc-cifras/indicator',
    '/api/central-history': '/sisc-cifras/publications/public',
    '/api/central-reconcile': '/sisc-cifras/reconcile',
    '/api/generator/ingestion/preflight': '/ingesta/policia/preflight',
    '/api/generator/ingestion/upload': '/ingesta/gate/POLICIA_SEMANAL',
  };
  if (aliases[url]) return request(aliases[url], options);
  if (url === '/api/generator/session' && (!options.method || options.method === 'GET')) {
    const response = await request('/auth/me', options);
    if (!response.ok) return response;
    return json({ ...await response.json(), authenticated: true });
  }
  if (url.startsWith('/api/generator/summary/')) return summary(url.split('/').pop()!, options);
  if (url.startsWith('/api/generator/ingestion/')) return request(`/ingesta/runs/${encodeURIComponent(url.split('/').pop()!)}`, options);
  if (url === '/api/sisc-publication') {
    if (options.method !== 'POST') return request('/sisc-cifras/publications/public', options);
    const body = JSON.parse(String(options.body));
    return request('/sisc-cifras/generate', { ...options, body: JSON.stringify({
      edition_type: body.edition_type, period_start: body.period_start, period_end: body.period_end,
      comparison_mode: body.comparison_mode || 'auto', source_codes: ['POLICIA_SEMANAL', 'INSPECCIONES_RNMC', 'COMISARIAS_FAMILIA'],
      max_insights: 6, save_history: Boolean(body.publish), publish_automatically: Boolean(body.publish),
      ...(body.source_version_id ? { source_version_id: body.source_version_id } : {}),
    }) });
  }
  if (url.startsWith('/api/piscc-sources?')) {
    return request('/sisc-cifras/piscc-sources?' + url.split('?')[1], options);
  }
  if (url === '/api/parse-pdf') {
    const file = (options.body as FormData)?.get('file');
    if (!(file instanceof File) || !file.size || file.size > 10 * 1024 * 1024) return json({ error: 'Seleccione un PDF no vacío de hasta 10 MB.' }, 422);
    const data = new Uint8Array(await file.arrayBuffer());
    if (new TextDecoder().decode(data.slice(0, 4)) !== '%PDF') return json({ error: 'El archivo no es un PDF válido.' }, 415);
    const { extractOperations } = await import('./pdfOperations');
    try { return json({ success: true, data: await extractOperations(data) }); }
    catch { return json({ error: 'No se pudo leer el PDF. Compruebe que contiene texto y no está protegido.' }, 422); }
  }
  return json({ error: 'Operación no disponible en el generador del SISC.' }, 404);
}
