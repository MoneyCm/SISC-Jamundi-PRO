import { API_BASE_URL } from './apiConfig';

const CACHE_KEY_PREFIX = 'sisc_public_dashboard_v3_rural_polygons';
const MAX_AGE_MS = 15 * 60 * 1000;

let memoryCache = {};
let pendingRequests = {};

const cacheKey = (minLocationCount) => {
    const normalized = Number.isFinite(Number(minLocationCount)) ? Number(minLocationCount) : 1;
    return `${CACHE_KEY_PREFIX}_min_${Math.max(1, Math.min(200, normalized))}`;
};

const readStoredEntry = (key) => {
    try {
        const raw = sessionStorage.getItem(key);
        if (!raw) return null;
        const entry = JSON.parse(raw);
        return entry?.data && entry?.savedAt ? entry : null;
    } catch {
        return null;
    }
};

export const getCachedPublicDashboard = (minLocationCount = 1) => {
    const key = cacheKey(minLocationCount);
    const entry = memoryCache[key] || readStoredEntry(key);
    if (!entry || Date.now() - entry.savedAt > MAX_AGE_MS) return null;
    memoryCache[key] = entry;
    return entry.data;
};

const saveDashboard = (data, minLocationCount = 1) => {
    const key = cacheKey(minLocationCount);
    const entry = { data, savedAt: Date.now() };
    memoryCache[key] = entry;
    try {
        sessionStorage.setItem(key, JSON.stringify(entry));
    } catch {
        // Memory cache remains available when storage is restricted.
    }
    return data;
};

export const loadPublicDashboard = async ({ force = false, minLocationCount = 1 } = {}) => {
    const threshold = Number.isFinite(Number(minLocationCount)) ? Number(minLocationCount) : 1;
    const normalizedMin = Math.max(1, Math.min(200, threshold));
    if (!force) {
        const cached = getCachedPublicDashboard(normalizedMin);
        if (cached) return cached;
    }
    const key = cacheKey(normalizedMin);
    if (pendingRequests[key]) return pendingRequests[key];

    const query = new URLSearchParams({ min_location_count: String(normalizedMin), map_schema: 'official_territory_polygons_v1' });
    pendingRequests[key] = fetch(`${API_BASE_URL}/analitica/public/dashboard?${query}`, {
        headers: { Accept: 'application/json' },
    })
        .then(async (response) => {
            if (!response.ok) throw new Error(`Servicio no disponible (${response.status})`);
            return saveDashboard(await response.json(), normalizedMin);
        })
        .finally(() => {
            pendingRequests[key] = null;
        });

    return pendingRequests[key];
};


