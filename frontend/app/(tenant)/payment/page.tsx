"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, CheckCircle2, AlertCircle, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function PaymentSubmit() {
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setSelectedFile(file);
            const reader = new FileReader();
            reader.onloadend = () => {
                setPreviewUrl(reader.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setIsSubmitting(true);

        const formData = new FormData(e.currentTarget);

        if (selectedFile) {
            formData.append("receipt_image", selectedFile);
        }

        try {
            const response = await fetch("http://localhost:8000/api/payment/submit", {
                method: "POST",
                body: formData,
            });

            if (response.ok) {
                alert("✅ 繳費記錄已提交，請等待房東確認");
                router.push("/(tenant)/dashboard");
            } else {
                alert("❌ 提交失敗，請稍後再試");
            }
        } catch (error) {
            alert("❌ 網路錯誤，請檢查連線");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="max-w-2xl mx-auto px-4">
                {/* Header */}
                <div className="mb-6">
                    <Link href="/(tenant)/dashboard" className="inline-flex items-center text-blue-600 hover:text-blue-700 mb-4">
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        返回首頁
                    </Link>
                    <h1 className="text-2xl font-bold text-gray-900">繳費回報</h1>
                    <p className="text-sm text-gray-500 mt-1">上傳您的轉帳證明，讓房東確認收款</p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-6 space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            繳費金額 (NT$)
                        </label>
                        <input
                            type="number"
                            name="amount"
                            required
                            defaultValue={15000}
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            繳費日期
                        </label>
                        <input
                            type="date"
                            name="payment_date"
                            required
                            defaultValue={new Date().toISOString().split('T')[0]}
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            繳費方式
                        </label>
                        <select
                            name="payment_method"
                            required
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="bank_transfer">銀行轉帳</option>
                            <option value="atm">ATM 轉帳</option>
                            <option value="cash">現金</option>
                            <option value="line_pay">LINE Pay</option>
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            備註（選填）
                        </label>
                        <textarea
                            name="note"
                            rows={3}
                            placeholder="例如：帳號末五碼 12345"
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>

                    {/* File Upload */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            轉帳證明 (建議上傳)
                        </label>
                        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-400 transition-colors">
                            {previewUrl ? (
                                <div className="space-y-4">
                                    <img src={previewUrl} alt="Preview" className="mx-auto max-h-64 rounded-lg" />
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setSelectedFile(null);
                                            setPreviewUrl(null);
                                        }}
                                        className="text-sm text-red-600 hover:text-red-700"
                                    >
                                        移除圖片
                                    </button>
                                </div>
                            ) : (
                                <label className="cursor-pointer">
                                    <Upload className="mx-auto h-12 w-12 text-gray-400" />
                                    <p className="mt-2 text-sm text-gray-600">點擊上傳截圖</p>
                                    <input
                                        type="file"
                                        accept="image/*"
                                        onChange={handleFileSelect}
                                        className="hidden"
                                    />
                                </label>
                            )}
                        </div>
                    </div>

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors flex items-center justify-center gap-2"
                    >
                        {isSubmitting ? (
                            <>
                                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                                提交中...
                            </>
                        ) : (
                            <>
                                <CheckCircle2 className="h-5 w-5" />
                                提交繳費記錄
                            </>
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
}
