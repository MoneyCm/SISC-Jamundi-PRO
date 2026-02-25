const getApiBaseUrl = () => {
    const host = window.location.hostname;
    let url = 'http://localhost:8000/api'; // Por defecto con prefijo /api

    // 1. Variable de entorno definida en build-time
    const envUrl = import.meta.env?.VITE_API_URL;
    if (envUrl && !envUrl.includes('localhost')) {
        url = envUrl.startsWith('http') ? envUrl : `https://${envUrl}`;
        if (!url.endsWith('/api')) url += '/api';
    }
    // 2. Tunnels / Cloudflare / Proxies locales
    else if (host.includes('trycloudflare.com') || host.includes('localhost') || host.includes('127.0.0.1')) {
        // En desarrollo usamos el proxy de Vite que empieza por /api
        url = '/api';
    }
    // 3. Render (producción)
    else if (host.includes('onrender.com')) {
        url = 'https://sisc-backend.onrender.com/api';
    }
    // 4. Codespaces
    else if (host.includes('app.github.dev')) {
        const baseUrl = host.replace(/-\d+(?=\.app\.github\.dev)/, '-8000');
        url = `https://${baseUrl}/api`;
    }

    console.log(`[API Config] Host: ${host} -> Backend URL: ${url}`);
    return url;
};

export const API_BASE_URL = getApiBaseUrl();
