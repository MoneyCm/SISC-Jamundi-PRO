// Comisarías de Familia: textos del análisis de casos de violencia intrafamiliar.

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

export const formatPct = (value) => (value == null ? 'sin dato' : `${String(value).replace('.', ',')} %`);

export const formatDays = (value) => {
    if (value == null) return 'sin dato';
    const days = Number.isInteger(value) ? value : String(value).replace('.', ',');
    return `${days} ${value === 1 ? 'día' : 'días'}`;
};

export const monthLabel = (month, short = false) => {
    const [year, number] = month.split('-').map(Number);
    return short ? `${MONTHS[number - 1]} ${String(year).slice(2)}` : `${MONTHS[number - 1]} ${year}`;
};

// La reincidencia por código de caso (misma víctima atendida otra vez) es la más confiable;
// si la comisaría no envía código, se usa su propia columna de nuevos episodios.
export const reincidenceSummary = (data) => {
    if (data.cases_by_code) {
        return {
            value: formatPct(data.rate_by_code),
            helper: `${data.repeated_by_code} de ${data.cases_by_code} casos volvieron a ser atendidos${data.median_days_to_repeat != null ? ` (mediana: ${formatDays(data.median_days_to_repeat)} después)` : ''}.`,
            method: 'Reincidencia medida con el código interno del caso: la misma huella atendida en dos fechas distintas. También cuenta como reincidente el caso que la comisaría marcó con nuevos episodios.',
        };
    }
    if (data.flag_known) {
        return {
            value: formatPct(data.rate_by_flag),
            helper: `${data.flag_yes} de ${data.flag_known} casos con nuevos episodios registrados por la comisaría.`,
            method: 'Sin código de caso, la reincidencia sale solo de la columna de nuevos episodios que diligencia la comisaría.',
        };
    }
    return {
        value: 'sin dato',
        helper: 'Las bases no traen código de caso ni registro de nuevos episodios.',
        method: 'Para medir reincidencia, pida a las Comisarías el código interno del caso o la columna de nuevos episodios.',
    };
};
