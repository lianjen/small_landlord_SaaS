# repositories/tenant_repository.py
"""
房客資料存取層
"""
from typing import List, Dict
from services.db import SupabaseDB
from psycopg2.extras import RealDictCursor

class TenantRepository:
    """房客資料存取物件"""
    
    def __init__(self):
        self.db = SupabaseDB()
    
    def get_active_tenants(self) -> List[Dict]:
        """取得所有活躍房客"""
        conn = self.db.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM tenants
            WHERE is_active = true
            ORDER BY room_number
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        return [dict(r) for r in results]
    
    def get_by_room(self, room_number: str) -> Dict:
        """依房號查詢"""
        conn = self.db.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            "SELECT * FROM tenants WHERE room_number = %s AND is_active = true",
            (room_number,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        return dict(result) if result else None
