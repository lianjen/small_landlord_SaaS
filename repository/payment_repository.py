# repositories/payment_repository.py
"""
租金資料存取層
職責：純資料庫 CRUD 操作，不含業務邏輯
"""
from typing import List, Dict, Optional
from datetime import datetime
from services.db import SupabaseDB
from psycopg2.extras import RealDictCursor

class PaymentRepository:
    """租金資料存取物件（Repository Pattern）"""
    
    def __init__(self):
        self.db = SupabaseDB()
    
    def create_schedule(self, **kwargs) -> int:
        """新增租金排程"""
        conn = self.db.get_connection()
        cur = conn.cursor()
        
        query = """
            INSERT INTO payment_schedule (
                room_number, tenant_name, payment_year, payment_month,
                amount, due_date, payment_method, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'unpaid')
            RETURNING id
        """
        
        cur.execute(query, (
            kwargs['room_number'], kwargs['tenant_name'],
            kwargs['payment_year'], kwargs['payment_month'],
            kwargs['amount'], kwargs['due_date'],
            kwargs['payment_method']
        ))
        
        schedule_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return schedule_id
    
    def schedule_exists(self, room_number: str, year: int, month: int) -> bool:
        """檢查排程是否已存在"""
        conn = self.db.get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 1 FROM payment_schedule
            WHERE room_number = %s
              AND payment_year = %s
              AND payment_month = %s
        """, (room_number, year, month))
        
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        
        return exists
    
    def get_by_status(self, status: str) -> List[Dict]:
        """依狀態查詢"""
        conn = self.db.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM payment_schedule
            WHERE status = %s
            ORDER BY due_date
        """, (status,))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        return [dict(r) for r in results]
    
    def get_by_id(self, payment_id: int) -> Optional[Dict]:
        """依 ID 查詢單筆"""
        conn = self.db.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            "SELECT * FROM payment_schedule WHERE id = %s",
            (payment_id,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        return dict(result) if result else None
    
    def update_payment_status(self, payment_id: int, **kwargs) -> bool:
        """更新付款狀態"""
        conn = self.db.get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE payment_schedule
            SET status = %s, paid_amount = %s, paid_date = %s, notes = %s
            WHERE id = %s
        """, (
            kwargs['status'], kwargs['paid_amount'],
            kwargs['paid_date'], kwargs['notes'], payment_id
        ))
        
        success = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        
        return success
    
    def get_by_period(self, year: int, month: int) -> List[Dict]:
        """依期間查詢"""
        conn = self.db.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM payment_schedule
            WHERE payment_year = %s AND payment_month = %s
            ORDER BY room_number
        """, (year, month))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        return [dict(r) for r in results]
