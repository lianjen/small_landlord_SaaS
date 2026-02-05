"""
租金管理服務 - v4.0 Final
✅ 租金排程 CRUD
✅ 批次操作
✅ 統計分析
✅ 逾期檢測
"""

import pandas as pd
from datetime import date
from typing import Optional, Tuple, List

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


class PaymentService(BaseDBService):
    """租金管理服務"""
    
    def __init__(self):
        super().__init__()
    
    # ==================== 查詢操作 ====================
    
    def get_payment_schedule(
        self, 
        year: Optional[int] = None, 
        month: Optional[int] = None,
        room: Optional[str] = None, 
        status: Optional[str] = None
    ) -> pd.DataFrame:
        """
        查詢租金排程
        
        Args:
            year: 年份
            month: 月份
            room: 房號
            status: 狀態 (unpaid/paid/overdue)
        
        Returns:
            租金排程 DataFrame
        """
        def query():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                conditions = ["1=1"]
                params = []
                
                if year:
                    conditions.append("payment_year = %s")
                    params.append(year)
                if month:
                    conditions.append("payment_month = %s")
                    params.append(month)
                if room:
                    conditions.append("room_number = %s")
                    params.append(room)
                if status:
                    conditions.append("status = %s")
                    params.append(status)
                
                query_sql = f"""
                    SELECT id, room_number, tenant_name, payment_year, payment_month,
                           amount, paid_amount, payment_method, due_date, status, created_at, updated_at
                    FROM payment_schedule
                    WHERE {' AND '.join(conditions)}
                    ORDER BY payment_year DESC, payment_month DESC, room_number
                """
                
                cursor.execute(query_sql, params)
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(data))
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)
    
    def get_payment_by_id(self, payment_id: int) -> dict:
        """
        根據 ID 查詢租金記錄
        
        Args:
            payment_id: 租金記錄 ID
        
        Returns:
            租金記錄字典
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, room_number, tenant_name, payment_year, payment_month,
                           amount, paid_amount, payment_method, due_date, status
                    FROM payment_schedule
                    WHERE id = %s
                """, (payment_id,))
                
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None
    
    def get_overdue_payments(self) -> pd.DataFrame:
        """
        查詢逾期租金
        
        Returns:
            逾期租金 DataFrame
        """
        def query():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT room_number, tenant_name, payment_year, payment_month, amount, due_date
                    FROM payment_schedule
                    WHERE status = 'unpaid' AND due_date < CURRENT_DATE
                    ORDER BY due_date
                """)
                
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                
                log_db_operation("SELECT", "payment_schedule (overdue)", True, len(data))
                logger.warning(f"⚠️ {len(data)} 筆逾期帳單")
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)
    
    # ==================== 新增操作 ====================
    
    def add_payment_schedule(
        self, 
        room: str, 
        tenant_name: str, 
        year: int, 
        month: int,
        amount: float, 
        payment_method: str, 
        due_date: Optional[date] = None
    ) -> Tuple[bool, str]:
        """
        新增租金排程
        
        Args:
            room: 房號
            tenant_name: 租客姓名
            year: 年份
            month: 月份
            amount: 金額
            payment_method: 付款方式
            due_date: 到期日
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 檢查是否已存在
                cursor.execute("""
                    SELECT COUNT(*) FROM payment_schedule 
                    WHERE room_number = %s AND payment_year = %s AND payment_month = %s
                """, (room, year, month))
                
                if cursor.fetchone()[0] > 0:
                    logger.warning(f"❌ {room} {year}/{month} 已有記錄")
                    return False, f"{year}/{month} {room} 已存在"
                
                cursor.execute("""
                    INSERT INTO payment_schedule 
                    (room_number, tenant_name, payment_year, payment_month, amount, paid_amount,
                     payment_method, due_date, status)
                    VALUES (%s, %s, %s, %s, %s, 0, %s, %s, 'unpaid')
                """, (room, tenant_name, year, month, amount, payment_method, due_date))
                
                log_db_operation("INSERT", "payment_schedule", True, 1)
                logger.info(f"✅ 新增帳單: {room} {year}/{month} {amount}元")
                return True, "新增成功"
        
        except Exception as e:
            log_db_operation("INSERT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 新增失敗: {str(e)}")
            return False, f"新增失敗: {str(e)[:100]}"
    
    def batch_create_payment_schedule(self, schedules: list) -> Tuple[int, int, int]:
        """
        批次建立租金排程
        
        Args:
            schedules: 排程列表，每個元素包含 room_number, tenant_name, year, month, amount 等
        
        Returns:
            (success_count, skip_count, fail_count)
        """
        success_count = 0
        skip_count = 0
        fail_count = 0
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for schedule in schedules:
                    try:
                        # 檢查是否已存在
                        cursor.execute("""
                            SELECT COUNT(*) FROM payment_schedule 
                            WHERE room_number = %s AND payment_year = %s AND payment_month = %s
                        """, (schedule['room_number'], schedule['payment_year'], schedule['payment_month']))
                        
                        if cursor.fetchone()[0] > 0:
                            skip_count += 1
                            continue
                        
                        # 插入記錄
                        cursor.execute("""
                            INSERT INTO payment_schedule 
                            (room_number, tenant_name, payment_year, payment_month, amount, 
                             paid_amount, payment_method, due_date, status)
                            VALUES (%s, %s, %s, %s, %s, 0, %s, %s, 'unpaid')
                        """, (schedule['room_number'], schedule['tenant_name'], 
                              schedule['payment_year'], schedule['payment_month'],
                              schedule['amount'], schedule['payment_method'], schedule['due_date']))
                        
                        success_count += 1
                    
                    except Exception as e:
                        logger.error(f"❌ {schedule['room_number']} 失敗: {e}")
                        fail_count += 1
                
                log_db_operation("INSERT", "payment_schedule (batch)", True, success_count)
                logger.info(f"✅ 批量新增: 成功 {success_count}, 跳過 {skip_count}, 失敗 {fail_count}")
                return success_count, skip_count, fail_count
        
        except Exception as e:
            logger.error(f"❌ 批量操作失敗: {str(e)}")
            return 0, 0, len(schedules)
    
    # ==================== 更新操作 ====================
    
    def mark_payment_done(self, payment_id: int, paid_amount: Optional[float] = None) -> bool:
        """
        標記為已繳款
        
        Args:
            payment_id: 租金記錄 ID
            paid_amount: 實際繳款金額（可選）
        
        Returns:
            bool: 成功/失敗
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if paid_amount:
                    cursor.execute("""
                        UPDATE payment_schedule 
                        SET status = 'paid', paid_amount = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (paid_amount, payment_id))
                else:
                    cursor.execute("""
                        UPDATE payment_schedule 
                        SET status = 'paid', paid_amount = amount, updated_at = NOW()
                        WHERE id = %s
                    """, (payment_id,))
                
                log_db_operation("UPDATE", "payment_schedule", True, 1)
                logger.info(f"✅ 標記已繳 ID: {payment_id}")
                return True
        
        except Exception as e:
            log_db_operation("UPDATE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False
    
    def batch_mark_paid(self, payment_ids: list) -> Tuple[int, int]:
        """
        批次標記為已繳款
        
        Args:
            payment_ids: 租金記錄 ID 列表
        
        Returns:
            (success_count, fail_count)
        """
        success_count = 0
        fail_count = 0
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for payment_id in payment_ids:
                    try:
                        cursor.execute("""
                            UPDATE payment_schedule 
                            SET status = 'paid', paid_amount = amount, updated_at = NOW()
                            WHERE id = %s
                        """, (payment_id,))
                        success_count += 1
                    except Exception as e:
                        logger.error(f"❌ ID {payment_id} 失敗: {e}")
                        fail_count += 1
                
                log_db_operation("UPDATE", "payment_schedule (batch)", True, success_count)
                logger.info(f"✅ 批量標記: 成功 {success_count}, 失敗 {fail_count}")
                return success_count, fail_count
        
        except Exception as e:
            logger.error(f"❌ 批量操作失敗: {str(e)}")
            return 0, len(payment_ids)
    
    # ==================== 刪除操作 ====================
    
    def delete_payment_schedule(self, payment_id: int) -> Tuple[bool, str]:
        """
        刪除租金排程
        
        Args:
            payment_id: 租金記錄 ID
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM payment_schedule WHERE id = %s", (payment_id,))
                
                log_db_operation("DELETE", "payment_schedule", True, 1)
                logger.info(f"✅ 刪除帳單 ID: {payment_id}")
                return True, "刪除成功"
        
        except Exception as e:
            log_db_operation("DELETE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 刪除失敗: {str(e)}")
            return False, f"刪除失敗: {str(e)}"
    
    # ==================== 統計分析 ====================
    
    def get_payment_statistics(self, year: int = None, month: int = None) -> dict:
        """
        取得租金統計數據
        
        Args:
            year: 年份（可選）
            month: 月份（可選）
        
        Returns:
            統計數據字典
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                conditions = ["1=1"]
                params = []
                
                if year:
                    conditions.append("payment_year = %s")
                    params.append(year)
                if month:
                    conditions.append("payment_month = %s")
                    params.append(month)
                
                where_clause = " AND ".join(conditions)
                
                cursor.execute(f"""
                    SELECT 
                        COUNT(*) as total_count,
                        SUM(amount) as total_amount,
                        SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_count,
                        SUM(CASE WHEN status = 'paid' THEN paid_amount ELSE 0 END) as paid_amount,
                        SUM(CASE WHEN status = 'unpaid' THEN 1 ELSE 0 END) as unpaid_count,
                        SUM(CASE WHEN status = 'unpaid' THEN amount ELSE 0 END) as unpaid_amount
                    FROM payment_schedule
                    WHERE {where_clause}
                """, params)
                
                row = cursor.fetchone()
                
                if not row or row[0] == 0:
                    logger.debug("📊 無統計數據")
                    return {
                        'total_amount': 0, 'paid_amount': 0, 'unpaid_amount': 0,
                        'total_count': 0, 'paid_count': 0, 'unpaid_count': 0, 'payment_rate': 0
                    }
                
                total_count, total_amount, paid_count, paid_amount, unpaid_count, unpaid_amount = row
                payment_rate = (paid_count / total_count * 100) if total_count > 0 else 0
                
                log_db_operation("SELECT", "payment_schedule (statistics)", True, total_count)
                
                return {
                    'total_amount': float(total_amount or 0),
                    'paid_amount': float(paid_amount or 0),
                    'unpaid_amount': float(unpaid_amount or 0),
                    'total_count': int(total_count),
                    'paid_count': int(paid_count),
                    'unpaid_count': int(unpaid_count),
                    'payment_rate': round(payment_rate, 1)
                }
        
        except Exception as e:
            logger.error(f"❌ 統計失敗: {str(e)}")
            return {}
    
    def get_payment_trends(self, year: int) -> List[dict]:
        """
        取得租金趨勢（按月）
        
        Args:
            year: 年份
        
        Returns:
            每月統計列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        payment_month,
                        SUM(amount) as total_amount,
                        SUM(CASE WHEN status = 'paid' THEN paid_amount ELSE 0 END) as paid_amount,
                        COUNT(*) as total_count,
                        SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_count
                    FROM payment_schedule
                    WHERE payment_year = %s
                    GROUP BY payment_month
                    ORDER BY payment_month
                """, (year,))
                
                trends = []
                for row in cursor.fetchall():
                    month, total_amt, paid_amt, total_cnt, paid_cnt = row
                    payment_rate = (paid_cnt / total_cnt * 100) if total_cnt > 0 else 0
                    trends.append({
                        'month': int(month),
                        'total_amount': float(total_amt or 0),
                        'paid_amount': float(paid_amt or 0),
                        'payment_rate': round(payment_rate, 1)
                    })
                
                log_db_operation("SELECT", "payment_schedule (trends)", True, len(trends))
                logger.info(f"✅ {year} 年趨勢: {len(trends)} 個月")
                return trends
        
        except Exception as e:
            logger.error(f"❌ 趨勢查詢失敗: {str(e)}")
            return []
    
    # ==================== 輔助方法 ====================
    
    def check_payment_exists(self, room: str, year: int, month: int) -> bool:
        """
        檢查租金記錄是否已存在
        
        Args:
            room: 房號
            year: 年份
            month: 月份
        
        Returns:
            bool: True=已存在, False=不存在
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM payment_schedule 
                    WHERE room_number = %s AND payment_year = %s AND payment_month = %s
                """, (room, year, month))
                
                exists = cursor.fetchone()[0] > 0
                logger.debug(f"🔍 {room} {year}/{month} - {'已存在' if exists else '不存在'}")
                return exists
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return False
