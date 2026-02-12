"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { KeyRound, Mail, ArrowRight, Loader2, Home } from "lucide-react";
import { login } from "@/lib/api";

const fadeUp = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } }
};

export default function TenantLogin() {
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError("");

        const formData = new FormData(e.target as HTMLFormElement);
        const email = formData.get("email") as string;
        const password = formData.get("passcode") as string;

        try {
            await login(email, password);
            router.push("/(tenant)/dashboard");
        } catch (err: any) {
            setError(err.message || "登入失敗，請檢查帳號密碼");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-warm-100 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
            {/* 背景暈染 */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
                <div className="absolute -top-[20%] -right-[10%] w-[60vh] h-[60vh] rounded-full bg-sage-100/50 blur-[120px]" />
                <div className="absolute top-[30%] -left-[10%] w-[50vh] h-[50vh] rounded-full bg-accent-100/30 blur-[100px]" />
            </div>

            <motion.div
                initial="hidden"
                animate="visible"
                variants={{
                    visible: { transition: { staggerChildren: 0.1 } }
                }}
                className="max-w-md w-full space-y-8 z-10"
            >
                {/* Logo 與標題 */}
                <motion.div variants={fadeUp} className="text-center">
                    <Link href="/" className="inline-flex items-center gap-2 mb-6 group">
                        <div className="bg-sage-500 p-2 rounded-xl shadow-sm group-hover:shadow-md transition-shadow">
                            <Home className="text-white w-5 h-5" />
                        </div>
                        <span className="text-lg font-bold tracking-tight text-heading">MicroRent</span>
                    </Link>
                    <h2 className="text-2xl font-bold text-heading tracking-tight">
                        歡迎回來
                    </h2>
                    <p className="mt-2 text-sm text-secondary">
                        房客專屬入口 — 查收帳單、輕鬆報修
                    </p>
                </motion.div>

                {/* 錯誤提示 */}
                {error && (
                    <motion.div
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="badge-danger px-4 py-3 rounded-button text-sm"
                    >
                        {error}
                    </motion.div>
                )}

                {/* 登入卡片 */}
                <motion.div
                    variants={fadeUp}
                    className="mr-card !p-8"
                >
                    <form className="space-y-5" onSubmit={handleSubmit}>
                        {/* Email 輸入 */}
                        <div>
                            <label htmlFor="email" className="block text-sm font-medium text-heading mb-1.5">
                                電子信箱
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                                    <Mail className="h-5 w-5 text-disabled" />
                                </div>
                                <input
                                    id="email"
                                    name="email"
                                    type="email"
                                    autoComplete="email"
                                    required
                                    className="input-field pl-11"
                                    placeholder="請輸入您的 Email"
                                />
                            </div>
                        </div>

                        {/* 通行碼輸入 */}
                        <div>
                            <label htmlFor="passcode" className="block text-sm font-medium text-heading mb-1.5">
                                通行碼
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                                    <KeyRound className="h-5 w-5 text-disabled" />
                                </div>
                                <input
                                    id="passcode"
                                    name="passcode"
                                    type="password"
                                    required
                                    className="input-field pl-11"
                                    placeholder="由房東提供的通行碼"
                                />
                            </div>
                        </div>

                        {/* 登入按鈕 */}
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="btn-primary w-full py-3.5 text-base font-bold group disabled:opacity-60 disabled:cursor-not-allowed"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="animate-spin h-5 w-5" />
                                    驗證中...
                                </>
                            ) : (
                                <>
                                    登入
                                    <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </button>
                    </form>

                    {/* 分隔線 */}
                    <div className="mt-6">
                        <div className="relative">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-warm-300" />
                            </div>
                            <div className="relative flex justify-center text-sm">
                                <span className="px-3 bg-white text-disabled">
                                    或者
                                </span>
                            </div>
                        </div>

                        {/* LINE 登入 */}
                        <div className="mt-6">
                            <button
                                type="button"
                                className="w-full inline-flex justify-center items-center gap-2 py-3.5 px-4 border-2 border-warm-300 rounded-button bg-white text-sm font-medium text-body hover:border-sage-300 hover:bg-sage-50 transition-all"
                            >
                                <span className="text-[#06C755] font-bold text-base">LINE</span>
                                <span>快速登入</span>
                            </button>
                        </div>
                    </div>
                </motion.div>

                {/* 底部 */}
                <motion.p variants={fadeUp} className="text-center text-sm text-disabled">
                    遇到問題？請聯繫您的房東取得協助
                </motion.p>
            </motion.div>
        </div>
    );
}
