// Reportes seguros del portal: estados de atención, acciones posibles y lectura del tiempo de espera.

export const REPORT_STATES = {
    RECIBIDO: { label: 'Recibido', chip: 'bg-amber-100 text-amber-900' },
    EN_GESTION: { label: 'En gestión', chip: 'bg-blue-100 text-blue-800' },
    CERRADO: { label: 'Cerrado', chip: 'bg-emerald-50 text-emerald-800' },
};

/** Acciones desde cada estado; cerrar y reabrir piden nota. */
export const REPORT_ACTIONS = {
    RECIBIDO: [{ to: 'EN_GESTION', label: 'Empezar gestión', needsNote: false }, { to: 'CERRADO', label: 'Cerrar', needsNote: true }],
    EN_GESTION: [{ to: 'CERRADO', label: 'Cerrar', needsNote: true }],
    CERRADO: [{ to: 'EN_GESTION', label: 'Reabrir', needsNote: true }],
};

export const daysWaiting = (receivedIso, todayIso) => {
    if (!receivedIso) return null;
    const received = new Date(`${receivedIso.slice(0, 10)}T00:00:00Z`);
    const today = new Date(`${todayIso}T00:00:00Z`);
    return Math.max(0, Math.round((today - received) / 86400000));
};

export const waitingText = (report, todayIso) => {
    if (report.estado === 'CERRADO') return '';
    const days = daysWaiting(report.recibido, todayIso);
    if (days === null) return '';
    if (days === 0) return 'Recibido hoy';
    return `${days} ${days === 1 ? 'día' : 'días'} abierto`;
};
