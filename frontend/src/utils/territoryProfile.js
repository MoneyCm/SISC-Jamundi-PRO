// Ficha territorial: búsqueda sin tildes y lectura de cambios con la regla de base pequeña.

export const searchText = (value) => String(value || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

export const formatChange = (cell) => {
    if (cell.variation_pct === null || cell.variation_pct === undefined) {
        const diff = cell.difference || 0;
        if (!diff) return 'igual';
        return `${diff > 0 ? '+' : ''}${diff} ${Math.abs(diff) === 1 ? 'hecho' : 'hechos'}`;
    }
    return `${cell.variation_pct > 0 ? '+' : ''}${String(cell.variation_pct).replace('.', ',')}%`;
};
