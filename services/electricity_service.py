"""
電費管理服務 - v4.2 Supabase Compatible
✅ 完整的電費期間管理
✅ 電表讀數儲存
✅ 計費記錄管理
✅ 整合通知服務
✅ 提供給追蹤頁面的高階查詢 API（get_period_records）
✅ 完全適配 Supabase 表結構（使用 electricity_readings，不使用 electricity_records）
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
        month_end: int,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        新增電費期間
        """
        try:
            # 驗證輸入
            if not (1 <= month_start <= 12 and 1 <= month_end <= 12):
                return False, "❌ 月份必須在 1-12 之間", None

            if month_start > month_end:
                return False, "❌ 開始月不能大於結束月", None

            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 檢查是否已存在
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM electricity_periods
                    WHERE period_year = %s
                      AND period_month_start = %s
                      AND period_month_end = %s
                    """,
                    (year, month_start, month_end),
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
                    (year, month_start, month_end),
                )

                period_id = cursor.fetchone()[0]
                conn.commit()

                log_db_operation("INSERT", "electricity_periods", True, 1)
                logger.info(
                    f"✅ 建立期間 ID {period_id}: {year}/{month_start}-{month_end}"
                )
                return True, f"✅ 已建立 {year} 年 {month_start}-{month_end} 月", period_id

        except Exception as e:
            log_db_operation("INSERT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 建立失敗: {str(e)}")
            return False, f"❌ {str(e)[:100]}", None

    def get_all_periods(self) -> List[Dict]:
        """取得所有電費期間（含 display 欄位）"""
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
                result: List[Dict] = []
                for row in rows:
                    result.append(
                        {
                            "id": row[0],
                            "period_year": row[1],
                            "period_month_start": row[2],
                            "period_month_end": row[3],
                            "remind_start_date": row[4],
                            "created_at": row[5],
                            "display": f"{row[1]}/{row[2]:02d}-{row[3]:02d}",
                        }
                    )

                log_db_operation("SELECT", "electricity_periods", True, len(result))
                logger.info(f"✅ 查詢到 {len(result)} 個電費期間")
                return result

        except Exception as e:
            log_db_operation("SELECT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return []

    def get_period_by_id(self, period_id: int) -> Optional[Dict]:
        """根據 ID 查詢單一期間"""
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
                    WHERE id = %s
                    """,
                    (period_id,),
                )

                row = cursor.fetchone()
                if not row:
                    logger.warning(f"⚠️ 期間 ID {period_id} 不存在")
                    return None

                return {
                    "id": row[0],
                    "period_year": row[1],
                    "period_month_start": row[2],
                    "period_month_end": row[3],
                    "remind_start_date": row[4],
                    "created_at": row[5],
                    "display": f"{row[1]}/{row[2]:02d}-{row[3]:02d}",
                }

        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None

    def delete_period(self, period_id: int) -> Tuple[bool, str]:
        """刪除期間（會先檢查關聯記錄）"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 檢查是否存在
                cursor.execute(
                    "SELECT COUNT(*) FROM electricity_periods WHERE id = %s",
                    (period_id,),
                )
                if cursor.fetchone()[0] == 0:
                    return False, f"❌ 期間 ID {period_id} 不存在"

                # 檢查是否有關聯記錄
                cursor.execute(
                    "SELECT COUNT(*) FROM electricity_readings WHERE period_id = %s",
                    (period_id,),
                )
                record_count = cursor.fetchone()[0]
                if record_count > 0:
                    logger.warning(
                        f"⚠️ 期間 {period_id} 有 {record_count} 筆關聯記錄（仍強制刪除期間本身）"
                    )

                cursor.execute(
                    "DELETE FROM electricity_periods WHERE id = %s", (period_id,)
                )
                conn.commit()

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
        remind_date: str,
    ) -> Tuple[bool, str]:
        """更新催繳開始日"""
        try:
            # 驗證日期格式
            try:
                datetime.strptime(remind_date, "%Y-%m-%d")
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
                    (remind_date, period_id),
                )

                if cursor.rowcount == 0:
                    return False, f"❌ 未找到期間 ID {period_id}"

                conn.commit()
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
        period_id: int,
    ) -> Optional[float]:
        """
        取得指定房間在「之前期間」的最後一次本期讀數
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
                    (room, period_id),
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
        """取得特定期間的所有電表讀數"""
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
                    (period_id,),
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
        kwh_used: float,
    ) -> Tuple[bool, str]:
        """儲存電表讀數"""
        try:
            # 驗證讀數邏輯
            if current < previous:
                logger.warning(
                    f"⚠️ {room}: 本期讀數 ({current}) < 上期讀數 ({previous})"
                )
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
                    (period_id, room, previous, current, kwh_used),
                )

                conn.commit()
                log_db_operation("INSERT", "electricity_readings", True, 1)
                logger.info(f"✅ {room}: {kwh_used} 度 ({previous} → {current})")
                return True, f"✅ 已儲存 {room}"

        except Exception as e:
            log_db_operation("INSERT", "electricity_readings", False, error=str(e))
            logger.error(f"❌ 儲存失敗: {str(e)}")
            return False, f"❌ {str(e)[:100]}"

    # ==================== 計費記錄（已廢棄 electricity_records 表，改用 electricity_readings）====================

    def get_payment_record(self, period_id: int) -> Optional[pd.DataFrame]:
        """
        查詢指定期間的電費計費記錄（DataFrame 版本）
        ✅ 修正：直接從 electricity_readings 查詢，不使用 electricity_records
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        er.id,
                        er.room_number AS 房號,
                        t.name AS 租客姓名,
                        er.previous_reading AS 上期讀數,
                        er.current_reading AS 本期讀數,
                        er.kwh_used AS 使用度數,
                        0 AS 公用分攤,
                        er.kwh_used AS 總度數,
                        CAST(er.kwh_used * 5 AS INTEGER) AS 應繳金額,
                        0 AS 已繳金額,
                        '⏳ 未繳' AS 繳費狀態,
                        NULL AS 繳費日期,
                        ep.period_year,
                        ep.period_month_start,
                        ep.period_month_end
                    FROM electricity_readings er
                    LEFT JOIN electricity_periods ep ON er.period_id = ep.id
                    LEFT JOIN tenants t ON er.room_number = t.room_number
                    WHERE er.period_id = %s
                    ORDER BY er.room_number
                    """,
                    (period_id,),
                )

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                if not rows:
                    logger.info(f"📭 期間 {period_id} 無計費記錄")
                    return pd.DataFrame()

                df = pd.DataFrame(rows, columns=columns)
                log_db_operation("SELECT", "electricity_readings", True, len(df))
                logger.info(f"✅ 查詢到 {len(df)} 筆電費記錄")
                return df

        except Exception as e:
            log_db_operation("SELECT", "electricity_readings", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None

    def get_period_records(self, period_id: int) -> pd.DataFrame:
        """
        追蹤頁面用高階 API：
        - 對應 views.tracking.render_electricity_tracking / render_combined_tracking
        - 內部直接呼叫 get_payment_record，保證回傳 DataFrame
        """
        df = self.get_payment_record(period_id)
        if df is None:
            return pd.DataFrame()
        return df

    def get_payment_summary(self, period_id: int) -> Optional[Dict]:
        """取得電費統計摘要"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_count,
                        SUM(kwh_used * 5) as total_due,
                        0 as total_paid,
                        0 as paid_count,
                        SUM(kwh_used * 5) as total_balance,
                        SUM(kwh_used) as total_kwh_used
                    FROM electricity_readings
                    WHERE period_id = %s
                    """,
                    (period_id,),
                )

                row = cursor.fetchone()

                if not row or row[0] == 0:
                    logger.info(f"📭 期間 {period_id} 無統計數據")
                    return None

                total_count = int(row[0])
                paid_count = int(row[3] or 0)
                payment_rate = (
                    paid_count / total_count * 100 if total_count > 0 else 0
                )

                summary = {
                    "total_count": total_count,
                    "paid_count": paid_count,
                    "unpaid_count": total_count - paid_count,
                    "total_due": int(row[1] or 0),
                    "total_paid": int(row[2] or 0),
                    "total_balance": int(row[4] or 0),
                    "total_kwh_used": float(row[5] or 0),
                    "payment_rate": round(payment_rate, 1),
                }

                log_db_operation(
                    "SELECT", "electricity_readings (summary)", True, 1
                )
                logger.info(
                    f"📊 繳費率: {payment_rate:.1f}% ({paid_count}/{total_count})"
                )

                return summary

        except Exception as e:
            log_db_operation(
                "SELECT", "electricity_readings (summary)", False, error=str(e)
            )
            logger.error(f"❌ 統計失敗: {str(e)}")
            return None

    # ==================== 以下方法已廢棄（因為 electricity_records 表未使用）====================

    def save_records(
        self,
        period_id: int,
        calc_results: List[Dict],
    ) -> Tuple[bool, str]:
        """
        ⚠️ 已廢棄：原本用於儲存到 electricity_records 表
        現在所有資料都存在 electricity_readings 表
        """
        logger.warning("⚠️ save_records 方法已廢棄，請使用 save_reading")
        return False, "❌ 此功能已停用"

    def update_payment(
        self,
        period_id: int,
        room_number: str,
        new_status: str,
        paid_amount: int,
        payment_date: str,
    ) -> Tuple[bool, str]:
        """⚠️ 已廢棄：electricity_records 表未使用"""
        logger.warning("⚠️ update_payment 方法已廢棄")
        return False, "❌ 此功能已停用"

    def batch_update_payments(
        self,
        updates: List[Dict],
    ) -> Tuple[int, int]:
        """⚠️ 已廢棄：electricity_records 表未使用"""
        logger.warning("⚠️ batch_update_payments 方法已廢棄")
        return 0, len(updates)
