const getApiBaseUrl = () => {
    const host = window.location.hostname;

    // Detectar si estamos en Codespaces (ej: legend-space-trout-r7qp6wr7v562p47j-5173.app.github.dev)
    if (host.includes('app.github.dev')) {
        // Reemplaza el sufijo de puerto (como -5173, -3000) por -8000 para el backend
        const baseUrl = host.replace(/-\d+(?=\.app\.github\.dev)/, '-8000');
        return `https://${baseUrl}`;
    }

    // Detectar si estamos en Render (frontend)
    if (host.includes('onrender.com')) {
        return 'https://sisc-backend.onrender.com';
    }

    // Localhost por defecto
    return 'http://localhost:8000';
};

export const API_BASE_URL = getApiBaseUrl();
