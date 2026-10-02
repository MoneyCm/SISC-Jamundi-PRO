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

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const longDate = (value) => { const [y, m, d] = value.split('-').map(Number); return `${d} de ${MONTHS[m - 1]} de ${y}`; };

/** Mensaje de recordatorio para una dependencia que no ha respondido (se copia al correo o WhatsApp). */
export const reminderMessage = (entity = {}, request = {}) => {
    const period = request.period_start && request.period_end ? `, del ${longDate(request.period_start)} al ${longDate(request.period_end)}` : '';
    const again = request.reminders ? ' Ya le habíamos escrito antes sobre esto.' : '';
    return `Buen día, ${entity.name || ''}.\n\n`
        + `Le recordamos que el ${longDate(request.requested_on)} le pedimos: ${request.what}${period}. `
        + `El plazo de respuesta era el ${longDate(request.due_on)} y todavía no lo hemos recibido.${again}\n\n`
        + 'Esta información alimenta el Observatorio del Delito y los informes de la Secretaría de Seguridad y Convivencia. '
        + 'Le agradecemos enviarla lo antes posible o avisarnos si hay alguna dificultad.\n\nMuchas gracias.';
};

/** "Recordado 2 veces, la última el 01/10" */
export const reminderSummary = (request = {}) => {
    if (!request.reminders) return '';
    const last = request.last_reminded_on.split('-').reverse().slice(0, 2).join('/');
    return request.reminders === 1 ? `Recordado el ${last}` : `Recordado ${request.reminders} veces, la última el ${last}`;
};

export const stateDetail = (entity) => {
    const date = (value) => value ? value.split('-').reverse().slice(0, 2).join('/') : '';
    if (entity.state === 'ATRASADA') return `Pedido el ${date(entity.open_since)}; el plazo venció el ${date(entity.due_on)}.`;
    if (entity.state === 'ESPERANDO') return `Pedido el ${date(entity.open_since)}; plazo hasta el ${date(entity.due_on)}.`;
    if (entity.last_received) return `Última respuesta: ${date(entity.last_received)} (hace ${entity.days_since_received} días).`;
    return 'Sin solicitudes registradas.';
};
