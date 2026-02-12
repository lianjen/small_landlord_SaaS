"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Bell, Wrench, Home } from "lucide-react";

const fadeUp = {
    hidden: { opacity: 0, y: 24 },
    visible: (i: number) => ({
        opacity: 1, y: 0,
        transition: { delay: i * 0.15, duration: 0.6, ease: "easeOut" }
    })
};

export default function LandingPage() {
    const features = [
        {
            icon: <ShieldCheck className="w-6 h-6" />,
            color: "text-sage-500",
            bg: "bg-sage-50",
            title: "安全透明",
            description: "合約與繳費紀錄清晰透明，隨時查閱，保障您的權益。"
        },
        {
            icon: <Bell className="w-6 h-6" />,
            color: "text-accent-400",
            bg: "bg-accent-50",
            title: "智慧提醒",
            description: "整合 LINE 自動通知，再也不怕忘記繳租，輕鬆管理信用。"
        },
        {
            icon: <Wrench className="w-6 h-6" />,
            color: "text-[#2C5F7F]",
            bg: "bg-[#EDF4F8]",
            title: "一鍵報修",
            description: "拍照上傳即刻報修，隨時掌握維修進度，生活不再延宕。"
        }
    ];

    return (
        <main className="min-h-screen bg-warm-100 flex flex-col items-center relative overflow-hidden">
            {/* 背景暈染裝飾 */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
                <div className="absolute -top-[15%] -left-[10%] w-[60vh] h-[60vh] rounded-full bg-sage-100/60 blur-[120px]" />
                <div className="absolute top-[50%] -right-[8%] w-[45vh] h-[45vh] rounded-full bg-accent-100/40 blur-[100px]" />
                <div className="absolute bottom-[5%] left-[20%] w-[30vh] h-[30vh] rounded-full bg-sage-200/30 blur-[80px]" />
            </div>

            {/* 導航列 */}
            <nav className="w-full max-w-6xl px-6 py-6 flex justify-between items-center z-10">
                <div className="flex items-center gap-2.5">
                    <div className="bg-sage-500 p-2 rounded-xl shadow-sm">
                        <Home className="text-white w-5 h-5" />
                    </div>
                    <span className="text-lg font-bold tracking-tight text-heading">MicroRent</span>
                </div>
                <Link
                    href="/login"
                    className="text-sm font-medium text-sage-700 hover:text-sage-500 transition-colors"
                >
                    登入 →
                </Link>
            </nav>

            {/* Hero 區塊 */}
            <div className="flex-1 w-full max-w-4xl px-6 flex flex-col items-center justify-center text-center z-10 pt-8 pb-16 md:pt-16 md:pb-24">
                <motion.div
                    initial="hidden"
                    animate="visible"
                    variants={{
                        visible: { transition: { staggerChildren: 0.12 } }
                    }}
                    className="flex flex-col items-center"
                >
                    {/* 標語膠囊 */}
                    <motion.span
                        variants={fadeUp}
                        custom={0}
                        className="inline-block px-4 py-1.5 mb-8 text-sm font-medium text-sage-700 bg-sage-100 rounded-pill"
                    >
                        🏠 小房東的理想租屋生活
                    </motion.span>

                    {/* 主標題 */}
                    <motion.h1
                        variants={fadeUp}
                        custom={1}
                        className="text-4xl md:text-6xl lg:text-7xl font-bold text-heading tracking-tight leading-[1.15] mb-6"
                    >
                        您的理想租屋生活
                        <br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-sage-500 to-sage-700">
                            從這裡化繁為簡
                        </span>
                    </motion.h1>

                    {/* 副文案 */}
                    <motion.p
                        variants={fadeUp}
                        custom={2}
                        className="max-w-xl mx-auto text-base md:text-lg text-secondary mb-10 leading-relaxed"
                    >
                        我們為您打造最順手、充滿質感的租務管理體驗。
                        <br className="hidden md:block" />
                        隨時掌握帳單、輕鬆報修，這才是現代房客該有的樣子。
                    </motion.p>

                    {/* CTA 按鈕組 */}
                    <motion.div
                        variants={fadeUp}
                        custom={3}
                        className="flex flex-col sm:flex-row items-center justify-center gap-4"
                    >
                        <Link
                            href="/login"
                            className="btn-primary w-full sm:w-auto px-10 py-4 text-base font-bold rounded-button group"
                        >
                            開始體驗
                            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                        </Link>
                        <button className="btn-secondary w-full sm:w-auto px-10 py-4 text-base">
                            了解更多
                        </button>
                    </motion.div>
                </motion.div>

                {/* 特色功能區 */}
                <motion.div
                    initial="hidden"
                    animate="visible"
                    variants={{
                        visible: { transition: { staggerChildren: 0.15, delayChildren: 0.5 } }
                    }}
                    className="mt-24 md:mt-32 grid grid-cols-1 md:grid-cols-3 gap-6 text-left w-full"
                >
                    {features.map((f, i) => (
                        <motion.div
                            key={i}
                            variants={fadeUp}
                            custom={i}
                            className="mr-card hover:shadow-float cursor-default"
                        >
                            <div className={`${f.bg} p-3 rounded-xl w-fit mb-5`}>
                                <div className={f.color}>{f.icon}</div>
                            </div>
                            <h3 className="text-lg font-bold text-heading mb-2">{f.title}</h3>
                            <p className="text-secondary leading-relaxed text-sm">
                                {f.description}
                            </p>
                        </motion.div>
                    ))}
                </motion.div>
            </div>

            {/* Footer */}
            <footer className="w-full py-10 px-6 text-center text-sm text-disabled z-10 border-t border-warm-200">
                <p>© 2026 MicroRent 租屋科技 · 讓管理更有溫度</p>
            </footer>
        </main>
    );
}
