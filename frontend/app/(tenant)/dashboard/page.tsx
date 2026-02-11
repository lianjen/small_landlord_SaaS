"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { getTenantInfo, getPaymentHistory, type TenantInfo, type PaymentRecord } from "@/lib/api";
import { Home, Calendar, CreditCard, AlertCircle, CheckCircle2, Clock } from "lucide-react";

export default function TenantDashboard() {
    const router = useRouter(); // Initialized useRouter
    const [tenant, setTenant] = useState<TenantInfo | null>(null);
    const [payments, setPayments] = useState<PaymentRecord[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // 檢查是否已登入
        const token = localStorage.getItem("microrent_access_token");
        if (!token) {
            router.push("/(tenant)/login");
            return;
        }

        // 載入資料
        Promise.all([
            getTenantInfo(),
            getPaymentHistory()
        ]).then(([tenantData, paymentData]) => {
            setTenant(tenantData);
            setPayments(paymentData);
            setIsLoading(false);
        }).catch(error => {
            console.error("Failed to load data:", error);
            // 若是 401 會在 api.ts 被攔截轉址，這裡是處理其他錯誤
            setIsLoading(false);
        });
    }, [router]); // Added router to dependency array

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    if (!tenant) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <p className="text-red-500">載入失敗，請稍後再試</p>
            </div>
        );
    }

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "paid":
                return (
                    <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        <CheckCircle2 className="h-3 w-3" />
                        已繳納
                    </span>
                );
            case "unpaid":
                return (
                    <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                        <Clock className="h-3 w-3" />
                        待繳納
                    </span>
                );
            case "overdue":
                return (
                    <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        <AlertCircle className="h-3 w-3" />
                        逾期
                    </span>
                );
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
            {/* Header */}
            <div className="bg-white shadow-sm border-b border-gray-200">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900">您好，{tenant.name}</h1>
                            <p className="text-sm text-gray-500 mt-1">{tenant.property_name} - {tenant.room_number}</p>
                        </div>
                        <div className="flex items-center gap-2">
                            <Home className="h-5 w-5 text-blue-600" />
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    {/* 租金狀態卡片 */}
                    <div className="bg-white rounded-2xl shadow-lg shadow-blue-900/5 p-6 border border-gray-100">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-semibold text-gray-900">本月租金</h2>
                            {getStatusBadge(tenant.payment_status)}
                        </div>
                        <div className="space-y-4">
                            <div>
                                <p className="text-sm text-gray-500">應繳金額</p>
                                <p className="text-3xl font-bold text-gray-900">
                                    ${tenant.rent_amount.toLocaleString()}
                                </p>
                            </div>
                            <div className="flex items-center gap-2 text-sm text-gray-600">
                                <Calendar className="h-4 w-4" />
                                繳費期限：{new Date(tenant.rent_due_date).toLocaleDateString('zh-TW')}
                            </div>
                            {tenant.payment_status === "unpaid" && (
                                <>
                                    <Link
                                        href="/(tenant)/payment"
                                        className="w-full mt-4 bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 transition-colors font-medium block text-center"
                                    >
                                        立即繳費
                                    </Link>
                                    <Link
                                        href="/(tenant)/repair"
                                        className="w-full mt-2 bg-gray-100 text-gray-700 py-3 px-4 rounded-lg hover:bg-gray-200 transition-colors font-medium block text-center"
                                    >
                                        🔧 我要報修
                                    </Link>
                                </>
                            )}
                        </div>
                    </div>

                    {/* 租約資訊卡片 */}
                    <div className="bg-white rounded-2xl shadow-lg shadow-blue-900/5 p-6 border border-gray-100">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4">租約資訊</h2>
                        <div className="space-y-3">
                            <div className="flex justify-between items-center">
                                <span className="text-sm text-gray-600">租約起始</span>
                                <span className="text-sm font-medium text-gray-900">
                                    {new Date(tenant.contract_start).toLocaleDateString('zh-TW')}
                                </span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-sm text-gray-600">租約到期</span>
                                <span className="text-sm font-medium text-gray-900">
                                    {new Date(tenant.contract_end).toLocaleDateString('zh-TW')}
                                </span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-sm text-gray-600">聯絡電話</span>
                                <span className="text-sm font-medium text-gray-900">{tenant.phone}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-sm text-gray-600">Email</span>
                                <span className="text-sm font-medium text-gray-900">{tenant.email}</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* 繳費紀錄 */}
                <div className="mt-8 bg-white rounded-2xl shadow-lg shadow-blue-900/5 p-6 border border-gray-100">
                    <div className="flex items-center gap-2 mb-4">
                        <CreditCard className="h-5 w-5 text-blue-600" />
                        <h2 className="text-lg font-semibold text-gray-900">繳費紀錄</h2>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead>
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        期間
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        金額
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        繳費日期
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        狀態
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {payments.map((payment) => (
                                    <tr key={payment.id} className="hover:bg-gray-50 transition-colors">
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                            {payment.period}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                            ${payment.amount.toLocaleString()}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {payment.paid_date ? new Date(payment.paid_date).toLocaleDateString('zh-TW') : '-'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            {getStatusBadge(payment.status)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
