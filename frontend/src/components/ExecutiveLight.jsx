import React, { useEffect, useMemo, useState } from 'react';
import { Download, Film, Loader2, Share2 } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';
import { buildLightSlides, LIGHT_SIZE, lightSlideSvg } from '../utils/executiveLight';

export async function svgToImage(svg) {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  try {
    const image = new Image();
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error('No se pudo preparar la lámina.'));
      image.src = url;
    });
    const canvas = document.createElement('canvas');
    canvas.width = LIGHT_SIZE.width; canvas.height = LIGHT_SIZE.height;
    canvas.getContext('2d').drawImage(image, 0, 0);
    return canvas;
  } finally { URL.revokeObjectURL(url); }
}

const canvasToPng = (canvas) => new Promise((resolve, reject) =>
  canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('No se pudo crear la imagen.'))), 'image/png'));

function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export default function ExecutiveLight({ publication, council, isCurrent, authHeaders, escudo, onPrepareTikTok }) {
  const [recurrence, setRecurrence] = useState(null);
  const [sat, setSat] = useState(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const get = (path) => fetch(`${API_BASE_URL}${path}`, { headers: authHeaders(), signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null)).catch(() => null);
    get('/council-commitments/recurrence').then((data) => { if (!controller.signal.aborted) setRecurrence(data); });
    get('/intelligence/sat-radar').then((data) => { if (!controller.signal.aborted) setSat(data); });
    return () => controller.abort();
  }, [authHeaders]);

  const deck = useMemo(() => buildLightSlides({ publication, council, recurrence, sat }), [publication, council, recurrence, sat]);
  const svgs = useMemo(() => deck.slides.map((slide, index) => lightSlideSvg(slide, index, { escudo, draft: deck.draft })), [deck, escudo]);
  const period = publication?.period?.end || 'borrador';
  const ready = isCurrent && !busy;

  const run = async (task) => {
    setBusy(true); setError(''); setStatus('');
    try { await task(); } catch (err) { if (err?.name !== 'AbortError') setError(err.message); } finally { setBusy(false); }
  };

  const imageFiles = async () => {
    const canvases = await Promise.all(svgs.map(svgToImage));
    const blobs = await Promise.all(canvases.map(canvasToPng));
    return blobs.map((blob, index) => new File([blob], `parte-ejecutivo-${period}-${index + 1}de3.png`, { type: 'image/png' }));
  };

  const share = () => run(async () => {
    const files = await imageFiles();
    if (navigator.canShare?.({ files })) {
      await navigator.share({ files, title: 'Parte ejecutivo SISC' });
      setStatus('Láminas enviadas a la aplicación elegida.');
    } else {
      files.forEach((file, index) => setTimeout(() => saveBlob(file, file.name), index * 400));
      setStatus('Se descargaron las 3 láminas. Adjúntelas juntas en WhatsApp, en orden 1, 2 y 3.');
    }
  });

  return (
    <section className="overflow-hidden rounded-lg border-2 border-[#281FD0] bg-white shadow-sm" aria-label="Parte ejecutivo rápido">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-6 py-5">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-[#281FD0]">Para directivos · uso interno</p>
          <h2 className="mt-1 text-2xl font-black text-slate-900">Versión rápida: 3 láminas</h2>
          <p className="mt-1 text-sm font-semibold text-slate-600">Cómo vamos, dónde y qué riesgo, y qué está pendiente. Se lee en el celular en 30 segundos. No publicar en la web.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={share} disabled={!ready} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-[#281FD0] px-4 text-xs font-black uppercase text-white hover:bg-[#1f18a8] disabled:opacity-40">
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Share2 size={16} />} Compartir / descargar láminas
          </button>
          {onPrepareTikTok && <button onClick={onPrepareTikTok} disabled={busy} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-[#FFE000] px-4 text-xs font-black uppercase text-slate-950 disabled:opacity-40">
            <Film size={16} /> Preparar TikTok ciudadano
          </button>}
        </div>
      </div>
      {deck.draft && (
        <p role="alert" className="bg-amber-50 px-6 py-3 text-sm font-bold text-amber-900">
          La revisión editorial de este periodo tiene bloqueos: las láminas salen marcadas como BORRADOR.
        </p>
      )}
      {!isCurrent && <p role="alert" className="bg-amber-50 px-6 py-3 text-sm font-bold text-amber-900">Cambió la selección. Genere de nuevo antes de compartir.</p>}
      {status && <p role="status" className="bg-emerald-50 px-6 py-3 text-sm font-bold text-emerald-900">{status}</p>}
      {error && <p role="alert" className="bg-red-50 px-6 py-3 text-sm font-bold text-red-800">{error}</p>}
      <div className="grid gap-4 bg-slate-50 p-5 sm:grid-cols-3">
        {svgs.map((svg, index) => (
          <figure key={deck.slides[index].key} className="space-y-2">
            <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`} alt={`Lámina ${index + 1}: ${deck.slides[index].title}`}
              className="w-full rounded-lg border border-slate-200 shadow-sm" />
            <figcaption className="flex items-center justify-between text-xs font-bold text-slate-600">
              {index + 1}. {deck.slides[index].title}
              <button disabled={!ready} onClick={() => run(async () => saveBlob(await canvasToPng(await svgToImage(svg)), `parte-ejecutivo-${period}-${index + 1}de3.png`))}
                className="inline-flex items-center gap-1 text-[#281FD0] hover:underline disabled:opacity-40" aria-label={`Descargar lámina ${index + 1}`}>
                <Download size={13} /> PNG
              </button>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
