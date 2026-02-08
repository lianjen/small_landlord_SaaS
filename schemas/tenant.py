"""
房客 Pydantic Schema - Supabase 適配版
✅ 完全對應實際資料庫欄位
✅ 移除 UUID，使用 str (TEXT)
✅ 修正欄位名稱：id_card → id_number
✅ 新增 rent_due_day 欄位
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import date, datetime


class TenantBase(BaseModel):
    """房客基本資料（對應資料庫欄位）"""
    name: str = Field(
        ..., 
        min_length=2, 
        max_length=100, 
        description="房客姓名",
        examples=["王小明"]
    )
    room_number: str = Field(
        ..., 
        min_length=1, 
        max_length=20, 
        description="房號",
        examples=["4C", "A101"]
    )
    phone: Optional[str] = Field(
        None, 
        pattern=r"^[0-9\-+\(\) ]{7,20}$", 
        description="電話",
        examples=["0912-345-678"]
    )
    email: Optional[EmailStr] = Field(
        None, 
        description="Email",
        examples=["tenant@example.com"]
    )
    id_number: Optional[str] = Field(
        None, 
        min_length=10, 
        max_length=50, 
        description="身分證字號",
        examples=["A123456789"]
    )
    rent_amount: float = Field(
        ..., 
        gt=0, 
        description="月租金",
        examples=[6000.0]
    )
    rent_due_day: int = Field(
        default=5, 
        ge=1, 
        le=31, 
        description="每月繳租日（1-31）",
        examples=[5]
    )
    deposit_amount: float = Field(
        default=0, 
        ge=0, 
        description="押金",
        examples=[12000.0]
    )
    move_in_date: date = Field(
        ..., 
        description="入住日期",
        examples=["2026-01-01"]
    )
    move_out_date: Optional[date] = Field(
        None, 
        description="退租日期",
        examples=["2027-01-01"]
    )
    status: str = Field(
        default="active", 
        pattern="^(active|inactive)$",
        description="狀態",
        examples=["active"]
    )
    notes: Optional[str] = Field(
        None, 
        max_length=1000, 
        description="備註",
        examples=["優良房客"]
    )
    
    @field_validator('move_out_date')
    @classmethod
    def validate_move_out_date(cls, v, info):
        """確保退租日期晚於入住日期"""
        if v and 'move_in_date' in info.data:
            move_in = info.data['move_in_date']
            if v < move_in:
                raise ValueError('退租日期不能早於入住日期')
        return v
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """驗證電話格式（台灣手機或市話）"""
        if v:
            # 移除所有非數字字元
            digits = ''.join(filter(str.isdigit, v))
            
            # 檢查是否為有效的台灣電話號碼
            if len(digits) < 7:
                raise ValueError('電話號碼長度不足')
            
            # 手機號碼檢查 (09開頭，10碼)
            if digits.startswith('09') and len(digits) != 10:
                raise ValueError('手機號碼應為 10 碼')
        
        return v
    
    @field_validator('id_number')
    @classmethod
    def validate_id_number(cls, v):
        """驗證台灣身分證字號格式"""
        if v:
            # 移除空白
            v = v.strip().upper()
            
            # 基本格式檢查：1個英文字母 + 9個數字
            import re
            if not re.match(r'^[A-Z][12]\d{8}$', v):
                raise ValueError('身分證字號格式錯誤（應為 1 個英文字母 + 9 個數字）')
        
        return v


class TenantCreate(TenantBase):
    """新增房客"""
    pass


class TenantUpdate(BaseModel):
    """更新房客（所有欄位可選）"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    room_number: Optional[str] = Field(None, min_length=1, max_length=20)
    phone: Optional[str] = Field(None, pattern=r"^[0-9\-+\(\) ]{7,20}$")
    email: Optional[EmailStr] = None
    id_number: Optional[str] = Field(None, min_length=10, max_length=50)
    rent_amount: Optional[float] = Field(None, gt=0)
    rent_due_day: Optional[int] = Field(None, ge=1, le=31)
    deposit_amount: Optional[float] = Field(None, ge=0)
    move_in_date: Optional[date] = None
    move_out_date: Optional[date] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")
    notes: Optional[str] = Field(None, max_length=1000)


class TenantResponse(TenantBase):
    """房客回應（含 ID 和時間戳）"""
    id: str  # ✅ 修正：使用 str 而非 UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # Pydantic v2


class TenantListItem(BaseModel):
    """房客列表項目（精簡版）"""
    id: str
    name: str
    room_number: str
    rent_amount: float
    status: str
    phone: Optional[str] = None
    move_in_date: date
    
    class Config:
        from_attributes = True


class TenantSearchResult(BaseModel):
    """搜尋結果"""
    total: int
    items: list[TenantListItem]
