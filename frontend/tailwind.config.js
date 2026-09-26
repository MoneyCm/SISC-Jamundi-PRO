/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                'primary-deep': '#281FD0',
                'primary-vibrant': '#384CF5',
                'accent-yellow': '#FFE000',
                'dark-gray': '#3A3A44',
                'slate-blue': '#606175',
                'light-slate': '#C5C5D2',
                'police-blue': '#0E2442',
                'police-green': '#2B7A4B',
                'police-accent': '#DAA520',
                'ui-bg': '#0b0c15',
                'ui-panel-bg': 'rgba(20,22,41,0.75)',
                'ui-border': 'rgba(255,255,255,0.08)',
                'ui-text-primary': '#f1f3f9',
                'ui-text-secondary': '#9ea4b8',
                'ui-accent': '#384CF5',
                'ui-card-bg': 'rgba(30,33,61,0.45)',
                primary: "#281FD0",    /* Azul Institucional */
                secondary: "#384CF5",  /* Azul Secundario */
                accent: "#FFB600",     /* Oro/Naranja acento */
                jamundi_yellow: "#FFE000", /* Amarillo Institucional */
                neutral: "#3A3A44",    /* Gris Oscuro Institucional */
                background: "#F2F4F7", /* Fondo */
                surface: "#ffffff",
            },
            fontFamily: {
                sans: ['Calibri', 'sans-serif'],
            }
        },
    },
    plugins: [],
}
