// Alertas Narrativas: reglas del editor y textos de apoyo (el backend vuelve a validar).

export const MAX_LINES = 6;
export const MAX_CHARS = 1200;

export const STATUS_LABELS = {
    BORRADOR: 'Borrador',
    ENVIADO: 'Enviado',
    DESCARTADO: 'Descartado',
    REEMPLAZADO: 'Reemplazado',
};

export const ACTION_LABELS = {
    GENERADO: 'Generado',
    EDITADO: 'Editado',
    ENVIADO: 'Marcado como enviado',
    DESCARTADO: 'Descartado',
    REEMPLAZADO: 'Reemplazado por una entrega más reciente',
};

export const DIMENSION_LABELS = { DELITO: 'Delito', BARRIO: 'Barrio o vereda', FRANJA: 'Franja horaria' };

export const STATE_LABELS = {
    VENCIDO: 'vencido',
    PROXIMO: 'vence pronto',
    ABIERTO: 'abierto',
    CUMPLIDO: 'cumplido',
};

export const cleanLines = (text) => (text || '').split('\n').map((line) => line.trimEnd()).filter((line) => line.trim());

export const checkText = (text) => {
    const lines = cleanLines(text);
    const chars = lines.join('\n').length;
    let error = '';
    if (!lines.length) error = 'El mensaje no puede quedar vacío.';
    else if (lines.length > MAX_LINES) error = `El mensaje tiene ${lines.length} líneas; el máximo es ${MAX_LINES}.`;
    else if (chars > MAX_CHARS) error = `El mensaje tiene ${chars} caracteres; el máximo es ${MAX_CHARS}.`;
    return { lines: lines.length, chars, error };
};

export const whatsappUrl = (text) => `https://wa.me/?text=${encodeURIComponent(text)}`;

export const formatProbability = (p) => {
    if (p < 0.0001) return 'menos de 1 en 10.000';
    return `${(p * 100).toFixed(p < 0.01 ? 2 : 1).replace('.', ',')} %`;
};
