const getApiBaseUrl = () => {
    const host = window.location.hostname;
    const protocol = window.location.protocol;
    
    // 1. Variable de entorno definida en build-time (Prioridad máxima)
    const envUrl = import.meta.env?.VITE_API_URL;
    
    // Si la envUrl es una ruta relativa (/api), la usamos directamente
    if (envUrl && envUrl.startsWith('/')) {
        console.log(`[API Config] Usando ruta relativa de entorno: ${envUrl}`);
        return envUrl;
    }

    // Si la envUrl es una URL completa (no localhost), la formateamos
    if (envUrl && !envUrl.includes('localhost')) {
        let url = envUrl.startsWith('http') ? envUrl : `https://${envUrl}`;
        if (!url.endsWith('/api')) url += '/api';
        console.log(`[API Config] Usando URL de entorno: ${url}`);
        return url;
    }

    // 2. Tunnels / Cloudflare / Proxies locales / IPs Privadas (Usar Proxy de Vite)
    if (
        host.includes('trycloudflare.com') || 
        host.includes('localhost') || 
        host.includes('127.0.0.1') ||
        host.startsWith('192.168.') || 
        host.startsWith('10.') || 
        host.startsWith('172.') ||
        host.endsWith('.local')
    ) {
        console.log(`[API Config] Entorno LOCAL detectado (${host}) -> Usando Proxy /api`);
        return '/api';
    }

    // 3. Render (producción)
    if (host.includes('onrender.com')) {
        return 'https://sisc-backend.onrender.com/api';
    }

    // 4. Codespaces
    if (host.includes('app.github.dev')) {
        const baseUrl = host.replace(/-\d+(?=\.app\.github\.dev)/, '-8000');
        return `https://${baseUrl}/api`;
    }

    // Fallback por defecto (Localhost directo)
    return 'http://localhost:8000/api';
};

export const API_BASE_URL = getApiBaseUrl();
