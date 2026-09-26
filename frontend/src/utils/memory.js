// Memoria institucional: filtros de búsqueda y lectura del resultado.

export const RECOMMENDATION_STATUS = {
    PROPUESTA: 'propuesta', PRESENTADA: 'presentada', ACEPTADA: 'aceptada',
    RECHAZADA: 'rechazada', EN_EJECUCION: 'en ejecución', CUMPLIDA: 'cumplida',
};

export const memoryQuery = ({ q, kind, year }) => {
    const params = new URLSearchParams();
    if (q && q.trim()) params.set('q', q.trim());
    if (kind) params.set('kind', kind);
    if (year) params.set('year', year);
    const text = params.toString();
    return text ? `?${text}` : '';
};

/** Color del resultado: rechazos y lo que quedó sin medir se destacan. */
export const OUTCOME_TONE = (outcome = '') => {
    if (outcome.startsWith('Rechazada') || outcome.includes('sin evaluar')) return 'text-amber-800';
    if (outcome === 'Cumplida' || outcome.startsWith('Evaluada')) return 'text-emerald-800';
    return 'text-slate-700';
};
