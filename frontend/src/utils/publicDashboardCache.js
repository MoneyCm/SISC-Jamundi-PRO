import { API_BASE_URL } from './apiConfig';

const CACHE_KEY = 'sisc_public_dashboard_v2_polygons';
const MAX_AGE_MS = 15 * 60 * 1000;

let memoryEntry = null;
let pendingRequest = null;

const readStoredEntry = () => {
    try {
        const raw = sessionStorage.getItem(CACHE_KEY);
        if (!raw) return null;
        const entry = JSON.parse(raw);
        return entry?.data && entry?.savedAt ? entry : null;
    } catch {
        return null;
    }
};

export const getCachedPublicDashboard = () => {
    const entry = memoryEntry || readStoredEntry();
    if (!entry || Date.now() - entry.savedAt > MAX_AGE_MS) return null;
    memoryEntry = entry;
    return entry.data;
};

const saveDashboard = (data) => {
    const entry = { data, savedAt: Date.now() };
    memoryEntry = entry;
    try {
        sessionStorage.setItem(CACHE_KEY, JSON.stringify(entry));
    } catch {
        // Memory cache remains available when storage is restricted.
    }
    return data;
};

export const loadPublicDashboard = async ({ force = false } = {}) => {
    if (!force) {
        const cached = getCachedPublicDashboard();
        if (cached) return cached;
    }
    if (pendingRequest) return pendingRequest;

    pendingRequest = fetch(`${API_BASE_URL}/analitica/public/dashboard`, {
        headers: { Accept: 'application/json' },
    })
        .then(async (response) => {
            if (!response.ok) throw new Error(`Servicio no disponible (${response.status})`);
            return saveDashboard(await response.json());
        })
        .finally(() => {
            pendingRequest = null;
        });

    return pendingRequest;
};
