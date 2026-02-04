/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
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
