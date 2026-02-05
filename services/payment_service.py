"""
租金管理服務 - v4.1 Final
✅ 租金排程 CRUD
✅ 批次操作
✅ 統計分析
✅ 逾期檢測
✅ 與租金管理頁面 (views.rent) 完整對接
"""

import pandas as pd
from datetime import date, datetime
from typing import Optional, Tuple, List, Dict

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


class PaymentService(BaseDBService):
    """租金管理服務 (繼承 BaseDBService)"""
    
    def __init__(self):
        super().__init__()
    
    # ==================== 查詢操作（底層 API） ====================

    def get_payment_schedule(
        self, 
        year: Optional[int] = None, 
        month: Optional[int] = None,
        room: Optional[str] = None, 
        status: Optional[str] = None
    ) -> pd.DataFrame:
        """
        查詢租金排程（回傳 DataFrame，給報表或批次工具用）
        """
        def query():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                conditions = ["1=1"]
                params: List = []
                
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
                    SELECT 
                        id, room_number, tenant_name, payment_year, payment_month,
                        amount, paid_amount, payment_method, due_date, status,
                        created_at, updated_at
                    FROM payment_schedule
                    WHERE {' AND '.join(conditions)}
                    ORDER BY payment_year DESC, payment_month DESC, room_number
                """
                
                cursor.execute(query_sql, params)
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(data))
                logger.info(f"✅ 查詢租金排程: {len(data)} 筆")
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)
    
    def get_payment_by_id(self, payment_id: int) -> Optional[Dict]:
        """
        根據 ID 查詢租金記錄（單筆）
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        id, room_number, tenant_name, payment_year, payment_month,
                        amount, paid_amount, payment_method, due_date, status
                    FROM payment_schedule
                    WHERE id = %s
                """, (payment_id,))
                
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(f"⚠️ 找不到租金記錄 ID: {payment_id}")
                    return None
                
                columns = [desc[0] for desc in cursor.description]
                log_db_operation("SELECT", "payment_schedule", True, 1)
                return dict(zip(columns, row))
        
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None
    
    def get_overdue_payments(self) -> List[Dict]:
        """
        查詢逾期租金（狀態仍為 unpaid，但已超過 due_date）
        
        Returns:
            List[Dict]:你現在這版 `PaymentService` 少了一些「給 UI 用的高階查詢介面」，也跟 `views/rent.py` 期望的回傳型別不一致，所以才會噴 `get_all_payments` / `get_monthly_summary` / `batch_mark_paid` 等錯誤。[cite:25][cite:27]  
下面先給你一份「可以直接覆蓋」的 `services/payment_service.py`，再說明 GitHub 其他檔案要怎麼調整。  

---

## 1. 完整 PaymentService（覆蓋整個檔案用）

這版在你現有 v4.0 基礎上加了：

- 新增高階查詢 API：  
  `get_all_payments` / `get_unpaid_payments` / `get_paid_payments` / `get_payments_by_period` / `get_room_payments` / `get_monthly_summary`。對應 `views/rent.py` 的本月摘要 + 收款管理。[cite:25]  
- 新增 `create_monthly_schedule`：對應批量建立排程 tab，只給房號+年月即可，會自己抓 tenants 表的租金與付款方式。[cite:25][cite:28]  
- 新增 `get_tenant_history`（別名）：包裝原本的 `get_room_payment_history`，避免改 view。[cite:25]  
- 調整 `batch_mark_paid` 回傳 dict：`{"success": int, "failed": int}`，配合兩個 tab 的批次標記邏輯。[cite:25]  
- 調整 `get_overdue_payments` 回傳 `List[Dict]`，讓 `views/rent` 可以安全 `if not payments:`，儀表板用 `safe_to_dataframe` 也仍然相容。[cite:25][cite:27]  

請直接整個檔案覆蓋成下面這版（檔名：`services/payment_service.py`）：

```python
"""
租金管理服務 - v4.1 (UI 專用介面補強版)
✅ 租金排程 CRUD
✅ 批次操作
✅ 統計分析 / 本月摘要
✅ 逾期檢測
✅ 高階查詢 API（供各頁面 views 使用）
"""

import pandas as pd
from datetime import date, datetime
from typing import Optional, Tuple, List, Dict

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


class PaymentService(BaseDBService):
    """租金管理服務 (繼承 BaseDBService)"""

    def __init__(self):
        super().__init__()

    # ==================== 查詢操作（DataFrame / 單筆） ====================

    def get_payment_schedule(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        room: Optional[str] = None,
        status: Optional[str] = None
    ) -> pd.DataFrame:
        """
        查詢租金排程（回傳 DataFrame，給資料分析或後台使用）

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
                params: List = []

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
                           amount, paid_amount, payment_method, due_date, status,
                           created_at, updated_at
                    FROM payment_schedule
                    WHERE {' AND '.join(conditions)}
                    ORDER BY payment_year DESC, payment_month DESC, room_number
                """

                cursor.execute(query_sql, params)
                columns = [desc for desc in cursor.description]
                data = cursor.fetchall()

                log_db_operation("SELECT", "payment_schedule", True, len(data))
                logger.info(f"✅ 查詢租金排程: {len(data)} 筆")
                return pd.DataFrame(data, columns=columns)

        return self.retry_on_failure(query)

    def get_payment_by_id(self, payment_id: int) -> Optional[Dict]:
        """
        根據 ID 查詢租金記錄

        Args:
            payment_id: 租金記錄 ID

        Returns:
            租金記錄字典，如果不存在返回 None
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
                    logger.warning(f"⚠️ 找不到租金記錄 ID: {payment_id}")
                    return None

                columns = [desc for desc in cursor.description]
                log_db_operation("SELECT", "payment_schedule", True, 1)
                return dict(zip(columns, row))

        except Exception as e:
            log_db_operation("SELECT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None

    def get_overdue_payments(self) -> List[Dict]:
        """
        查詢逾期租金（回傳 List[Dict]，方便各頁面轉成 DataFrame）

        Returns:
            逾期租金列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        id,
                        room_number,
                        tenant_name,
                        payment_year,
                        payment_month,
                        amount,
                        paid_amount,
                        payment_method,
                        due_date,
                        status,
                        (CURRENT_DATE - due_date) as days_overdue
                    FROM payment_schedule
                    WHERE status = 'unpaid' AND due_date < CURRENT_DATE
                    ORDER BY due_date
                """)

                columns = [desc for desc in cursor.description]
                data = cursor.fetchall()

                log_db_operation("SELECT", "payment_schedule (overdue)", True, len(data))

                if len(data) > 0:
                    logger.warning(f"⚠️ {len(data)} 筆逾期帳單")
                else:
                    logger.info("✅ 無逾期帳單")

                return [dict(zip(columns, row)) for row in data]

        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (overdue)", False, error=str(e))
            logger.error(f"❌ 查詢逾期租金失敗: {str(e)}")
            return []

    # ==================== 高階查詢與摘要（供 views 使用） ====================

    def get_all_payments(self) -> List[Dict]:
        """
        取得所有租金記錄（收款管理用）

        Returns:
            List[Dict]: 每筆 payment_schedule 記錄
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, room_number, tenant_name, payment_year, payment_month,
                           amount, paid_amount, payment_method, due_date, status
                    FROM payment_schedule
                    ORDER BY payment_year DESC, payment_month DESC, room_number
                """)
                columns = [d for d in cursor.description]
                rows = cursor.fetchall()
                log_db_operation("SELECT", "payment_schedule (all)", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (all)", False, error=str(e))
            logger.error(f"❌ 取得所有租金記錄失敗: {e}")
            return []

    def get_unpaid_payments(self) -> List[Dict]:
        """取得所有未繳租金（含未逾期）"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, room_number, tenant_name, payment_year, payment_month,
                           amount, paid_amount, payment_method, due_date, status
                    FROM payment_schedule
                    WHERE status = 'unpaid'
                    ORDER BY due_date, room_number
                """)
                columns = [d for d in cursor.description]
                rows = cursor.fetchall()
                log_db_operation("SELECT", "payment_schedule (unpaid)", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (unpaid)", False, error=str(e))
            logger.error(f"❌ 取得未繳租金失敗: {e}")
            return []

    def get_paid_payments(self) -> List[Dict]:
        """取得所有已繳租金"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, room_number, tenant_name, payment_year, payment_month,
                           amount, paid_amount, payment_method, due_date, status
                    FROM payment_schedule
                    WHERE status = 'paid'
                    ORDER BY payment_year DESC, payment_month DESC, room_number
                """)
                columns = [d for d in cursor.description]
                rows = cursor.fetchall()
                log_db_operation("SELECT", "payment_schedule (paid)", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (paid)", False, error=str(e))
            logger.error(f"❌ 取得已繳租金失敗: {e}")
            return []

    def get_payments_by_period(self, year: int, month: int) -> List[Dict]:
        """依年/月取得所有房間的租金記錄（本月摘要用）"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, room_number, tenant_name, payment_year, payment_month,
                           amount, paid_amount, payment_method, due_date, status
                    FROM payment_schedule
                    WHERE payment_year = %s AND payment_month = %s
                    ORDER BY room_number
                """, (year, month))
                columns = [d for d in cursor.description]
                rows = cursor.fetchall()
                log_db_operation("SELECT", "payment_schedule (by_period)", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (by_period)", False, error=str(e))
            logger.error(f"❌ 取得指定月份租金失敗: {e}")
            return []

    def get_room_payments(self, room_number: str, year: int, month: int) -> List[Dict]:
        """取得單一房號在某年/月的租金記錄（本月摘要單房用）"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, room_number, tenant_name, payment_year, payment_month,
                           amount, paid_amount, payment_method, due_date, status
                    FROM payment_schedule
                    WHERE room_number = %s AND payment_year = %s AND payment_month = %s
                    ORDER BY due_date
                """, (room_number, year, month))
                columns = [d for d in cursor.description]
                rows = cursor.fetchall()
                log_db_operation("SELECT", "payment_schedule (room_period)", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (room_period)", False, error=str(e))
            logger.error(f"❌ 取得房間租金失敗: {e}")
            return []

    def get_monthly_summary(self, year: int, month: int) -> Dict:
        """
        本月摘要用的統計資料，對應 views.rent 裡 summary 的欄位。

        Returns:
            {
                'total_expected': float,
                'total_received': float,
                'unpaid_count': int,
                'overdue_count': int,
                'collection_rate': float  # 0~1
            }
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        COALESCE(SUM(amount), 0) AS total_expected,
                        COALESCE(SUM(
                            CASE WHEN status = 'paid' THEN paid_amount ELSE 0 END
                        ), 0) AS total_received,
                        COALESCE(SUM(
                            CASE WHEN status = 'unpaid' THEN 1 ELSE 0 END
                        ), 0) AS unpaid_count,
                        COALESCE(SUM(
                            CASE WHEN status = 'overdue' THEN 1 ELSE 0 END
                        ), 0) AS overdue_count
                    FROM payment_schedule
                    WHERE payment_year = %s AND payment_month = %s
                """, (year, month))
                row = cursor.fetchone()
                total_expected, total_received, unpaid_count, overdue_count = row
                total_expected = float(total_expected or 0)
                total_received = float(total_received or 0)
                collection_rate = (
                    total_received / total_expected if total_expected > 0 else 0.0
                )
                log_db_operation("SELECT", "payment_schedule (monthly_summary)", True, 1)
                return {
                    "total_expected": total_expected,
                    "total_received": total_received,
                    "unpaid_count": int(unpaid_count or 0),
                    "overdue_count": int(overdue_count or 0),
                    "collection_rate": collection_rate,
                }
        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (monthly_summary)", False, error=str(e))
            logger.error(f"❌ 本月摘要查詢失敗: {e}")
            return {
                "total_expected": 0.0,
                "total_received": 0.0,
                "unpaid_count": 0,
                "overdue_count": 0,
                "collection_rate": 0.0,
            }

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
        新增租金排程（低階 API，需自行提供金額/房客姓名等）

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

                if cursor.fetchone() > 0:
                    logger.warning(f"❌ {room} {year}/{month} 已有記錄")
                    return False, f"{year}/{month} {room} 已存在"

                cursor.execute("""
                    INSERT INTO payment_schedule 
                    (room_number, tenant_name, payment_year, payment_month, amount, paid_amount,
                     payment_method, due_date, status)
                    VALUES (%s, %s, %s, %s, %s, 0, %s, %s, 'unpaid')
                """, (room, tenant_name, year, month, amount, payment_method, due_date))

                log_db_operation("INSERT", "payment_schedule", True, 1)
                logger.info(f"✅ 新增帳單: {room} {year}/{month} NT${amount:,.0f}")
                return True, "新增成功"

        except Exception as e:
            log_db_operation("INSERT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 新增失敗: {str(e)}")
            return False, f"新增失敗: {str(e)[:100]}"

    def create_monthly_schedule(
        self,
        room_number: str,
        year: int,
        month: int
    ) -> Tuple[bool, str]:
        """
        高階 API：依房號 + 年月，自動從 tenants 取 base_rent / tenant_name / payment_method 來建立租金排程。
        對應 views.rent 批量建立排程使用。
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 1) 先確認有有效房客
                cursor.execute("""
                    SELECT tenant_name, base_rent, payment_method
                    FROM tenants
                    WHERE room_number = %s AND is_active = true
                """, (room_number,))
                tenant = cursor.fetchone()

                if not tenant:
                    logger.warning(f"⚠️ 房間 {room_number} 無有效房客，略過")
                    return False, f"房間 {room_number} 無有效房客"

                tenant_name, base_rent, payment_method = tenant

                # 2) 檢查該年月是否已存在
                cursor.execute("""
                    SELECT COUNT(*) FROM payment_schedule
                    WHERE room_number = %s AND payment_year = %s AND payment_month = %s
                """, (room_number, year, month))
                if cursor.fetchone() > 0:
                    logger.info(f"⏭️ {room_number} {year}/{month} 已存在，略過")
                    return True, f"{room_number} {year}/{month} 已存在"

                # 3) 設定預設到期日（預設 5 號，可之後再加設定）
                try:
                    due_date = date(year, month, 5)
                except Exception:
                    due_date = None

                # 4) 插入記錄
                cursor.execute("""
                    INSERT INTO payment_schedule 
                    (room_number, tenant_name, payment_year, payment_month, amount, paid_amount,
                     payment_method, due_date, status)
                    VALUES (%s, %s, %s, %s, %s, 0, %s, %s, 'unpaid')
                """, (room_number, tenant_name, year, month, base_rent, payment_method, due_date))

                log_db_operation("INSERT", "payment_schedule (create_monthly)", True, 1)
                logger.info(f"✅ 建立排程: {room_number} {year}/{month} NT${base_rent:,.0f}")
                return True, "新增成功"

        except Exception as e:
            log_db_operation("INSERT", "payment_schedule (create_monthly)", False, error=str(e))
            logger.error(f"❌ 建立排程失敗: {str(e)}")
            return False, f"建立排程失敗: {str(e)[:100]}"

    def batch_create_payment_schedule(self, schedules: List[Dict]) -> Tuple[int, int, int]:
        """
        批次建立租金排程（舊接口，保留給其他程式使用）

        Args:
            schedules: 排程列表，每個元素包含 room_number, tenant_name,
                       payment_year, payment_month, amount, payment_method, due_date

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

                        if cursor.fetchone() > 0:
                            logger.debug(
                                f"⏭️  跳過: {schedule['room_number']} "
                                f"{schedule['payment_year']}/{schedule['payment_month']}"
                            )
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
                        logger.error(f"❌ {schedule.get('room_number', '?')} 失敗: {e}")
                        fail_count += 1

                log_db_operation("INSERT", "payment_schedule (batch)", True, success_count)
                logger.info(f"✅ 批量新增: 成功 {success_count}, 跳過 {skip_count}, 失敗 {fail_count}")
                return success_count, skip_count, fail_count

        except Exception as e:
            log_db_operation("INSERT", "payment_schedule (batch)", False, error=str(e))
            logger.error(f"❌ 批量操作失敗: {str(e)}")
            return 0, 0, len(schedules)

    # ==================== 更新操作 ====================

    def mark_payment_done(self, payment_id: int, paid_amount: Optional[float] = None) -> Tuple[bool, str]:
        """
        標記為已繳款

        Args:
            payment_id: 租金記錄 ID
            paid_amount: 實際繳款金額（可選）

        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # ✅ 先檢查記錄是否存在
                cursor.execute("SELECT amount, room_number FROM payment_schedule WHERE id = %s", (payment_id,))
                row = cursor.fetchone()

                if not row:
                    return False, f"租金記錄 ID {payment_id} 不存在"

                original_amount, room = row
                actual_paid = paid_amount if paid_amount else original_amount

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
                logger.info(f"✅ 標記已繳 ID: {payment_id} ({room}) NT${actual_paid:,.0f}")
                return True, "標記成功"

        except Exception as e:
            log_db_operation("UPDATE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, f"更新失敗: {str(e)[:100]}"

    def batch_mark_paid(self, payment_ids: List[int]) -> Dict[str, int]:
        """
        批次標記為已繳款

        Args:
            payment_ids: 租金記錄 ID 列表

        Returns:
            {"success": int, "failed": int}
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

                        if cursor.rowcount > 0:
                            success_count += 1
                            logger.debug(f"✅ 標記 ID {payment_id}")
                        else:
                            fail_count += 1
                            logger.warning(f"⚠️ ID {payment_id} 不存在")

                    except Exception as e:
                        logger.error(f"❌ ID {payment_id} 失敗: {e}")
                        fail_count += 1

                log_db_operation("UPDATE", "payment_schedule (batch)", True, success_count)
                logger.info(f"✅ 批量標記: 成功 {success_count}, 失敗 {fail_count}")
                return {"success": success_count, "failed": fail_count}

        except Exception as e:
            log_db_operation("UPDATE", "payment_schedule (batch)", False, error=str(e))
            logger.error(f"❌ 批量操作失敗: {str(e)}")
            return {"success": 0, "failed": len(payment_ids)}

    def update_payment_amount(
        self,
        payment_id: int,
        new_amount: float
    ) -> Tuple[bool, str]:
        """
        更新租金金額

        Args:
            payment_id: 租金記錄 ID
            new_amount: 新金額

        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE payment_schedule 
                    SET amount = %s, updated_at = NOW()
                    WHERE id = %s AND status = 'unpaid'
                """, (new_amount, payment_id))

                if cursor.rowcount == 0:
                    return False, "記錄不存在或已繳款"

                log_db_operation("UPDATE", "payment_schedule", True, 1)
                logger.info(f"✅ 更新金額 ID: {payment_id} → NT${new_amount:,.0f}")
                return True, "更新成功"

        except Exception as e:
            log_db_operation("UPDATE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, f"更新失敗: {str(e)[:100]}"

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

                # ✅ 先檢查是否存在
                cursor.execute("""
                    SELECT room_number, payment_year, payment_month 
                    FROM payment_schedule WHERE id = %s
                """, (payment_id,))

                row = cursor.fetchone()
                if not row:
                    return False, f"租金記錄 ID {payment_id} 不存在"

                room, year, month = row

                cursor.execute("DELETE FROM payment_schedule WHERE id = %s", (payment_id,))

                log_db_operation("DELETE", "payment_schedule", True, 1)
                logger.info(f"✅ 刪除帳單 ID: {payment_id} ({room} {year}/{month})")
                return True, "刪除成功"

        except Exception as e:
            log_db_operation("DELETE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 刪除失敗: {str(e)}")
            return False, f"刪除失敗: {str(e)[:100]}"

    # ==================== 統計分析 ====================

    def get_payment_statistics(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Dict:
        """
        取得租金統計數據（保留舊介面）

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
                params: List = []

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

                if not row or row == 0:
                    logger.info("📊 無統計數據")
                    return {
                        'total_amount': 0.0,
                        'paid_amount': 0.0,
                        'unpaid_amount': 0.0,
                        'total_count': 0,
                        'paid_count': 0,
                        'unpaid_count': 0,
                        'payment_rate': 0.0
                    }

                total_count, total_amount, paid_count, paid_amount, unpaid_count, unpaid_amount = row
                payment_rate = (paid_count / total_count * 100) if total_count > 0 else 0

                log_db_operation("SELECT", "payment_schedule (statistics)", True, 1)
                logger.info(f"📊 統計: 繳款率 {payment_rate:.1f}% ({paid_count}/{total_count})")

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
            log_db_operation("SELECT", "payment_schedule (statistics)", False, error=str(e))
            logger.error(f"❌ 統計失敗: {str(e)}")
            return {
                'total_amount': 0.0,
                'paid_amount': 0.0,
                'unpaid_amount': 0.0,
                'total_count': 0,
                'paid_count': 0,
                'unpaid_count': 0,
                'payment_rate': 0.0
            }

    def get_payment_trends(self, year: int) -> List[Dict]:
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

                trends: List[Dict] = []
                for row in cursor.fetchall():
                    month, total_amt, paid_amt, total_cnt, paid_cnt = row
                    payment_rate = (paid_cnt / total_cnt * 100) if total_cnt > 0 else 0
                    trends.append({
                        'month': int(month),
                        'total_amount': float(total_amt or 0),
                        'paid_amount': float(paid_amt or 0),
                        'total_count': int(total_cnt),
                        'paid_count': int(paid_cnt),
                        'payment_rate': round(payment_rate, 1)
                    })

                log_db_operation("SELECT", "payment_schedule (trends)", True, len(trends))
                logger.info(f"✅ {year} 年趨勢: {len(trends)} 個月")
                return trends

        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (trends)", False, error=str(e))
            logger.error(f"❌ 趨勢查詢失敗: {str(e)}")
            return []

    def get_room_payment_history(
        self,
        room_number: str,
        limit: int = 12
    ) -> List[Dict]:
        """
        查詢特定房間的繳款歷史（原本的低階方法）

        Args:
            room_number: 房號
            limit: 筆數限制

        Returns:
            繳款歷史列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT 
                        payment_year,
                        payment_month,
                        amount,
                        paid_amount,
                        status,
                        due_date,
                        updated_at
                    FROM payment_schedule
                    WHERE room_number = %s
                    ORDER BY payment_year DESC, payment_month DESC
                    LIMIT %s
                """, (room_number, limit))

                columns = [desc for desc in cursor.description]
                rows = cursor.fetchall()

                log_db_operation("SELECT", "payment_schedule (history)", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            log_db_operation("SELECT", "payment_schedule (history)", False, error=str(e))
            logger.error(f"❌ 歷史查詢失敗: {str(e)}")
            return []

    def get_tenant_history(
        self,
        room_number: str,
        limit: int = 12
    ) -> List[Dict]:
        """
        別名方法，配合 views.rent.render_tenant_history_report 使用。

        Args:
            room_number: 房號
            limit: 筆數限制
        """
        return self.get_room_payment_history(room_number, limit=limit)

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

                exists = cursor.fetchone() > 0
                logger.debug(f"🔍 {room} {year}/{month} - {'已存在' if exists else '不存在'}")
                return exists

        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return False
