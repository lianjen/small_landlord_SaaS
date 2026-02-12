import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "MicroRent — 您的理想租屋生活",
    description: "小房東的智慧租屋管家。輕鬆查詢租金、一鍵報修、LINE 自動提醒，讓管理更有溫度。",
    manifest: "/manifest.json",
};

export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="zh-TW">
            <body>{children}</body>
        </html>
    );
}
