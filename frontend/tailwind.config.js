/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                // 鼠尾草綠系 (Sage Green Palette)
                sage: {
                    50: '#F5F7F5',
                    100: '#E8EDE8',
                    200: '#D0DBD0',
                    300: '#B5D4B3',
                    400: '#9DBF9B',
                    500: '#8BA888', // 主色
                    600: '#7A9777',
                    700: '#5F7A5C',
                    800: '#4A5F48',
                    900: '#3D4D3B',
                },
                // CTA / 強調色
                accent: {
                    50: '#FDF8F3',
                    100: '#F9EDE0',
                    200: '#F0D8BF',
                    300: '#E5C09A',
                    400: '#D4A574', // 主 CTA
                    500: '#C89560',
                    600: '#B07D4A',
                    700: '#8F6438',
                    800: '#6E4D2C',
                    900: '#4D3620',
                },
                // 暖色背景
                warm: {
                    50: '#FAF8F5',
                    100: '#F7F6F3',
                    200: '#F0EFEC',
                    300: '#E0DDD8',
                },
                // 功能狀態色（低飽和版）
                success: '#A8D5BA',
                warning: '#FFD7A1',
                danger: '#FFBDAD',
                info: '#B3D4E5',
                // 文字色系
                heading: '#2A2A2A',
                body: '#4A4A4A',
                secondary: '#7A7A7A',
                disabled: '#AFAFAF',
            },
            borderRadius: {
                'card': '16px',
                'button': '12px',
                'pill': '9999px',
            },
            boxShadow: {
                'soft': '0 4px 20px rgba(0, 0, 0, 0.06)',
                'card': '0 2px 12px rgba(0, 0, 0, 0.08)',
                'float': '0 8px 24px rgba(0, 0, 0, 0.12)',
                'neu': '8px 8px 16px rgba(163, 177, 198, 0.15), -8px -8px 16px rgba(255, 255, 255, 0.8)',
            },
            fontFamily: {
                sans: ['"Noto Sans TC"', '"Inter"', 'system-ui', 'sans-serif'],
                display: ['"Inter"', '"DM Sans"', 'sans-serif'],
            },
        },
    },
    plugins: [],
}
