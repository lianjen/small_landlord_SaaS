"""
房間管理服務 (RoomService)
處理房間的 CRUD 操作與狀態管理
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from services.base_db import BaseDBService
from schemas.room import Room, RoomCreate, RoomUpdate, RoomWithTenant


class RoomService(BaseDBService):
    """房間管理服務"""
    
    TABLE_NAME = "rooms"
    
    def __init__(self):
        super().__init__()
    
    def create_room(self, room_data: RoomCreate) -> Optional[Room]:
        """
        建立新房間
        
        Args:
            room_data: 房間資料
            
        Returns:
            Room: 建立的房間，失敗返回 None
        """
        try:
            data = room_data.model_dump()
            data["created_at"] = datetime.now().isoformat()
            data["updated_at"] = datetime.now().isoformat()
            
            result = self.supabase.table(self.TABLE_NAME).insert(data).execute()
            
            if result.data:
                # 更新 property 的房間統計
                from services.property_service import PropertyService
                property_service = PropertyService()
                property_service.update_room_stats(room_data.property_id)
                
                return Room(**result.data[0])
            return None
            
        except Exception as e:
            self.logger.error(f"建立房間失敗: {e}")
            return None
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """
        取得單一房間
        
        Args:
            room_id: 房間 ID
            
        Returns:
            Room: 房間資料，未找到返回 None
        """
        try:
            result = self.supabase.table(self.TABLE_NAME).select("*").eq("id", room_id).single().execute()
            
            if result.data:
                return Room(**result.data)
            return None
            
        except Exception as e:
            self.logger.error(f"取得房間失敗: {e}")
            return None
    
    def get_rooms_by_property(self, property_id: str) -> List[Room]:
        """
        取得物件的所有房間
        
        Args:
            property_id: 物件 ID
            
        Returns:
            List[Room]: 房間列表
        """
        try:
            result = self.supabase.table(self.TABLE_NAME)\
                .select("*")\
                .eq("property_id", property_id)\
                .order("room_number")\
                .execute()
            
            if result.data:
                return [Room(**item) for item in result.data]
            return []
            
        except Exception as e:
            self.logger.error(f"取得房間列表失敗: {e}")
            return []
    
    def get_rooms_with_tenants(self, property_id: str) -> List[RoomWithTenant]:
        """
        取得房間列表（包含房客資訊）
        
        Args:
            property_id: 物件 ID
            
        Returns:
            List[RoomWithTenant]: 帶房客資訊的房間列表
        """
        try:
            # 使用 JOIN 查詢房間與房客資訊
            result = self.supabase.table(self.TABLE_NAME)\
                .select("*, tenants(name, phone, lease_end)")\
                .eq("property_id", property_id)\
                .order("room_number")\
                .execute()
            
            if not result.data:
                return []
            
            rooms_with_tenants = []
            for item in result.data:
                tenant_data = item.get("tenants", [])
                tenant = tenant_data[0] if tenant_data else None
                
                room = RoomWithTenant(
                    **{k: v for k, v in item.items() if k != "tenants"},
                    tenant_name=tenant.get("name") if tenant else None,
                    tenant_phone=tenant.get("phone") if tenant else None,
                    lease_end=tenant.get("lease_end") if tenant else None
                )
                rooms_with_tenants.append(room)
            
            return rooms_with_tenants
            
        except Exception as e:
            self.logger.error(f"取得房間與房客資訊失敗: {e}")
            return []
    
    def update_room(self, room_id: str, update_data: RoomUpdate) -> Optional[Room]:
        """
        更新房間資料
        
        Args:
            room_id: 房間 ID
            update_data: 更新資料
            
        Returns:
            Room: 更新後的房間，失敗返回 None
        """
        try:
            data = update_data.model_dump(exclude_unset=True)
            data["updated_at"] = datetime.now().isoformat()
            
            result = self.supabase.table(self.TABLE_NAME)\
                .update(data)\
                .eq("id", room_id)\
                .execute()
            
            if result.data:
                # 如果狀態改變，更新 property 統計
                if "status" in data:
                    room = Room(**result.data[0])
                    from services.property_service import PropertyService
                    property_service = PropertyService()
                    property_service.update_room_stats(room.property_id)
                
                return Room(**result.data[0])
            return None
            
        except Exception as e:
            self.logger.error(f"更新房間失敗: {e}")
            return None
    
    def update_room_status(self, room_id: str, status: str) -> bool:
        """
        更新房間狀態
        
        Args:
            room_id: 房間 ID
            status: 新狀態 (vacant/occupied/maintenance/reserved)
            
        Returns:
            bool: 成功返回 True
        """
        try:
            update_data = RoomUpdate(status=status)
            result = self.update_room(room_id, update_data)
            return result is not None
            
        except Exception as e:
            self.logger.error(f"更新房間狀態失敗: {e}")
            return False
    
    def delete_room(self, room_id: str) -> bool:
        """
        刪除房間
        
        Args:
            room_id: 房間 ID
            
        Returns:
            bool: 成功返回 True
        """
        try:
            # 先取得房間資訊（用於更新統計）
            room = self.get_room(room_id)
            if not room:
                return False
            
            # 刪除房間
            result = self.supabase.table(self.TABLE_NAME).delete().eq("id", room_id).execute()
            
            # 更新 property 統計
            from services.property_service import PropertyService
            property_service = PropertyService()
            property_service.update_room_stats(room.property_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"刪除房間失敗: {e}")
            return False
    
    def get_vacant_rooms(self, owner_id: str) -> List[Room]:
        """
        取得所有空房
        
        Args:
            owner_id: 房東 ID
            
        Returns:
            List[Room]: 空房列表
        """
        try:
            result = self.supabase.table(self.TABLE_NAME)\
                .select("*")\
                .eq("owner_id", owner_id)\
                .eq("status", "vacant")\
                .order("property_id, room_number")\
                .execute()
            
            if result.data:
                return [Room(**item) for item in result.data]
            return []
            
        except Exception as e:
            self.logger.error(f"取得空房列表失敗: {e}")
            return []
