"""
基礎數據庫服務 - v4.1
✅ 單例連接池管理（Streamlit / 非 Streamlit 通用）
✅ 統一的錯誤處理和重試機制
✅ Streamlit 資源快取整合（若可用）
"""

import os
import time
import contextlib
from typing import Generator, Tuple, Callable, Any

import psycopg2
from psycopg2 import pool

# ========= 可選的 Streamlit 依賴 =========
try:
    import streamlit as st  # type: ignore
    HAS_STREAMLIT = True
except ImportError:
    st = None  # type: ignore
    HAS_STREAMLIT = False

# ========= 日誌 =========
try:
    from services.logger import logger, log_db_operation
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    def log_db_operation(op, table, success, count: int = 0, error: str | None = None):
        if success:
            logger.info(f"✅ {op} {table}: {count} rows")
        else:
            logger.error(f"❌ {op} {table}: {error}")


# ============== 連接池管理 ==============
class DatabaseConnectionPool:
    """單例連接池 - 避免在 Streamlit rerun / 多處重複建立"""

    _instance: "DatabaseConnectionPool | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._pool: pool.ThreadedConnectionPool | None = None
        self._initialized: bool = False

    def initialize(self, config: dict):
        """初始化連接池 - 只執行一次"""
        if self._initialized and self._pool is not None:
            logger.debug("連接池已存在，跳過初始化")
            return

        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=config.get("min_connections", 2),
                maxconn=config.get("max_connections", 10),
                host=config.get("host"),
                port=config.get("port", 5432),
                database=config.get("database"),
                user=config.get("user"),
                password=config.get("password"),
                connect_timeout=10,
            )
            self._initialized = True
            logger.info("✅ 連接池初始化成功")

        except Exception as e:
            logger.error(f"❌ 連接池初始化失敗: {e}")
            raise

    def get_connection(self):
        """獲取連接"""
        if self._pool is None or not self._initialized:
            raise RuntimeError("連接池未初始化")
        return self._pool.getconn()

    def return_connection(self, conn):
        """歸還連接"""
        if self._pool and conn:
            self._pool.putconn(conn)

    def is_initialized(self) -> bool:
        """檢查是否已初始化"""
        return self._initialized and self._pool is not None

    def close_all(self):
        """關閉所有連接"""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            self._initialized = False
            logger.info("✅ 連接池已關閉")


def _load_db_config() -> dict:
    """
    載入 DB 設定：
    - 若在 Streamlit 環境：使用 st.secrets['supabase']
    - 否則：使用環境變數 SUPABASE_*
    """
    if HAS_STREAMLIT and hasattr(st, "secrets"):
        supa = st.secrets.get("supabase", {})  # type: ignore[attr-defined]
        return {
            "host": supa.get("host"),
            "port": supa.get("port", 5432),
            "database": supa.get("database"),
            "user": supa.get("user"),
            "password": supa.get("password"),
            "min_connections": 2,
            "max_connections": 10,
        }

    # 非 Streamlit 環境：讀取環境變數
    return {
        "host": os.getenv("SUPABASE_HOST"),
        "port": int(os.getenv("SUPABASE_PORT", "5432")),
        "database": os.getenv("SUPABASE_DB"),
        "user": os.getenv("SUPABASE_USER"),
        "password": os.getenv("SUPABASE_PASSWORD"),
        "min_connections": int(os.getenv("DB_MIN_CONNECTIONS", "2")),
        "max_connections": int(os.getenv("DB_MAX_CONNECTIONS", "10")),
    }


# ============== 連接池入口 ==============
# Streamlit 環境：使用 cache_resource；非 Streamlit：使用全域單例
_pool_instance = DatabaseConnectionPool()

if HAS_STREAMLIT and hasattr(st, "cache_resource"):

    @st.cache_resource  # type: ignore[attr-defined]
    def get_connection_pool() -> DatabaseConnectionPool:
        """Streamlit 資源快取 - 確保整個 session 只創建一次"""
        if not _pool_instance.is_initialized():
            config = _load_db_config()
            _pool_instance.initialize(config)
        return _pool_instance

else:

    def get_connection_pool() -> DatabaseConnectionPool:
        """非 Streamlit 環境使用的連接池取得方法"""
        if not _pool_instance.is_initialized():
            config = _load_db_config()
            _pool_instance.initialize(config)
        return _pool_instance


# ============== 基礎服務類 ==============
class BaseDBService:
    """基礎數據庫服務 - 所有服務的父類"""

    def __init__(self):
        """初始化服務 - 使用共用連接池"""
        self.pool = get_connection_pool()

    @contextlib.contextmanager
    def get_connection(self) -> Generator:
        """
        Context Manager - 自動處理事務

        使用方式:
        ```python
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
        ```
        """
        conn = None
        try:
            conn = self.pool.get_connection()
            yield conn
            conn.commit()
            logger.debug("✅ 事務提交成功")

        except psycopg2.IntegrityError as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 數據完整性錯誤: {e}")
            raise

        except psycopg2.OperationalError as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 數據庫操作錯誤: {e}")
            raise

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ 未知錯誤: {e}")
            raise

        finally:
            if conn:
                self.pool.return_connection(conn)

    def retry_on_failure(
        self,
        func: Callable[[], Any],
        max_retries: int = 3,
        delay: int = 1,
    ):
        """
        重試機制 - 處理臨時性網路錯誤

        Args:
            func: 要執行的函數
            max_retries: 最大重試次數
            delay: 重試延遲（秒）

        Returns:
            func 的返回值
        """
        for attempt in range(max_retries):
            try:
                return func()

            except psycopg2.OperationalError as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ 重試 {max_retries} 次後仍失敗: {e}")
                    raise

                wait_time = delay * (attempt + 1)
                logger.warning(
                    f"⚠️ 第 {attempt + 1}/{max_retries} 次嘗試失敗，"
                    f"等待 {wait_time}s 後重試..."
                )
                time.sleep(wait_time)

    def health_check(self) -> bool:
        """健康檢查"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

            logger.info("✅ 數據庫連接正常")
            return result is not None

        except Exception as e:
            logger.error(f"❌ 健康檢查失敗: {e}")
            return False

    def execute_query(
        self,
        query: str,
        params: Tuple | None = None,
        fetch_one: bool = False,
        fetch_all: bool = True,
    ):
        """
        通用查詢執行器

        Args:
            query: SQL 查詢
            params: 參數
            fetch_one: 是否只取一筆
            fetch_all: 是否取全部

        Returns:
            查詢結果
        """

        def _execute():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)

                if fetch_one:
                    return cursor.fetchone()
                elif fetch_all:
                    return cursor.fetchall()
                else:
                    return cursor.rowcount

        return self.retry_on_failure(_execute)

    def batch_insert(
        self,
        table: str,
        columns: list[str],
        values_list: list[Tuple],
    ) -> Tuple[int, int]:
        """
        批次插入

        Args:
            table: 表名
            columns: 欄位列表
            values_list: 值列表（每個元素是一個 tuple）

        Returns:
            (success_count, fail_count)
        """
        success_count = 0
        fail_count = 0

        placeholders = ", ".join(["%s"] * len(columns))
        query = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({placeholders})
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()

            for values in values_list:
                try:
                    cursor.execute(query, values)
                    success_count += 1
                except Exception as e:
                    logger.error(f"❌ 批次插入失敗: {e}")
                    fail_count += 1

        log_db_operation("BATCH_INSERT", table, True, success_count)
        return success_count, fail_count
