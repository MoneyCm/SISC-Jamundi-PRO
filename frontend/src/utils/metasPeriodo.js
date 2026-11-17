// Metas del PISCC por periodo (mes, trimestre, semestre, año o rango): textos, colores y descarga.

export const TIPOS_PERIODO = [
    { id: 'mes', label: 'Mes' },
    { id: 'trimestre', label: 'Trimestre' },
    { id: 'semestre', label: 'Semestre' },
    { id: 'anio', label: 'Año' },
    { id: 'rango', label: 'Rango de meses' },
];

// Color del ritmo frente a la parte de la meta anual que corresponde al periodo.
export function tonoRitmo(status) {
    if (status === 'EN_RITMO') return 'verde';
    if (status === 'SOBRE_RITMO' || status === 'SUPERADA') return 'rojo';
    return 'gris';
}

const numero = (valor) => Number(valor).toLocaleString('es-CO', { maximumFractionDigits: 1 });

// "9 menos (-34,6 %)", "3 más", "igual" o "—" si no hay con qué comparar.
export function textoCambio(item = {}) {
    if (item.diferencia == null) return '—';
    if (item.diferencia === 0) return 'Igual';
    const sentido = item.diferencia > 0 ? 'más' : 'menos';
    const pct = item.variacion_pct == null ? '' : ` (${item.variacion_pct > 0 ? '+' : ''}${numero(item.variacion_pct)} %)`;
    return `${numero(Math.abs(item.diferencia))} ${sentido}${pct}`;
}

// En seguridad y convivencia menos casos es mejor: bajar es verde y subir es rojo.
export function tonoCambio(item = {}) {
    if (item.diferencia == null || item.diferencia === 0) return 'gris';
    return item.diferencia < 0 ? 'verde' : 'rojo';
}

// "85 de 105" con aviso si el acumulado del año ya pasó la meta anual.
// "Después del corte de MinDefensa: +19 víctimas en la sábana, del 1 de octubre al 6 de noviembre".
// Homicidios se cuenta por víctima y lo demás por hecho único: la unidad va en el texto.
export function textoReciente(meta = {}, fecha = (v) => v) {
    const r = meta.reciente;
    if (!r || r.since == null) return '';
    const unidad = meta.id === 'homicidios' ? (r.since === 1 ? 'víctima' : 'víctimas') : (r.since === 1 ? 'hecho' : 'hechos');
    return `Después del corte de MinDefensa: +${r.since} ${unidad} en la sábana de la Policía, del ${fecha(r.since_start)} al ${fecha(r.cutoff)}. No se suman a la cifra de arriba.`;
}

export function textoAcumulado(item = {}) {
    if (item.year_to_date == null) return '—';
    return `${numero(item.year_to_date)} de ${numero(item.goal_2027)}`;
}

// Índices (0 a 11) de los meses del año final que caen dentro del periodo contado.
export function mesesResaltados(item = {}) {
    if (!item.counted_from || !item.counted_to) return [];
    const [anioFin, mesFin] = item.counted_to.split('-').map(Number);
    const [anioIni, mesIni] = item.counted_from.split('-').map(Number);
    const primero = anioIni < anioFin ? 1 : mesIni;
    return Array.from({ length: mesFin - primero + 1 }, (_, i) => primero - 1 + i);
}

export function opcionesDeTipo(opciones = [], tipo) {
    return opciones.filter((opcion) => opcion.tipo === tipo);
}

const celda = (valor) => {
    const texto = valor == null ? '' : String(valor);
    return /[",;\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
};

// CSV con punto y coma (Excel en español lo abre en columnas) y fuente y corte en cada fila.
export function csvMetasPeriodo(data = {}) {
    const encabezado = ['Indicador', 'Periodo', 'Casos en el periodo', 'Mismos meses del año anterior', 'Diferencia',
        'Variación %', 'Acumulado del año', 'Referencia de la meta a ese mes', 'Meta anual 2027', 'Línea base 2023',
        'Ritmo', 'Meses pedidos', 'Meses contados', 'Fuente', 'Publicado hasta'];
    const filas = (data.indicators || []).map((item) => [
        item.label, data.periodo, item.value, item.previous, item.diferencia, item.variacion_pct, item.year_to_date,
        item.year_to_date_reference, item.goal_2027, item.baseline_2023, item.status_label, item.months_requested,
        item.months_counted, item.source, item.published_until,
    ]);
    return [encabezado, ...filas].map((fila) => fila.map(celda).join(';')).join('\r\n');
}

export function nombreArchivoMetas(data = {}) {
    const tramo = data.desde === data.hasta ? data.desde : `${data.desde}_a_${data.hasta}`;
    return `sisc-jamundi-metas-piscc-${tramo || 'periodo'}.csv`;
}
