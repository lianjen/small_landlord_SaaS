"""
房客 Pydantic Schema
用於資料驗證和 API 序列化
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import date
from uuid import UUID


class TenantBase(BaseModel):
    """房客基本資料"""
    name: str = Field(..., min_length=2, max_length=100, description="房客姓名")
    email: Optional[EmailStr] = Field(None, description="Email")
    phone: Optional[str] = Field(None, pattern=r"^[0-9\-+\(\) ]{7,20}$", description="電話")
    id_card: Optional[str] = Field(None, min_length=10, max_length=50, description="身分證字號")
    room_number: str = Field(..., min_length=1, max_length=20, description="房號")
    rent_amount: int = Field(..., gt=0, description="月租金")
    deposit_amount: int = Field(default=0, ge=0, description="押金")
    move_in_date: date = Field(..., description="入住日期")
    move_out_date: Optional[date] = Field(None, description="退租日期")
    status: str = Field(default="active", pattern="^(active|inactive|overdue)$")
    notes: Optional[str] = Field(None, max_length=1000, description="備註")
    
    @field_validator('move_out_date')
    @classmethod
    def validate_move_out_date(cls, v, info):
        """確保退租日期晚於入住日期"""
        if v and 'move_in_date' in info.data and v < info.data['move_in_date']:
            raise ValueError('退租日期不能早於入住日期')
        return v


class TenantCreate(TenantBase):
    """新增房客"""
    pass


class TenantUpdate(BaseModel):
    """更新房客（所有欄位可選）"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r"^[0-9\-+\(\) ]{7,20}$")
    id_card: Optional[str] = None
    room_number: Optional[str] = None
    rent_amount: Optional[int] = Field(None, gt=0)
    deposit_amount: Optional[int] = Field(None, ge=0)
    move_out_date: Optional[date] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|overdue)$")
    notes: Optional[str] = None


class TenantResponse(TenantBase):
    """房客回應（含 ID 和時間戳）"""
    id: UUID
    user_id: UUID
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True  # Pydantic v2


class TenantListItem(BaseModel):
    """房客列表項目（精簡版）"""
    id: UUID
    name: str
    room_number: str
    rent_amount: int
    status: str
    phone: Optional[str] = None
