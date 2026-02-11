from typing import List, Dict, Any, Optional
from services.base_db import BaseDBService
from config.constants import ROOMS

class TenantService(BaseDBService):
    """
    房客管理服務 (TenantService) v2.0
    支援 room_id 關聯與物件層級查詢
    """
    
    TABLE_NAME = "tenants"

    def get_all_tenants(self) -> List[Dict[str, Any]]:
        """取得所有房客資料（包含房間與物件資訊）"""
        try:
            # 使用 JOIN 查詢完整資訊
            response = self.supabase.table(self.TABLE_NAME)\
                .select("*, rooms(room_number, floor, properties(name))")\
                .order("created_at", desc=True)\
                .execute()
            
            tenants = response.data
            
            # 扁平化結構方便前端使用
            for tenant in tenants:
                room = tenant.get("rooms")
                if room:
                    tenant["room_number"] = room.get("room_number")
                    tenant["floor"] = room.get("floor")
                    property_info = room.get("properties")
                    if property_info:
                        tenant["property_name"] = property_info.get("name")
            
            return tenants
        except Exception as e:
            self.logger.error(f"查詢房客失敗: {e}")
            return []

    def get_tenant_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """取得單一房客詳情"""
        try:
            response = self.supabase.table(self.TABLE_NAME)\
                .select("*")\
                .eq("id", tenant_id)\
                .single()\
                .execute()
            return response.data
        except Exception as e:
            self.logger.error(f"查詢單一房客失敗: {e}")
            return None

    def create_tenant(self, tenant_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """建立新房客"""
        try:
            response = self.supabase.table(self.TABLE_NAME)\
                .insert(tenant_data)\
                .execute()
            
            if response.data:
                # 如果有 room_id，更新房間狀態為 occupied
                room_id = tenant_data.get("room_id")
                if room_id:
                    self.supabase.table("rooms")\
                        .update({"status": "occupied"})\
                        .eq("id", room_id)\
                        .execute()
                
                return response.data[0]
            return None
        except Exception as e:
            self.logger.error(f"建立房客失敗: {e}")
            return None

    def update_tenant(self, tenant_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新房客資料"""
        try:
            response = self.supabase.table(self.TABLE_NAME)\
                .update(update_data)\
                .eq("id", tenant_id)\
                .execute()
            
            return response.data[0] if response.data else None
        except Exception as e:
            self.logger.error(f"更新房客失敗: {e}")
            return None

    def delete_tenant(self, tenant_id: str) -> bool:
        """刪除房客（軟刪除或硬刪除視需求）"""
        try:
            # 先查詢房客以取得 room_id
            tenant = self.get_tenant_by_id(tenant_id)
            if not tenant:
                return False

            # 刪除房客
            self.supabase.table(self.TABLE_NAME)\
                .delete()\
                .eq("id", tenant_id)\
                .execute()
            
            # 更新房間狀態為 vacant
            room_id = tenant.get("room_id")
            if room_id:
                self.supabase.table("rooms")\
                    .update({"status": "vacant"})\
                    .eq("id", room_id)\
                    .execute()
                    
            return True
        except Exception as e:
            self.logger.error(f"刪除房客失敗: {e}")
            return False

    def get_tenants_by_room(self, room_id: str) -> List[Dict[str, Any]]:
        """查詢特定房間的房客"""
        try:
            response = self.supabase.table(self.TABLE_NAME)\
                .select("*")\
                .eq("room_id", room_id)\
                .execute()
            return response.data
        except Exception as e:
            self.logger.error(f"查詢房間房客失敗: {e}")
            return []
