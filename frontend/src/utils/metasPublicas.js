const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
    'noviembre', 'diciembre'];

// Color del semáforo de una meta del PISCC según su estado en el año.
export function semaforoMeta(status) {
    if (status === 'EN_META') return 'verde';
    if (status === 'DESVIACION') return 'amarillo';
    if (status === 'SUPERADA') return 'rojo';
    return 'gris';
}

export function fechaCorta(valor) {
    if (!valor) return '';
    const [anio, mes, dia] = String(valor).slice(0, 10).split('-').map(Number);
    return `${dia} de ${MESES[mes - 1]} de ${anio}`;
}

// "En el año · meta 2027: 105 · línea base 2023: 115"
export function textoMeta(meta = {}) {
    return `En lo corrido del año · meta 2027: ${meta.goal_2027} · línea base 2023: ${meta.baseline_2023}`;
}

// Posición de Jamundí en el Valle: "puesto 19 de 42 (1 = tasa más alta)".
export function textoPuesto(puesto = {}) {
    if (!puesto?.puesto) return '';
    return `Jamundí ocupa el puesto ${puesto.puesto} de ${puesto.de} municipios del Valle (el 1 es la tasa más alta).`;
}
