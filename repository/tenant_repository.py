"""
房客資料存取層 - Supabase 適配版
✅ 修正所有欄位名稱適配 Supabase Schema
✅ is_active → status
✅ tenant_name → name
✅ base_rent → rent_amount
✅ deposit → deposit_amount
✅ lease_start → move_in_date
✅ lease_end → move_out_date
"""
from typing import List, Dict, Optional
from services.db import SupabaseDB
from psycopg2.extras import RealDictCursor
from services.logger import logger, log_db_operation


class TenantRepository:
    """房客資料存取物件"""
    
    def __init__(self):
        self.db = SupabaseDB()
    
    def get_active_tenants(self) -> List[Dict]:
        """取得所有活躍房客"""
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # ✅ 修正：status = 'active' 替代 is_active = true
                cur.execute("""
                    SELECT 
                        id,
                        name,
                        room_number,
                        phone,
                        email,
                        id_number,
                        rent_amount,
                        rent_due_day,
                        deposit_amount,
                        move_in_date,
                        move_out_date,
                        status,
                        notes,
                        created_at,
                        updated_at
                    FROM tenants
                    WHERE status = 'active'
                    ORDER BY room_number
                """)
                
                results = cur.fetchall()
                
                log_db_operation("SELECT", "tenants", True, len(results))
                logger.info(f"✅ 查詢活躍房客: {len(results)} 位")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 查詢活躍房客失敗: {str(e)}")
            return []
    
    def get_by_room(self, room_number: str) -> Optional[Dict]:
        """依房號查詢"""
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # ✅ 修正：status = 'active'
                cur.execute("""
                    SELECT 
                        id,
                        name,
                        room_number,
                        phone,
                        email,
                        id_number,
                        rent_amount,
                        rent_due_day,
                        deposit_amount,
                        move_in_date,
                        move_out_date,
                        status,
                        notes,
                        created_at,
                        updated_at
                    FROM tenants 
                    WHERE room_number = %s AND status = 'active'
                """, (room_number,))
                
                result = cur.fetchone()
                
                if result:
                    log_db_operation("SELECT", "tenants", True, 1)
                    logger.info(f"✅ 查詢房客: {room_number}")
                    return dict(result)
                else:
                    logger.info(f"ℹ️ 房號 {room_number} 無活躍房客")
                    return None
        
        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 查詢房客失敗 ({room_number}): {str(e)}")
            return None
    
    def get_all_tenants(self, active_only: bool = True) -> List[Dict]:
        """取得所有房客
        
        Args:
            active_only: 只取得活躍房客
            
        Returns:
            房客列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # ✅ 修正：status = 'active'
                if active_only:
                    cur.execute("""
                        SELECT 
                            id,
                            name,
                            room_number,
                            phone,
                            email,
                            id_number,
                            rent_amount,
                            rent_due_day,
                            deposit_amount,
                            move_in_date,
                            move_out_date,
                            status,
                            notes,
                            created_at,
                            updated_at
                        FROM tenants
                        WHERE status = 'active'
                        ORDER BY room_number
                    """)
                else:
                    cur.execute("""
                        SELECT 
                            id,
                            name,
                            room_number,
                            phone,
                            email,
                            id_number,
                            rent_amount,
                            rent_due_day,
                            deposit_amount,
                            move_in_date,
                            move_out_date,
                            status,
                            notes,
                            created_at,
                            updated_at
                        FROM tenants
                        ORDER BY room_number
                    """)
                
                results = cur.fetchall()
                
                log_db_operation("SELECT", "tenants", True, len(results))
                logger.info(f"✅ 查詢所有房客: {len(results)} 位")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 查詢所有房客失敗: {str(e)}")
            return []
    
    def get_by_id(self, tenant_id: int) -> Optional[Dict]:
        """依 ID 查詢房客
        
        Args:
            tenant_id: 房客 ID
            
        Returns:
            房客資料字典，找不到回傳 None
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("""
                    SELECT 
                        id,
                        name,
                        room_number,
                        phone,
                        email,
                        id_number,
                        rent_amount,
                        rent_due_day,
                        deposit_amount,
                        move_in_date,
                        move_out_date,
                        status,
                        notes,
                        created_at,
                        updated_at
                    FROM tenants 
                    WHERE id = %s
                """, (tenant_id,))
                
                result = cur.fetchone()
                
                if result:
                    log_db_operation("SELECT", "tenants", True, 1)
                    logger.info(f"✅ 查詢房客: ID {tenant_id}")
                    return dict(result)
                else:
                    logger.warning(f"⚠️ 房客不存在: ID {tenant_id}")
                    return None
        
        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 查詢房客失敗 (ID {tenant_id}): {str(e)}")
            return None
    
    def create_tenant(self, **kwargs) -> Optional[int]:
        """新增房客
        
        Args:
            **kwargs: 房客資料
                - room_number: 房號 (必填)
                - name: 姓名 (必填)
                - phone: 電話 (必填)
                - email: Email (選填)
                - id_number: 身分證字號 (選填)
                - rent_amount: 租金 (必填)
                - rent_due_day: 繳租日 (選填，預設 5)
                - deposit_amount: 押金 (必填)
                - move_in_date: 入住日期 (必填)
                - move_out_date: 退租日期 (選填)
                - notes: 備註 (選填)
                - status: 狀態 (選填，預設 'active')
            
        Returns:
            新增的房客 ID，失敗回傳 None
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                # ✅ 修正：使用正確的欄位名稱
                cur.execute("""
                    INSERT INTO tenants (
                        room_number,
                        name,
                        phone,
                        email,
                        id_number,
                        rent_amount,
                        rent_due_day,
                        deposit_amount,
                        move_in_date,
                        move_out_date,
                        notes,
                        status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    kwargs['room_number'],
                    kwargs.get('name', kwargs.get('tenant_name')),  # ✅ 兼容舊參數名稱
                    kwargs['phone'],
                    kwargs.get('email'),
                    kwargs.get('id_number'),
                    kwargs.get('rent_amount', kwargs.get('base_rent')),  # ✅ 兼容舊參數名稱
                    kwargs.get('rent_due_day', 5),
                    kwargs.get('deposit_amount', kwargs.get('deposit')),  # ✅ 兼容舊參數名稱
                    kwargs.get('move_in_date', kwargs.get('lease_start')),  # ✅ 兼容舊參數名稱
                    kwargs.get('move_out_date', kwargs.get('lease_end')),  # ✅ 兼容舊參數名稱
                    kwargs.get('notes', ''),
                    kwargs.get('status', 'active')
                ))
                
                tenant_id = cur.fetchone()[0]
                
                log_db_operation("INSERT", "tenants", True, 1)
                logger.info(f"✅ 新增房客: {kwargs.get('name', kwargs.get('tenant_name'))} ({kwargs['room_number']})")
                
                return tenant_id
        
        except Exception as e:
            log_db_operation("INSERT", "tenants", False, error=str(e))
            logger.error(f"❌ 新增房客失敗: {str(e)}")
            return None
    
    def update_tenant(self, tenant_id: int, **kwargs) -> bool:
        """更新房客資料
        
        Args:
            tenant_id: 房客 ID
            **kwargs: 要更新的欄位（同 create_tenant）
            
        Returns:
            是否更新成功
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                # ✅ 修正：使用正確的欄位名稱
                cur.execute("""
                    UPDATE tenants
                    SET 
                        room_number = %s,
                        name = %s,
                        phone = %s,
                        email = %s,
                        id_number = %s,
                        rent_amount = %s,
                        rent_due_day = %s,
                        deposit_amount = %s,
                        move_in_date = %s,
                        move_out_date = %s,
                        notes = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    kwargs['room_number'],
                    kwargs.get('name', kwargs.get('tenant_name')),  # ✅ 兼容舊參數名稱
                    kwargs['phone'],
                    kwargs.get('email'),
                    kwargs.get('id_number'),
                    kwargs.get('rent_amount', kwargs.get('base_rent')),  # ✅ 兼容舊參數名稱
                    kwargs.get('rent_due_day', 5),
                    kwargs.get('deposit_amount', kwargs.get('deposit')),  # ✅ 兼容舊參數名稱
                    kwargs.get('move_in_date', kwargs.get('lease_start')),  # ✅ 兼容舊參數名稱
                    kwargs.get('move_out_date', kwargs.get('lease_end')),  # ✅ 兼容舊參數名稱
                    kwargs.get('notes', ''),
                    tenant_id
                ))
                
                success = cur.rowcount > 0
                
                if success:
                    log_db_operation("UPDATE", "tenants", True, 1)
                    logger.info(f"✅ 更新房客: ID {tenant_id}")
                else:
                    logger.warning(f"⚠️ 房客不存在: ID {tenant_id}")
                
                return success
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 更新房客失敗 (ID {tenant_id}): {str(e)}")
            return False
    
    def delete_tenant(self, tenant_id: int) -> bool:
        """軟刪除房客（標記為非活躍）
        
        Args:
            tenant_id: 房客 ID
            
        Returns:
            是否刪除成功
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                # ✅ 修正：status = 'inactive'
                cur.execute("""
                    UPDATE tenants
                    SET status = 'inactive', updated_at = NOW()
                    WHERE id = %s
                """, (tenant_id,))
                
                success = cur.rowcount > 0
                
                if success:
                    log_db_operation("UPDATE", "tenants", True, 1)
                    logger.info(f"✅ 軟刪除房客: ID {tenant_id}")
                else:
                    logger.warning(f"⚠️ 房客不存在: ID {tenant_id}")
                
                return success
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 刪除房客失敗 (ID {tenant_id}): {str(e)}")
            return False
    
    def hard_delete_tenant(self, tenant_id: int) -> bool:
        """硬刪除房客（實際從資料庫移除）
        
        ⚠️ 警告：此操作無法復原！
        
        Args:
            tenant_id: 房客 ID
            
        Returns:
            是否刪除成功
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    DELETE FROM tenants
                    WHERE id = %s
                """, (tenant_id,))
                
                success = cur.rowcount > 0
                
                if success:
                    log_db_operation("DELETE", "tenants", True, 1)
                    logger.warning(f"⚠️ 硬刪除房客: ID {tenant_id}")
                else:
                    logger.warning(f"⚠️ 房客不存在: ID {tenant_id}")
                
                return success
        
        except Exception as e:
            log_db_operation("DELETE", "tenants", False, error=str(e))
            logger.error(f"❌ 硬刪除房客失敗 (ID {tenant_id}): {str(e)}")
            return False
    
    def restore_tenant(self, tenant_id: int) -> bool:
        """恢復已刪除的房客
        
        Args:
            tenant_id: 房客 ID
            
        Returns:
            是否恢復成功
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    UPDATE tenants
                    SET status = 'active', updated_at = NOW()
                    WHERE id = %s
                """, (tenant_id,))
                
                success = cur.rowcount > 0
                
                if success:
                    log_db_operation("UPDATE", "tenants", True, 1)
                    logger.info(f"✅ 恢復房客: ID {tenant_id}")
                else:
                    logger.warning(f"⚠️ 房客不存在: ID {tenant_id}")
                
                return success
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 恢復房客失敗 (ID {tenant_id}): {str(e)}")
            return False
    
    def get_tenant_count(self, active_only: bool = True) -> int:
        """取得房客數量
        
        Args:
            active_only: 只計算活躍房客
            
        Returns:
            房客數量
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                if active_only:
                    cur.execute("""
                        SELECT COUNT(*) FROM tenants
                        WHERE status = 'active'
                    """)
                else:
                    cur.execute("SELECT COUNT(*) FROM tenants")
                
                count = cur.fetchone()[0]
                
                log_db_operation("SELECT", "tenants_count", True, 1)
                
                return count
        
        except Exception as e:
            log_db_operation("SELECT", "tenants_count", False, error=str(e))
            logger.error(f"❌ 查詢房客數量失敗: {str(e)}")
            return 0
    
    def search_tenants(self, keyword: str, active_only: bool = True) -> List[Dict]:
        """搜尋房客（姓名、房號、電話）
        
        Args:
            keyword: 搜尋關鍵字
            active_only: 只搜尋活躍房客
            
        Returns:
            符合的房客列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                status_clause = "AND status = 'active'" if active_only else ""
                
                cur.execute(f"""
                    SELECT 
                        id,
                        name,
                        room_number,
                        phone,
                        email,
                        id_number,
                        rent_amount,
                        rent_due_day,
                        deposit_amount,
                        move_in_date,
                        move_out_date,
                        status,
                        notes,
                        created_at,
                        updated_at
                    FROM tenants
                    WHERE (
                        name ILIKE %s OR
                        room_number ILIKE %s OR
                        phone ILIKE %s
                    )
                    {status_clause}
                    ORDER BY room_number
                """, (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
                
                results = cur.fetchall()
                
                log_db_operation("SELECT", "tenants", True, len(results))
                logger.info(f"✅ 搜尋房客: {len(results)} 筆符合 '{keyword}'")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 搜尋房客失敗: {str(e)}")
            return []
    
    def get_vacant_rooms(self, all_rooms: List[str]) -> List[str]:
        """取得空房列表
        
        Args:
            all_rooms: 所有房號列表
            
        Returns:
            空房號列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT DISTINCT room_number
                    FROM tenants
                    WHERE status = 'active'
                """)
                
                occupied_rooms = {row[0] for row in cur.fetchall()}
                vacant_rooms = [room for room in all_rooms if room not in occupied_rooms]
                
                log_db_operation("SELECT", "vacant_rooms", True, len(vacant_rooms))
                logger.info(f"✅ 空房統計: {len(vacant_rooms)} 間")
                
                return sorted(vacant_rooms)
        
        except Exception as e:
            log_db_operation("SELECT", "vacant_rooms", False, error=str(e))
            logger.error(f"❌ 查詢空房失敗: {str(e)}")
            return []
