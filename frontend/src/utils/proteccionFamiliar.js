// Página pública de Comisarías de Familia: nombres claros, temas y resumen en palabras sencillas.

const quitarTildes = (valor) => String(valor || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

// Indicador (sin tildes, minúsculas) -> [tema, nombre claro, explicación opcional].
const CATALOGO = {
    'nuevos procesos de violencia en el contexto familiar': ['violencia', 'Nuevos casos de violencia en la familia'],
    'casos de violencia intrafamiliar atendidos': ['violencia', 'Casos de violencia intrafamiliar atendidos'],
    'casos de violencia contra mujeres en el contexto familiar': ['violencia', 'Casos contra mujeres'],
    'casos de violencia contra hombres en el contexto familiar': ['violencia', 'Casos contra hombres'],
    'casos de violencia contra adultos mayores': ['violencia', 'Casos contra personas mayores'],
    'medidas de proteccion urgentes': ['proteccion', 'Medidas de protección urgentes', 'Se dictan de inmediato para detener la violencia mientras avanza el proceso.'],
    'medidas de proteccion definitivas': ['proteccion', 'Medidas de protección definitivas', 'Se dictan al final del proceso.'],
    'procesos administrativos de restablecimiento de derechos': ['ninez', 'Procesos para restablecer derechos de niñas, niños y adolescentes', 'Se abren cuando los derechos de un menor de edad están amenazados o vulnerados (PARD).'],
    'pard con institucionalizacion': ['ninez', 'Menores de edad ubicados en una institución de protección'],
    'pard con permanencia en medio familiar': ['ninez', 'Menores de edad que siguen con su familia durante el proceso'],
    'verificaciones de derechos de nna': ['ninez', 'Verificaciones de derechos de niñas, niños y adolescentes'],
    'audiencias realizadas': ['atencion', 'Audiencias realizadas'],
    'acompanamientos psicologicos': ['atencion', 'Acompañamientos psicológicos'],
    'atenciones de psicologia': ['atencion', 'Atenciones de psicología'],
    'atenciones de trabajo social': ['atencion', 'Atenciones de trabajo social'],
    'valoraciones de trabajo social': ['atencion', 'Valoraciones de trabajo social'],
    'casos reportados en zona urbana': ['quienes', 'Casos en la zona urbana'],
    'casos reportados en zona rural': ['quienes', 'Casos en la zona rural'],
    'casos sin zona registrada': ['quienes', 'Casos sin zona registrada'],
    'casos con poblacion migrante involucrada': ['quienes', 'Casos con población migrante'],
    'casos en poblacion afrodescendiente': ['quienes', 'Casos en población afrodescendiente'],
    'casos en poblacion mestiza': ['quienes', 'Casos en población mestiza'],
};

export const TEMAS = [
    { id: 'violencia', titulo: 'Violencia en la familia' },
    { id: 'proteccion', titulo: 'Medidas de protección' },
    { id: 'ninez', titulo: 'Niñas, niños y adolescentes' },
    { id: 'atencion', titulo: 'Atención y seguimiento' },
    {
        id: 'quienes', titulo: 'Dónde y a quiénes',
        nota: 'Estas cifras describen a las personas que acudieron a la comisaría. No indican que una población o una zona sea más violenta que otra.',
    },
    { id: 'otros', titulo: 'Otros indicadores' },
];

// Conteos por barrio con solo dos barrios informados: se leerían como un señalamiento.
export const esPublicable = (registro) => !quitarTildes(registro?.indicator).startsWith('denuncias en ');

export function describir(indicador) {
    const [tema, nombre, explicacion] = CATALOGO[quitarTildes(indicador)] || ['otros', String(indicador || '').trim()];
    return { tema, nombre, explicacion: explicacion || null };
}

export function agruparPorTema(registros = []) {
    const grupos = {};
    registros.filter(esPublicable).forEach((registro) => {
        const info = describir(registro.indicator);
        (grupos[info.tema] = grupos[info.tema] || []).push({ ...registro, ...info });
    });
    // Dentro de cada tema, en el orden del catálogo (lo principal primero).
    const orden = Object.keys(CATALOGO);
    const posicion = (registro) => {
        const i = orden.indexOf(quitarTildes(registro.indicator));
        return i === -1 ? orden.length : i;
    };
    return TEMAS.filter((tema) => grupos[tema.id]?.length)
        .map((tema) => ({ ...tema, registros: [...grupos[tema.id]].sort((a, b) => posicion(a) - posicion(b)) }));
}

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

export function fechaLarga(valor) {
    if (!valor) return '';
    const [anio, mes, dia] = String(valor).slice(0, 10).split('-').map(Number);
    return dia ? `${dia} de ${MESES[mes - 1]} de ${anio}` : `${MESES[mes - 1]} de ${anio}`;
}

// "enero a junio de 2026" para un reporte acumulado del periodo 2026-06.
export function rangoPeriodo(periodo, acumulado = true) {
    if (!/^\d{4}-\d{2}$/.test(periodo || '')) return periodo || '';
    const [anio, mes] = periodo.split('-').map(Number);
    return acumulado && mes > 1 ? `enero a ${MESES[mes - 1]} de ${anio}` : `${MESES[mes - 1]} de ${anio}`;
}

const valor = (registros, indicador) => {
    const fila = registros.find((r) => quitarTildes(r.indicator) === indicador);
    return fila ? Number(fila.value) : null;
};

export const conMayuscula = (texto = '') => texto.charAt(0).toUpperCase() + texto.slice(1);

// Frase de resumen de una comisaría: casos nuevos, proporción contra mujeres y medidas urgentes.
export function resumenComisaria(nombre, registros = []) {
    const nuevos = valor(registros, 'nuevos procesos de violencia en el contexto familiar')
        ?? valor(registros, 'casos de violencia intrafamiliar atendidos');
    if (nuevos == null) return null;
    const mujeres = valor(registros, 'casos de violencia contra mujeres en el contexto familiar');
    const urgentes = valor(registros, 'medidas de proteccion urgentes');
    const acumulado = registros[0]?.reporting_basis === 'CUMULATIVE';
    let texto = `${nombre}: ${nuevos.toLocaleString('es-CO')} casos nuevos de violencia en la familia (${rangoPeriodo(registros[0]?.period, acumulado)})`;
    if (mujeres != null && nuevos > 0) texto += `; ${Math.round((mujeres / nuevos) * 100)} % contra mujeres`;
    if (urgentes != null) texto += `; ${urgentes.toLocaleString('es-CO')} medidas de protección urgentes`;
    return `${texto}.`;
}
