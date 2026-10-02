import React, { useState } from 'react';
import { CalendarX, Check, Copy, Loader2, Send, X } from 'lucide-react';
import { apiFetch, readApiError } from '../utils/apiClient';
import { fechaActa, mensajePedido, periodoLegible, resumenPedidas } from '../utils/archivoActas';

// Cuántos periodos sin acta se muestran al comienzo (los más recientes); el resto se ve con «Ver todas».
const MAX_FALTANTES = 12;

const hoyIso = () => {
    const ahora = new Date();
    return new Date(ahora.getTime() - ahora.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

const estiloChip = (solicitud, elegido) => {
    if (elegido) return 'border-[#281FD0] bg-[#281FD0] text-white';
    if (!solicitud) return 'border-red-200 bg-white text-red-800 hover:border-red-400';
    return solicitud.vencida ? 'border-red-500 bg-red-100 text-red-900 hover:border-red-700' : 'border-amber-300 bg-amber-50 text-amber-900 hover:border-amber-500';
};

// Una reunión con actas que faltan: se eligen las actas, se anota a quién y cuándo se pidieron, y se copia el mensaje.
const ActasFaltantes = ({ reunion, onCambio }) => {
    const [elegidas, setElegidas] = useState([]);
    const [verTodas, setVerTodas] = useState(false);
    const [fecha, setFecha] = useState(hoyIso());
    const [destinatario, setDestinatario] = useState(reunion.responsables || '');
    const [nota, setNota] = useState('');
    const [guardando, setGuardando] = useState(false);
    const [mensaje, setMensaje] = useState('');

    const unidad = reunion.frecuencia === 'semanal' ? ['semana', 'semanas'] : ['mes', 'meses'];
    const solicitudes = reunion.solicitudes || {};
    const { pedidas, vencidas } = resumenPedidas(reunion);
    const todas = [...reunion.faltan, ...reunion.sin_acta_oficial].sort();
    const visibles = verTodas ? reunion.faltan : reunion.faltan.slice(-MAX_FALTANTES);
    const algunaPedida = elegidas.some((p) => solicitudes[p]);

    const alternar = (periodo) => setElegidas((actual) => (actual.includes(periodo) ? actual.filter((p) => p !== periodo) : [...actual, periodo]));

    const enviar = async (ruta, cuerpo, exito) => {
        setGuardando(true);
        setMensaje('');
        try {
            const response = await apiFetch(`/council-commitments/acts/${ruta}`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo),
            });
            if (!response.ok) throw new Error(await readApiError(response));
            setMensaje(exito);
            setElegidas([]);
            await onCambio?.();
        } catch (requestError) {
            setMensaje(requestError.message);
        } finally {
            setGuardando(false);
        }
    };

    const marcarPedidas = () => enviar('requests', {
        instance: reunion.instance, periodos: elegidas, requested_on: fecha, requested_to: destinatario.trim(), note: nota.trim() || null,
    }, `${elegidas.length === 1 ? 'Quedó anotada 1 acta pedida' : `Quedaron anotadas ${elegidas.length} actas pedidas`} a ${destinatario.trim()}.`);

    const quitarMarca = () => enviar('requests/remove', { instance: reunion.instance, periodos: elegidas.filter((p) => solicitudes[p]) },
        'Se quitó la marca de pedida.');

    const copiarMensaje = async () => {
        try {
            await navigator.clipboard.writeText(mensajePedido(reunion, elegidas, destinatario.trim()));
            setMensaje('Mensaje copiado: péguelo en el correo o en WhatsApp.');
        } catch {
            setMensaje('No se pudo copiar el mensaje en este navegador.');
        }
    };

    const chip = (periodo) => {
        const solicitud = solicitudes[periodo];
        const elegido = elegidas.includes(periodo);
        const detalle = solicitud ? `Pedida el ${fechaActa(solicitud.pedida_el)} a ${solicitud.pedida_a}${solicitud.veces > 1 ? ` (${solicitud.veces} veces)` : ''}${solicitud.nota ? `. ${solicitud.nota}` : ''}` : 'Sin pedir';
        return (
            <button type="button" key={periodo} onClick={() => alternar(periodo)} aria-pressed={elegido} title={detalle}
                className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-bold ${estiloChip(solicitud, elegido)}`}>
                {elegido && <Check size={12} />}
                {periodoLegible(periodo, reunion.frecuencia)}
                {solicitud && <span className="font-semibold opacity-80">· pedida hace {solicitud.dias} {solicitud.dias === 1 ? 'día' : 'días'}</span>}
            </button>
        );
    };

    return (
        <section className="border-l-4 border-red-400 bg-red-50 p-4" aria-label={`Actas que faltan: ${reunion.instance_label}`}>
            <h2 className="flex items-center gap-2 text-base font-black text-red-900"><CalendarX size={18} /> Actas que faltan del {reunion.instance_label}</h2>
            <p className="mt-1 text-sm font-semibold text-red-900/80">
                Se reúne cada {unidad[0]}; última acta: {fechaActa(reunion.ultima)}.{' '}
                {reunion.responsables ? <>Pedirlas a: <strong>{reunion.responsables}</strong>.</> : <>Falta definir a quién se le piden.</>}
            </p>
            {pedidas > 0 && (
                <p className="mt-1 text-sm font-bold text-red-900">
                    {pedidas} {pedidas === 1 ? 'pedida' : 'pedidas'} sin llegar{vencidas > 0 && <>; <span className="text-red-700">{vencidas} hace más de {reunion.dias_plazo} días</span></>}.
                </p>
            )}

            {reunion.faltan.length > 0 && (
                <>
                    <p className="mt-2 text-xs font-black uppercase text-red-900">{reunion.faltan.length} {reunion.faltan.length === 1 ? unidad[0] : unidad[1]} sin acta</p>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                        {visibles.map(chip)}
                        {reunion.faltan.length > MAX_FALTANTES && (
                            <button type="button" onClick={() => setVerTodas(!verTodas)} className="px-1 text-xs font-black text-red-900 underline">
                                {verTodas ? 'Ver solo las recientes' : `Ver las ${reunion.faltan.length - MAX_FALTANTES} anteriores`}
                            </button>
                        )}
                    </div>
                </>
            )}
            {reunion.sin_acta_oficial.length > 0 && (
                <>
                    <p className="mt-2 text-xs font-black uppercase text-red-900">Solo hay una nota, falta el acta oficial</p>
                    <div className="mt-1 flex flex-wrap gap-1.5">{reunion.sin_acta_oficial.map(chip)}</div>
                </>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs font-bold text-red-900">
                <span>Toque las actas para elegirlas.</span>
                <button type="button" onClick={() => setElegidas(todas.filter((p) => !solicitudes[p]))} className="underline">Elegir las que no se han pedido</button>
                <button type="button" onClick={() => setElegidas(todas)} className="underline">Elegir todas ({todas.length})</button>
                {elegidas.length > 0 && <button type="button" onClick={() => setElegidas([])} className="underline">Ninguna</button>}
            </div>

            {elegidas.length > 0 && (
                <div className="mt-3 space-y-3 border border-red-200 bg-white p-3">
                    <p className="text-sm font-black text-slate-900">{elegidas.length} {elegidas.length === 1 ? 'acta elegida' : 'actas elegidas'}</p>
                    <div className="flex flex-wrap gap-3">
                        <label className="text-xs font-black uppercase text-slate-500">Se pidieron el
                            <input type="date" value={fecha} max={hoyIso()} onChange={(e) => setFecha(e.target.value)} className="mt-1 block min-h-10 border border-slate-300 px-2 text-sm font-bold text-slate-800" />
                        </label>
                        <label className="text-xs font-black uppercase text-slate-500">A quién
                            <input type="text" value={destinatario} maxLength={200} onChange={(e) => setDestinatario(e.target.value)} className="mt-1 block min-h-10 w-56 border border-slate-300 px-2 text-sm font-bold text-slate-800" />
                        </label>
                        <label className="min-w-[14rem] flex-1 text-xs font-black uppercase text-slate-500">Nota (opcional)
                            <input type="text" value={nota} maxLength={1000} placeholder="Por ejemplo: por correo, por WhatsApp" onChange={(e) => setNota(e.target.value)} className="mt-1 block min-h-10 w-full border border-slate-300 px-2 text-sm font-semibold text-slate-800" />
                        </label>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={copiarMensaje} className="inline-flex min-h-10 items-center gap-1.5 border border-slate-300 px-3 text-sm font-black text-slate-700 hover:bg-slate-50">
                            <Copy size={15} /> Copiar mensaje para pedirlas
                        </button>
                        <button type="button" disabled={guardando || destinatario.trim().length < 2 || !fecha} onClick={marcarPedidas}
                            className="inline-flex min-h-10 items-center gap-1.5 bg-[#281FD0] px-3 text-sm font-black text-white hover:bg-[#1F18A8] disabled:opacity-40">
                            {guardando ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Anotar como pedidas
                        </button>
                        {algunaPedida && (
                            <button type="button" disabled={guardando} onClick={quitarMarca} className="inline-flex min-h-10 items-center gap-1.5 border border-slate-300 px-3 text-sm font-black text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                                <X size={15} /> Quitar la marca de pedida
                            </button>
                        )}
                    </div>
                </div>
            )}
            {mensaje && <p role="status" className="mt-2 text-sm font-bold text-indigo-950">{mensaje}</p>}
        </section>
    );
};

export default ActasFaltantes;
