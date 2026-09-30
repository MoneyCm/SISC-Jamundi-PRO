import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Download, Play, Pause, Video } from 'lucide-react';
import { buildTikTokStory, drawTikTokFrame, recordTikTok, tikTokCandidates, tikTokScript, tikTokSubtitles, TIKTOK_SIZE } from '../utils/publicTikTok';

function save(content, name, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(content instanceof Blob ? content : new Blob([content], { type }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export default function PublicTikTok({ publication, isCurrent }) {
  const candidates = useMemo(() => tikTokCandidates(publication), [publication]);
  const [selected, setSelected] = useState('');
  const story = useMemo(() => buildTikTokStory(publication, candidates.some((item) => item.id === selected) ? selected : undefined), [publication, candidates, selected]);
  const [seconds, setSeconds] = useState(0.6);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const canvas = useRef(null);
  const controller = useRef(null);
  const ready = Boolean(story && isCurrent && progress === null);
  useEffect(() => {
    setPlaying(false); setSeconds(0.6); setMessage(''); setError('');
    return () => controller.current?.abort();
  }, [story, isCurrent]);
  useEffect(() => {
    if (story && canvas.current) drawTikTokFrame(canvas.current.getContext('2d'), story, seconds);
  }, [story, seconds, isCurrent]);
  useEffect(() => {
    if (!playing || !story) return undefined;
    let frame;
    const start = performance.now() - seconds * 1000;
    const tick = () => {
      const current = Math.min(story.duration, (performance.now() - start) / 1000);
      setSeconds(current);
      if (current < story.duration) frame = requestAnimationFrame(tick);
      else setPlaying(false);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // Capture the starting position once when playback starts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, story]);

  const download = async () => {
    if (!ready) return;
    setPlaying(false); setProgress(0); setError(''); setMessage('');
    const current = new AbortController(); controller.current = current;
    try {
      const { blob, extension } = await recordTikTok(story, setProgress, current.signal);
      if (current.signal.aborted) return;
      save(blob, `sisc-tiktok-${publication.period.end}.${extension}`);
      setMessage(extension === 'mp4' ? 'Video MP4 descargado sin voz. Añada la narración con el guion antes de publicarlo.' : 'Video WebM descargado sin voz. Conviértalo a MP4 si su editor no lo admite; añada la narración con el guion.');
    } catch (err) { if (err.name !== 'AbortError') setError(err.message); }
    finally { setProgress(null); }
  };

  return <section id="sisc-tiktok" className="rounded-xl border border-indigo-200 bg-white p-5" aria-label="TikTok ciudadano">
    <div className="flex items-center gap-2"><Video size={20} className="text-indigo-700"/><h2 className="text-lg font-black text-slate-900">TikTok ciudadano</h2></div>
    <p className="mt-2 text-sm text-slate-600">Un dato público explicado en 30 segundos. Video vertical 9:16 con texto en pantalla y guion para añadir la voz en TikTok.</p>
    {!isCurrent ? <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Actualice las cifras antes de preparar esta pieza.</p>
      : !story ? <p className="mt-4 rounded-lg bg-slate-100 p-3 text-sm text-slate-700">Use una edición aprobada y publicada con indicadores públicos del periodo y fuente identificada. Puede seleccionarla en «Último boletín publicado».</p>
      : <>
        <label className="mt-4 block text-sm font-bold text-slate-700">Dato para explicar
          <select value={candidates.some((item) => item.id === selected) ? selected : candidates[0]?.id || ''} disabled={progress !== null} onChange={(event) => setSelected(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3 font-normal">
            {candidates.map((item) => <option key={item.id} value={item.id}>{item.indicator_name}</option>)}
          </select>
        </label>
        <div className="mt-5 grid gap-5 md:grid-cols-[240px_minmax(0,1fr)]">
          <div className="mx-auto w-full max-w-[280px]">
            <canvas ref={canvas} width={TIKTOK_SIZE.width} height={TIKTOK_SIZE.height} role="img" aria-label={`Vista previa de TikTok: ${story.title}. Guion disponible a continuación.`} className="aspect-[9/16] w-full rounded-xl bg-[#131044]"/>
            <div className="mt-3 flex items-center gap-3">
              <button disabled={!ready} onClick={() => { if (seconds >= story.duration) setSeconds(0); setPlaying(!playing); }} aria-label={playing ? 'Pausar vista previa' : 'Reproducir vista previa'} className="rounded-lg bg-indigo-700 p-2 text-white disabled:opacity-40">{playing ? <Pause size={18}/> : <Play size={18}/>}</button>
              <input aria-label="Posición del video" type="range" min="0" max={story.duration} step="0.1" value={seconds} disabled={!ready} onChange={(event) => { setPlaying(false); setSeconds(Number(event.target.value)); }} className="min-w-0 flex-1"/>
              <span className="text-xs tabular-nums text-slate-600">{Math.floor(seconds)} / 30 s</span>
            </div>
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-800">Guion de narración</h3>
            <ol className="mt-3 space-y-3">{story.scenes.map((scene) => <li key={scene.kind} className="border-l-2 border-indigo-200 pl-3"><span className="text-xs font-bold text-indigo-700">{scene.start}–{scene.end} s · {scene.heading}</span><p className="mt-1 text-sm leading-6 text-slate-700">{scene.narration}</p></li>)}</ol>
            <p className="mt-4 text-xs leading-5 text-slate-500">Fuente: {story.source}. Corte: {story.cutoff}. Periodo: {story.period}.{story.comparison && ` Comparación: ${story.comparison}.`}</p>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <button onClick={download} disabled={!ready} className="inline-flex items-center gap-2 rounded-lg bg-indigo-700 px-4 py-3 text-sm font-bold text-white disabled:opacity-40"><Download size={16}/>{progress === null ? 'Descargar video sin voz' : `Preparando ${progress} %`}</button>
          <button disabled={!ready} onClick={() => save(tikTokScript(story), `sisc-tiktok-${publication.period.end}-guion.txt`)} className="rounded-lg border px-4 py-3 text-sm font-bold disabled:opacity-40">Guion TXT</button>
          <button disabled={!ready} onClick={() => save(tikTokSubtitles(story), `sisc-tiktok-${publication.period.end}.srt`)} className="rounded-lg border px-4 py-3 text-sm font-bold disabled:opacity-40">Subtítulos SRT</button>
        </div>
      </>}
    {progress !== null && <p role="status" className="mt-3 text-sm text-indigo-700">Mantenga esta pestaña visible durante los 30 segundos de exportación. <button onClick={() => controller.current?.abort()} className="font-bold underline">Cancelar</button></p>}
    {message && <p role="status" className="mt-3 text-sm text-emerald-800">{message}</p>}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
  </section>;
}
