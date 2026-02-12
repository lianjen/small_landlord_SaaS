/** @type {import('next').NextConfig} */
const nextConfig = {
    // 只有在環境變數 EXPORT=1 時才啟用靜態導出 (為了 Capacitor)
    // Vercel 部署時預設為標準模式 (動態模式)
    output: process.env.EXPORT === '1' ? 'export' : undefined,
    images: {
        unoptimized: true,
    },
}

module.exports = nextConfig
