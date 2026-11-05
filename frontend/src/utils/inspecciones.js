// Nombres de los despachos de inspección tal como los guarda el backend (PRIMERA, SEGUNDA...).
export const SIN_IDENTIFICAR = 'SIN IDENTIFICAR';

export const etiquetaInspeccion = (valor) => {
    const texto = String(valor ?? '').trim().toUpperCase();
    if (!texto || texto === SIN_IDENTIFICAR) return 'Sin identificar';
    return `${texto.charAt(0)}${texto.slice(1).toLowerCase()}`;
};

// Parte de las medidas de una inspección que ya tienen decisión (pagada, ratificada o no impuesta).
export const porcentajeResuelto = (fila) => {
    const total = ['pagadas', 'ratificadas', 'no_impuestas', 'en_proceso', 'otras']
        .reduce((suma, campo) => suma + Number(fila?.[campo] || 0), 0);
    if (!total) return 0;
    const resueltas = Number(fila.pagadas || 0) + Number(fila.ratificadas || 0) + Number(fila.no_impuestas || 0);
    return Math.round((resueltas / total) * 100);
};

// Pesos colombianos en millones con una cifra decimal: 45107193 -> "$45,1 M".
export const millones = (valor) => {
    const cifra = Number(valor || 0) / 1_000_000;
    return `$${cifra.toLocaleString('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} M`;
};
