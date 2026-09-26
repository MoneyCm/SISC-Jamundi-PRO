// Cuatro nombres distintos para cuatro cosas distintas. Una señal del radar no es una alerta, y
// solo la Defensoría del Pueblo emite Alertas Tempranas.

export const ALERT_TERMS = [
    {
        key: 'SENAL',
        label: 'Señal estadística',
        text: 'La calcula el radar del SISC cuando una cifra se sale de lo esperado. Pide mirar el dato; no es una alerta ni mide el riesgo.',
    },
    {
        key: 'ANALISIS',
        label: 'Situación para análisis',
        text: 'Una señal que el Observatorio decidió estudiar: se abre un estudio con su pregunta.',
    },
    {
        key: 'ALERTA_SISC',
        label: 'Alerta SISC',
        text: 'Aviso que el SISC eleva para gestión (bandeja de Alertas SISC o nota a la Secretaria), con su regla explícita.',
    },
    {
        key: 'DEFENSORIA',
        label: 'Alerta Temprana de la Defensoría',
        text: 'Documento oficial de la Defensoría del Pueblo. El SISC no la emite: solo la contrasta con los hechos registrados.',
    },
];

export const termLabel = (key) => ALERT_TERMS.find((term) => term.key === key)?.label || key;
