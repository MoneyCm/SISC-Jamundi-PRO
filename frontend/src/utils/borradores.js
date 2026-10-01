const EDICIONES = { weekly: 'Semanal', monthly: 'Mensual', semester: 'Semestral', annual: 'Anual' };

export const etiquetaEdicion = (tipo) => EDICIONES[tipo] || tipo || 'Edición';

export const textoBorrador = (draft = {}) =>
    `${etiquetaEdicion(draft.edition_type).toLowerCase()} del ${draft.period_start} al ${draft.period_end}`;
