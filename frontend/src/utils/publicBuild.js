// Build del portal ciudadano: VITE_PUBLIC_ONLY=true al compilar.
// Sin login, sin botón "Ingreso institucional" y sin páginas internas.
export const PUBLIC_ONLY = import.meta.env?.VITE_PUBLIC_ONLY === 'true';
// Formularios ciudadanos (reporte seguro, frentes, propuestas): solo si el backend público acepta escrituras.
export const PUBLIC_FORMS = !PUBLIC_ONLY || import.meta.env?.VITE_PUBLIC_FORMS === 'true';
