"""
支出記錄 Pydantic Schema
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import date
from uuid import UUID


class ExpenseBase(BaseModel):
    """支出記錄基本資料"""
    category: str = Field(..., min_length=1, max_length=50, description="支出類別")
    description: str = Field(..., min_length=1, max_length=500, description="支出說明")
    amount: int = Field(..., gt=0, description="金額")
    expense_date: date = Field(..., description="支出日期")
    room_number: Optional[str] = Field(None, max_length=20, description="關聯房號")
    receipt_url: Optional[str] = Field(None, description="收據圖片 URL")


class ExpenseCreate(ExpenseBase):
    """新增支出記錄"""
    pass


class ExpenseUpdate(BaseModel):
    """更新支出記錄"""
    category: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[int] = Field(None, gt=0)
    expense_date: Optional[date] = None
    room_number: Optional[str] = None
    receipt_url: Optional[str] = None


class ExpenseResponse(ExpenseBase):
    """支出記錄回應"""
    id: UUID
    user_id: UUID
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True
