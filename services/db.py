import streamlit as st
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
import pandas as pd
import contextlib
import logging
from datetime import datetime, date
from typing import Optional, Tuple, List, Dict
import time
from services.logger import logger, log_db_operation

# ===== 常數載入 =====
try:
    from config.constants import ROOMS, PAYMENT, EXPENSE, ELECTRICITY, SYSTEM, UI
    CONSTANTS_LOADED = True
except ImportError as e:
    logger.error(f"⚠️ 無法載入 config.constants: {e}")
    logger.warning("使用預設常數")
    CONSTANTS_LOADED = False
    
    class BackupConstants:
        """當 config.constants 無法載入時的備用常數"""
        class ROOMS:
            ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
            SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
            EXCLUSIVE_ROOMS = ["1A", "1B"]
        
        class PAYMENT:
            METHODS = ["現金", "轉帳", "匯款"]
            STATUSES = ["unpaid", "paid", "overdue"]
        
        class EXPENSE:
            CATEGORIES = ["維修", "清潔", "管理費", "其他"]
        
        class ELECTRICITY:
            WATER_FEE = 100
        
        class SYSTEM:
            CONNECTION_POOL_MIN = 2
            CONNECTION_POOL_MAX = 10
            RETRY_DELAY = 1

def validate_constants():
    """驗證常數是否正確"""
    try:
        if not CONSTANTS_LOADED:
            logger.warning("使用備用常數")
            return (BackupConstants.ROOMS, BackupConstants.PAYMENT, 
                   BackupConstants.EXPENSE, BackupConstants.ELECTRICITY)
        
        # === TITLE: 驗證房間列表 ===
        assert len(ROOMS.ALL_ROOMS) > 0, "ALL_ROOMS 不能為空"
        assert len(ROOMS.SHARING_ROOMS) > 0, "SHARING_ROOMS 不能為空"
        assert len(ROOMS.EXCLUSIVE_ROOMS) > 0, "EXCLUSIVE_ROOMS 不能為空"
        
        # === TITLE: 驗證房間邏輯 ===
        for room in ROOMS.EXCLUSIVE_ROOMS:
            assert room in ROOMS.ALL_ROOMS, f"獨立房間 {room} 不在所有房間列表中"
        for room in ROOMS.SHARING_ROOMS:
            assert room in ROOMS.ALL_ROOMS, f"分攤房間 {room} 不在所有房間列表中"
        
        # === TITLE: 驗證付款相關 ===
        assert len(PAYMENT.METHODS) > 0, "PAYMENT_METHODS 不能為空"
        assert len(PAYMENT.STATUSES) > 0, "PAYMENT_STATUSES 不能為空"
        
        # === TITLE: 驗證費用類別 ===
        assert len(EXPENSE.CATEGORIES) > 0, "EXPENSE_CATEGORIES 不能為空"
        
        logger.info("✅ 常數驗證通過")
        return ROOMS, PAYMENT, EXPENSE, ELECTRICITY
        
    except AssertionError as e:
        logger.error(f"❌ 常數驗證失敗: {e}")
        return (BackupConstants.ROOMS, BackupConstants.PAYMENT, 
               BackupConstants.EXPENSE, BackupConstants.ELECTRICITY)
    except Exception as e:
        logger.error(f"❌ 常數驗證發生錯誤: {e}")
        return (BackupConstants.ROOMS, BackupConstants.PAYMENT, 
               BackupConstants.EXPENSE, BackupConstants.ELECTRICITY)

# ===== TITLE: 資料庫連線池 =====
class DatabaseConnectionPool:
    """單例模式的資料庫連線池"""
    _instance = None
    pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, config: dict):
        """初始化連線池
        
        Args:
            config: {host: ..., port: ..., database: ..., user: ..., password: ...}
        """
        if self.pool is not None:
            logger.warning("⚠️ 連線池已存在，跳過初始化")
            return
        
        try:
            minconn = SYSTEM.CONNECTION_POOL_MIN if CONSTANTS_LOADED else 2
            maxconn = SYSTEM.CONNECTION_POOL_MAX if CONSTANTS_LOADED else 10
            
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn, maxconn,
                host=config.get("host"),
                port=config.get("port", 5432),
                database=config.get("database"),
                user=config.get("user"),
                password=config.get("password"),
                connect_timeout=10
            )
            logger.info(f"✅ 資料庫連線池初始化完成 (min={minconn}, max={maxconn})")
        except Exception as e:
            logger.error(f"❌ 連線池初始化失敗: {e}")
            raise
    
    def get_connection(self):
        if self.pool is None:
            raise RuntimeError("連線池尚未初始化")
        return self.pool.getconn()
    
    def return_connection(self, conn):
        if self.pool and conn:
            self.pool.putconn(conn)
    
    def close_all(self):
        if self.pool:
            self.pool.closeall()
            self.pool = None
            logger.info("🔌 所有資料庫連線已關閉")

# ===== TITLE: 主要資料庫類別 =====
class SupabaseDB:
    """Supabase 資料庫操作類別 - v2.2 完整版"""
    
    def __init__(self):
        self.pool = DatabaseConnectionPool()
        self.validated_constants = validate_constants()
        
        try:
            self.pool.initialize(st.secrets.get("supabase", {}))
            logger.info("✅ SupabaseDB 初始化完成")
        except Exception as e:
            logger.error(f"❌ SupabaseDB 初始化失敗: {e}")
            st.error(f"❌ 資料庫連線失敗")
    
    @contextlib.contextmanager
    def get_connection(self):
        """Context Manager - 自動管理連線取得與歸還"""
        conn = None
        try:
            conn = self.pool.get_connection()
            yield conn
            conn.commit()
            logger.debug("✅ 交易提交成功")
        except psycopg2.IntegrityError as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 資料完整性錯誤: {e}")
            raise
        except psycopg2.OperationalError as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 資料庫操作錯誤: {e}")
            raise
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 發生錯誤: {e}")
            raise
        finally:
            if conn:
                self.pool.return_connection(conn)
    
    def retry_on_failure(self, func, max_retries: int = 3):
        """重試機制"""
        retry_delay = SYSTEM.RETRY_DELAY if CONSTANTS_LOADED else 1
        for attempt in range(max_retries):
            try:
                return func()
            except psycopg2.OperationalError as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ 重試 {max_retries} 次後仍失敗: {e}")
                    raise
                wait_time = retry_delay * (attempt + 1)
                logger.warning(f"⚠️ 第 {attempt + 1}/{max_retries} 次嘗試失敗，"
                             f"等待 {wait_time}s 後重試... ({str(e)[:100]})")
                time.sleep(wait_time)
    
    def health_check(self) -> bool:
        """健康檢查 - 測試連線是否正常"""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                result = cur.fetchone()
            logger.info("✅ 資料庫連線測試成功")
            return result is not None
        except Exception as e:
            logger.error(f"❌ 資料庫連線測試失敗: {e}")
            return False

    # ===== TITLE: 房客管理 =====
    
    def get_tenants(self, active_only: bool = True) -> pd.DataFrame:
        """取得房客列表
        
        Args:
            active_only: 是否只顯示啟用中的房客
        
        Returns:
            DataFrame 包含所有房客資料
        """
        def query():
            with self.get_connection() as conn:
                cur = conn.cursor()
                condition = "WHERE is_active = true" if active_only else ""
                cur.execute(f"""
                    SELECT 
                        id, room_number, tenant_name, phone, deposit, base_rent,
                        lease_start, lease_end, payment_method, has_water_fee,
                        annual_discount_months, discount_notes, last_ac_cleaning_date,
                        is_active, created_at
                    FROM tenants
                    {condition}
                    ORDER BY room_number
                """)
                columns = [desc[0] for desc in cur.description]
                data = cur.fetchall()
                if not data:
                    logger.info("📋 查無房客資料")
                    return pd.DataFrame(columns=columns)
                logger.info(f"📋 取得 {len(data)} 筆房客資料")
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)
    
    def add_tenant(self, room: str, name: str, phone: str, deposit: float, 
                   base_rent: float, start: date, end: date, payment_method: str,
                   has_water_fee: bool = False, annual_discount_months: int = 0,
                   discount_notes: str = "") -> Tuple[bool, str]:
        """新增房客
        
        Args:
            room: 房號
            name: 房客姓名
            phone: 電話
            ...
        
        Returns:
            (成功與否, 訊息)
        """
        try:
            # === TITLE: 驗證房號 ===
            all_rooms = ROOMS.ALL_ROOMS if CONSTANTS_LOADED else BackupConstants.ROOMS.ALL_ROOMS
            if room not in all_rooms:
                logger.warning(f"❌ 無效的房號: {room}")
                return False, f"無效的房號: {room}"
            
            # === TITLE: 驗證付款方式 ===
            methods = PAYMENT.METHODS if CONSTANTS_LOADED else BackupConstants.PAYMENT.METHODS
            if payment_method not in methods:
                logger.warning(f"❌ 無效的付款方式: {payment_method}")
                return False, f"無效的付款方式: {payment_method}"
            
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                # === TITLE: 檢查房間是否已被占用 ===
                cur.execute("""
                    SELECT COUNT(*) FROM tenants 
                    WHERE room_number = %s AND is_active = true
                """, (room,))
                if cur.fetchone()[0] > 0:
                    logger.warning(f"❌ 房間 {room} 已被占用")
                    return False, f"房間 {room} 已被占用"
                
                # === TITLE: 新增房客 ===
                cur.execute("""
                    INSERT INTO tenants (
                        room_number, tenant_name, phone, deposit, base_rent,
                        lease_start, lease_end, payment_method, has_water_fee,
                        annual_discount_months, discount_notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (room, name, phone, deposit, base_rent, start, end, 
                     payment_method, has_water_fee, annual_discount_months, discount_notes))
                
                log_db_operation("INSERT", "tenants", True, 1)
                logger.info(f"✅ 新增房客: {name} ({room})")
                return True, f"新增房客 {name} 成功"
        
        except Exception as e:
            log_db_operation("INSERT", "tenants", False, error=str(e))
            logger.error(f"❌ 新增房客失敗: {str(e)}")
            return False, f"新增失敗: {str(e)[:100]}"
    
    def update_tenant(self, tenant_id: int, room: str, name: str, phone: str,
                     deposit: float, base_rent: float, start: date, end: date,
                     payment_method: str, has_water_fee: bool = False,
                     annual_discount_months: int = 0, discount_notes: str = "") -> Tuple[bool, str]:
        """更新房客資料"""
        try:
            all_rooms = ROOMS.ALL_ROOMS if CONSTANTS_LOADED else BackupConstants.ROOMS.ALL_ROOMS
            methods = PAYMENT.METHODS if CONSTANTS_LOADED else BackupConstants.PAYMENT.METHODS
            
            if room not in all_rooms:
                return False, f"無效的房號: {room}"
            if payment_method not in methods:
                return False, f"無效的付款方式: {payment_method}"
            
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE tenants SET
                        room_number = %s, tenant_name = %s, phone = %s,
                        # === TITLE: 更新所有欄位 ===
                        deposit = %s, base_rent = %s, lease_start = %s, lease_end = %s,
                        payment_method = %s, has_water_fee = %s,
                        annual_discount_months = %s, discount_notes = %s
                    WHERE id = %s
                """, (room, name, phone, deposit, base_rent, start, end,
                     payment_method, has_water_fee, annual_discount_months, discount_notes, tenant_id))
                
                log_db_operation("UPDATE", "tenants", True, 1)
                logger.info(f"✅ 更新房客 ID {tenant_id}")
                return True, f"更新房客 {name} 成功"
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 更新房客失敗: {str(e)}")
            return False, f"更新失敗: {str(e)[:100]}"
    
    def delete_tenant(self, tenant_id: int) -> Tuple[bool, str]:
        """刪除房客（軟刪除）"""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE tenants SET is_active = false WHERE id = %s
                """, (tenant_id,))
                
                log_db_operation("UPDATE", "tenants", True, 1)
                logger.info(f"✅ 刪除房客 ID {tenant_id}")
                return True, "刪除房客成功"
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 刪除房客失敗: {str(e)}")
            return False, f"刪除失敗: {str(e)[:100]}"

    # ===== TITLE: 租金管理 =====
    
    def get_payment_schedule(self, year: Optional[int] = None, month: Optional[int] = None,
                           room: Optional[str] = None, status: Optional[str] = None) -> pd.DataFrame:
        """取得租金排程
        
        Args:
            year: 年份篩選
            month: 月份篩選
            room: 房號篩選
            status: 狀態篩選
        
        Returns:
            DataFrame 包含租金排程資料
        """
        def query():
            with self.get_connection() as conn:
                cur = conn.cursor()
                
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
                    SELECT 
                        id, room_number, tenant_name, payment_year, payment_month,
                        amount, paid_amount, payment_method, due_date, status,
                        created_at, updated_at
                    FROM payment_schedule
                    WHERE {" AND ".join(conditions)}
                    ORDER BY payment_year DESC, payment_month DESC, room_number
                """
                
                cur.execute(query_sql, params)
                columns = [desc[0] for desc in cur.description]
                data = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(data))
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)

    # ===== TITLE: 電費管理 - 新增讀數記錄功能 =====
    
    def get_latest_meter_reading(self, room: str, period_id: int) -> Optional[float]:
        """取得房間最新電表讀數
        
        Args:
            room: 房號
            period_id: 當前期間ID（會往前查找上一期）
        
        Returns:
            最新的本期讀數，如果沒有則返回 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT current_reading
                    FROM electricity_readings
                    WHERE room_number = %s AND period_id < %s
                    ORDER BY period_id DESC
                    LIMIT 1
                """, (room, period_id))
                
                result = cursor.fetchone()
                if result:
                    logger.debug(f"📊 取得 {room} 上期讀數: {result[0]}")
                    return float(result[0])
                return None
        except Exception as e:
            logger.error(f"❌ 取得電表讀數失敗: {str(e)}")
            return None
    
    def save_electricity_reading(self, period_id: int, room: str, 
                                previous: float, current: float, kwh_used: float) -> Tuple[bool, str]:
        """儲存電表讀數
        
        Args:
            period_id: 計費期間ID
            room: 房號
            previous: 上期讀數
            current: 本期讀數
            kwh_used: 使用度數
        
        Returns:
            (成功與否, 訊息)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO electricity_readings 
                    (period_id, room_number, previous_reading, current_reading, kwh_used)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (period_id, room_number) 
                    DO UPDATE SET 
                        previous_reading = EXCLUDED.previous_reading,
                        current_reading = EXCLUDED.current_reading,
                        kwh_used = EXCLUDED.kwh_used
                """, (period_id, room, previous, current, kwh_used))
                
                log_db_operation("INSERT", "electricity_readings", True, 1)
                logger.info(f"✅ 儲存電表讀數: {room} = {kwh_used} 度")
                return True, f"儲存成功"
        except Exception as e:
            log_db_operation("INSERT", "electricity_readings", False, error=str(e))
            logger.error(f"❌ 儲存電表讀數失敗: {str(e)}")
            return False, str(e)
    
    def add_electricity_period(self, year: int, month_start: int, month_end: int) -> Tuple[bool, str, Optional[int]]:
        """新增電費計費期間"""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO electricity_periods 
                    (period_year, period_month_start, period_month_end)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (year, month_start, month_end))
                period_id = cur.fetchone()[0]
                
                log_db_operation("INSERT", "electricity_periods", True, 1)
                logger.info(f"✅ 新增電費期間: {year}/{month_start}-{month_end}")
                return True, f"已建立 {year} 年 {month_start}-{month_end} 月計費期間", period_id
        
        except Exception as e:
            log_db_operation("INSERT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 新增期間失敗: {str(e)}")
            return False, str(e), None
    
    def get_all_periods(self) -> List[Dict]:
        """取得所有計費期間"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, period_year, period_month_start, period_month_end, created_at
                    FROM electricity_periods
                    ORDER BY period_year DESC, period_month_start DESC
                """)
                rows = cursor.fetchall()
                result = [
                    {
                        'id': row[0],
                        'period_year': row[1],
                        'period_month_start': row[2],
                        'period_month_end': row[3],
                        'created_at': row[4]
                    }
                    for row in rows
                ]
                # === TITLE: 記錄查詢結果 ===
                log_db_operation("SELECT", "electricity_periods", True, len(result))
                return result
        except Exception as e:
            log_db_operation("SELECT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 取得期間失敗: {str(e)}")
            return []
    
    def delete_electricity_period(self, period_id: int) -> Tuple[bool, str]:
        """刪除電費期間"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM electricity_periods WHERE id = %s
                """, (period_id,))
                
                log_db_operation("DELETE", "electricity_periods", True, 1)
                logger.info(f"✅ 刪除期間 ID {period_id}")
                return True, "刪除成功"
        except Exception as e:
            log_db_operation("DELETE", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 刪除期間失敗: {str(e)}")
            return False, str(e)
    
    def save_electricity_record(self, period_id: int, calc_results: list) -> Tuple[bool, str]:
        """儲存電費計算結果（含原始讀數）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                for result in calc_results:
                    # 先儲存讀數記錄
                    if 'previous_reading' in result and 'current_reading' in result:
                        cursor.execute("""
                            INSERT INTO electricity_readings 
                            (period_id, room_number, previous_reading, current_reading, kwh_used)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (period_id, room_number) 
                            DO UPDATE SET 
                                previous_reading = EXCLUDED.previous_reading,
                                current_reading = EXCLUDED.current_reading,
                                kwh_used = EXCLUDED.kwh_used
                        """, (
                            period_id,
                            result['房號'],
                            result['previous_reading'],
                            result['current_reading'],
                            result['使用度數']
                        ))
                    
                    # 再儲存計費記錄
                    cursor.execute("""
                        INSERT INTO electricity_records 
                        (period_id, room_number, room_type, usage_kwh, public_share_kwh, total_kwh, amount_due, payment_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'unpaid')
                        ON CONFLICT (period_id, room_number) DO UPDATE SET
                            room_type = EXCLUDED.room_type,
                            usage_kwh = EXCLUDED.usage_kwh,
                            public_share_kwh = EXCLUDED.public_share_kwh,
                            total_kwh = EXCLUDED.total_kwh,
                            # === TITLE: 更新金額 ===
                            amount_due = EXCLUDED.amount_due
                    """, (
                        period_id,
                        result['房號'],
                        result['類型'],
                        result['使用度數'],
                        result['公用分攤'],
                        result['總度數'],
                        result['應繳金額']
                    ))
                
                log_db_operation("INSERT", "electricity_records", True, len(calc_results))
                logger.info(f"✅ 儲存 {len(calc_results)} 筆電費記錄（含讀數）")
                return True, "儲存成功"
            except Exception as e:
                log_db_operation("INSERT", "electricity_records", False, error=str(e))
                logger.error(f"❌ 儲存電費記錄失敗: {str(e)}")
                return False, str(e)
    
    def get_electricity_payment_record(self, period_id: int) -> pd.DataFrame:
        """取得電費繳費記錄"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        room_number, amount_due, paid_amount, payment_status,
                        payment_date, notes, updated_at
                    FROM electricity_records
                    WHERE period_id = %s
                    ORDER BY room_number
                """, (period_id,))
                rows = cursor.fetchall()
                
                if not rows:
                    return pd.DataFrame()
                
                data = [
                    [
                        row[0], row[1], row[2] or 0, row[3],
                        row[4].strftime("%Y-%m-%d") if row[4] else "-",
                        row[5] or "-",
                        row[6].strftime("%Y-%m-%d %H:%M") if row[6] else "-"
                    ]
                    for row in rows
                ]
                
                log_db_operation("SELECT", "electricity_records", True, len(data))
                return pd.DataFrame(data, columns=["room_number", "amount_due", "paid_amount", "payment_status", "payment_date", "notes", "updated_at"])
                # === TITLE: 返回結果 ===
        except Exception as e:
            log_db_operation("SELECT", "electricity_records", False, error=str(e))
            logger.error(f"❌ 取得繳費記錄失敗: {str(e)}")
            return pd.DataFrame()
    
    def update_electricity_payment(self, period_id: int, room_number: str, 
                                   payment_status: str, paid_amount: int = 0,
                                   payment_date: str = None, notes: str = "") -> Tuple[bool, str]:
        """更新電費繳費狀態"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE electricity_records SET
                        payment_status = %s,
                        paid_amount = %s,
                        payment_date = %s,
                        notes = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE period_id = %s AND room_number = %s
                """, (payment_status, paid_amount, payment_date, notes, period_id, room_number))
                
                log_db_operation("UPDATE", "electricity_records", True, 1)
                logger.info(f"✅ 更新電費繳費: {room_number} - {payment_status}")
                return True, f"更新 {room_number} 繳費狀態成功"
        except Exception as e:
            log_db_operation("UPDATE", "electricity_records", False, error=str(e))
            logger.error(f"❌ 更新繳費失敗: {str(e)}")
            return False, str(e)
    
    def get_electricity_payment_summary(self, period_id: int) -> dict:
        """取得電費繳費摘要"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        SUM(amount_due) as total_due,
                        SUM(paid_amount) as total_paid,
                        COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_rooms,
                        COUNT(CASE WHEN payment_status = 'unpaid' THEN 1 END) as unpaid_rooms,
                        COUNT(*) as total_rooms
                        # === TITLE: 統計查詢 ===
                    FROM electricity_records
                    WHERE period_id = %s
                """, (period_id,))
                row = cursor.fetchone()
                
                total_due = row[0] or 0
                total_paid = row[1] or 0
                paid_rooms = row[2] or 0
                unpaid_rooms = row[3] or 0
                total_rooms = row[4] or 0
                collection_rate = (total_paid / total_due * 100) if total_due > 0 else 0
                
                log_db_operation("SELECT", "electricity_records summary", True, total_rooms)
                logger.debug(f"📊 總應收: {total_due:,.0f}, 已收: {total_paid:,.0f}, 收款率: {collection_rate:.1f}%")
                
                return {
                    'total_due': total_due,
                    'total_paid': total_paid,
                    'total_balance': total_due - total_paid,
                    'paid_rooms': paid_rooms,
                    'unpaid_rooms': unpaid_rooms,
                    'total_rooms': total_rooms,
                    'collection_rate': collection_rate
                }
        except Exception as e:
            log_db_operation("SELECT", "electricity_records summary", False, error=str(e))
            logger.error(f"❌ 取得統計失敗: {str(e)}")
            return {}

# ===== TITLE: Streamlit 快取 =====
@st.cache_resource
def get_db() -> SupabaseDB:
    """取得資料庫實例 - Streamlit 快取
    
    Returns:
        SupabaseDB 實例
    """
    logger.info("🔄 初始化 SupabaseDB 實例")
    return SupabaseDB()


if __name__ == "__main__":
    logger.info("✅ services/db.py 模組載入完成")
    
    # === TITLE: 1. 測試常數驗證 ===
    print("=" * 50)
    print("測試 1: 常數驗證")
    print("=" * 50)
    try:
        validate_constants()
        print("✅ 常數驗證通過")
    except Exception as e:
        print(f"❌ 常數驗證失敗: {e}")
    
    # === TITLE: 2. 測試連線池 ===
    print("\n" + "=" * 50)
    print("測試 2: 連線池初始化")
    print("=" * 50)
    try:
        pool = DatabaseConnectionPool()
        print("✅ 連線池建立成功")
    except Exception as e:
        print(f"❌ 連線池建立失敗: {e}")
    
    logger.info("✅ services/db.py 測試完成")
    # === TITLE: 2. 測試完成 ===
