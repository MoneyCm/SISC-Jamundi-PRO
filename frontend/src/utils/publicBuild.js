// Build del portal ciudadano: VITE_PUBLIC_ONLY=true al compilar.
// Sin login, sin botón "Ingreso institucional" y sin páginas internas.
export const PUBLIC_ONLY = import.meta.env?.VITE_PUBLIC_ONLY === 'true';
