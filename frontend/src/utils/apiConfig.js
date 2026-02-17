const getApiBaseUrl = () => {
    const host = window.location.hostname;
    let url = 'http://localhost:8000'; // Default

    // 1. Variable de entorno definida en build-time (Prioridad máxima en despliegue)
    const envUrl = import.meta.env?.VITE_API_URL;
    if (envUrl && !envUrl.includes('localhost')) {
        url = envUrl.startsWith('http') ? envUrl : `https://${envUrl}`;
    }
    // 2. Detectar si estamos en un túnel de Cloudflare
    else if (host.includes('trycloudflare.com')) {
        url = '/api';
    }
    // 3. Detectar si estamos en Render (producción) - Intento inteligente
    else if (host.includes('onrender.com')) {
        // Intentamos adivinar el nombre basándonos en el frontend, 
        // pero preferimos sisc-backend por defecto.
        url = 'https://sisc-backend.onrender.com';
    }
    // 4. Fallback para Codespaces
    else if (host.includes('app.github.dev')) {
        const baseUrl = host.replace(/-\d+(?=\.app\.github\.dev)/, '-8000');
        url = `https://${baseUrl}`;
    }

    console.log(`[API Config] Host: ${host} -> Backend URL: ${url}`);
    return url;
};

export const API_BASE_URL = getApiBaseUrl();
