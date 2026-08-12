export const DEFAULT_PUBLIC_FILTERS = Object.freeze({
    year: '',
    periodMode: 'year_to_date',
    comparison: 'same_period_previous_year',
    startDate: '',
    endDate: '',
    conducta: '',
    zona: '',
    territorio: '',
});

export const PERIOD_OPTIONS = Object.freeze([
    { value: 'year_to_date', label: 'Año a la fecha' },
    { value: 'last_30_days', label: 'Últimos 30 días' },
    { value: 'last_7_days', label: 'Últimos 7 días' },
    { value: 'custom', label: 'Periodo personalizado' },
]);

export const COMPARISON_OPTIONS = Object.freeze([
    { value: 'same_period_previous_year', label: 'Mismo periodo del año anterior' },
    { value: 'previous_period', label: 'Periodo anterior equivalente' },
    { value: 'none', label: 'Sin comparación' },
]);

const validValue = (value, options, fallback) => (
    options.some((option) => option.value === value) ? value : fallback
);

export const parsePublicFilters = (search = '') => {
    const params = new URLSearchParams(search);
    return {
        year: params.get('year') || '',
        periodMode: validValue(params.get('period') || '', PERIOD_OPTIONS, DEFAULT_PUBLIC_FILTERS.periodMode),
        comparison: validValue(params.get('compare') || '', COMPARISON_OPTIONS, DEFAULT_PUBLIC_FILTERS.comparison),
        startDate: params.get('from') || '',
        endDate: params.get('to') || '',
        conducta: params.get('conducta') || '',
        zona: params.get('zona') || '',
        territorio: params.get('barrio') || '',
    };
};

export const filtersToSearchParams = (filters = {}, page = '') => {
    const merged = { ...DEFAULT_PUBLIC_FILTERS, ...filters };
    const params = new URLSearchParams();
    if (page && page !== 'hub') params.set('page', page);
    if (merged.year) params.set('year', merged.year);
    if (merged.periodMode !== DEFAULT_PUBLIC_FILTERS.periodMode) params.set('period', merged.periodMode);
    if (merged.comparison !== DEFAULT_PUBLIC_FILTERS.comparison) params.set('compare', merged.comparison);
    if (merged.periodMode === 'custom' && merged.startDate) params.set('from', merged.startDate);
    if (merged.periodMode === 'custom' && merged.endDate) params.set('to', merged.endDate);
    if (merged.conducta) params.set('conducta', merged.conducta);
    if (merged.zona) params.set('zona', merged.zona);
    if (merged.territorio) params.set('barrio', merged.territorio);
    return params;
};

const numberFormatter = new Intl.NumberFormat('es-CO');
const percentFormatter = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 });

export const formatNumber = (value) => numberFormatter.format(Number(value) || 0);

export const formatVariation = (value) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Sin base comparable';
    const numeric = Number(value);
    return `${numeric > 0 ? '+' : ''}${percentFormatter.format(numeric)}%`;
};

export const variationTone = (value) => {
    if (value === null || value === undefined || Number(value) === 0) return 'neutral';
    return Number(value) > 0 ? 'up' : 'down';
};

const comparisonText = (metadata = {}) => (
    metadata.comparison_label?.toLowerCase() || 'el periodo de comparación'
);

export const buildCitizenInsights = (data, limit = 4) => {
    if (!data) return [];
    const insights = [];
    const variation = data.kpis?.variation_pct;
    const total = Number(data.kpis?.total_hechos || 0);
    const previous = Number(data.kpis?.previous_total || 0);

    if (variation !== null && variation !== undefined) {
        const direction = Number(variation) > 0 ? 'aumentaron' : Number(variation) < 0 ? 'disminuyeron' : 'se mantuvieron';
        insights.push({
            id: 'overall-change',
            eyebrow: 'Balance general',
            title: `${formatVariation(variation)} en los casos agregados`,
            summary: `Se registraron ${formatNumber(total)} casos, frente a ${formatNumber(previous)} en ${comparisonText(data.metadata)}. Los registros ${direction}.`,
            tone: variationTone(variation),
        });
    }

    const comparableConductas = (data.conductas || [])
        .filter((item) => item.previous_value !== undefined)
        .sort((a, b) => Math.abs(Number(b.difference || 0)) - Math.abs(Number(a.difference || 0)) || String(a.name).localeCompare(String(b.name)));
    const conducta = comparableConductas[0];
    if (conducta) {
        const difference = Number(conducta.difference || 0);
        insights.push({
            id: 'conducta-change',
            eyebrow: 'Mayor cambio por conducta',
            title: conducta.name,
            summary: `${formatNumber(conducta.value)} casos en el periodo: ${formatNumber(Math.abs(difference))} ${difference >= 0 ? 'más' : 'menos'} que en la comparación (${formatVariation(conducta.variation_pct)}).`,
            tone: variationTone(conducta.variation_pct),
        });
    }

    const weekly = data.weekly_trend || [];
    if (weekly.length) {
        const latest = weekly[weekly.length - 1];
        const prior = weekly.length > 1 ? weekly[weekly.length - 2] : null;
        const difference = prior ? Number(latest.total || 0) - Number(prior.total || 0) : null;
        insights.push({
            id: 'latest-week',
            eyebrow: 'Último corte semanal',
            title: `${latest.name}: ${formatNumber(latest.total)} casos`,
            summary: difference === null
                ? 'No hay una semana anterior completa en la consulta para comparar.'
                : difference === 0
                    ? 'Sin cambio frente a la semana anterior incluida en la consulta.'
                    : `${formatNumber(Math.abs(difference))} casos ${difference > 0 ? 'más' : 'menos'} que la semana anterior incluida en la consulta.`,
            tone: variationTone(difference),
        });
    }

    const territory = data.territories?.[0];
    if (territory) {
        insights.push({
            id: 'top-territory',
            eyebrow: 'Concentración territorial',
            title: territory.name,
            summary: `${formatNumber(territory.total)} casos agregados en el periodo. Esta cifra indica concentración de registros, no riesgo individual ni ubicación exacta.`,
            tone: 'territory',
        });
    }

    return insights.slice(0, Math.max(1, limit));
};

export const territoryByName = (data, name) => (
    (data?.territories || []).find((item) => item.name === name)
    || (data?.filters?.available?.territories || []).find((item) => item.name === name)
    || null
);
