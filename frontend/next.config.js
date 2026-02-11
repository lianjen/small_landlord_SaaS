/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'export',  // 啟用靜態輸出，這是 Capacitor App 的必要設定
    images: {
        unoptimized: true, // App 環境不支援 Next.js Image Optimization Server
    },
}

module.exports = nextConfig
