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

export function textoCobertura(meses) {
    if (!meses.length) return '';
    return `La sábana de la Policía cargada no trae completo: ${meses.join(', ')}. `
        + 'Los totales y comparaciones que incluyen esos meses están incompletos; conviene pedir esos datos a la Policía.';
}

// Meses de la tendencia sin datos (llegan vacíos para no saltarlos en la gráfica).
export function mesesSinDatos(tendencia = []) {
    return tendencia.filter((fila) => fila?.sin_datos).map((fila) => fila.name);
}
