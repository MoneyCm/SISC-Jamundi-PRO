// Build del portal ciudadano: VITE_PUBLIC_ONLY=true al compilar.
// Sin login, sin botón "Ingreso institucional" y sin páginas internas.
export const PUBLIC_ONLY = import.meta.env?.VITE_PUBLIC_ONLY === 'true';
// Generador de "SISC en cifras" y archivo de boletines: herramientas de la oficina. En el portal
// público no se muestran, porque la página ya presenta las cifras al día.
export const HIDDEN_PUBLIC_PAGES = PUBLIC_ONLY ? ['sisc-cifras', 'technical-bulletins'] : [];

// Formularios ciudadanos (reporte seguro, frentes, propuestas): solo si el backend público acepta escrituras.
export const PUBLIC_FORMS = !PUBLIC_ONLY || import.meta.env?.VITE_PUBLIC_FORMS === 'true';
