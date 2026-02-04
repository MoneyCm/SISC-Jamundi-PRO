const getApiBaseUrl = () => {
    const host = window.location.hostname;

    // 1. Prioridad: Variable de entorno definida en build-time
    const envUrl = import.meta.env?.VITE_API_URL;
    if (envUrl) return envUrl.startsWith('http') ? envUrl : `https://${envUrl}`;

    // 2. Detectar si estamos en Render (frontend)
    if (host.includes('onrender.com')) {
        return 'https://sisc-backend.onrender.com';
    }

    // 3. Fallback para Codespaces
    if (host.includes('app.github.dev')) {
        const baseUrl = host.replace(/-\d+(?=\.app\.github\.dev)/, '-8000');
        return `https://${baseUrl}`;
    }

    // Localhost por defecto
    return 'http://localhost:8000';
};

export const API_BASE_URL = getApiBaseUrl();
