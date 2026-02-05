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
    """電費管理服務 (繼承 BaseDBService)"""
    
    def __init__(self):
        super().__init__()
    
    # ==================== 期間管理 ====================
    
    def add_period(
        self, 
        year: int, 
        month_start: int, 
        month_end: int
    ) -> Tuple[bool, str, Optional[int]]:
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
            # ✅ 驗證輸入
            if not (1 <= month_start <= 12 and 1 <= month_end <= 12):
                return False, "❌ 月份必須在 1-12 之間", None
            
            if month_start > month_end:
                return False, "❌ 開始月不能大於結束月", None
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 檢查是否已存在
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM electricity_periods
                    WHERE period_year = %s 
                    AND period_month_start = %s 
                    AND period_month_end = %s
                    """,
                    (year, month_start, month_end)
                )
                
                if cursor.fetchone()[0] > 0:
                    logger.warning(f"⚠️ 期間已存在: {year}/{month_start}-{month_end}")
                    return False, f"❌ {year}/{month_start}-{month_end} 已存在", None
                
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
                logger.info(f"✅ 建立期間 ID {period_id}: {year}/{month_start}-{month_end}")
                return True, f"✅ 已建立 {year} 年 {month_start}-{month_end} 月", period_id
        
        except Exception as e:
            log_db_operation("INSERT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 建立失敗: {str(e)}")
            return False, f"❌ {str(e)[:100]}", None
    
    def get_all_periods(self) -> List[Dict]:
        """取得所有期間"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT 
                        id, 
                        period_year, 
                        period_month_start, 
                        period_month_end, 
                        remind_start_date, 
                        created_at
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
                        'created_at': row[5],
                        'display': f"{row[1]}/{row[2]:02d}-{row[3]:02d}"  # ✅ 新增顯示格式
                    }
                    for row in rows
                ]
                
                log_db_operation("SELECT", "electricity_periods", True, len(result))
                logger.info(f"✅ 查詢到 {len(result)} 個電費期間")
                return result
        
        except Exception as e:
            log_db_operation("SELECT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return []
    
    def get_period_by_id(self, period_id: int) -> Optional[Dict]:
        """
        根據 ID 查詢期間
        
        Args:
            period_id: 期間 ID
        
        Returns:
            期間資訊字典
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT 
                        id, period_year, period_month_start, 
                        period_month_end, remind_start_date, created_at
                    FROM electricity_periods
                    WHERE id = %s
                    """,
                    (period_id,)
                )
                
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(f"⚠️ 期間 ID {period_id} 不存在")
                    return None
                
                return {
                    'id': row[0],
                    'period_year': row[1],
                    'period_month_start': row[2],
                    'period_month_end': row[3],
                    'remind_start_date': row[4],
                    'created_at': row[5],
                    'display': f"{row[1]}/{row[2]:02d}-{row[3]:02d}"
                }
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None
    
    def delete_period(self, period_id: int) -> Tuple[bool, str]:
        """刪除期間"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 檢查是否存在
                cursor.execute("SELECT COUNT(*) FROM electricity_periods WHERE id = %s", (period_id,))
                if cursor.fetchone()[0] == 0:
                    return False, f"❌ 期間 ID {period_id} 不存在"
                
                # ✅ 檢查是否有關聯記錄
                cursor.execute("SELECT COUNT(*) FROM electricity_records WHERE period_id = %s", (period_id,))
                record_count = cursor.fetchone()[0]
                
                if record_count > 0:
                    logger.warning(f"⚠️ 期間 {period_id} 有 {record_count} 筆關聯記錄")
                    # 可選：是否允許強制刪除？
                    # return False, f"❌ 期間有 {record_count} 筆關聯記錄，請先刪除記錄"
                
                cursor.execute("DELETE FROM electricity_periods WHERE id = %s", (period_id,))
                
                log_db_operation("DELETE", "electricity_periods", True, 1)
                logger.info(f"✅ 刪除期間 ID: {period_id}")
                return True, "✅ 已刪除期間"
        
        except Exception as e:
            log_db_operation("DELETE", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 刪除失敗: {str(e)}")
            return False, f"❌ {str(e)[:100]}"
    
    def update_period_remind_date(
        self, 
        period_id: int, 
        remind_date: str
    ) -> Tuple[bool, str]:
        """更新催繳開始日"""
        try:
            # ✅ 驗證日期格式
            try:
                datetime.strptime(remind_date, '%Y-%m-%d')
            except ValueError:
                return False, "❌ 日期格式錯誤，應為 YYYY-MM-DD"
            
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
                    return False, f"❌ 未找到期間 ID {period_id}"
                
                log_db_operation("UPDATE", "electricity_periods", True, 1)
                logger.info(f"✅ 設定催繳日期: {remind_date} (期間 {period_id})")
                return True, f"✅ 已設定催繳日期: {remind_date}"
        
        except Exception as e:
            log_db_operation("UPDATE", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, f"❌ {str(e)[:100]}"
    
    # ==================== 電表讀數 ====================
    
    def get_latest_meter_reading(
        self, 
        room: str, 
        period_id: int
    ) -> Optional[float]:
        """
        取得最新電表讀數
        
        Args:
            room: 房號
            period_id: 當前期間 ID
        
        Returns:
            最新讀數，如果沒有則返回 None
        """
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
                    logger.debug(f"🔍 {room} 上期讀數: {result[0]}")
                    return float(result[0])
                
                logger.debug(f"📭 {room} 無上期讀數")
                return None
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None
    
    def get_all_readings(self, period_id: int) -> List[Dict]:
        """
        取得特定期間的所有電表讀數
        
        Args:
            period_id: 期間 ID
        
        Returns:
            讀數列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT 
                        room_number,
                        previous_reading,
                        current_reading,
                        kwh_used,
                        created_at
                    FROM electricity_readings
                    WHERE period_id = %s
                    ORDER BY room_number
                    """,
                    (period_id,)
                )
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                log_db_operation("SELECT", "electricity_readings", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]
        
        except Exception as e:
            log_db_operation("SELECT", "electricity_readings", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return []
    
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
            # ✅ 驗證讀數邏輯
            if current < previous:
                logger.warning(f"⚠️ {room}: 本期讀數 ({current}) < 上期讀數 ({previous})")
                return False, f"❌ {room}: 本期讀數不能小於上期讀數"
            
            if abs((current - previous) - kwh_used) > 0.01:
                logger.warning(f"⚠️ {room}: 使用度數計算不符")
                return False, f"❌ {room}: 使用度數計算錯誤"
            
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
                logger.info(f"✅ {room}: {kwh_used} 度 ({previous} → {current})")
                return True, f"✅ 已儲存 {room}"
        
        except Exception as e:
            log_db_operation("INSERT", "electricity_readings", False, error=str(e))
            logger.error(f"❌ 儲存失敗: {str(e)}")
            return False, f"❌ {str(e)[:100]}"
    
    # ==================== 計費記錄 ====================
    
    def save_records(
        self, 
        period_id: int, 
        calc_results: List[Dict]
    ) -> Tuple[bool, str]:
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
                
                logger.info(f"📋 活躍租客: {len(tenant_map)} 位")
                
                # 2. 刪除舊記錄
                cursor.execute("DELETE FROM electricity_records WHERE period_id = %s", (period_id,))
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"🗑️ 已刪除 {deleted_count} 筆舊記錄")
                
                success_count = 0
                skip_count = 0
                
                for result in calc_results:
                    # ✅ 支援中英文欄位名稱
                    room_number = result.get('房号') or result.get('房號') or result.get('room_number', '')
                    room_type = result.get('类型') or result.get('類型') or result.get('room_type', '')
                    usage_kwh = float(result.get('使用度数') or result.get('使用度數') or result.get('usage_kwh', 0))
                    public_share_kwh = float(result.get('公用分摊') or result.get('公用分攤') or result.get('public_share_kwh', 0))
                    total_kwh = float(result.get('总度数') or result.get('總度數') or result.get('total_kwh', 0))
                    amount_due = int(result.get('应缴金额') or result.get('應繳金額') or result.get('amount_due', 0))
                    
                    tenant_id = tenant_map.get(room_number)
                    
                    if not tenant_id:
                        logger.warning(f"⚠️ 房間 {room_number} 沒有活躍租客，跳過")
                        skip_count += 1
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
                
                summary = f"✅ 成功儲存 {success_count} 筆計費記錄"
                if skip_count > 0:
                    summary += f"，跳過 {skip_count} 筆"
                
                logger.info(summary)
                return True, summary
            
            except Exception as e:
                log_db_operation("INSERT", "electricity_records", False, error=str(e))
                logger.error(f"❌ 儲存失敗: {str(e)}")
                return False, f"❌ {str(e)[:100]}"
    
    def get_payment_record(self, period_id: int) -> Optional[pd.DataFrame]:
        """查詢電費計費記錄"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    SELECT 
                        er.id,
                        er.room_number AS 房號,
                        er.room_type AS 類型,
                        COALESCE(eread.previous_reading, 0) AS 上期讀數,
                        COALESCE(eread.current_reading, 0) AS 本期讀數,
                        er.usage_kwh AS 使用度數,
                        er.public_share_kwh AS 公用分攤,
                        er.total_kwh AS 總度數,
                        er.amount_due AS 應繳金額,
                        er.paid_amount AS 已繳金額,
                        CASE 
                            WHEN er.payment_status = 'paid' THEN '✅ 已繳'
                            ELSE '⏳ 未繳'
                        END AS 繳費狀態,
                        er.payment_date AS 繳費日期,
                        t.tenant_name AS 租客姓名
                    FROM electricity_records er
                    LEFT JOIN electricity_readings eread 
                        ON er.period_id = eread.period_id 
                        AND er.room_number = eread.room_number
                    LEFT JOIN tenants t ON er.tenant_id = t.id
                    WHERE er.period_id = %s
                    ORDER BY er.room_number
                    """,
                    (period_id,)
                )
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                if not rows:
                    logger.info(f"📭 期間 {period_id} 無計費記錄")
                    return pd.DataFrame()
                
                df = pd.DataFrame(rows, columns=columns)
                log_db_operation("SELECT", "electricity_records", True, len(df))
                logger.info(f"✅ 查詢到 {len(df)} 筆計費記錄")
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
                        COUNT(*) as total_count,
                        SUM(amount_due) as total_due,
                        SUM(CASE WHEN payment_status = 'paid' THEN paid_amount ELSE 0 END) as total_paid,
                        SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END) as paid_count,
                        SUM(CASE WHEN payment_status = 'unpaid' THEN amount_due ELSE 0 END) as total_balance,
                        SUM(total_kwh) as total_kwh_used
                    FROM electricity_records
                    WHERE period_id = %s
                    """,
                    (period_id,)
                )
                
                row = cursor.fetchone()
                
                if not row or row[0] == 0:
                    logger.info(f"📭 期間 {period_id} 無統計數據")
                    return None
                
                total_count = int(row[0])
                paid_count = int(row[3] or 0)
                payment_rate = (paid_count / total_count * 100) if total_count > 0 else 0
                
                summary = {
                    'total_count': total_count,
                    'paid_count': paid_count,
                    'unpaid_count': total_count - paid_count,
                    'total_due': int(row[1] or 0),
                    'total_paid': int(row[2] or 0),
                    'total_balance': int(row[4] or 0),
                    'total_kwh_used': float(row[5] or 0),
                    'payment_rate': round(payment_rate, 1)
                }
                
                log_db_operation("SELECT", "electricity_records (summary)", True, 1)
                logger.info(f"📊 繳費率: {payment_rate:.1f}% ({paid_count}/{total_count})")
                
                return summary
        
        except Exception as e:
            log_db_operation("SELECT", "electricity_records (summary)", False, error=str(e))
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
            # ✅ 驗證狀態
            valid_statuses = ['paid', 'unpaid', 'partial']
            if new_status not in valid_statuses:
                return False, f"❌ 無效狀態: {new_status}"
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 檢查記錄是否存在
                cursor.execute(
                    """
                    SELECT amount_due FROM electricity_records
                    WHERE period_id = %s AND room_number = %s
                    """,
                    (period_id, room_number)
                )
                
                row = cursor.fetchone()
                if not row:
                    return False, f"❌ 未找到 {room_number} 的記錄"
                
                amount_due = row[0]
                
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
                
                log_db_operation("UPDATE", "electricity_records", True, 1)
                logger.info(f"✅ 更新繳費狀態: {room_number} -> {new_status} (NT${paid_amount:,}/NT${amount_due:,})")
                return True, f"✅ 更新成功: {room_number}"
        
        except Exception as e:
            log_db_operation("UPDATE", "electricity_records", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, f"❌ {str(e)[:100]}"
    
    def batch_update_payments(
        self,
        updates: List[Dict]
    ) -> Tuple[int, int]:
        """
        批次更新繳費狀態
        
        Args:
            updates: 更新列表，每個元素包含 period_id, room_number, status, paid_amount, payment_date
        
        Returns:
            (success_count, fail_count)
        """
        success_count = 0
        fail_count = 0
        
        for update in updates:
            try:
                success, msg = self.update_payment(
                    update['period_id'],
                    update['room_number'],
                    update['status'],
                    update['paid_amount'],
                    update['payment_date']
                )
                
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            
            except Exception as e:
                logger.error(f"❌ 批次更新失敗 {update.get('room_number', '?')}: {e}")
                fail_count += 1
        
        logger.info(f"✅ 批次更新: 成功 {success_count}, 失敗 {fail_count}")
        return success_count, fail_count
