const API_URL = import.meta.env.PROD
    ? 'https://sisc-jamundi-backend.onrender.com' // Cambia esto por la URL real de tu backend en Render
    : 'http://localhost:8000';

export default API_URL;
