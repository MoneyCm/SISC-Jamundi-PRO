// Intervenciones: requisitos por etapa (espejo de api/interventions.py) y lectura del seguimiento 30/60/90.

export const STAGES = [
    { code: 'BORRADOR', label: 'Borrador' },
    { code: 'DECIDIDA', label: 'Decidida' },
    { code: 'EN_EJECUCION', label: 'En ejecución' },
    { code: 'FINALIZADA', label: 'Finalizada' },
];
export const STAGE_LABELS = { ...Object.fromEntries(STAGES.map((stage) => [stage.code, stage.label])), EVALUADA: 'Evaluada' };

// Desde cada etapa solo se puede seguir igual o avanzar a la siguiente.
const NEXT = { BORRADOR: ['BORRADOR', 'DECIDIDA'], DECIDIDA: ['DECIDIDA', 'EN_EJECUCION'], EN_EJECUCION: ['EN_EJECUCION', 'FINALIZADA'], FINALIZADA: ['FINALIZADA'] };
export const allowedStages = (current) => STAGES.filter((stage) => (NEXT[current] || []).includes(stage.code));

const REQUIRED = {
    DECIDIDA: [['recommendation', 'recomendación'], ['decision', 'decisión'], ['responsible', 'responsable'], ['decision_date', 'fecha de la decisión'], ['deadline', 'plazo']],
    EN_EJECUCION: [['intervention', 'qué se hizo'], ['started_on', 'fecha de inicio']],
    FINALIZADA: [['completed_on', 'fecha de fin']],
};
const ORDER = ['DECIDIDA', 'EN_EJECUCION', 'FINALIZADA'];

export const missingFor = (doc, status) => {
    const reached = ORDER.slice(0, ORDER.indexOf(status) + 1);
    const missing = reached.flatMap((stage) => REQUIRED[stage]).filter(([key]) => !String(doc[key] || '').trim()).map(([, label]) => label);
    if (status === 'FINALIZADA' && !(doc.evidence || []).length) missing.push('al menos una evidencia');
    return missing;
};

const number = (value) => new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 }).format(value);
const signed = (value) => `${value > 0 ? '+' : ''}${number(value)}`;

// Base pequeña: diferencia en casos; si no, porcentaje.
export const describeWindow = (window) => {
    if (window.status !== 'MEDIDO') return window.detail || '';
    const change = window.variation_pct === null || window.variation_pct === undefined
        ? `${signed(window.difference)} hechos`
        : `${signed(window.variation_pct)}%`;
    return `${window.before} → ${window.after} (${change})`;
};
