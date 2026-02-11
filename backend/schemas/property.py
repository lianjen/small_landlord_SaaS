"""
物件 (Property) 資料模型
支援多棟建築物管理
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class PropertyBase(BaseModel):
    """物件基礎模型"""
    name: str = Field(..., description="物件名稱，例如：A棟、台北中山社區")
    type: str = Field(default="apartment", description="物件類型：apartment/house/building/mixed")
    address: Optional[str] = Field(None, description="地址")
    city: Optional[str] = Field(None, description="城市")
    district: Optional[str] = Field(None, description="區域")
    lat: Optional[float] = Field(None, description="緯度")
    lng: Optional[float] = Field(None, description="經度")
    notes: Optional[str] = Field(None, description="備註")


class PropertyCreate(PropertyBase):
    """建立物件時使用的模型"""
    owner_id: str = Field(..., description="房東 ID")


class PropertyUpdate(BaseModel):
    """更新物件時使用的模型"""
    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    notes: Optional[str] = None


class Property(PropertyBase):
    """完整物件模型（包含資料庫欄位）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    owner_id: str
    total_rooms: int = 0
    occupied_rooms: int = 0
    vacant_rooms: int = 0
    created_at: datetime
    updated_at: datetime


class PropertyWithStats(Property):
    """帶統計資訊的物件模型"""
    monthly_income: Optional[float] = Field(None, description="本月預計收入")
    occupancy_rate: Optional[float] = Field(None, description="出租率 (0-1)")
