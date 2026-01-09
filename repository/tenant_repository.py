# repository/tenant_repository.py
"""
房客資料存取層
"""
from typing import List, Dict, Optional
from services.db import SupabaseDB
from psycopg2.extras import RealDictCursor


class TenantRepository:
    """房客資料存取物件"""
    
    def __init__(self):
        self.db = SupabaseDB()
    
    def get_active_tenants(self) -> List[Dict]:
        """取得所有活躍房客"""
        with self.db.get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT * FROM tenants
                WHERE is_active = true
                ORDER BY room_number
            """)
            
            results = cur.fetchall()
            
            return [dict(r) for r in results]
    
    def get_by_room(self, room_number: str) -> Optional[Dict]:
        """依房號查詢"""
        with self.db.get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute(
                "SELECT * FROM tenants WHERE room_number = %s AND is_active = true",
                (room_number,)
            )
            
            result = cur.fetchone()
            
            return dict(result) if result else None
    
    def get_all_tenants(self, active_only: bool = True) -> List[Dict]:
        """取得所有房客
        
        Args:
            active_only: 只取得活躍房客
            
        Returns:
            房客列表
        """
        with self.db.get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            if active_only:
                cur.execute("""
                    SELECT * FROM tenants
                    WHERE is_active = true
                    ORDER BY room_number
                """)
            else:
                cur.execute("""
                    SELECT * FROM tenants
                    ORDER BY room_number
                """)
            
            results = cur.fetchall()
            
            return [dict(r) for r in results]
    
    def get_by_id(self, tenant_id: int) -> Optional[Dict]:
        """依 ID 查詢房客
        
        Args:
            tenant_id: 房客 ID
            
        Returns:
            房客資料字典，找不到回傳 None
        """
        with self.db.get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute(
                "SELECT * FROM tenants WHERE id = %s",
                (tenant_id,)
            )
            
            result = cur.fetchone()
            
            return dict(result) if result else None
    
    def create_tenant(self, **kwargs) -> Optional[int]:
        """新增房客
        
        Args:
            **kwargs: 房客資料（room_number, tenant_name, phone, etc.）
            
        Returns:
            新增的房客 ID，失敗回傳 None
        """
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO tenants (
                    room_number, tenant_name, phone, deposit, base_rent,
                    lease_start, lease_end, payment_method, has_water_fee,
                    annual_discount_months, discount_notes, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
                RETURNING id
            """, (
                kwargs['room_number'], kwargs['tenant_name'], kwargs['phone'],
                kwargs['deposit'], kwargs['base_rent'], kwargs['lease_start'],
                kwargs['lease_end'], kwargs['payment_method'], kwargs.get('has_water_fee', False),
                kwargs.get('annual_discount_months', 0), kwargs.get('discount_notes', '')
            ))
            
            tenant_id = cur.fetchone()[0]
            
            return tenant_id
    
    def update_tenant(self, tenant_id: int, **kwargs) -> bool:
        """更新房客資料
        
        Args:
            tenant_id: 房客 ID
            **kwargs: 要更新的欄位
            
        Returns:
            是否更新成功
        """
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE tenants
                SET room_number = %s, tenant_name = %s, phone = %s,
                    deposit = %s, base_rent = %s, lease_start = %s,
                    lease_end = %s, payment_method = %s, has_water_fee = %s,
                    annual_discount_months = %s, discount_notes = %s
                WHERE id = %s
            """, (
                kwargs['room_number'], kwargs['tenant_name'], kwargs['phone'],
                kwargs['deposit'], kwargs['base_rent'], kwargs['lease_start'],
                kwargs['lease_end'], kwargs['payment_method'], kwargs.get('has_water_fee', False),
                kwargs.get('annual_discount_months', 0), kwargs.get('discount_notes', ''),
                tenant_id
            ))
            
            return cur.rowcount > 0
    
    def delete_tenant(self, tenant_id: int) -> bool:
        """軟刪除房客（標記為非活躍）
        
        Args:
            tenant_id: 房客 ID
            
        Returns:
            是否刪除成功
        """
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE tenants
                SET is_active = false
                WHERE id = %s
            """, (tenant_id,))
            
            return cur.rowcount > 0
