// Meses que la sábana de la Policía no trae completos, reunidos de varias consultas (periodo y comparación).
export function mesesIncompletos(coberturas = []) {
    const meses = [];
    for (const cobertura of coberturas) {
        if (!cobertura || cobertura.completa !== false) continue;
        for (const mes of cobertura.meses_incompletos || []) {
            if (!meses.includes(mes)) meses.push(mes);
        }
    }
    return meses;
}

export function textoCobertura(meses, { publico = false } = {}) {
    if (!meses.length) return '';
    if (publico) {
        return `La información de la Policía disponible no incluye completo: ${meses.join(', ')}. `
            + 'Los totales y comparaciones que incluyen esos meses están incompletos.';
    }
    return `La sábana de la Policía cargada no trae completo: ${meses.join(', ')}. `
        + 'Los totales y comparaciones que incluyen esos meses están incompletos; conviene pedir esos datos a la Policía.';
}

// Por qué no se muestra la tasa de homicidios en el portal ciudadano.
export function motivoSinTasa(metadata = {}, filtros = {}, suprimido = null) {
    if (suprimido) return 'Sin cifras: muy pocos casos para este filtro.';
    if (metadata?.cobertura?.completa === false) return 'Sin tasa: faltan meses de datos en este periodo.';
    if (filtros?.territorio || filtros?.zona) return 'La tasa se calcula solo para todo el municipio.';
    return 'Sin proyección de población disponible para calcular la tasa.';
}

// Meses de la tendencia sin datos (llegan vacíos para no saltarlos en la gráfica).
export function mesesSinDatos(tendencia = []) {
    return tendencia.filter((fila) => fila?.sin_datos).map((fila) => fila.name);
}
