export const buildPrioritizedTotalComparison = (items) => {
    if (items.length < 2) return null;

    const periodMonths = new Set(items.map(item => item.period_end_month || 12));
    const hasMixedPeriods = periodMonths.size !== 1;

    const rowMaps = items.map(item => new Map(
        item.territorial_comparison.rows.map(row => [row.codigo_dane || row.municipio, row])
    ));
    const baseRows = items[0].territorial_comparison.rows;
    const combinedRows = baseRows.map(baseRow => {
        const key = baseRow.codigo_dane || baseRow.municipio;
        const matchingRows = rowMaps.map(rowMap => rowMap.get(key));
        if (matchingRows.some(row => !row || row.casos == null)) return null;

        const population = Number(baseRow.poblacion);
        if (!Number.isFinite(population) || population <= 0) return null;

        const cases = matchingRows.reduce((total, row) => total + Number(row.casos), 0);
        return {
            ...baseRow,
            casos: cases,
            tasa_por_100k: Math.round((cases / population) * 100000 * 100) / 100
        };
    }).filter(Boolean);

    if (combinedRows.length < 2) return null;

    combinedRows.sort((left, right) => right.tasa_por_100k - left.tasa_por_100k);
    const targetRate = combinedRows.find(row => row.es_objetivo)?.tasa_por_100k;
    const rows = combinedRows.map((row, index) => ({
        ...row,
        posicion: index + 1,
        diferencia_tasa_objetivo: targetRate == null
            ? null
            : Math.round((row.tasa_por_100k - targetRate) * 100) / 100
    }));
    const cutoffs = [...new Set(items.map(item => item.territorial_comparison.cutoff).filter(Boolean))];

    return {
        delito: 'TOTAL_CONDUCTAS_PRIORIZADAS',
        label: `Total de conductas priorizadas (${items.length})`,
        isAggregate: true,
        hasMixedPeriods,
        period_end_month: hasMixedPeriods ? null : [...periodMonths][0],
        periodsByConducta: items.map(item => ({
            delito: item.delito,
            period_end_month: item.period_end_month || 12
        })),
        territorial_comparison: {
            rows,
            observed_municipalities: rows.length,
            expected_municipalities: Math.max(...items.map(item => item.territorial_comparison.expected_municipalities || 0)),
            cutoff: cutoffs.length === 1 ? cutoffs[0] : null
        }
    };
};
