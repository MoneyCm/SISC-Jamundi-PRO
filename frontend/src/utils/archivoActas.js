// Archivo de actas: agrupación, filtros y textos.

export const ESTADOS_ACTA = {
    CONFIRMADA: { etiqueta: 'Archivada', clase: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
    PENDIENTE: { etiqueta: 'Pendiente de revisar', clase: 'bg-amber-50 text-amber-900 border-amber-200' },
    HISTORICA: { etiqueta: 'Histórica (solo análisis)', clase: 'bg-slate-100 text-slate-700 border-slate-200' },
};

// Una nota o resumen (por ejemplo, de Gemini) no reemplaza el acta oficial: hay que pedirla.
export const sinActaOficial = (acta = {}) => /sin acta oficial|nota de gemini|resumen/i.test(acta.filename || '');

export const anioActa = (acta = {}) => (acta.act_date ? Number(acta.act_date.slice(0, 4)) : null);

export function filtrarActas(actas = [], { instancia = '', anio = '', estado = '' } = {}) {
    return actas.filter((acta) => (!instancia || acta.instance === instancia)
        && (!anio || String(anioActa(acta)) === String(anio))
        && (!estado || acta.status === estado));
}

// Resumen por instancia: total, pendientes de revisar, sin archivo original y sin acta oficial.
export function resumenPorInstancia(actas = []) {
    const grupos = {};
    actas.forEach((acta) => {
        const g = grupos[acta.instance] || (grupos[acta.instance] = {
            instancia: acta.instance, nombre: acta.instance_label, total: 0, pendientes: 0, sinArchivo: 0, sinOficial: 0, ultima: null,
        });
        g.total += 1;
        if (acta.status === 'PENDIENTE') g.pendientes += 1;
        if (!acta.has_file) g.sinArchivo += 1;
        if (sinActaOficial(acta)) g.sinOficial += 1;
        if (acta.act_date && (!g.ultima || acta.act_date > g.ultima)) g.ultima = acta.act_date;
    });
    return Object.values(grupos).sort((a, b) => b.total - a.total);
}

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

export function fechaActa(valor) {
    if (!valor) return 'Sin fecha';
    const [anio, mes, dia] = String(valor).slice(0, 10).split('-').map(Number);
    return `${dia} de ${MESES[mes - 1]} de ${anio}`;
}

export const tamanoArchivo = (bytes) => (bytes == null ? '' : bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`);
