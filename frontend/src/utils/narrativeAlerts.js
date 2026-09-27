// Alertas Narrativas: reglas del editor y textos de apoyo (el backend vuelve a validar).

export const MAX_LINES = 6;
export const MAX_CHARS = 1200;

export const TYPES = [
    { code: 'SEMANAL', label: 'Semanal', maxLines: 6 },
    { code: 'MENSUAL', label: 'Mensual', maxLines: 10 },
    { code: 'CONSEJO', label: 'Consejo de Seguridad', maxLines: 12 },
    { code: 'SEMESTRAL', label: 'Semestral', maxLines: 12 },
    { code: 'ANUAL', label: 'Anual', maxLines: 15 },
];
export const typeLabel = (code) => TYPES.find((type) => type.code === code)?.label || code;

export const TRIGGER_LABELS = { PROGRAMADA: 'Programado', CARGA: 'Al cargar la sábana' };

export const SOURCE_LABELS = {
    DEFENSORIA_AT: 'Alertas Tempranas de la Defensoría',
    MEDICINA_LEGAL: 'Medicina Legal',
    COMISARIAS: 'Comisarías de Familia',
    SENALES: 'Señales estadísticas',
    PORTAL_CIUDADANO: 'Portal ciudadano',
};

export const STATUS_LABELS = {
    BORRADOR: 'Borrador',
    ENVIADO: 'Enviado',
    DESCARTADO: 'Descartado',
    REEMPLAZADO: 'Reemplazado',
};

export const ACTION_LABELS = {
    GENERADO: 'Generado',
    EDITADO: 'Editado',
    ACTUALIZADO: 'Actualizado con los datos del momento',
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

export const checkText = (text, maxLines = MAX_LINES, maxChars = MAX_CHARS) => {
    const lines = cleanLines(text);
    const chars = lines.join('\n').length;
    let error = '';
    if (!lines.length) error = 'El mensaje no puede quedar vacío.';
    else if (lines.length > maxLines) error = `El mensaje tiene ${lines.length} líneas; el máximo es ${maxLines}.`;
    else if (chars > maxChars) error = `El mensaje tiene ${chars} caracteres; el máximo es ${maxChars}.`;
    return { lines: lines.length, chars, error };
};

export const whatsappUrl = (text) => `https://wa.me/?text=${encodeURIComponent(text)}`;

export const formatProbability = (p) => {
    if (p < 0.0001) return 'menos de 1 en 10.000';
    return `${(p * 100).toFixed(p < 0.01 ? 2 : 1).replace('.', ',')} %`;
};
