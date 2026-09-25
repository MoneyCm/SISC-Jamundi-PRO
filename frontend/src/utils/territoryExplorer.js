export function territoryKind(point) {
    const source = String(point.source || '').toLowerCase();
    if (source.includes('vereda') || ['cvc_catastro_veredas', 'igac_veredas'].includes(source)) return 'rural';
    if (source.startsWith('barrios_jamundi_valle')) return 'urban';
    return 'unknown';
}

export const searchTerritory = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

export function visibleTerritories(points, scope, query) {
    const search = searchTerritory(query);
    return points.filter((point) => (scope === 'all' || territoryKind(point) === scope)
        && searchTerritory([point.name, ...(point.aliases || [])].join(' ')).includes(search))
        .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name, 'es'));
}

export function reviewableTerritories(map) {
    return (map.unmapped_names || []).filter((item) => item.reason !== 'baja frecuencia' && Number(item.total) >= (map.min_location_count || 3));
}
