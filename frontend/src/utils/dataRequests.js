// Solicitudes de datos: textos y valores por defecto de la rutina del lunes.

export const STATE_LABELS = {
    ATRASADA: { label: 'Atrasada', chip: 'bg-red-100 text-red-800' },
    TOCA_PEDIR: { label: 'Toca pedir', chip: 'bg-amber-100 text-amber-900' },
    ESPERANDO: { label: 'Esperando respuesta', chip: 'bg-slate-100 text-slate-700' },
    AL_DIA: { label: 'Al día', chip: 'bg-emerald-50 text-emerald-800' },
};
export const REQUEST_STATUS_LABELS = { PEDIDA: 'Pedida', RECIBIDA: 'Recibida', INCOMPLETA: 'Incompleta', SIN_RESPUESTA: 'Sin respuesta' };
export const CADENCE_LABELS = { SEMANAL: 'Semanal', QUINCENAL: 'Quincenal', MENSUAL: 'Mensual' };
export const PROGRAM_LABELS = { INSPECCIONES: 'Inspección', COMISARIAS: 'Comisaría', OTRA: 'Otra' };

const iso = (value) => value.toISOString().slice(0, 10);
const utc = (text) => new Date(`${text}T00:00:00Z`);
const addDays = (text, days) => { const value = utc(text); value.setUTCDate(value.getUTCDate() + days); return iso(value); };

/** Semana anterior (lunes a domingo) respecto a `today` (AAAA-MM-DD). */
export const previousWeek = (today) => {
    const weekday = (utc(today).getUTCDay() + 6) % 7; // lunes = 0
    const start = addDays(today, -weekday - 7);
    return { start, end: addDays(start, 6) };
};

/** Mes anterior completo respecto a `today`. */
export const previousMonth = (today) => {
    const [year, month] = today.split('-').map(Number);
    const start = new Date(Date.UTC(year, month - 2, 1));
    const end = new Date(Date.UTC(year, month - 1, 0));
    return { start: iso(start), end: iso(end) };
};

export const defaultRequest = (today, cadence = 'SEMANAL') => {
    const period = cadence === 'MENSUAL' ? previousMonth(today) : previousWeek(today);
    return {
        what: cadence === 'MENSUAL' ? 'Informe mensual de gestión' : 'Reporte semanal de actuaciones y medidas',
        period_start: period.start,
        period_end: period.end,
        requested_on: today,
        due_on: addDays(today, 3),
        channel: 'Correo',
    };
};

export const stateDetail = (entity) => {
    const date = (value) => value ? value.split('-').reverse().slice(0, 2).join('/') : '';
    if (entity.state === 'ATRASADA') return `Pedido el ${date(entity.open_since)}; el plazo venció el ${date(entity.due_on)}.`;
    if (entity.state === 'ESPERANDO') return `Pedido el ${date(entity.open_since)}; plazo hasta el ${date(entity.due_on)}.`;
    if (entity.last_received) return `Última respuesta: ${date(entity.last_received)} (hace ${entity.days_since_received} días).`;
    return 'Sin solicitudes registradas.';
};
