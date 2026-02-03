const API_URL = import.meta.env.PROD
    ? (import.meta.env.VITE_API_URL || 'https://sisc-backend.onrender.com')
    : 'http://localhost:8000';

export default API_URL;
