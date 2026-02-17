const getApiBaseUrl = () => {
    const host = window.location.hostname;

    // 1. Detectar si estamos en un túnel de Cloudflare (Prioridad máxima para acceso web)
    if (host.includes('trycloudflare.com')) {
        return '/api';
    }

    // 2. Detectar si estamos en Render (producción)
    if (host.includes('onrender.com')) {
        return 'https://sisc-backend.onrender.com';
    }

    // 3. Fallback para Codespaces
    if (host.includes('app.github.dev')) {
        const baseUrl = host.replace(/-\d+(?=\.app\.github\.dev)/, '-8000');
        return `https://${baseUrl}`;
    }

    // 4. Variable de entorno definida en build-time/docker (Si existe y no es localhost)
    const envUrl = import.meta.env?.VITE_API_URL;
    if (envUrl && !envUrl.includes('localhost')) {
        return envUrl.startsWith('http') ? envUrl : `https://${envUrl}`;
    }

    // 5. Localhost por defecto (Desarrollo local)
    return 'http://localhost:8000';
};

export const API_BASE_URL = getApiBaseUrl();
