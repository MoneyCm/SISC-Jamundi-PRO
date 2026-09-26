import React, { useEffect, useMemo, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';
import { buildExecutiveBrief, executiveBriefSvg, jpegPdf } from '../utils/executiveBrief';
import ExecutiveLight from './ExecutiveLight';

async function renderCanvas(svg) {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  try {
    const image = new Image();
    await new Promise((resolve, reject) => { image.onload = resolve; image.onerror = () => reject(new Error('No se pudo preparar la imagen.')); image.src = url; });
    const canvas = document.createElement('canvas'); canvas.width = 1080; canvas.height = 1600;
    canvas.getContext('2d').drawImage(image, 0, 0);
    return canvas;
  } finally { URL.revokeObjectURL(url); }
}

export default function ExecutiveBrief({ publication, isCurrent, authHeaders }) {
  const [followup, setFollowup] = useState(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [escudo, setEscudo] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setFollowup(null); setError('');
    fetch(`${API_BASE_URL}/sisc-cifras/executive-followup`, { headers: authHeaders(), signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'Se requiere acceso institucional para consultar los compromisos.' : 'No se pudo consultar el seguimiento institucional.');
        const data = await response.json();
        if (!controller.signal.aborted) setFollowup(data);
      }).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [publication, revision, authHeaders]);
  useEffect(() => {
    fetch('/assets/escudo-limpio.png').then(response => response.blob()).then(blob => new Promise(resolve => {
      const reader = new FileReader(); reader.onloadend = () => resolve(reader.result); reader.readAsDataURL(blob);
    })).then(setEscudo).catch(() => setEscudo(''));
  }, []);
  const brief = useMemo(() => followup ? buildExecutiveBrief(publication, followup) : null, [publication, followup]);
  const svg = useMemo(() => brief ? executiveBriefSvg(brief, escudo) : '', [brief, escudo]);
  const ready = Boolean(brief && isCurrent && !busy);

  const download = async (format) => {
    if (!ready) return;
    setBusy(true); setError('');
    try {
      const canvas = await renderCanvas(svg);
      let blob;
      if (format === 'pdf') {
        const bytes = Uint8Array.from(atob(canvas.toDataURL('image/jpeg', 0.95).split(',')[1]), c => c.charCodeAt(0));
        blob = jpegPdf(bytes, canvas.width, canvas.height);
      } else {
        blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      }
      if (!blob) throw new Error('No se pudo crear el archivo.');
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url;
      link.download = `parte-ejecutivo-sisc-${publication.period?.end || 'borrador'}.${format}`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return <section className="space-y-4" aria-label="Parte ejecutivo SISC">
    {followup && <ExecutiveLight publication={publication} council={followup.council} isCurrent={isCurrent} authHeaders={authHeaders} escudo={escudo} />}
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 bg-white px-6 py-5">
        <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#281FD0]">Redacción estadística automatizada</p>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-3xl font-black uppercase tracking-tight text-slate-900">SISC en cifras</h2><p className="mt-1 text-sm font-semibold text-slate-500">Parte ejecutivo · versión completa (una página)</p></div><span className="rounded-md bg-[#FFE000] px-3 py-2 text-[10px] font-black uppercase text-slate-950">Borrador institucional</span></div>
      </div>
      <div className="p-6">
      <p className="text-sm font-semibold text-slate-600">Una lectura para decidir y hacer seguimiento · {publication.period?.start} al {publication.period?.end}</p>
      <p className="mt-2 text-xs font-semibold text-slate-500">Para Secretaría de Seguridad, Alcaldía y equipo autorizado. El seguimiento refleja el estado actual de los expedientes, independiente del período de las cifras.</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button disabled={!ready} onClick={() => download('png')} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-[#281FD0] px-4 py-2 text-xs font-black uppercase text-white hover:bg-[#1f18a8] disabled:opacity-40"><Download size={17}/> Imagen para WhatsApp</button>
        <button disabled={!ready} onClick={() => download('pdf')} className="inline-flex min-h-11 items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase text-slate-700 hover:bg-slate-50 disabled:opacity-40"><Download size={17}/> Descargar PDF</button>
        <button disabled={busy} onClick={() => setRevision(v => v + 1)} className="inline-flex min-h-11 items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase text-slate-700 hover:bg-slate-50"><RefreshCw size={17}/> Actualizar seguimiento</button>
      </div>
      {busy && <p role="status" className="mt-3 text-sm">Preparando archivo…</p>}
      </div>
    </div>
    {!isCurrent && <p role="alert" className="rounded-lg bg-amber-50 p-4 text-amber-900">Cambió la selección. Genera el parte de nuevo antes de descargarlo.</p>}
    {error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-red-800">{error} Usa «Actualizar seguimiento» para reintentar.</p>}
    {!followup && !error && <p role="status">Consultando decisiones y compromisos…</p>}
    {brief && <>
      <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`} alt="Vista previa del Parte ejecutivo SISC; contenido accesible a continuación" className="mx-auto hidden w-full max-w-[760px] rounded-xl border border-slate-200 shadow-sm sm:block"/>
      <details open className="rounded-xl bg-white p-5 text-slate-700">
        <summary className="cursor-pointer font-bold">Leer contenido y referencias</summary>
        <p className="mt-3">Cifras: {brief.period}. Comparación: {brief.comparison}.</p>
        {brief.sections.map(section => <section key={section.title} className="mt-5"><h3 className="font-bold">{section.title}</h3><ul className="mt-2 list-disc space-y-2 pl-5">{section.lines.map((line, i) => <li key={i}>{line}</li>)}</ul></section>)}
        <p className="mt-5 text-sm">{brief.sources}</p>
        <p className="mt-2 text-sm">Seguimiento consultado: {new Date(brief.checkedAt).toLocaleString('es-CO').replace(/\.$/, '')}. Los cambios observados no demuestran causalidad.</p>
      </details>
    </>}
  </section>;
}
