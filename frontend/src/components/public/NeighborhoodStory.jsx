import React, { useMemo, useState } from 'react';
import { CalendarDays, Info, LifeBuoy, MessageCircle, Phone, ShieldCheck } from 'lucide-react';
import { formatNumber } from '../../utils/citizenInsights';

const WEEKDAYS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
const WEEKDAY_SHORT = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
// Con pocos registros un "patrón" por día es azar: no se muestra.
const MIN_CASES_FOR_WEEKDAY = 15;

// Recomendaciones generales de autocuidado por conducta (no dependen del territorio).
const ADVICE = {
    HURTO_PERSONAS: [
        'Evita exhibir el celular en la calle, paraderos y semáforos.',
        'Prefiere vías iluminadas y concurridas, sobre todo al caminar de noche.',
        'Si te roban, no opongas resistencia: tu vida vale más. Luego denuncia.',
    ],
    HURTO_VEHICULOS: [
        'Usa parqueaderos vigilados y un bloqueo adicional (candado de disco o cadena).',
        'No dejes documentos ni llaves de repuesto dentro del vehículo.',
        'Si te roban el vehículo, denuncia de inmediato: las primeras horas son clave.',
    ],
    LESIONES: [
        'Ante una riña, aléjate y llama al 123; no intervengas directamente.',
        'Los conflictos entre vecinos se pueden resolver con mediación en la Inspección de Policía.',
    ],
    HOMICIDIO: [
        'Si conoces amenazas o riesgos contra alguien, repórtalo al 123 o por el canal de reporte seguro.',
    ],
    HURTO_RESIDENCIAS: [
        'Refuerza cerraduras y conoce a tus vecinos: una red de vecinos atenta previene.',
        'No publiques en redes cuándo tu casa quedará sola.',
    ],
    HURTO_COMERCIO: [
        'Evita manejar efectivo en exceso y usa medios de pago digitales cuando sea posible.',
        'Coordínate con comercios vecinos y con el cuadrante de Policía de tu sector.',
    ],
    VIF: [
        'Si vives violencia en tu hogar, no estás sola ni solo: la Comisaría de Familia puede darte protección.',
    ],
};

const CHANNELS = [
    { label: 'Emergencias', value: '123', href: 'tel:123', icon: Phone },
    { label: 'Orientación a mujeres víctimas de violencia', value: 'Línea 155', href: 'tel:155', icon: LifeBuoy },
    { label: 'Protección de niñas, niños y adolescentes (ICBF)', value: 'Línea 141', href: 'tel:141', icon: ShieldCheck },
];

const formatLongDate = (value) => (value
    ? new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(`${value}T12:00:00`))
    : '');

const joinWords = (items) => (items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} y ${items[items.length - 1]}`);

/** Relato en lenguaje claro de un territorio, calculado solo con cifras publicadas. */
export const buildNeighborhoodSentence = (name, profile) => {
    const kpis = profile?.kpis || {};
    const meta = profile?.metadata || {};
    const total = Number(kpis.total_hechos || 0);
    const parts = [
        `En ${name}, entre el ${formatLongDate(meta.period_start)} y el ${formatLongDate(meta.period_end)}, se registraron ${formatNumber(total)} ${total === 1 ? 'caso' : 'casos'}`,
    ];
    if (meta.comparison_start && kpis.previous_total !== undefined && kpis.previous_total !== null) {
        const previous = Number(kpis.previous_total);
        const difference = total - previous;
        const year = String(meta.comparison_end || '').slice(0, 4);
        parts[0] += difference === 0
            ? `, la misma cifra que en el mismo periodo de ${year}.`
            : `: ${formatNumber(Math.abs(difference))} ${difference > 0 ? 'más' : 'menos'} que en el mismo periodo de ${year} (${formatNumber(previous)}).`;
    } else {
        parts[0] += '.';
    }
    const top = profile?.conductas?.[0];
    if (top && Number(top.value) > 0) {
        parts.push(`Lo más registrado fue ${String(top.name).toLowerCase()} (${formatNumber(top.value)}).`);
    }
    return parts.join(' ');
};

const NeighborhoodStory = ({ name, profile, municipalTotal, shareUrl, onNavigate }) => {
    const [copied, setCopied] = useState('');
    const sentence = useMemo(() => buildNeighborhoodSentence(name, profile), [name, profile]);
    const total = Number(profile?.kpis?.total_hechos || 0);
    const share = municipalTotal ? (total / municipalTotal) * 100 : null;

    const weekday = profile?.weekday || [];
    const weekdayMax = Math.max(0, ...weekday.map((item) => Number(item.total || 0)));
    const showWeekday = total >= MIN_CASES_FOR_WEEKDAY && weekdayMax > 0;
    const topDays = showWeekday
        ? weekday.filter((item) => Number(item.total) === weekdayMax).map((item) => WEEKDAYS[item.day - 1])
        : [];

    const topCodes = (profile?.conductas || []).slice(0, 2).map((item) => item.code).filter((code) => ADVICE[code]);
    const advice = [...new Set(topCodes.flatMap((code) => ADVICE[code]))].slice(0, 4);

    const shareText = `${sentence} Fuente: SISC Jamundí (datos agregados, sin información personal). ${shareUrl || ''}`.trim();
    const shareWhatsApp = () => {
        window.open(`https://wa.me/?text=${encodeURIComponent(shareText)}`, '_blank', 'noopener,noreferrer');
    };
    const copySummary = async () => {
        try {
            await navigator.clipboard.writeText(shareText);
            setCopied('Resumen copiado.');
        } catch {
            setCopied('No fue posible copiar el resumen.');
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <p className="text-xs font-black uppercase tracking-wide text-[#281FD0]">Tu territorio en claro</p>
                <p className="mt-2 text-lg font-bold leading-8 text-slate-900 md:text-xl">{sentence}</p>
                {share !== null && share > 0 && (
                    <p className="mt-2 text-sm font-semibold text-slate-600">
                        Equivale al {share.toLocaleString('es-CO', { maximumFractionDigits: 1 })} % de los casos registrados en Jamundí en el mismo periodo.
                    </p>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                    <button onClick={shareWhatsApp} className="inline-flex min-h-11 items-center gap-2 bg-[#128C4A] px-4 text-sm font-black text-white hover:bg-[#0e733c]">
                        <MessageCircle size={17} /> Compartir por WhatsApp
                    </button>
                    <button onClick={copySummary} className="inline-flex min-h-11 items-center gap-2 border border-slate-300 px-4 text-sm font-black text-slate-700 hover:bg-slate-50">
                        Copiar resumen
                    </button>
                </div>
                {copied && <p className="mt-2 text-xs font-bold text-slate-500" role="status">{copied}</p>}
            </div>

            <div className="border-t border-slate-200 pt-5">
                <p className="flex items-center gap-2 text-xs font-black uppercase tracking-wide text-slate-500"><CalendarDays size={15} /> Días con más registros</p>
                {showWeekday ? (
                    <>
                        <div className="mt-3 grid grid-cols-7 items-end gap-1.5" style={{ height: 88 }} aria-hidden="true">
                            {weekday.map((item) => {
                                const height = Math.max(6, (Number(item.total) / weekdayMax) * 72);
                                const peak = Number(item.total) === weekdayMax;
                                return (
                                    <div key={item.day} className="flex h-full flex-col items-center justify-end gap-1">
                                        <div className={peak ? 'w-full bg-[#281FD0]' : 'w-full bg-slate-300'} style={{ height }} />
                                        <span className={`text-[10px] font-black ${peak ? 'text-[#281FD0]' : 'text-slate-500'}`}>{WEEKDAY_SHORT[item.day - 1]}</span>
                                    </div>
                                );
                            })}
                        </div>
                        <p className="mt-3 text-sm font-semibold text-slate-700">
                            Los registros se concentran el {joinWords(topDays)}. Es un patrón del periodo consultado, no una predicción.
                        </p>
                    </>
                ) : (
                    <p className="mt-2 text-sm font-semibold text-slate-500">Hay muy pocos registros para identificar un patrón por día sin exponer casos individuales.</p>
                )}
            </div>

            {(advice.length > 0 || CHANNELS.length > 0) && (
                <div className="border-t border-slate-200 pt-5">
                    <p className="text-xs font-black uppercase tracking-wide text-slate-500">¿Qué puedes hacer?</p>
                    {advice.length > 0 && (
                        <ul className="mt-3 space-y-2">
                            {advice.map((item) => (
                                <li key={item} className="flex gap-2 text-sm font-semibold leading-6 text-slate-700"><span className="mt-2 h-1.5 w-1.5 shrink-0 bg-[#FFB600]" />{item}</li>
                            ))}
                        </ul>
                    )}
                    <div className="mt-4 grid gap-2 sm:grid-cols-3">
                        {CHANNELS.map(({ label, value, href, icon: Icon }) => (
                            <a key={value} href={href} className="flex items-start gap-2 border border-slate-200 p-3 hover:border-[#281FD0]">
                                <Icon size={16} className="mt-0.5 shrink-0 text-[#281FD0]" />
                                <span><span className="block text-sm font-black text-slate-900">{value}</span><span className="block text-[11px] font-semibold leading-4 text-slate-500">{label}</span></span>
                            </a>
                        ))}
                    </div>
                    <button onClick={() => onNavigate?.('reporting')} className="mt-3 text-sm font-black text-[#281FD0] underline underline-offset-4">
                        Reportar un riesgo de forma segura
                    </button>
                </div>
            )}

            <p className="inline-flex items-start gap-2 bg-slate-50 p-3 text-xs font-semibold leading-5 text-slate-600">
                <Info size={16} className="mt-0.5 shrink-0 text-[#281FD0]" />
                Registros agregados de la Policía Nacional (SIEDCO). No indican el riesgo de una persona ni ubicaciones exactas, y no incluyen direcciones ni datos personales.
            </p>
        </div>
    );
};

export default NeighborhoodStory;
