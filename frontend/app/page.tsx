```javascript
"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Bell, PenTool, LayoutDashboard } from "lucide-react";

export default function Home() {
    const features = [
        {
            icon: <ShieldCheck className="w-6 h-6 text-indigo-500" />,
            title: "安全透明",
            description: "合約與繳費紀錄清晰透明，隨時查閱，保障您的權益。"
        },
        {
            icon: <Bell className="w-6 h-6 text-emerald-500" />,
            title: "收租提醒",
            description: "整合 LINE 自動通知，再也不怕忘記繳租，輕鬆管理信用。"
        },
        {
            icon: <PenTool className="w-6 h-6 text-blue-500" />,
            title: "一鍵報修",
            description: "拍照上傳即刻報修，隨時掌握維修進度，生活不再延宕。"
        }
    ];

    return (
        <main className="min-h-screen bg-[#F9FAFB] flex flex-col items-center relative overflow-hidden">
            {/* 背景裝飾 */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
                <div className="absolute -top-[10%] -left-[5%] w-[50vh] h-[50vh] rounded-full bg-indigo-100/50 blur-[100px]" />
                <div className="absolute top-[40%] -right-[5%] w-[40vh] h-[40vh] rounded-full bg-blue-100/40 blur-[100px]" />
            </div>

            {/* Header / Logo */}
            <nav className="w-full max-w-7xl px-6 py-8 flex justify-between items-center z-10">
                <div className="flex items-center gap-2">
                    <div className="bg-indigo-600 p-2 rounded-xl">
                        <LayoutDashboard className="text-white w-6 h-6" />
                    </div>
                    <span className="text-xl font-bold tracking-tight text-gray-900">MicroRent</span>
                </div>
            </nav>

            {/* Hero Section */}
            <div className="flex-1 w-full max-w-5xl px-6 flex flex-col items-center justify-center text-center z-10 pt-10 pb-20">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    <span className="inline-block px-4 py-1.5 mb-6 text-sm font-semibold text-indigo-600 bg-indigo-50 rounded-full">
                        MicroRent 房客端專屬入口
                    </span>
                    <h1 className="text-5xl md:text-7xl font-extrabold text-gray-900 tracking-tight leading-[1.1] mb-8">
                        您的理想租屋生活<br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-blue-500">
                            從這裡化繁為簡
                        </span>
                    </h1>
                    <p className="max-w-2xl mx-auto text-lg md:text-xl text-gray-500 mb-12 leading-relaxed">
                        我們為您打造了最順手、且充滿質感的租務管理體驗。<br />
                        隨時掌握帳單、輕鬆報修，這才是現代房客該有的樣子。
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link
                            href="/login"
                            className="w-full sm:w-auto px-10 py-4 bg-indigo-600 text-white font-bold rounded-2xl hover:bg-slate-900 transition-all duration-300 shadow-xl shadow-indigo-200 flex items-center justify-center gap-2 group"
                        >
                            房客登入體驗
                            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                        </Link>
                        <button className="w-full sm:w-auto px-10 py-4 bg-white text-gray-700 font-semibold rounded-2xl border border-gray-200 hover:border-gray-300 transition-all duration-300">
                            了解更多
                        </button>
                    </div>
                </motion.div>

                {/* Features Grid */}
                <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4, duration: 0.8 }}
                    className="mt-32 grid grid-cols-1 md:grid-cols-3 gap-8 text-left"
                >
                    {features.map((f, i) => (
                        <div key={i} className="bg-white/60 backdrop-blur-sm p-8 rounded-3xl border border-white shadow-sm hover:shadow-md transition-all duration-300">
                            <div className="bg-white p-3 rounded-2xl shadow-sm w-fit mb-6 border border-gray-50">
                                {f.icon}
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 mb-3">{f.title}</h3>
                            <p className="text-gray-500 leading-relaxed text-sm">
                                {f.description}
                            </p>
                        </div>
                    ))}
                </motion.div>
            </div>

            {/* Footer */}
            <footer className="w-full py-12 px-6 text-center text-sm text-gray-400 z-10 border-t border-gray-100">
                <p>© 2026 MicroRent 租屋科技. 讓管理更有溫度。</p>
            </footer>
        </main>
    );
}
```
