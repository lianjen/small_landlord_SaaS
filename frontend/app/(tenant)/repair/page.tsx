"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Camera, Send, ArrowLeft, X } from "lucide-react";
import Link from "next/link";

export default function RepairRequest() {
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [previewUrls, setPreviewUrls] = useState<string[]>([]);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || []);

        if (files.length + selectedFiles.length > 5) {
            alert("最多只能上傳 5 張照片");
            return;
        }

        setSelectedFiles([...selectedFiles, ...files]);

        files.forEach(file => {
            const reader = new FileReader();
            reader.onloadend = () => {
                setPreviewUrls(prev => [...prev, reader.result as string]);
            };
            reader.readAsDataURL(file);
        });
    };

    const removeImage = (index: number) => {
        setSelectedFiles(selectedFiles.filter((_, i) => i !== index));
        setPreviewUrls(previewUrls.filter((_, i) => i !== index));
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setIsSubmitting(true);

        const formData = new FormData(e.currentTarget);

        selectedFiles.forEach(file => {
            formData.append("images", file);
        });

        try {
            const response = await fetch("http://localhost:8000/api/repair/create", {
                method: "POST",
                body: formData,
            });

            if (response.ok) {
                alert("✅ 維修申請已提交");
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
                    <h1 className="text-2xl font-bold text-gray-900">報修申請</h1>
                    <p className="text-sm text-gray-500 mt-1">拍照描述問題，我們會盡快處理</p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-6 space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            問題標題
                        </label>
                        <input
                            type="text"
                            name="title"
                            required
                            placeholder="例如：廁所水龍頭漏水"
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            問題類型
                        </label>
                        <select
                            name="category"
                            required
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="plumbing">水電問題</option>
                            <option value="electrical">電器故障</option>
                            <option value="furniture">家具損壞</option>
                            <option value="other">其他</option>
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            問題描述
                        </label>
                        <textarea
                            name="description"
                            required
                            rows={4}
                            placeholder="請詳細描述問題狀況..."
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>

                    {/* Image Upload */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            現場照片 (最多 5 張)
                        </label>

                        {previewUrls.length > 0 && (
                            <div className="grid grid-cols-2 gap-4 mb-4">
                                {previewUrls.map((url, index) => (
                                    <div key={index} className="relative">
                                        <img src={url} alt={`Preview ${index + 1}`} className="w-full h-32 object-cover rounded-lg" />
                                        <button
                                            type="button"
                                            onClick={() => removeImage(index)}
                                            className="absolute top-2 right-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600"
                                        >
                                            <X className="h-4 w-4" />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}

                        {previewUrls.length < 5 && (
                            <label className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-400 transition-colors cursor-pointer block">
                                <Camera className="mx-auto h-12 w-12 text-gray-400" />
                                <p className="mt-2 text-sm text-gray-600">點擊拍照或選擇照片</p>
                                <p className="text-xs text-gray-400 mt-1">已選擇 {previewUrls.length} / 5 張</p>
                                <input
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    onChange={handleFileSelect}
                                    className="hidden"
                                />
                            </label>
                        )}
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
                                <Send className="h-5 w-5" />
                                提交報修申請
                            </>
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
}
