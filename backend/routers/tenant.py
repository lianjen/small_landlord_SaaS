"""
Tenant API Router
提供房客相關的 API 端點
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import sys
import os

# 添加 backend 到 Python Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.supabase import get_supabase

router = APIRouter(prefix="/api/tenant", tags=["tenant"])

# 資料模型
class TenantInfo(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    room_number: str
    property_name: str
    rent_amount: int
    rent_due_date: date
    payment_status: str
    contract_start: date
    contract_end: date

class PaymentRecord(BaseModel):
    id: str
    amount: int
    paid_date: Optional[str]
    period: str
    status: str

# JWT Token 驗證依賴
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    從 Authorization Header 提取並驗證 JWT Token
    """
    if not authorization or not authorization.startswith("Bearer "):
        # 開發階段：允許無 Token 訪問（使用模擬資料）
        return {"id": "dev-user", "email": "dev@example.com"}
    
    token = authorization.replace("Bearer ", "")
    supabase = get_supabase()
    
    try:
        user = supabase.auth.get_user(token)
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token 無效或已過期")

@router.get("/me", response_model=TenantInfo)
async def get_tenant_info(current_user: dict = Depends(get_current_user)):
    """
    取得當前登入房客的資訊
    """
    try:
        supabase = get_supabase()
        
        # 查詢房客資料（聯合查詢 tenants, rooms, properties）
        response = supabase.table("tenants")\
            .select("*, rooms(room_number, base_rent, properties(name))")\
            .eq("user_id", current_user.get("id"))\
            .single()\
            .execute()
        
        if not response.data:
            # 若無資料，回傳模擬資料（開發階段）
            return TenantInfo(
                id="tenant-001",
                name="王大明",
                email="example@gmail.com",
                phone="0912-345-678",
                room_number="A101",
                property_name="幸福大樓",
                rent_amount=15000,
                rent_due_date=date(2026, 2, 28),
                payment_status="unpaid",
                contract_start=date(2025, 1, 1),
                contract_end=date(2026, 12, 31)
            )
        
        tenant = response.data
        return TenantInfo(
            id=tenant["id"],
            name=tenant["name"],
            email=tenant["email"],
            phone=tenant["phone"],
            room_number=tenant["rooms"]["room_number"],
            property_name=tenant["rooms"]["properties"]["name"],
            rent_amount=int(tenant["rooms"]["base_rent"]),
            rent_due_date=date.fromisoformat(tenant["rent_due_date"]),
            payment_status=tenant.get("payment_status", "unpaid"),
            contract_start=date.fromisoformat(tenant["contract_start"]),
            contract_end=date.fromisoformat(tenant["contract_end"])
        )
    
    except Exception as e:
        # 開發階段：發生錯誤時回傳模擬資料
        print(f"查詢失敗，使用模擬資料: {e}")
        return TenantInfo(
            id="tenant-001",
            name="王大明",
            email="example@gmail.com",
            phone="0912-345-678",
            room_number="A101",
            property_name="幸福大樓",
            rent_amount=15000,
            rent_due_date=date(2026, 2, 28),
            payment_status="unpaid",
            contract_start=date(2025, 1, 1),
            contract_end=date(2026, 12, 31)
        )

@router.get("/payments")
async def get_payment_history(current_user: dict = Depends(get_current_user)):
    """取得繳費紀錄"""
    try:
        supabase = get_supabase()
        
        response = supabase.table("payments")\
            .select("*")\
            .eq("tenant_id", current_user.get("id"))\
            .order("period", desc=True)\
            .limit(12)\
            .execute()
        
        if not response.data:
            # 模擬資料
            return {
                "payments": [
                    {
                        "id": "pay-001",
                        "amount": 15000,
                        "paid_date": "2026-01-31",
                        "period": "2026年1月",
                        "status": "paid"
                    },
                    {
                        "id": "pay-002",
                        "amount": 15000,
                        "paid_date": None,
                        "period": "2026年2月",
                        "status": "unpaid"
                    }
                ]
            }
        
        return {"payments": response.data}
    
    except Exception as e:
        # 模擬資料
        return {
            "payments": [
                {
                    "id": "pay-001",
                    "amount": 15000,
                    "paid_date": "2026-01-31",
                    "period": "2026年1月",
                    "status": "paid"
                },
                {
                    "id": "pay-002",
                    "amount": 15000,
                    "paid_date": None,
                    "period": "2026年2月",
                    "status": "unpaid"
                }
            ]
        }

