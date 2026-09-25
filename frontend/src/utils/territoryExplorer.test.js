import test from 'node:test';
import assert from 'node:assert/strict';
import { territoryKind, visibleTerritories, reviewableTerritories } from './territoryExplorer.js';
test('scope follows cartography, not incident zone or polygon size', () => {
    assert.equal(territoryKind({ source: 'barrios_jamundi_valle_extra.geojson', zones: ['RURAL'] }), 'urban');
    assert.equal(territoryKind({ source: 'veredas_jamundi_oficial.geojson' }), 'rural');
    assert.equal(territoryKind({ source: 'IGAC_VEREDAS' }), 'rural');
    assert.equal(territoryKind({ source: 'other', zones: ['URBANA'] }), 'unknown');
});
test('search resolves accents and aliases within scope', () => {
    const points = [{ name: 'Belalcázar', aliases: ['Anterior'], total: 3, source: 'barrios_jamundi_valle.geojson' }];
    assert.equal(visibleTerritories(points, 'urban', 'belalcazar').length, 1);
    assert.equal(visibleTerritories(points, 'all', 'anterior').length, 1);
    assert.equal(visibleTerritories(points, 'rural', '').length, 0);
});
test('review and export do not disclose suppressed territories', () => {
    const map = { min_location_count: 3, unmapped_names: [{ name: 'Hidden', total: 2, reason: 'baja frecuencia' }, { name: 'Hidden too', total: 1 }, { name: 'Review', total: 4, reason: 'sin polígono' }] };
    assert.deepEqual(reviewableTerritories(map).map((item) => item.name), ['Review']);
});
