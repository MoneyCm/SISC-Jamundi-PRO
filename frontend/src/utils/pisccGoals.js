// Metas del PISCC: textos de lectura para la tabla del Centro de análisis.

export const formatVersusLastYear = (item) => {
    if (item.previous === null || item.previous === undefined) return 'sin año anterior comparable';
    const diff = item.count - item.previous;
    if (!diff) return `igual que el año pasado (${item.previous})`;
    return `${diff > 0 ? '+' : ''}${diff} frente al año pasado (${item.previous})`;
};

export const goalReading = (item) => {
    if (item.status === 'SIN_DATOS') return item.detail;
    if (item.compares === 'acumulado' || item.status === 'SUPERADA' || item.status === 'PRELIMINAR') return item.detail;
    return `Ritmo anual ≈${item.projection} frente a meta ${item.goal_2027}.`;
};
