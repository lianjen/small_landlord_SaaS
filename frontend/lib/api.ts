/**
 * API Client for Frontend
 * 封裝所有後端 API 的呼叫邏輯
 * 包含 Token 管理與認證
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Types ---

export interface User {
    id: string;
    email: string;
    role: string;
}

export interface LoginResponse {
    access_token: string;
    refresh_token: string;
    user: User;
}

export interface TenantInfo {
    id: string;
    name: string;
    email: string;
    phone: string;
    room_number: string;
    property_name: string;
    rent_amount: number;
    rent_due_date: string;
    payment_status: "paid" | "unpaid" | "overdue";
    contract_start: string;
    contract_end: string;
}

export interface PaymentRecord {
    id: string;
    amount: number;
    paid_date: string | null;
    period: string;
    status: "paid" | "unpaid";
}

// --- Token Management ---

const TOKEN_KEY = "microrent_access_token";

export function getAccessToken(): string | null {
    if (typeof window !== "undefined") {
        return localStorage.getItem(TOKEN_KEY);
    }
    return null;
}

export function setAccessToken(token: string) {
    if (typeof window !== "undefined") {
        localStorage.setItem(TOKEN_KEY, token);
    }
}

export function clearAccessToken() {
    if (typeof window !== "undefined") {
        localStorage.removeItem(TOKEN_KEY);
    }
}

// --- Helper ---

async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
    const token = getAccessToken();

    const headers = {
        ...options.headers,
        "Authorization": token ? `Bearer ${token}` : "",
    };

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
    });

    if (response.status === 401) {
        // Token 失效，強制登出
        clearAccessToken();
        if (typeof window !== "undefined") {
            window.location.href = "/(tenant)/login";
        }
        throw new Error("Unauthorized");
    }

    return response;
}

// --- API Methods ---

/**
 * 登入
 */
export async function login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "登入失敗");
    }

    const data = await response.json();
    setAccessToken(data.access_token);
    return data;
}

/**
 * 取得房客資訊
 */
export async function getTenantInfo(): Promise<TenantInfo> {
    const response = await fetchWithAuth("/api/tenant/me");

    if (!response.ok) {
        throw new Error("無法取得房客資訊");
    }

    return response.json();
}

/**
 * 取得繳費紀錄
 */
export async function getPaymentHistory(): Promise<PaymentRecord[]> {
    const response = await fetchWithAuth("/api/tenant/payments");

    if (!response.ok) {
        throw new Error("無法取得繳費紀錄");
    }

    const data = await response.json();
    return data.payments;
}
