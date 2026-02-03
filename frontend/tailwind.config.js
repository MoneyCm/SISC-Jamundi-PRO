/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                primary: "#AF8254", // Driftwood
                secondary: "#85A3E1", // Chetwode Blue
                accent: "#FFB600", // Yellow
                neutral: "#606175", // Grey text
                background: "#f8fafc", // Slate 50
                surface: "#ffffff",
            },
            fontFamily: {
                sans: ['Calibri', 'sans-serif'],
            }
        },
    },
    plugins: [],
}
