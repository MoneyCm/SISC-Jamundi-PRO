import React, { useEffect, useRef, useState } from 'react';
import { Copy, Loader2, Mic, Printer, Send, ShieldCheck, Sparkles, Volume2, X } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

// Asesor SISC: preguntas de la dirección con cifras oficiales verificadas (backend: /api/asistente).
const ROLES = ['DIRECTIVE', 'ANALYST', 'FUNC_ADMIN', 'TI_ADMIN', 'DATA_OWNER'];
const CLAVE = 'sisc_asesor_conversacion';
const INICIALES = [
    '¿Cómo vamos esta semana?',
    '¿Qué le pido a la Policía en el próximo Consejo?',
    '¿Qué barrio me debe preocupar más?',
    '¿Cómo va el PISCC?',
    '¿Cómo va la convivencia este año?',
    'Resúmame la semana para WhatsApp',
];

const leerGuardado = () => {
    try { return JSON.parse(sessionStorage.getItem(CLAVE) || '[]'); } catch { return []; }
};

const textoCompartible = (mensaje) => `${mensaje.texto}\n\nFuente: ${(mensaje.fuentes || []).join('; ')}. SISC Jamundí.`;

const imprimir = (pregunta, mensaje, nombre) => {
    const ventana = window.open('', '_blank', 'width=800,height=900');
    if (!ventana) return;
    const escapar = (t) => String(t || '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
    ventana.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Asesor SISC</title>
        <style>body{font-family:Arial,sans-serif;max-width:680px;margin:40px auto;color:#1f2937;line-height:1.55}
        h1{color:#281FD0;font-size:20px;margin:0}p.meta{color:#6b7280;font-size:12px}
        .q{font-weight:bold;margin-top:24px}.a{white-space:pre-wrap;font-size:15px}.f{color:#6b7280;font-size:12px;margin-top:18px;border-top:1px solid #e5e7eb;padding-top:8px}</style>
        </head><body><h1>Asesor SISC · Secretaría de Seguridad y Convivencia de Jamundí</h1>
        <p class="meta">Consulta de ${escapar(nombre)} · ${new Date().toLocaleString('es-CO')}</p>
        <p class="q">${escapar(pregunta)}</p><div class="a">${escapar(mensaje.texto)}</div>
        <p class="f">Fuentes: ${escapar((mensaje.fuentes || []).join('; '))}. Cifras verificadas por el SISC. Documento de uso interno.</p>
        <script>window.onload=()=>window.print()</script></body></html>`);
    ventana.document.close();
};

const Burbuja = ({ mensaje, pregunta, nombre, onSugerencia }) => {
    const [copiado, setCopiado] = useState(false);
    const [hablando, setHablando] = useState(false);
    if (mensaje.rol === 'usuario') {
        return <div className="ml-10 self-end rounded-2xl rounded-br-sm bg-[#281FD0] px-4 py-2.5 text-[15px] text-white">{mensaje.texto}</div>;
    }
    const copiar = async () => {
        try { await navigator.clipboard.writeText(textoCompartible(mensaje)); } catch { /* sin portapapeles */ }
        setCopiado(true); setTimeout(() => setCopiado(false), 1800);
    };
    const escuchar = () => {
        if (!('speechSynthesis' in window)) return;
        if (hablando) { window.speechSynthesis.cancel(); setHablando(false); return; }
        const voz = new SpeechSynthesisUtterance(mensaje.texto.replace(/[•]/g, ''));
        voz.lang = 'es-CO'; voz.rate = 0.95;
        voz.onend = () => setHablando(false);
        window.speechSynthesis.cancel(); window.speechSynthesis.speak(voz); setHablando(true);
    };
    const boton = 'inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-bold text-slate-600 hover:border-[#281FD0] hover:text-[#281FD0]';
    return (
        <div className="mr-4 self-start">
            <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-[15px] leading-relaxed text-slate-800 shadow-sm">
                <p className="whitespace-pre-wrap">{mensaje.texto}</p>
                {mensaje.fuentes?.length > 0 && (
                    <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
                        <ShieldCheck size={12} className="-mt-0.5 mr-1 inline text-emerald-600" />
                        Cifras verificadas · {mensaje.fuentes.join(' · ')}
                    </p>
                )}
            </div>
            {!mensaje.bienvenida && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {'speechSynthesis' in window && <button type="button" onClick={escuchar} className={boton}><Volume2 size={13} />{hablando ? 'Detener' : 'Escuchar'}</button>}
                    <button type="button" onClick={copiar} className={boton}><Copy size={13} />{copiado ? '¡Copiado!' : 'Copiar'}</button>
                    <a className={boton} href={`https://wa.me/?text=${encodeURIComponent(textoCompartible(mensaje))}`} target="_blank" rel="noopener noreferrer">WhatsApp</a>
                    <button type="button" onClick={() => imprimir(pregunta, mensaje, nombre)} className={boton}><Printer size={13} />Imprimir</button>
                </div>
            )}
            {mensaje.sugerencias?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                    {mensaje.sugerencias.map((s) => (
                        <button key={s} type="button" onClick={() => onSugerencia(s)} className="rounded-full bg-indigo-50 px-3 py-1.5 text-left text-xs font-bold text-[#281FD0] hover:bg-indigo-100">{s}</button>
                    ))}
                </div>
            )}
        </div>
    );
};

const AsesorSISC = ({ userRoles = [], currentUser }) => {
    const [abierto, setAbierto] = useState(false);
    const [mensajes, setMensajes] = useState(leerGuardado);
    const [texto, setTexto] = useState('');
    const [ocupado, setOcupado] = useState(false);
    const [escuchando, setEscuchando] = useState(false);
    const fondo = useRef(null);
    const nombre = (currentUser?.full_name || currentUser?.username || '').split(' ')[0];
    const Reconocimiento = typeof window !== 'undefined' && window.isSecureContext && (window.SpeechRecognition || window.webkitSpeechRecognition);

    useEffect(() => { try { sessionStorage.setItem(CLAVE, JSON.stringify(mensajes.slice(-20))); } catch { /* sin almacenamiento */ } }, [mensajes]);
    useEffect(() => { fondo.current?.scrollIntoView({ behavior: 'smooth' }); }, [mensajes, ocupado, abierto]);

    if (!userRoles.some((rol) => ROLES.includes(rol))) return null;

    const preguntar = async (pregunta) => {
        const limpia = (pregunta || '').trim();
        if (!limpia || ocupado) return;
        const historial = mensajes.filter((m) => !m.bienvenida).slice(-6).map((m) => ({ rol: m.rol, texto: m.texto }));
        setMensajes((actual) => [...actual, { rol: 'usuario', texto: limpia }]);
        setTexto(''); setOcupado(true);
        try {
            const r = await apiJson('/asistente/preguntar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pregunta: limpia, historial }) });
            setMensajes((actual) => [...actual, { rol: 'asesor', texto: r.respuesta, fuentes: r.fuentes, sugerencias: r.sugerencias, pregunta: limpia }]);
        } catch (error) {
            setMensajes((actual) => [...actual, { rol: 'asesor', texto: `No pude responder en este momento (${error.message || 'sin conexión'}). Intente de nuevo en un momento.`, pregunta: limpia }]);
        } finally {
            setOcupado(false);
        }
    };

    const dictar = () => {
        if (!Reconocimiento || escuchando) return;
        const rec = new Reconocimiento();
        rec.lang = 'es-CO'; rec.interimResults = false;
        rec.onresult = (e) => { const dicho = e.results[0][0].transcript; setTexto(dicho); preguntar(dicho); };
        rec.onend = () => setEscuchando(false);
        rec.onerror = () => setEscuchando(false);
        setEscuchando(true); rec.start();
    };

    const bienvenida = { rol: 'asesor', bienvenida: true,
        texto: `Hola${nombre ? `, ${nombre}` : ''}. Soy el Asesor SISC. Pregúnteme lo que necesite sobre la seguridad de Jamundí: le respondo con las cifras oficiales del sistema, y cada número va verificado.`,
        sugerencias: INICIALES };
    const visibles = mensajes.length ? mensajes : [bienvenida];

    return (
        <>
            {!abierto && (
                <button type="button" onClick={() => setAbierto(true)} aria-label="Abrir el Asesor SISC"
                    className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-[#281FD0] px-5 py-3.5 text-sm font-black text-white shadow-xl shadow-indigo-900/30 hover:bg-[#3026D9] print:hidden">
                    <Sparkles size={18} /> Pregúntele al SISC
                </button>
            )}
            {abierto && (
                <section role="dialog" aria-label="Asesor SISC"
                    className="fixed inset-0 z-50 flex flex-col bg-slate-50 sm:inset-auto sm:bottom-5 sm:right-5 sm:h-[640px] sm:max-h-[calc(100vh-40px)] sm:w-[420px] sm:rounded-2xl sm:border sm:border-slate-200 sm:shadow-2xl print:hidden">
                    <header className="flex items-center justify-between rounded-t-2xl bg-[#281FD0] px-4 py-3 text-white">
                        <div className="flex items-center gap-2">
                            <Sparkles size={18} />
                            <div><p className="text-sm font-black">Asesor SISC</p><p className="text-[11px] text-indigo-100">Cifras oficiales verificadas</p></div>
                        </div>
                        <div className="flex items-center gap-1">
                            {mensajes.length > 0 && <button type="button" onClick={() => setMensajes([])} className="rounded-lg px-2 py-1 text-xs font-bold text-indigo-100 hover:bg-white/10">Nueva consulta</button>}
                            <button type="button" onClick={() => { window.speechSynthesis?.cancel(); setAbierto(false); }} aria-label="Cerrar" className="rounded-lg p-1.5 hover:bg-white/10"><X size={18} /></button>
                        </div>
                    </header>
                    <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-3 py-4">
                        {visibles.map((m, i) => (
                            <Burbuja key={i} mensaje={m} pregunta={m.pregunta} nombre={currentUser?.full_name || currentUser?.username} onSugerencia={preguntar} />
                        ))}
                        {ocupado && <div className="mr-4 inline-flex items-center gap-2 self-start rounded-2xl bg-white px-4 py-3 text-sm text-slate-500 shadow-sm"><Loader2 size={16} className="animate-spin" /> Revisando las cifras del SISC…</div>}
                        <div ref={fondo} />
                    </div>
                    <form onSubmit={(e) => { e.preventDefault(); preguntar(texto); }} className="flex items-end gap-2 border-t border-slate-200 bg-white p-3 sm:rounded-b-2xl">
                        <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={1} maxLength={500}
                            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); preguntar(texto); } }}
                            placeholder="Escriba su pregunta…" className="max-h-28 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2.5 text-[15px] focus:border-[#281FD0] focus:outline-none" />
                        {Reconocimiento && (
                            <button type="button" onClick={dictar} aria-label="Dictar la pregunta" className={`rounded-xl p-3 ${escuchando ? 'bg-red-500 text-white' : 'bg-slate-100 text-slate-600'}`}><Mic size={18} /></button>
                        )}
                        <button type="submit" disabled={ocupado || !texto.trim()} aria-label="Enviar" className="rounded-xl bg-[#281FD0] p-3 text-white disabled:opacity-40"><Send size={18} /></button>
                    </form>
                </section>
            )}
        </>
    );
};

export default AsesorSISC;
