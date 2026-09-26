// Centro de análisis: agrupación de señales y ciclo de las recomendaciones (espejo de api/observatory.py).

export const RECOMMENDATION_LABELS = {
    PROPUESTA: 'Propuesta',
    PRESENTADA: 'Presentada',
    ACEPTADA: 'Aceptada',
    RECHAZADA: 'Rechazada',
    EN_EJECUCION: 'En ejecución',
    CUMPLIDA: 'Cumplida',
};

const TRANSITIONS = {
    PROPUESTA: ['PRESENTADA'],
    PRESENTADA: ['ACEPTADA', 'RECHAZADA'],
    ACEPTADA: ['EN_EJECUCION', 'CUMPLIDA'],
    EN_EJECUCION: ['CUMPLIDA'],
};

export const nextRecommendationSteps = (status) => TRANSITIONS[status] || [];

const LEVEL_ORDER = { ALTA: 0, MEDIA: 1, INFO: 2, OK: 3 };

// Grupos en el orden del backend; dentro de cada uno, lo urgente primero. Un grupo sin señales no se muestra.
export const groupSignals = (overview) => (overview?.groups || [])
    .map((group) => ({
        ...group,
        signals: (overview.signals || [])
            .filter((item) => item.group === group.key)
            .sort((a, b) => (LEVEL_ORDER[a.level] ?? 9) - (LEVEL_ORDER[b.level] ?? 9)),
    }))
    .filter((group) => group.signals.length > 0);
