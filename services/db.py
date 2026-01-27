"""
数据库操作模块 - v2.8 修复版
✅ 修复电费表名：electricity_records/electricity_readings/electricity_periods
✅ 修复欄位对齐：DataFrame columns 与 UI 完全一致
✅ 加强 logging 和错误处理
"""

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


# ============== 配置常量 ==============
try:
    from config.constants import ROOMS, PAYMENT, EXPENSE, ELECTRICITY, SYSTEM, UI
    CONSTANTS_LOADED = True
except ImportError as e:
    logger.error(f"⚠️ 无法载入 config.constants: {e}")
    logger.warning("使用备用常量配置")
    CONSTANTS_LOADED = False
    
    class BackupConstants:
        """备用常量 (当 config.constants 无法载入时使用)"""
        class ROOMS:
            ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
            SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
            EXCLUSIVE_ROOMS = ["1A", "1B"]
        
        class PAYMENT:
            METHODS = ["现金", "转账", "其他"]
            STATUSES = ["unpaid", "paid", "overdue"]
        
        class EXPENSE:
            CATEGORIES = ["维修", "清洁", "水电", "其他"]
        
        class ELECTRICITY:
            WATER_FEE = 100
        
        class SYSTEM:
            CONNECTION_POOL_MIN = 2
            CONNECTION_POOL_MAX = 10
            RETRY_DELAY = 1


def validate_constants():
    """验证常量配置"""
    try:
        if not CONSTANTS_LOADED:
            logger.warning("使用备用常量")
            return (BackupConstants.ROOMS, BackupConstants.PAYMENT, 
                    BackupConstants.EXPENSE, BackupConstants.ELECTRICITY)
        
        # 验证 ROOMS
        assert len(ROOMS.ALL_ROOMS) > 0, "ALL_ROOMS 不能为空"
        assert len(ROOMS.SHARING_ROOMS) > 0, "SHARING_ROOMS 不能为空"
        assert len(ROOMS.EXCLUSIVE_ROOMS) > 0, "EXCLUSIVE_ROOMS 不能为空"
        
        # 验证房号一致性
        for room in ROOMS.EXCLUSIVE_ROOMS:
            assert room in ROOMS.ALL_ROOMS, f"独立房间 {room} 不在总房间列表中"
        for room in ROOMS.SHARING_ROOMS:
            assert room in ROOMS.ALL_ROOMS, f"分摊房间 {room} 不在总房间列表中"
        
        # 验证 PAYMENT
        assert len(PAYMENT.METHODS) > 0, "PAYMENT_METHODS 不能为空"
        assert len(PAYMENT.STATUSES) > 0, "PAYMENT_STATUSES 不能为空"
        
        # 验证 EXPENSE
        assert len(EXPENSE.CATEGORIES) > 0, "EXPENSE_CATEGORIES 不能为空"
        
        logger.info("✅ 常量验证通过")
        return ROOMS, PAYMENT, EXPENSE, ELECTRICITY
    
    except AssertionError as e:
        logger.error(f"❌ 常量验证失败: {e}")
        return (BackupConstants.ROOMS, BackupConstants.PAYMENT, 
                BackupConstants.EXPENSE, BackupConstants.ELECTRICITY)
    
    except Exception as e:
        logger.error(f"❌ 验证过程出错: {e}")
        return (BackupConstants.ROOMS, BackupConstants.PAYMENT, 
                BackupConstants.EXPENSE, BackupConstants.ELECTRICITY)


# ============== 连接池管理 ==============
class DatabaseConnectionPool:
    """单例连接池"""
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, config: dict):
        """
        初始化连接池
        
        Args:
            config: {'host': ..., 'port': ..., 'database': ..., 'user': ..., 'password': ...}
        """
        if self._pool is not None:
            logger.warning("连接池已初始化")
            return
        
        try:
            minconn = SYSTEM.CONNECTION_POOL_MIN if CONSTANTS_LOADED else 2
            maxconn = SYSTEM.CONNECTION_POOL_MAX if CONSTANTS_LOADED else 10
            
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn,
                maxconn,
                host=config.get('host'),
                port=config.get('port', 5432),
                database=config.get('database'),
                user=config.get('user'),
                password=config.get('password'),
                connect_timeout=10
            )
            logger.info(f"✅ 连接池初始化成功 (min={minconn}, max={maxconn})")
        
        except Exception as e:
            logger.error(f"❌ 连接池初始化失败: {e}")
            raise
    
    def get_connection(self):
        if self._pool is None:
            raise RuntimeError("连接池未初始化")
        return self._pool.getconn()
    
    def return_connection(self, conn):
        if self._pool and conn:
            self._pool.putconn(conn)
    
    def close_all(self):
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("✅ 连接池已关闭")


# ============== 主数据库类 ==============
class SupabaseDB:
    """Supabase 数据库操作 - v2.8 修复版"""
    
    def __init__(self):
        self.pool = DatabaseConnectionPool()
        self.validated_constants = validate_constants()
        
        try:
            self.pool.initialize(st.secrets.get("supabase", {}))
            logger.info("✅ SupabaseDB 初始化成功")
        except Exception as e:
            logger.error(f"❌ SupabaseDB 初始化失败: {e}")
            st.error(f"数据库初始化失败: {e}")
    
    @contextlib.contextmanager
    def get_connection(self):
        """Context Manager - 自动处理事务"""
        conn = None
        try:
            conn = self.pool.get_connection()
            yield conn
            conn.commit()
            logger.debug("✅ 事务提交成功")
        
        except psycopg2.IntegrityError as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 数据完整性错误: {e}")
            raise
        
        except psycopg2.OperationalError as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 数据库操作错误: {e}")
            raise
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 未知错误: {e}")
            raise
        
        finally:
            if conn:
                self.pool.return_connection(conn)
    
    def retry_on_failure(self, func, max_retries: int = 3):
        retry_delay = SYSTEM.RETRY_DELAY if CONSTANTS_LOADED else 1
        
        for attempt in range(max_retries):
            try:
                return func()
            except psycopg2.OperationalError as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ 重试 {max_retries} 次后仍失败: {e}")
                    raise
                
                wait_time = retry_delay * (attempt + 1)
                logger.warning(f"⚠️ 第 {attempt + 1}/{max_retries} 次尝试失败，"
                              f"等待 {wait_time}s 后重试... ({str(e)[:100]})")
                time.sleep(wait_time)
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                result = cur.fetchone()
            logger.info("✅ 数据库连接正常")
            return result is not None
        except Exception as e:
            logger.error(f"❌ 健康检查失败: {e}")
            return False
    
    # ==================== 租客管理 ====================
    
    def get_tenants(self, active_only: bool = True) -> pd.DataFrame:
        """获取租客列表"""
        def query():
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                condition = "WHERE is_active = true" if active_only else ""
                cur.execute(f"""
                    SELECT id, room_number, tenant_name, phone, deposit, base_rent,
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
                    logger.info("📭 无租客记录")
                    return pd.DataFrame(columns=columns)
                
                logger.info(f"✅ 查询到 {len(data)} 位租客")
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)
    
    def add_tenant(
        self, room: str, name: str, phone: str, deposit: float, base_rent: float,
        start: date, end: date, payment_method: str, has_water_fee: bool = False,
        annual_discount_months: int = 0, discount_notes: str = ""
    ) -> Tuple[bool, str]:
        try:
            all_rooms = ROOMS.ALL_ROOMS if CONSTANTS_LOADED else BackupConstants.ROOMS.ALL_ROOMS
            if room not in all_rooms:
                logger.warning(f"❌ 房号无效: {room}")
                return False, f"无效房号: {room}"
            
            methods = PAYMENT.METHODS if CONSTANTS_LOADED else BackupConstants.PAYMENT.METHODS
            if payment_method not in methods:
                logger.warning(f"❌ 支付方式无效: {payment_method}")
                return False, f"无效支付方式: {payment_method}"
            
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute(
                    "SELECT COUNT(*) FROM tenants WHERE room_number = %s AND is_active = true",
                    (room,)
                )
                
                if cur.fetchone()[0] > 0:
                    logger.warning(f"❌ 房间已被占用: {room}")
                    return False, f"房间 {room} 已有租客"
                
                cur.execute("""
                    INSERT INTO tenants 
                    (room_number, tenant_name, phone, deposit, base_rent, lease_start, 
                     lease_end, payment_method, has_water_fee, annual_discount_months, discount_notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (room, name, phone, deposit, base_rent, start, end, 
                      payment_method, has_water_fee, annual_discount_months, discount_notes))
                
                log_db_operation("INSERT", "tenants", True, 1)
                logger.info(f"✅ 新增租客: {name} ({room})")
                return True, f"成功新增租客 {name}"
        
        except Exception as e:
            log_db_operation("INSERT", "tenants", False, error=str(e))
            logger.error(f"❌ 新增失败: {str(e)}")
            return False, f"新增失败: {str(e)[:100]}"
    
    def update_tenant(
        self, tenant_id: int, room: str, name: str, phone: str, deposit: float,
        base_rent: float, start: date, end: date, payment_method: str,
        has_water_fee: bool = False, annual_discount_months: int = 0, discount_notes: str = ""
    ) -> Tuple[bool, str]:
        try:
            all_rooms = ROOMS.ALL_ROOMS if CONSTANTS_LOADED else BackupConstants.ROOMS.ALL_ROOMS
            methods = PAYMENT.METHODS if CONSTANTS_LOADED else BackupConstants.PAYMENT.METHODS
            
            if room not in all_rooms:
                return False, f"无效房号: {room}"
            if payment_method not in methods:
                return False, f"无效支付方式: {payment_method}"
            
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE tenants SET
                        room_number = %s, tenant_name = %s, phone = %s, deposit = %s,
                        base_rent = %s, lease_start = %s, lease_end = %s, payment_method = %s,
                        has_water_fee = %s, annual_discount_months = %s, discount_notes = %s
                    WHERE id = %s
                """, (room, name, phone, deposit, base_rent, start, end, 
                      payment_method, has_water_fee, annual_discount_months, discount_notes, tenant_id))
                
                log_db_operation("UPDATE", "tenants", True, 1)
                logger.info(f"✅ 更新租客 ID: {tenant_id}")
                return True, f"成功更新租客 {name}"
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 更新失败: {str(e)}")
            return False, f"更新失败: {str(e)[:100]}"
    
    def delete_tenant(self, tenant_id: int) -> Tuple[bool, str]:
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE tenants SET is_active = false WHERE id = %s", (tenant_id,))
                
                log_db_operation("UPDATE", "tenants", True, 1)
                logger.info(f"✅ 删除租客 ID: {tenant_id}")
                return True, "删除成功"
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 删除失败: {str(e)}")
            return False, f"删除失败: {str(e)[:100]}"
    
    # ==================== 租金管理 ====================
    
    def get_payment_schedule(
        self, year: Optional[int] = None, month: Optional[int] = None,
        room: Optional[str] = None, status: Optional[str] = None
    ) -> pd.DataFrame:
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
                    SELECT id, room_number, tenant_name, payment_year, payment_month,
                           amount, paid_amount, payment_method, due_date, status, created_at, updated_at
                    FROM payment_schedule
                    WHERE {' AND '.join(conditions)}
                    ORDER BY payment_year DESC, payment_month DESC, room_number
                """
                
                cur.execute(query_sql, params)
                columns = [desc[0] for desc in cur.description]
                data = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule", True, len(data))
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)
    
    def add_payment_schedule(
        self, room: str, tenant_name: str, year: int, month: int,
        amount: float, payment_method: str, due_date: Optional[date] = None
    ) -> Tuple[bool, str]:
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT COUNT(*) FROM payment_schedule 
                    WHERE room_number = %s AND payment_year = %s AND payment_month = %s
                """, (room, year, month))
                
                if cur.fetchone()[0] > 0:
                    logger.warning(f"❌ {room} {year}/{month} 已有记录")
                    return False, f"{year}/{month} {room} 已存在"
                
                cur.execute("""
                    INSERT INTO payment_schedule 
                    (room_number, tenant_name, payment_year, payment_month, amount, paid_amount,
                     payment_method, due_date, status)
                    VALUES (%s, %s, %s, %s, %s, 0, %s, %s, 'unpaid')
                """, (room, tenant_name, year, month, amount, payment_method, due_date))
                
                log_db_operation("INSERT", "payment_schedule", True, 1)
                logger.info(f"✅ 新增账单: {room} {year}/{month} {amount}元")
                return True, "新增成功"
        
        except Exception as e:
            log_db_operation("INSERT", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 新增失败: {str(e)}")
            return False, f"新增失败: {str(e)[:100]}"
    
    def mark_payment_done(self, payment_id: int, paid_amount: Optional[float] = None) -> bool:
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                if paid_amount:
                    cur.execute("""
                        UPDATE payment_schedule 
                        SET status = 'paid', paid_amount = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (paid_amount, payment_id))
                else:
                    cur.execute("""
                        UPDATE payment_schedule 
                        SET status = 'paid', paid_amount = amount, updated_at = NOW()
                        WHERE id = %s
                    """, (payment_id,))
                
                log_db_operation("UPDATE", "payment_schedule", True, 1)
                logger.info(f"✅ 标记已缴 ID: {payment_id}")
                return True
        
        except Exception as e:
            log_db_operation("UPDATE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 更新失败: {str(e)}")
            return False
    
    def get_overdue_payments(self) -> pd.DataFrame:
        def query():
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT room_number, tenant_name, payment_year, payment_month, amount, due_date
                    FROM payment_schedule
                    WHERE status = 'unpaid' AND due_date < CURRENT_DATE
                    ORDER BY due_date
                """)
                
                columns = [desc[0] for desc in cur.description]
                data = cur.fetchall()
                
                log_db_operation("SELECT", "payment_schedule (overdue)", True, len(data))
                logger.warning(f"⚠️ {len(data)} 笔逾期账单")
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)
    
    def check_payment_exists(self, room: str, year: int, month: int) -> bool:
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT COUNT(*) FROM payment_schedule 
                    WHERE room_number = %s AND payment_year = %s AND payment_month = %s
                """, (room, year, month))
                
                exists = cur.fetchone()[0] > 0
                logger.debug(f"🔍 {room} {year}/{month} - {'已存在' if exists else '不存在'}")
                return exists
        
        except Exception as e:
            logger.error(f"❌ 查询失败: {str(e)}")
            return False
    
    def batch_create_payment_schedule(self, schedules: list) -> tuple:
        success_count = 0
        skip_count = 0
        fail_count = 0
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                for schedule in schedules:
                    try:
                        cur.execute("""
                            SELECT COUNT(*) FROM payment_schedule 
                            WHERE room_number = %s AND payment_year = %s AND payment_month = %s
                        """, (schedule['room_number'], schedule['payment_year'], schedule['payment_month']))
                        
                        if cur.fetchone()[0] > 0:
                            skip_count += 1
                            continue
                        
                        cur.execute("""
                            INSERT INTO payment_schedule 
                            (room_number, tenant_name, payment_year, payment_month, amount, 
                             paid_amount, payment_method, due_date, status)
                            VALUES (%s, %s, %s, %s, %s, 0, %s, %s, 'unpaid')
                        """, (schedule['room_number'], schedule['tenant_name'], 
                              schedule['payment_year'], schedule['payment_month'],
                              schedule['amount'], schedule['payment_method'], schedule['due_date']))
                        
                        success_count += 1
                    
                    except Exception as e:
                        logger.error(f"❌ {schedule['room_number']} 失败: {e}")
                        fail_count += 1
                
                log_db_operation("INSERT", "payment_schedule (batch)", True, success_count)
                logger.info(f"✅ 批量新增: 成功 {success_count}, 跳过 {skip_count}, 失败 {fail_count}")
                return success_count, skip_count, fail_count
        
        except Exception as e:
            logger.error(f"❌ 批量操作失败: {str(e)}")
            return 0, 0, len(schedules)
    
    def get_payment_statistics(self, year: int = None, month: int = None) -> dict:
        try:
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
                
                where_clause = " AND ".join(conditions)
                
                cur.execute(f"""
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
                
                row = cur.fetchone()
                
                if not row or row[0] == 0:
                    logger.debug("📊 无统计数据")
                    return {
                        'total_amount': 0, 'paid_amount': 0, 'unpaid_amount': 0,
                        'total_count': 0, 'paid_count': 0, 'unpaid_count': 0, 'payment_rate': 0
                    }
                
                total_count, total_amount, paid_count, paid_amount, unpaid_count, unpaid_amount = row
                payment_rate = (paid_count / total_count * 100) if total_count > 0 else 0
                
                log_db_operation("SELECT", "payment_schedule (statistics)", True, total_count)
                logger.debug(f"📊 应收: {total_amount or 0:,.0f}, 已收: {paid_amount or 0:,.0f}, 收缴率: {payment_rate:.1f}%")
                
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
            logger.error(f"❌ 统计失败: {str(e)}")
            return {}
    
    def get_payment_trends(self, year: int) -> list:
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
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
                for row in cur.fetchall():
                    month, total_amt, paid_amt, total_cnt, paid_cnt = row
                    payment_rate = (paid_cnt / total_cnt * 100) if total_cnt > 0 else 0
                    trends.append({
                        'month': int(month),
                        'total_amount': float(total_amt or 0),
                        'paid_amount': float(paid_amt or 0),
                        'payment_rate': round(payment_rate, 1)
                    })
                
                log_db_operation("SELECT", "payment_schedule (trends)", True, len(trends))
                logger.info(f"✅ {year} 年趋势: {len(trends)} 个月")
                return trends
        
        except Exception as e:
            logger.error(f"❌ 趋势查询失败: {str(e)}")
            return []
    
    def batch_mark_paid(self, payment_ids: list) -> tuple:
        success_count = 0
        fail_count = 0
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                for payment_id in payment_ids:
                    try:
                        cur.execute("""
                            UPDATE payment_schedule 
                            SET status = 'paid', paid_amount = amount, updated_at = NOW()
                            WHERE id = %s
                        """, (payment_id,))
                        success_count += 1
                    except Exception as e:
                        logger.error(f"❌ ID {payment_id} 失败: {e}")
                        fail_count += 1
                
                log_db_operation("UPDATE", "payment_schedule (batch)", True, success_count)
                logger.info(f"✅ 批量标记: 成功 {success_count}, 失败 {fail_count}")
                return success_count, fail_count
        
        except Exception as e:
            logger.error(f"❌ 批量操作失败: {str(e)}")
            return 0, len(payment_ids)
    
    def delete_payment_schedule(self, payment_id: int) -> tuple:
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM payment_schedule WHERE id = %s", (payment_id,))
                
                log_db_operation("DELETE", "payment_schedule", True, 1)
                logger.info(f"✅ 删除账单 ID: {payment_id}")
                return True, "删除成功"
        
        except Exception as e:
            log_db_operation("DELETE", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 删除失败: {str(e)}")
            return False, f"删除失败: {str(e)}"
    
    # ==================== 备忘录 ====================
    
    def add_memo(self, text: str, priority: str = "normal") -> bool:
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO memos (memo_text, priority) VALUES (%s, %s)", (text, priority))
                
                log_db_operation("INSERT", "memos", True, 1)
                logger.info(f"✅ 新增备忘录 ({priority})")
                return True
        
        except Exception as e:
            log_db_operation("INSERT", "memos", False, error=str(e))
            logger.error(f"❌ 新增失败: {str(e)}")
            return False
    
    def get_memos(self, include_completed: bool = False) -> List[Dict]:
        def query():
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                condition = "" if include_completed else "WHERE is_completed = false"
                cur.execute(f"""
                    SELECT id, memo_text, priority, is_completed, created_at
                    FROM memos
                    {condition}
                    ORDER BY is_completed, priority DESC, created_at DESC
                """)
                
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        
        return self.retry_on_failure(query)
    
    # ==================== 支出管理 ====================
    
    def add_expense(self, expense_date: date, category: str, amount: float, description: str) -> Tuple[bool, str]:
        try:
            categories = EXPENSE.CATEGORIES if CONSTANTS_LOADED else BackupConstants.EXPENSE.CATEGORIES
            if category not in categories:
                logger.warning(f"❌ 类别无效: {category}")
                return False, f"无效类别: {category}"
            
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO expenses (expense_date, category, amount, description)
                    VALUES (%s, %s, %s, %s)
                """, (expense_date, category, amount, description))
                
                log_db_operation("INSERT", "expenses", True, 1)
                logger.info(f"✅ 新增支出: {category} NT${amount:,.0f}")
                return True, "新增成功"
        
        except Exception as e:
            log_db_operation("INSERT", "expenses", False, error=str(e))
            logger.error(f"❌ 新增失败: {str(e)}")
            return False, f"新增失败: {str(e)[:100]}"
    
    def get_expenses(self, limit: int = 50) -> pd.DataFrame:
        def query():
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, expense_date, category, amount, description, created_at
                    FROM expenses
                    ORDER BY expense_date DESC
                    LIMIT %s
                """, (limit,))
                
                columns = [desc[0] for desc in cur.description]
                data = cur.fetchall()
                
                log_db_operation("SELECT", "expenses", True, len(data))
                return pd.DataFrame(data, columns=columns)
        
        return self.retry_on_failure(query)
    
    # ==================== 电费管理 (v2.8 修复版) ====================
    
    def getlatestmeterreading(self, room: str, period_id: int) -> Optional[float]:
        """
        取得最新电表读数 - v2.8 修复版
        
        Args:
            room: 房号
            period_id: 当前期间 ID
        
        Returns:
            上期读数 (float) 或 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 修复：表名改成 electricity_readings
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
                    logger.debug(f"📖 {room}: {result[0]}")
                    return float(result[0])
                
                return None
        
        except Exception as e:
            logger.error(f"❌ 查询失败: {str(e)}")
            return None
    
    def saveelectricityreading(
        self, 
        period_id: int, 
        room: str, 
        previous: float, 
        current: float, 
        kwh_used: float
    ) -> Tuple[bool, str]:
        """
        储存电表读数 - v2.8 修复版
        
        Args:
            period_id: 期间 ID
            room: 房号
            previous: 上期读数
            current: 本期读数
            kwh_used: 用电度数
        
        Returns:
            (bool, str): 成功/失败訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 修复：表名改成 electricity_readings
                cursor.execute(
                    """
                    INSERT INTO electricity_readings 
                    (period_id, room_number, previous_reading, current_reading, kwh_used)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (period_id, room_number) DO UPDATE SET
                        previous_reading = EXCLUDED.previous_reading,
                        current_reading = EXCLUDED.current_reading,
                        kwh_used = EXCLUDED.kwh_used
                    """,
                    (period_id, room, previous, current, kwh_used)
                )
                
                log_db_operation("INSERT", "electricity_readings", True, 1)
                logger.info(f"✅ {room}: {kwh_used} 度")
                return True, f"✅ 已储存 {room}"
        
        except Exception as e:
            log_db_operation("INSERT", "electricity_readings", False, error=str(e))
            logger.error(f"❌ 储存失败: {str(e)}")
            return False, str(e)
    
    def addelectricityperiod(self, year: int, month_start: int, month_end: int) -> Tuple[bool, str, Optional[int]]:
        """
        新增电费期间 - v2.8 修复版
        
        Args:
            year: 年份
            month_start: 开始月
            month_end: 结束月
        
        Returns:
            (bool, str, period_id): 成功/失败訊息 + 期间 ID
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                # ✅ 修复：表名改成 electricity_periods
                cur.execute(
                    """
                    INSERT INTO electricity_periods 
                    (period_year, period_month_start, period_month_end)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (year, month_start, month_end)
                )
                
                period_id = cur.fetchone()[0]
                
                log_db_operation("INSERT", "electricity_periods", True, 1)
                logger.info(f"✅ 建立期间: {year}/{month_start}-{month_end}")
                return True, f"✅ 已建立 {year} 年 {month_start}-{month_end} 月", period_id
        
        except Exception as e:
            log_db_operation("INSERT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 建立失败: {str(e)}")
            return False, str(e), None
    
    def getallperiods(self) -> List[Dict]:
        """
        取得所有期间 - v2.8 修复版
        
        Returns:
            期间列表 (List[Dict])
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 修复：表名改成 electricity_periods
                cursor.execute(
                    """
                    SELECT id, period_year, period_month_start, period_month_end, created_at
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
                        'created_at': row[4]
                    }
                    for row in rows
                ]
                
                log_db_operation("SELECT", "electricity_periods", True, len(result))
                return result
        
        except Exception as e:
            log_db_operation("SELECT", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 查询失败: {str(e)}")
            return []
    
    def deleteelectricityperiod(self, period_id: int) -> Tuple[bool, str]:
        """
        删除期间 - v2.8 修复版
        
        Args:
            period_id: 期间 ID
        
        Returns:
            (bool, str): 成功/失败訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 修复：表名改成 electricity_periods
                cursor.execute(
                    "DELETE FROM electricity_periods WHERE id = %s",
                    (period_id,)
                )
                
                log_db_operation("DELETE", "electricity_periods", True, 1)
                logger.info(f"✅ 删除期间 ID: {period_id}")
                return True, "✅ 已删除期间"
        
        except Exception as e:
            log_db_operation("DELETE", "electricity_periods", False, error=str(e))
            logger.error(f"❌ 删除失败: {str(e)}")
            return False, str(e)
    
    def saveelectricityrecord(self, period_id: int, calc_results: list) -> Tuple[bool, str]:
        """
        储存电费计算结果 - v2.8 修复版
        
        Args:
            period_id: 期间 ID
            calc_results: 计算结果列表
                - 必须包含：'房号', '楼层', '类型', '使用度数', '公用分摊', '总度数', '单价', '应缴金额'
                - 选择性包含：'previous_reading', 'current_reading'
        
        Returns:
            (bool, str): 成功/失败訊息
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 1. 先删除该期间的旧记录（避免重复）
                # ✅ 修复：表名改成 electricity_records
                cursor.execute(
                    "DELETE FROM electricity_records WHERE period_id = %s",
                    (period_id,)
                )
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"已删除 {deleted_count} 笔旧记录")
                
                success_count = 0
                for result in calc_results:
                    # 1.1 更新读数表（如果有提供 previous_reading/current_reading）
                    if 'previous_reading' in result and 'current_reading' in result:
                        # ✅ 修复：表名改成 electricity_readings
                        cursor.execute(
                            """
                            INSERT INTO electricity_readings 
                            (period_id, room_number, previous_reading, current_reading, kwh_used)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (period_id, room_number) DO UPDATE SET
                                previous_reading = EXCLUDED.previous_reading,
                                current_reading = EXCLUDED.current_reading,
                                kwh_used = EXCLUDED.kwh_used
                            """,
                            (
                                period_id,
                                result['房号'],
                                result['previous_reading'],
                                result['current_reading'],
                                result['使用度数']
                            )
                        )
                    
                    # 1.2 插入计费记录
                    # ✅ 修复：表名改成 electricity_records
                    cursor.execute(
                        """
                        INSERT INTO electricity_records 
                        (period_id, room_number, floor, room_type, previous_reading, current_reading,
                         usage_kwh, public_share_kwh, total_kwh, unit_price, amount_due, 
                         payment_status, paid_amount, payment_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (period_id, room_number) DO UPDATE SET
                            floor = EXCLUDED.floor,
                            room_type = EXCLUDED.room_type,
                            previous_reading = EXCLUDED.previous_reading,
                            current_reading = EXCLUDED.current_reading,
                            usage_kwh = EXCLUDED.usage_kwh,
                            public_share_kwh = EXCLUDED.public_share_kwh,
                            total_kwh = EXCLUDED.total_kwh,
                            unit_price = EXCLUDED.unit_price,
                            amount_due = EXCLUDED.amount_due
                        """,
                        (
                            period_id,
                            result['房号'],
                            result['楼层'],
                            result['类型'],
                            result.get('previous_reading', 0),
                            result.get('current_reading', 0),
                            result['使用度数'],
                            result['公用分摊'],
                            result['总度数'],
                            result['单价'],
                            result['应缴金额'],
                            'unpaid',
                            0,
                            None
                        )
                    )
                    success_count += 1
                
                log_db_operation("INSERT", "electricity_records", True, success_count)
                logger.info(f"✅ 成功储存 {success_count} 笔计费记录")
                return True, f"✅ 已储存 {success_count} 笔计费记录"
            
            except Exception as e:
                log_db_operation("INSERT", "electricity_records", False, error=str(e))
                logger.error(f"❌ 储存失败: {str(e)}")
                return False, str(e)
    
    def getelectricitypaymentrecord(self, period_id: int) -> pd.DataFrame:
        """
        查询电费缴费记录 - v2.8 修复版
        
        Args:
            period_id: 期间 ID
        
        Returns:
            pd.DataFrame: 缴费记录（欄位名与 UI 对齐）
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 修复：表名改成 electricity_records，欄位名对齐 UI
                cursor.execute(
                    """
                    SELECT 
                        room_number,
                        floor,
                        room_type,
                        previous_reading,
                        current_reading,
                        usage_kwh,
                        public_share_kwh,
                        total_kwh,
                        unit_price,
                        amount_due,
                        paid_amount,
                        payment_status,
                        payment_date,
                        notes,
                        updated_at
                    FROM electricity_records
                    WHERE period_id = %s
                    ORDER BY 
                        CASE floor 
                            WHEN '1F' THEN 1 
                            WHEN '2F' THEN 2 
                            WHEN '3F' THEN 3 
                            WHEN '4F' THEN 4 
                            ELSE 5 
                        END,
                        room_number
                    """,
                    (period_id,)
                )
                
                rows = cursor.fetchall()
                
                if not rows:
                    logger.warning(f"⚠️ period_id={period_id} 没有记录")
                    return pd.DataFrame()
                
                # 组装 DataFrame（欄位名与 UI 严格对齐）
                data = []
                for row in rows:
                    data.append({
                        '房号': row[0],
                        '楼层': row[1],
                        '类型': row[2],
                        '上期读数': row[3],
                        '本期读数': row[4],
                        '使用度数': row[5],
                        '公用分摊': row[6],
                        '总度数': row[7],
                        '单价': f"{row[8]:.2f}" if row[8] else "-",
                        '应缴金额': f"${row[9]:,}" if row[9] else "$0",
                        '已缴金额': f"${row[10]:,}" if row[10] else "$0",
                        '缴费状态': '✅ 已缴' if row[11] == 'paid' else '⏳ 未缴',
                        '缴费日期': row[12].strftime('%Y-%m-%d') if row[12] else "-",
                        '备注': row[13] or "-",
                        '更新时间': row[14].strftime('%Y-%m-%d %H:%M') if row[14] else "-"
                    })
                
                log_db_operation("SELECT", "electricity_records", True, len(data))
                logger.info(f"✅ 查询到 {len(data)} 笔记录")
                
                return pd.DataFrame(data)
        
        except Exception as e:
            log_db_operation("SELECT", "electricity_records", False, error=str(e))
            logger.error(f"❌ 查询失败: {str(e)}")
            return pd.DataFrame()
    
    def updateelectricitypayment(
        self, 
        period_id: int, 
        room_number: str, 
        payment_status: str, 
        paid_amount: int = 0, 
        payment_date: str = None, 
        notes: str = ""
    ) -> Tuple[bool, str]:
        """
        更新电费缴费状态 - v2.8 修复版
        
        Args:
            period_id: 期间 ID
            room_number: 房号
            payment_status: 缴费状态 (paid/unpaid)
            paid_amount: 已缴金额
            payment_date: 缴费日期
            notes: 备注
        
        Returns:
            (bool, str): 成功/失败訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 修复：表名改成 electricity_records
                cursor.execute(
                    """
                    UPDATE electricity_records 
                    SET payment_status = %s,
                        paid_amount = %s,
                        payment_date = %s,
                        notes = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE period_id = %s AND room_number = %s
                    """,
                    (payment_status, paid_amount, payment_date, notes, period_id, room_number)
                )
                
                log_db_operation("UPDATE", "electricity_records", True, 1)
                logger.info(f"✅ {room_number} - {payment_status}")
                return True, f"✅ 已更新 {room_number} 缴费状态"
        
        except Exception as e:
            log_db_operation("UPDATE", "electricity_records", False, error=str(e))
            logger.error(f"❌ 更新失败: {str(e)}")
            return False, str(e)
    
    def getelectricitypaymentsummary(self, period_id: int) -> dict:
        """
        统计电费缴费摘要 - v2.8 修复版
        
        Args:
            period_id: 期间 ID
        
        Returns:
            dict: 统计摘要
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 修复：表名改成 electricity_records
                cursor.execute(
                    """
                    SELECT 
                        SUM(amount_due) as total_due,
                        SUM(paid_amount) as total_paid,
                        COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_rooms,
                        COUNT(CASE WHEN payment_status = 'unpaid' THEN 1 END) as unpaid_rooms,
                        COUNT(*) as total_rooms
                    FROM electricity_records
                    WHERE period_id = %s
                    """,
                    (period_id,)
                )
                
                row = cursor.fetchone()
                
                total_due = row[0] or 0
                total_paid = row[1] or 0
                paid_rooms = row[2] or 0
                unpaid_rooms = row[3] or 0
                total_rooms = row[4] or 0
                
                collection_rate = (total_paid / total_due * 100) if total_due > 0 else 0
                
                log_db_operation("SELECT", "electricity_records summary", True, total_rooms)
                logger.debug(f"📊 应收: {total_due:,.0f}, 已收: {total_paid:,.0f}, 收缴率: {collection_rate:.1f}%")
                
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
            logger.error(f"❌ 统计失败: {str(e)}")
            return {}


# ============== Streamlit 缓存 ==============
@st.cache_resource
def get_db() -> SupabaseDB:
    """Streamlit 缓存的数据库实例"""
    logger.info("🔄 初始化 SupabaseDB")
    return SupabaseDB()


# ============== 测试代码 ==============
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("services/db.py 测试模式")
    logger.info("=" * 50)
    
    print("\n" + "=" * 50)
    print("测试 1: 验证常量")
    print("=" * 50)
    try:
        validate_constants()
        print("✅ 常量验证通过")
    except Exception as e:
        print(f"❌ 常量验证失败: {e}")
    
    print("\n" + "=" * 50)
    print("测试 2: 连接池初始化")
    print("=" * 50)
    try:
        pool = DatabaseConnectionPool()
        print("✅ 连接池创建成功")
    except Exception as e:
        print(f"❌ 连接池创建失败: {e}")
    
    logger.info("=" * 50)
    logger.info("services/db.py 测试完成")
    logger.info("=" * 50 + "\n")
    
    # Streamlit 环境下会自动调用 get_db()
