"""
租金資料存取層 - Supabase 適配版 v2.3
✅ 移除 paid_date 和 notes 欄位（資料庫無這些欄位）
✅ 完整的錯誤處理和日誌追蹤
✅ 職責：純資料庫 CRUD 操作，不含業務邏輯
"""
from typing import List, Dict, Optional
from datetime import datetime
from services.db import SupabaseDB
from psycopg2.extras import RealDictCursor
from services.logger import logger, log_db_operation


class PaymentRepository:
    """租金資料存取物件（Repository Pattern）"""
    
    def __init__(self):
        self.db = SupabaseDB()
    
    # ==================== 新增方法 ====================
    
    def create_schedule(self, schedule_data: Dict) -> Optional[int]:
        """新增租金排程
        
        Args:
            schedule_data: 租金排程資料
                - room_number: 房號
                - tenant_name: 租客姓名
                - payment_year: 年份
                - payment_month: 月份
                - amount: 應繳金額
                - due_date: 到期日
                - payment_method: 繳費方式
                - status: 狀態（預設 'unpaid'）
        
        Returns:
            新增的排程 ID，失敗回傳 None
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                query = """
                    INSERT INTO payment_schedule (
                        room_number, tenant_name, payment_year, payment_month,
                        amount, due_date, payment_method, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                
                cur.execute(query, (
                    schedule_data['room_number'],
                    schedule_data['tenant_name'],
                    schedule_data['payment_year'],
                    schedule_data['payment_month'],
                    schedule_data['amount'],
                    schedule_data['due_date'],
                    schedule_data['payment_method'],
                    schedule_data.get('status', 'unpaid')
                ))
                
                schedule_id = cur.fetchone()[0]
                
                log_db_operation("INSERT", "payment_schedule", True, 1)
                logger.info(f"✅ 新增租金排程: {schedule_data['room_number']} - {schedule_data['payment_year']}/{schedule_data['payment_month']}")
                
                return schedule_id
        
        except Exception as e:
            log_db_operation("INSERT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 新增租金排程失敗: {str(e)}")
            return None
    
    def schedule_exists(self, room_number: str, year: int, month: int) -> bool:
        """檢查排程是否已存在
        
        Args:
            room_number: 房號
            year: 年份
            month: 月份
        
        Returns:
            是否存在
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT 1 FROM payment_schedule
                    WHERE room_number = %s
                      AND payment_year = %s
                      AND payment_month = %s
                """, (room_number, year, month))
                
                exists = cur.fetchone() is not None
                
                log_db_operation("SELECT", "payment_schedule", True, 1 if exists else 0)
                
                return exists
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 檢查排程存在失敗: {str(e)}")
            return False
    
    # ==================== 查詢方法 ====================
    
    def get_by_status(self, status: str) -> List[Dict]:
        """依狀態查詢
        
        Args:
            status: 狀態 (paid/unpaid/overdue)
        
        Returns:
            租金記錄列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("""
                    SELECT 
                        id, room_number, tenant_name,
                        payment_year, payment_month,
                        amount, paid_amount, due_date,
                        payment_method, status,
                        created_at, updated_at
                    FROM payment_schedule
                    WHERE status = %s
                    ORDER BY due_date
                """, (status,))
                
                results = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(results))
                logger.info(f"✅ 查詢租金 (狀態: {status}): {len(results)} 筆")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢租金失敗 (狀態: {status}): {str(e)}")
            return []
    
    def get_by_id(self, payment_id: int) -> Optional[Dict]:
        """依 ID 查詢單筆
        
        Args:
            payment_id: 租金記錄 ID
        
        Returns:
            租金記錄或 None
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("""
                    SELECT 
                        id, room_number, tenant_name,
                        payment_year, payment_month,
                        amount, paid_amount, due_date,
                        payment_method, status,
                        created_at, updated_at
                    FROM payment_schedule 
                    WHERE id = %s
                """, (payment_id,))
                
                result = cur.fetchone()
                
                if result:
                    log_db_operation("SELECT", "payment_schedule", True, 1)
                    logger.info(f"✅ 查詢租金: ID {payment_id}")
                    return dict(result)
                else:
                    logger.warning(f"⚠️ 租金記錄不存在: ID {payment_id}")
                    return None
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢租金失敗 (ID {payment_id}): {str(e)}")
            return None
    
    def find_by_id(self, payment_id: int) -> Optional[Dict]:
        """依 ID 查詢單筆（別名方法）
        
        Args:
            payment_id: 租金記錄 ID
        
        Returns:
            租金記錄或 None
        """
        return self.get_by_id(payment_id)
    
    def get_by_period(self, year: int, month: int) -> List[Dict]:
        """依期間查詢
        
        Args:
            year: 年份
            month: 月份
        
        Returns:
            租金記錄列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("""
                    SELECT 
                        id, room_number, tenant_name,
                        payment_year, payment_month,
                        amount, paid_amount, due_date,
                        payment_method, status,
                        created_at, updated_at
                    FROM payment_schedule
                    WHERE payment_year = %s AND payment_month = %s
                    ORDER BY room_number
                """, (year, month))
                
                results = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(results))
                logger.info(f"✅ 查詢租金 ({year}/{month}): {len(results)} 筆")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢租金失敗 ({year}/{month}): {str(e)}")
            return []
    
    def get_by_room_and_period(self, room_number: str, year: int, month: int) -> List[Dict]:
        """取得指定房間和期間的租金記錄
        
        Args:
            room_number: 房號
            year: 年份
            month: 月份
        
        Returns:
            租金記錄列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("""
                    SELECT 
                        id, room_number, tenant_name,
                        payment_year, payment_month,
                        amount, paid_amount, due_date,
                        payment_method, status,
                        created_at, updated_at,
                        CASE 
                            WHEN status = 'unpaid' AND due_date < CURRENT_DATE 
                            THEN 'overdue'
                            ELSE status
                        END as display_status
                    FROM payment_schedule
                    WHERE room_number = %s
                        AND payment_year = %s
                        AND payment_month = %s
                    ORDER BY due_date DESC
                """, (room_number, year, month))
                
                results = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(results))
                logger.info(f"✅ 查詢房間租金記錄: {room_number} {year}/{month} - {len(results)} 筆")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢房間租金記錄失敗: {str(e)}")
            return []
    
    def get_all_payments(
        self,
        year: Optional[int] = None, 
        month: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """取得所有租金記錄（支援篩選）
        
        Args:
            year: 年份（選填）
            month: 月份（選填）
            status: 狀態（選填）
        
        Returns:
            租金記錄列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                conditions = []
                params = []
                
                if year:
                    conditions.append("payment_year = %s")
                    params.append(year)
                
                if month:
                    conditions.append("payment_month = %s")
                    params.append(month)
                
                if status:
                    conditions.append("status = %s")
                    params.append(status)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                query = f"""
                    SELECT 
                        id, room_number, tenant_name,
                        payment_year, payment_month,
                        amount, paid_amount, due_date,
                        payment_method, status,
                        created_at, updated_at
                    FROM payment_schedule
                    WHERE {where_clause}
                    ORDER BY payment_year DESC, payment_month DESC, room_number
                """
                
                cur.execute(query, tuple(params))
                results = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(results))
                logger.info(f"✅ 查詢所有租金: {len(results)} 筆")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢所有租金失敗: {str(e)}")
            return []
    
    def get_overdue_payments(self) -> List[Dict]:
        """取得所有逾期未繳的租金記錄
        
        Returns:
            逾期租金記錄列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("""
                    SELECT 
                        id, room_number, tenant_name,
                        payment_year, payment_month,
                        amount, paid_amount, due_date,
                        payment_method, status,
                        created_at, updated_at,
                        CURRENT_DATE - due_date as overdue_days
                    FROM payment_schedule
                    WHERE status = 'unpaid' AND due_date < CURRENT_DATE
                    ORDER BY due_date ASC
                """)
                
                results = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(results))
                logger.info(f"✅ 查詢逾期租金: {len(results)} 筆")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢逾期租金失敗: {str(e)}")
            return []
    
    def get_tenant_payment_history(self, room_number: str, limit: int = 12) -> List[Dict]:
        """取得房客繳款歷史
        
        Args:
            room_number: 房號
            limit: 筆數限制
        
        Returns:
            繳款歷史列表
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("""
                    SELECT 
                        id, room_number, tenant_name,
                        payment_year, payment_month,
                        amount, paid_amount, due_date,
                        payment_method, status,
                        created_at, updated_at
                    FROM payment_schedule
                    WHERE room_number = %s
                    ORDER BY payment_year DESC, payment_month DESC
                    LIMIT %s
                """, (room_number, limit))
                
                results = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(results))
                logger.info(f"✅ 查詢繳款歷史: {room_number} - {len(results)} 筆")
                
                return [dict(r) for r in results]
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢繳款歷史失敗: {str(e)}")
            return []
    
    # ==================== 統計方法 ====================
    
    def get_payment_summary(self, year: int, month: int) -> Dict:
        """取得租金摘要統計
        
        Args:
            year: 年份
            month: 月份
        
        Returns:
            統計資料字典
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                cur.execute("""
                    SELECT
                        COUNT(*) as total_count,
                        SUM(amount) as total_expected,
                        SUM(CASE WHEN status = 'paid' THEN paid_amount ELSE 0 END) as total_received,
                        COUNT(CASE WHEN status = 'unpaid' THEN 1 END) as unpaid_count,
                        COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_count,
                        COUNT(CASE WHEN status = 'unpaid' AND due_date < CURRENT_DATE THEN 1 END) as overdue_count
                    FROM payment_schedule
                    WHERE payment_year = %s AND payment_month = %s
                """, (year, month))
                
                result = cur.fetchone()
                
                if not result or result['total_count'] == 0:
                    log_db_operation("SELECT", "payment_summary", True, 0)
                    logger.info(f"✅ 租金摘要 ({year}/{month}): 無記錄")
                    
                    return {
                        'total_expected': 0,
                        'total_received': 0,
                        'unpaid_count': 0,
                        'paid_count': 0,
                        'overdue_count': 0,
                        'collection_rate': 0.0
                    }
                
                total_expected = float(result['total_expected'] or 0)
                total_received = float(result['total_received'] or 0)
                collection_rate = total_received / total_expected if total_expected > 0 else 0.0
                
                summary = {
                    'total_expected': total_expected,
                    'total_received': total_received,
                    'unpaid_count': int(result['unpaid_count'] or 0),
                    'paid_count': int(result['paid_count'] or 0),
                    'overdue_count': int(result['overdue_count'] or 0),
                    'collection_rate': collection_rate
                }
                
                log_db_operation("SELECT", "payment_summary", True, 1)
                logger.info(f"✅ 租金摘要 ({year}/{month}): 已收 {summary['paid_count']}/{summary['paid_count'] + summary['unpaid_count']}")
                
                return summary
        
        except Exception as e:
            log_db_operation("SELECT", "payment_summary", False, error=str(e))
            logger.error(f"❌ 查詢租金摘要失敗: {str(e)}")
            return {
                'total_expected': 0,
                'total_received': 0,
                'unpaid_count': 0,
                'paid_count': 0,
                'overdue_count': 0,
                'collection_rate': 0.0
            }
    
    # ==================== 更新方法 ====================
    
    def mark_as_paid(
        self,
        payment_id: int,
        paid_amount: float,
        paid_date: datetime = None,  # 保留參數以向後兼容，但不使用
        notes: str = ""              # 保留參數以向後兼容，但不使用
    ) -> bool:
        """標記為已繳款
        
        Args:
            payment_id: 排程 ID
            paid_amount: 繳款金額
            paid_date: 繳款日期（已移除，保留相容性）
            notes: 備註（已移除，保留相容性）
        
        Returns:
            是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                # ✅ 只更新資料庫實際存在的欄位
                cur.execute("""
                    UPDATE payment_schedule
                    SET status = 'paid',
                        paid_amount = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (paid_amount, payment_id))
                
                success = cur.rowcount > 0
                
                if success:
                    log_db_operation("UPDATE", "payment_schedule", True, 1)
                    logger.info(f"✅ 標記已繳款: ID {payment_id}, 金額 NT${paid_amount:,.0f}")
                else:
                    logger.warning(f"⚠️ 租金記錄不存在: ID {payment_id}")
                
                return success
        
        except Exception as e:
            log_db_operation("UPDATE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 標記已繳款失敗 (ID {payment_id}): {str(e)}")
            return False
    
    def update_overdue_status(self) -> int:
        """更新逾期狀態
        
        Returns:
            更新的筆數
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    UPDATE payment_schedule
                    SET status = 'overdue', updated_at = NOW()
                    WHERE status = 'unpaid'
                      AND due_date < CURRENT_DATE
                """)
                
                updated_count = cur.rowcount
                
                log_db_operation("UPDATE", "payment_schedule", True, updated_count)
                logger.info(f"✅ 更新逾期狀態: {updated_count} 筆")
                
                return updated_count
        
        except Exception as e:
            log_db_operation("UPDATE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 更新逾期狀態失敗: {str(e)}")
            return 0
    
    def update_payment(self, payment_id: int, update_data: Dict) -> bool:
        """更新租金記錄
        
        Args:
            payment_id: 租金記錄 ID
            update_data: 要更新的欄位字典
        
        Returns:
            是否更新成功
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                # 允許更新的欄位
                allowed_fields = [
                    'room_number', 'tenant_name', 'payment_year', 'payment_month',
                    'amount', 'paid_amount', 'due_date', 'payment_method', 'status'
                ]
                
                set_clauses = []
                values = []
                
                for field in allowed_fields:
                    if field in update_data:
                        set_clauses.append(f"{field} = %s")
                        values.append(update_data[field])
                
                if not set_clauses:
                    logger.warning("⚠️ 沒有要更新的欄位")
                    return False
                
                set_clauses.append("updated_at = NOW()")
                values.append(payment_id)
                
                query = f"""
                    UPDATE payment_schedule
                    SET {', '.join(set_clauses)}
                    WHERE id = %s
                """
                
                cur.execute(query, values)
                
                success = cur.rowcount > 0
                
                if success:
                    log_db_operation("UPDATE", "payment_schedule", True, 1)
                    logger.info(f"✅ 更新租金記錄: ID {payment_id}")
                else:
                    logger.warning(f"⚠️ 租金記錄不存在: ID {payment_id}")
                
                return success
        
        except Exception as e:
            log_db_operation("UPDATE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 更新租金記錄失敗 (ID {payment_id}): {str(e)}")
            return False
    
    # ==================== 刪除方法 ====================
    
    def delete_payment(self, payment_id: int) -> bool:
        """刪除租金記錄
        
        Args:
            payment_id: 租金記錄 ID
        
        Returns:
            是否刪除成功
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    DELETE FROM payment_schedule
                    WHERE id = %s
                """, (payment_id,))
                
                success = cur.rowcount > 0
                
                if success:
                    log_db_operation("DELETE", "payment_schedule", True, 1)
                    logger.info(f"✅ 刪除租金記錄: ID {payment_id}")
                else:
                    logger.warning(f"⚠️ 租金記錄不存在: ID {payment_id}")
                
                return success
        
        except Exception as e:
            log_db_operation("DELETE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 刪除租金記錄失敗 (ID {payment_id}): {str(e)}")
            return False
    
    def batch_delete_by_period(self, year: int, month: int) -> int:
        """批次刪除指定期間的租金記錄
        
        Args:
            year: 年份
            month: 月份
        
        Returns:
            刪除的筆數
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    DELETE FROM payment_schedule
                    WHERE payment_year = %s AND payment_month = %s
                """, (year, month))
                
                deleted_count = cur.rowcount
                
                log_db_operation("DELETE", "payment_schedule", True, deleted_count)
                logger.info(f"✅ 批次刪除租金記錄: {year}/{month} - {deleted_count} 筆")
                
                return deleted_count
        
        except Exception as e:
            log_db_operation("DELETE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 批次刪除租金記錄失敗: {str(e)}")
            return 0
