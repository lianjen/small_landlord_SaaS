"""
房間 (Room) 資料模型
支援靈活的房號編號系統
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class RoomBase(BaseModel):
    """房間基礎模型"""
    room_number: str = Field(..., description="房號，例如：101、A1-客房、套房-201")
    floor: Optional[int] = Field(None, description="樓層")
    area_sqm: Optional[float] = Field(None, description="坪數/平方米")
    bedrooms: int = Field(default=1, description="臥室數")
    bathrooms: int = Field(default=1, description="浴室數")
    amenities: Dict[str, Any] = Field(default_factory=dict, description="設施，例如：{'air_conditioner': true}")
    base_rent: float = Field(..., description="基礎租金")
    deposit: Optional[float] = Field(None, description="押金")
    utilities_included: Dict[str, bool] = Field(default_factory=dict, description="包含的費用")
    status: str = Field(default="vacant", description="狀態：vacant/occupied/maintenance/reserved")
    photos: List[str] = Field(default_factory=list, description="照片 URLs")
    notes: Optional[str] = Field(None, description="備註")


class RoomCreate(RoomBase):
    """建立房間時使用的模型"""
    property_id: str = Field(..., description="物件 ID")
    owner_id: str = Field(..., description="房東 ID")


class RoomUpdate(BaseModel):
    """更新房間時使用的模型"""
    room_number: Optional[str] = None
    floor: Optional[int] = None
    area_sqm: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    amenities: Optional[Dict[str, Any]] = None
    base_rent: Optional[float] = None
    deposit: Optional[float] = None
    utilities_included: Optional[Dict[str, bool]] = None
    status: Optional[str] = None
    photos: Optional[List[str]] = None
    notes: Optional[str] = None


class Room(RoomBase):
    """完整房間模型（包含資料庫欄位）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    property_id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime


class RoomWithTenant(Room):
    """帶房客資訊的房間模型"""
    tenant_name: Optional[str] = Field(None, description="房客姓名")
    tenant_phone: Optional[str] = Field(None, description="房客電話")
    lease_end: Optional[datetime] = Field(None, description="租約到期日")
    payment_status: Optional[str] = Field(None, description="繳費狀態")
