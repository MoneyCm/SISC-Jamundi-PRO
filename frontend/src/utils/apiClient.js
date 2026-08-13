import { API_BASE_URL } from './apiConfig';

export const SESSION_EXPIRED_EVENT = 'sisc:session-expired';

export class ApiError extends Error {
    constructor(message, status, payload = null) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.payload = payload;
    }
}

const resolveUrl = (endpoint) => {
    if (/^https?:\/\//i.test(endpoint)) return endpoint;
    const base = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL;
    const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${base}${path}`;
};

export const clearStoredSession = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userRoles');
    localStorage.removeItem('dataLevel');
};

export const apiFetch = async (endpoint, options = {}) => {
    const headers = new Headers(options.headers || {});
    const token = localStorage.getItem('token');
    if (token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await fetch(resolveUrl(endpoint), { ...options, headers });
    if (response.status === 401 && options.signalSessionExpiry !== false) {
        window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    }
    return response;
};

export const readApiError = async (response, fallback = 'No fue posible completar la solicitud.') => {
    try {
        const payload = await response.json();
        return payload?.detail || payload?.message || fallback;
    } catch {
        return fallback;
    }
};

export const apiJson = async (endpoint, options = {}) => {
    const response = await apiFetch(endpoint, options);
    if (!response.ok) {
        const message = await readApiError(response);
        throw new ApiError(message, response.status);
    }
    if (response.status === 204) return null;
    return response.json();
};
