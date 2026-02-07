"""
租金記錄 Pydantic Schema
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date
from uuid import UUID
import re


class PaymentBase(BaseModel):
    """租金記錄基本資料"""
    tenant_id: UUID = Field(..., description="房客 ID")
    rent_month: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="租金月份 (YYYY-MM)")
    amount: int = Field(..., gt=0, description="應繳金額")
    status: str = Field(default="unpaid", pattern="^(unpaid|paid|overdue|partial)$")
    paid_date: Optional[date] = Field(None, description="實際繳款日期")
    paid_amount: int = Field(default=0, ge=0, description="已繳金額")
    payment_method: Optional[str] = Field(None, max_length=50, description="繳款方式")
    notes: Optional[str] = Field(None, max_length=500)
    
    @field_validator('rent_month')
    @classmethod
    def validate_rent_month(cls, v):
        """驗證月份格式"""
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", v):
            raise ValueError('月份格式必須為 YYYY-MM')
        return v


class PaymentCreate(PaymentBase):
    """新增租金記錄"""
    pass


class PaymentUpdate(BaseModel):
    """更新租金記錄"""
    status: Optional[str] = Field(None, pattern="^(unpaid|paid|overdue|partial)$")
    paid_date: Optional[date] = None
    paid_amount: Optional[int] = Field(None, ge=0)
    payment_method: Optional[str] = None
    notes: Optional[str] = None


class PaymentResponse(PaymentBase):
    """租金記錄回應"""
    id: UUID
    user_id: UUID
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True
