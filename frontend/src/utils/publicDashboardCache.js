import { API_BASE_URL } from './apiConfig';

const CACHE_KEY_PREFIX = 'sisc_public_dashboard_v5_normalized_territories';
const MAX_AGE_MS = 10 * 60 * 1000;

let memoryCache = {};
let pendingRequests = {};

const normalizeOptions = (input = {}) => {
    const source = typeof input === 'number' ? { minLocationCount: input } : input || {};
    const threshold = Number.isFinite(Number(source.minLocationCount)) ? Number(source.minLocationCount) : 3;
    return {
        minLocationCount: Math.max(1, Math.min(200, threshold)),
        includeMap: source.includeMap !== false,
        year: source.year || '',
        periodMode: source.periodMode || 'year_to_date',
        comparison: source.comparison || 'same_period_previous_year',
        startDate: source.startDate || '',
        endDate: source.endDate || '',
        conducta: source.conducta || '',
        zona: source.zona || '',
        territorio: source.territorio || '',
    };
};

const cacheKey = (input) => {
    const options = normalizeOptions(input);
    return `${CACHE_KEY_PREFIX}_${Object.entries(options).map(([key, value]) => `${key}:${value}`).join('|')}`;
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

export const getCachedPublicDashboard = (input = {}) => {
    const key = cacheKey(input);
    const entry = memoryCache[key] || readStoredEntry(key);
    if (!entry || Date.now() - entry.savedAt > MAX_AGE_MS) return null;
    memoryCache[key] = entry;
    return entry.data;
};

const saveDashboard = (data, input) => {
    const key = cacheKey(input);
    const entry = { data, savedAt: Date.now() };
    memoryCache[key] = entry;
    try {
        sessionStorage.setItem(key, JSON.stringify(entry));
    } catch {
        // The in-memory cache remains available when storage is restricted.
    }
    return data;
};

const buildQuery = (options) => {
    const query = new URLSearchParams({
        min_location_count: String(options.minLocationCount),
        include_map: String(options.includeMap),
        period_mode: options.periodMode,
        comparison: options.comparison,
    });
    const optional = {
        year: options.year,
        start_date: options.startDate,
        end_date: options.endDate,
        conducta: options.conducta,
        zona: options.zona,
        territorio: options.territorio,
    };
    Object.entries(optional).forEach(([key, value]) => {
        if (value !== '' && value !== null && value !== undefined) query.set(key, String(value));
    });
    return query;
};

export const loadPublicDashboard = async ({ force = false, ...input } = {}) => {
    const options = normalizeOptions(input);
    if (!force) {
        const cached = getCachedPublicDashboard(options);
        if (cached) return cached;
    }
    const key = cacheKey(options);
    if (pendingRequests[key]) return pendingRequests[key];

    pendingRequests[key] = fetch(`${API_BASE_URL}/analitica/public/dashboard?${buildQuery(options)}`, {
        headers: { Accept: 'application/json' },
        cache: force ? 'no-store' : 'default',
    })
        .then(async (response) => {
            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                throw new Error(payload?.detail || `Servicio no disponible (${response.status})`);
            }
            return saveDashboard(await response.json(), options);
        })
        .finally(() => {
            delete pendingRequests[key];
        });

    return pendingRequests[key];
};
