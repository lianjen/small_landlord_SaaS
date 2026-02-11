"""
物件管理服務 (PropertyService)
處理多棟建築物的 CRUD 操作
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from services.base_db import BaseDBService
from schemas.property import Property, PropertyCreate, PropertyUpdate, PropertyWithStats


class PropertyService(BaseDBService):
    """物件管理服務"""
    
    TABLE_NAME = "properties"
    
    def __init__(self):
        super().__init__()
    
    def create_property(self, property_data: PropertyCreate) -> Optional[Property]:
        """
        建立新物件
        
        Args:
            property_data: 物件資料
            
        Returns:
            Property: 建立的物件，失敗返回 None
        """
        try:
            data = property_data.model_dump()
            data["created_at"] = datetime.now().isoformat()
            data["updated_at"] = datetime.now().isoformat()
            
            result = self.supabase.table(self.TABLE_NAME).insert(data).execute()
            
            if result.data:
                return Property(**result.data[0])
            return None
            
        except Exception as e:
            self.logger.error(f"建立物件失敗: {e}")
            return None
    
    def get_property(self, property_id: str) -> Optional[Property]:
        """
        取得單一物件
        
        Args:
            property_id: 物件 ID
            
        Returns:
            Property: 物件資料，未找到返回 None
        """
        try:
            result = self.supabase.table(self.TABLE_NAME).select("*").eq("id", property_id).single().execute()
            
            if result.data:
                return Property(**result.data)
            return None
            
        except Exception as e:
            self.logger.error(f"取得物件失敗: {e}")
            return None
    
    def get_properties_by_owner(self, owner_id: str) -> List[Property]:
        """
        取得房東的所有物件
        
        Args:
            owner_id: 房東 ID
            
        Returns:
            List[Property]: 物件列表
        """
        try:
            result = self.supabase.table(self.TABLE_NAME)\
                .select("*")\
                .eq("owner_id", owner_id)\
                .order("created_at", desc=True)\
                .execute()
            
            if result.data:
                return [Property(**item) for item in result.data]
            return []
            
        except Exception as e:
            self.logger.error(f"取得物件列表失敗: {e}")
            return []
    
    def get_properties_with_stats(self, owner_id: str) -> List[PropertyWithStats]:
        """
        取得帶統計資訊的物件列表
        
        Args:
            owner_id: 房東 ID
            
        Returns:
            List[PropertyWithStats]: 帶統計資訊的物件列表
        """
        try:
            # 取得物件基本資訊
            properties = self.get_properties_by_owner(owner_id)
            
            result = []
            for prop in properties:
                # 計算出租率
                occupancy_rate = 0.0
                if prop.total_rooms > 0:
                    occupancy_rate = prop.occupied_rooms / prop.total_rooms
                
                # TODO: 從 payments 表計算本月收入
                monthly_income = 0.0
                
                prop_with_stats = PropertyWithStats(
                    **prop.model_dump(),
                    occupancy_rate=occupancy_rate,
                    monthly_income=monthly_income
                )
                result.append(prop_with_stats)
            
            return result
            
        except Exception as e:
            self.logger.error(f"取得物件統計失敗: {e}")
            return []
    
    def update_property(self, property_id: str, update_data: PropertyUpdate) -> Optional[Property]:
        """
        更新物件資料
        
        Args:
            property_id: 物件 ID
            update_data: 更新資料
            
        Returns:
            Property: 更新後的物件，失敗返回 None
        """
        try:
            data = update_data.model_dump(exclude_unset=True)
            data["updated_at"] = datetime.now().isoformat()
            
            result = self.supabase.table(self.TABLE_NAME)\
                .update(data)\
                .eq("id", property_id)\
                .execute()
            
            if result.data:
                return Property(**result.data[0])
            return None
            
        except Exception as e:
            self.logger.error(f"更新物件失敗: {e}")
            return None
    
    def delete_property(self, property_id: str) -> bool:
        """
        刪除物件（連帶刪除所有房間）
        
        Args:
            property_id: 物件 ID
            
        Returns:
            bool: 成功返回 True
        """
        try:
            result = self.supabase.table(self.TABLE_NAME).delete().eq("id", property_id).execute()
            return True
            
        except Exception as e:
            self.logger.error(f"刪除物件失敗: {e}")
            return False
    
    def update_room_stats(self, property_id: str) -> bool:
        """
        更新物件的房間統計數據
        
        Args:
            property_id: 物件 ID
            
        Returns:
            bool: 成功返回 True
        """
        try:
            # 統計房間數量
            rooms_result = self.supabase.table("rooms")\
                .select("status")\
                .eq("property_id", property_id)\
                .execute()
            
            if not rooms_result.data:
                return True
            
            total_rooms = len(rooms_result.data)
            occupied_rooms = sum(1 for room in rooms_result.data if room["status"] == "occupied")
            vacant_rooms = sum(1 for room in rooms_result.data if room["status"] == "vacant")
            
            # 更新統計
            update_result = self.supabase.table(self.TABLE_NAME)\
                .update({
                    "total_rooms": total_rooms,
                    "occupied_rooms": occupied_rooms,
                    "vacant_rooms": vacant_rooms,
                    "updated_at": datetime.now().isoformat()
                })\
                .eq("id", property_id)\
                .execute()
            
            return True
            
        except Exception as e:
            self.logger.error(f"更新房間統計失敗: {e}")
            return False
