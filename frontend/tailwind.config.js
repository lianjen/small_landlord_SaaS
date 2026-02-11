/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                primary: "#2563EB", // Royal Blue
                secondary: "#64748B", // Slate 500
                success: "#10B981", // Emerald 500
                danger: "#EF4444", // Red 500
                warning: "#F59E0B", // Amber 500
            },
        },
    },
    plugins: [],
}
