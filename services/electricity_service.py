"""
電費管理服務 - v4.0 Final
✅ 完整的電費期間管理
✅ 電表讀數儲存
✅ 計費記錄管理
✅ 整合通知服務
"""

import pandas as pd
from typing import Optional, Tuple, List, Dict
from datetime import datetime

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


class ElectricityService(BaseDBService):
    """電費管理服務"""
    
    def __init__(self):
        super().__init__()
    
    # ==================== 期間管理 ====================
    
    def add_period(self, year: int, month_start: int, month_end: int) -> Tuple[bool, str, Optional[int]]:
        """
        新增電費期間
        
        Args:
            year: 年份
            month_start: 開始月
            month_end: 結束月
        
        Returns:
            (bool, str, period_id): 成功/失敗訊息 + 期間 ID
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    INSERT INTO electricity_periods 
                    (period_year, period_month_start, period_month_end)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (year, month_start, month_end)
                )
                
                period_id = cursor.fetchone()[0]
                
                log_db_operation("INSERT", "electricity_periods", True, 1)
                logger.info(f"✅ 建立期間: {year}/{month_start}-{month_end}")
                return True, f"✅ 已建立 {year} 年 {month_start}-{month_end} 月", period_id
        
        except Exception as e:
            log_db_operation("INSERT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 建立失敗: {str(e)}")
            return False, str(e), None
    
    def get_all_periods(self) -> List[Dict]:
        """取得所有期間"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT id, period_year, period_month_start, period_month_end, 
                           remind_start_date, created_at
                    FROM electricity_periods
                    ORDER BY period_year DESC, period_month_start DESC
                    """
                )
                
                rows = cursor.fetchall()
                
                result = [
                    {
                        'id': row[0],
                        'period_year': row[1],
                        'period_month_start': row[2],
                        'period_month_end': row[3],
                        'remind_start_date': row[4],
                        'created_at': row[5]
                    }
                    for row in rows
                ]
                
                log_db_operation("SELECT", "electricity_periods", True, len(result))
                return result
        
        except Exception as e:
            log_db_operation("SELECT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return []
    
    def delete_period(self, period_id: int) -> Tuple[bool, str]:
        """刪除期間"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM electricity_periods WHERE id = %s", (period_id,))
                
                log_db_operation("DELETE", "electricity_periods", True, 1)
                logger.info(f"✅ 刪除期間 ID: {period_id}")
                return True, "✅ 已刪除期間"
        
        except Exception as e:
            log_db_operation("DELETE", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 刪除失敗: {str(e)}")
            return False, str(e)
    
    def update_period_remind_date(self, period_id: int, remind_date: str) -> Tuple[bool, str]:
        """更新催繳開始日"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    UPDATE electricity_periods 
                    SET remind_start_date = %s
                    WHERE id = %s
                    """,
                    (remind_date, period_id)
                )
                
                if cursor.rowcount == 0:
                    return False, f"❌ 未找到期間"
                
                log_db_operation("UPDATE", "electricity_periods", True, 1)
                logger.info(f"✅ 設定催繳日期: {remind_date}")
                return True, f"✅ 已設定催繳日期: {remind_date}"
        
        except Exception as e:
            log_db_operation("UPDATE", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, str(e)
    
    # ==================== 電表讀數 ====================
    
    def get_latest_meter_reading(self, room: str, period_id: int) -> Optional[float]:
        """取得最新電表讀數"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT current_reading 
                    FROM electricity_readings
                    WHERE room_number = %s AND period_id < %s
                    ORDER BY period_id DESC
                    LIMIT 1
                    """,
                    (room, period_id)
                )
                
                result = cursor.fetchone()
                if result:
                    return float(result[0])
                
                return None
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None
    
    def save_reading(
        self, 
        period_id: int, 
        room: str, 
        previous: float, 
        current: float, 
        kwh_used: float
    ) -> Tuple[bool, str]:
        """儲存電表讀數"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    INSERT INTO electricity_readings 
                    (period_id, room_number, previous_reading, current_reading, kwh_used)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (period_id, room_number) DO UPDATE SET
                        previous_reading = EXCLUDED.previous_reading,
                        current_reading = EXCLUDED.current_reading,
                        kwh_used = EXCLUDED.kwh_used,
                        updated_at = NOW()
                    """,
                    (period_id, room, previous, current, kwh_used)
                )
                
                log_db_operation("INSERT", "electricity_readings", True, 1)
                logger.info(f"✅ {room}: {kwh_used} 度")
                return True, f"✅ 已儲存 {room}"
        
        except Exception as e:
            log_db_operation("INSERT", "electricity_readings", False, error=str(e))
            logger.error(f"❌ 儲存失敗: {str(e)}")
            return False, str(e)
    
    # ==================== 計費記錄 ====================
    
    def save_records(self, period_id: int, calc_results: list) -> Tuple[bool, str]:
        """
        儲存電費計算結果
        
        Args:
            period_id: 期間 ID
            calc_results: 計算結果列表
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 1. 取得租客映射
                tenant_map = {}
                cursor.execute("""
                    SELECT id, room_number 
                    FROM tenants 
                    WHERE is_active = true
                """)
                for row in cursor.fetchall():
                    tenant_map[row[1]] = row[0]
                
                # 2. 刪除舊記錄
                cursor.execute("DELETE FROM electricity_records WHERE period_id = %s", (period_id,))
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"🗑️ 已刪除 {deleted_count} 筆舊記錄")
                
                success_count = 0
                for result in calc_results:
                    room_number = result.get('房号', result.get('房號', ''))
                    room_type = result.get('类型', result.get('類型', ''))
                    usage_kwh = float(result.get('使用度数', result.get('使用度數', 0)))
                    public_share_kwh = float(result.get('公用分摊', result.get('公用分攤', 0)))
                    total_kwh = float(result.get('总度数', result.get('總度數', 0)))
                    amount_due = int(result.get('应缴金额', result.get('應繳金額', 0)))
                    
                    tenant_id = tenant_map.get(room_number)
                    
                    if not tenant_id:
                        logger.warning(f"⚠️ 房間 {room_number} 沒有活躍租客，跳過")
                        continue
                    
                    # 更新讀數
                    if 'previous_reading' in result and 'current_reading' in result:
                        cursor.execute(
                            """
                            INSERT INTO electricity_readings 
                            (period_id, room_number, previous_reading, current_reading, kwh_used)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (period_id, room_number) DO UPDATE SET
                                previous_reading = EXCLUDED.previous_reading,
                                current_reading = EXCLUDED.current_reading,
                                kwh_used = EXCLUDED.kwh_used,
                                updated_at = NOW()
                            """,
                            (period_id, room_number, result['previous_reading'], 
                             result['current_reading'], usage_kwh)
                        )
                    
                    # 插入計費記錄
                    cursor.execute(
                        """
                        INSERT INTO electricity_records 
                        (period_id, room_number, room_type, tenant_id, status,
                         usage_kwh, public_share_kwh, total_kwh, 
                         amount_due, paid_amount, payment_status, payment_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (period_id, room_number) DO UPDATE SET
                            room_type = EXCLUDED.room_type,
                            tenant_id = EXCLUDED.tenant_id,
                            status = EXCLUDED.status,
                            usage_kwh = EXCLUDED.usage_kwh,
                            public_share_kwh = EXCLUDED.public_share_kwh,
                            total_kwh = EXCLUDED.total_kwh,
                            amount_due = EXCLUDED.amount_due,
                            updated_at = NOW()
                        """,
                        (period_id, room_number, room_type, tenant_id, 'unpaid',
                         usage_kwh, public_share_kwh, total_kwh, amount_due,
                         0, 'unpaid', None)
                    )
                    success_count += 1
                
                log_db_operation("INSERT", "electricity_records", True, success_count)
                logger.info(f"✅ 成功儲存 {success_count} 筆計費記錄")
                return True, f"✅ 已儲存 {success_count} 筆計費記錄"
            
            except Exception as e:
                log_db_operation("INSERT", "electricity_records", False, error=str(e))
                logger.error(f"❌ 儲存失敗: {str(e)}")
                return False, str(e)
    
    def get_payment_record(self, period_id: int) -> Optional[pd.DataFrame]:
        """查詢電費計費記錄"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT 
                        er.room_number AS 房號,
                        er.room_type AS 類型,
                        COALESCE(eread.previous_reading, 0) AS 上期讀數,
                        COALESCE(eread.current_reading, 0) AS 本期讀數,
                        er.usage_kwh AS 使用度數,
                        er.public_share_kwh AS 公用分攤,
                        er.total_kwh AS 總度數,
                        er.amount_due AS 應繳金額,
                        CASE 
                            WHEN er.payment_status = 'paid' THEN '✅ 已繳'
                            ELSE '⏳ 未繳'
                        END AS 繳費狀態,
                        er.payment_date AS 繳費日期
                    FROM electricity_records er
                    LEFT JOIN electricity_readings eread 
                        ON er.period_id = eread.period_id 
                        AND er.room_number = eread.room_number
                    WHERE er.period_id = %s
                    ORDER BY er.room_number
                    """,
                    (period_id,)
                )
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                if not rows:
                    return pd.DataFrame()
                
                df = pd.DataFrame(rows, columns=columns)
                log_db_operation("SELECT", "electricity_records", True, len(df))
                return df
        
        except Exception as e:
            log_db_operation("SELECT", "electricity_records", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None
    
    def get_payment_summary(self, period_id: int) -> Optional[Dict]:
        """取得電費統計摘要"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT 
                        SUM(amount_due) as total_due,
                        SUM(CASE WHEN payment_status = 'paid' THEN paid_amount ELSE 0 END) as total_paid,
                        SUM(CASE WHEN payment_status = 'unpaid' THEN amount_due ELSE 0 END) as total_balance
                    FROM electricity_records
                    WHERE period_id = %s
                    """,
                    (period_id,)
                )
                
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return {
                    'total_due': int(row[0] or 0),
                    'total_paid': int(row[1] or 0),
                    'total_balance': int(row[2] or 0)
                }
        
        except Exception as e:
            logger.error(f"❌ 統計失敗: {str(e)}")
            return None
    
    def update_payment(
        self, 
        period_id: int, 
        room_number: str, 
        new_status: str, 
        paid_amount: int, 
        payment_date: str
    ) -> Tuple[bool, str]:
        """更新電費繳費狀態"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    UPDATE electricity_records 
                    SET payment_status = %s, 
                        status = %s,
                        paid_amount = %s, 
                        payment_date = %s,
                        updated_at = NOW()
                    WHERE period_id = %s AND room_number = %s
                    """,
                    (new_status, new_status, paid_amount, payment_date, period_id, room_number)
                )
                
                if cursor.rowcount == 0:
                    return False, "❌ 未找到記錄"
                
                log_db_operation("UPDATE", "electricity_records", True, 1)
                logger.info(f"✅ 更新繳費狀態: {room_number} -> {new_status}")
                return True, "✅ 更新成功"
        
        except Exception as e:
            log_db_operation("UPDATE", "electricity_records", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, str(e)
