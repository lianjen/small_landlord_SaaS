"""
支出管理服務 - v4.0 Final
✅ 支出 CRUD 操作
✅ 支出統計與分析
✅ 完整日誌記錄
"""

import pandas as pd
from datetime import date
from typing import Tuple, Dict, List, Optional
from services.basedb import BaseDBService
from services.logger import logger, log_db_operation

try:
    from config.constants import EXPENSE
    CONSTANTS_LOADED = True
except ImportError:
    logger.warning("無法載入 config.constants，使用備用常量")
    CONSTANTS_LOADED = False

    class BackupConstants:
        class EXPENSE:
            CATEGORIES = ["維修", "清潔", "水電", "其他"]


class ExpenseService(BaseDBService):
    """支出管理服務 (繼承 BaseDBService)"""

    def __init__(self):
        super().__init__()
        self.categories = EXPENSE.CATEGORIES if CONSTANTS_LOADED else BackupConstants.EXPENSE.CATEGORIES

    def add_expense(
        self, expense_date: date, category: str, amount: float, description: str
    ) -> Tuple[bool, str]:
        """
        新增支出
        
        Args:
            expense_date: 支出日期
            category: 類別 (維修/清潔/水電/其他)
            amount: 金額
            description: 描述
            
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            if category not in self.categories:
                logger.warning(f"❌ 類別無效: {category}")
                return False, f"無效類別: {category}"

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO expenses (expense_date, category, amount, description)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (expense_date, category, amount, description)
                )

                log_db_operation("INSERT", "expenses", True, 1)
                logger.info(f"✅ 新增支出: {category} NT${amount:,.0f}")
                return True, "新增成功"

        except Exception as e:
            log_db_operation("INSERT", "expenses", False, error=str(e))
            logger.error(f"❌ 新增失敗: {str(e)}")
            return False, f"新增失敗: {str(e)[:100]}"

    def get_expenses(self, limit: int = 50) -> pd.DataFrame:
        """
        取得支出列表
        
        Args:
            limit: 筆數限制
            
        Returns:
            支出 DataFrame
        """
        def query():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, expense_date, category, amount, description, created_at
                    FROM expenses
                    ORDER BY expense_date DESC
                    LIMIT %s
                    """,
                    (limit,)
                )

                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()

                log_db_operation("SELECT", "expenses", True, len(data))
                return pd.DataFrame(data, columns=columns)

        return self.retry_on_failure(query)

    def get_expense_statistics(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> Dict:
        """
        取得支出統計
        
        Args:
            year: 年份 (可選)
            month: 月份 (可選)
            
        Returns:
            統計字典 {總支出, 各類別支出}
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                conditions = ["1=1"]
                params = []

                if year:
                    conditions.append("EXTRACT(YEAR FROM expense_date) = %s")
                    params.append(year)

                if month:
                    conditions.append("EXTRACT(MONTH FROM expense_date) = %s")
                    params.append(month)

                where_clause = " AND ".join(conditions)

                cursor.execute(
                    f"""
                    SELECT 
                        COUNT(*) as total_count,
                        SUM(amount) as total_amount,
                        category,
                        SUM(amount) as category_amount
                    FROM expenses
                    WHERE {where_clause}
                    GROUP BY category
                    ORDER BY category_amount DESC
                    """,
                    params
                )

                rows = cursor.fetchall()
                total_count = sum(row[0] for row in rows)
                total_amount = sum(row[1] for row in rows)
                by_category = {row[2]: float(row[3]) for row in rows}

                log_db_operation("SELECT", "expenses (statistics)", True, total_count)
                logger.info(f"✅ 統計: 總計 NT${total_amount:,.0f}, {total_count} 筆")

                return {
                    "total_count": total_count,
                    "total_amount": float(total_amount or 0),
                    "by_category": by_category
                }

        except Exception as e:
            log_db_operation("SELECT", "expenses (statistics)", False, error=str(e))
            logger.error(f"❌ 統計失敗: {str(e)}")
            return {"total_count": 0, "total_amount": 0, "by_category": {}}

    def delete_expense(self, expense_id: int) -> Tuple[bool, str]:
        """
        刪除支出記錄
        
        Args:
            expense_id: 支出 ID
            
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))

                log_db_operation("DELETE", "expenses", True, 1)
                logger.info(f"✅ 刪除支出 ID: {expense_id}")
                return True, "刪除成功"

        except Exception as e:
            log_db_operation("DELETE", "expenses", False, error=str(e))
            logger.error(f"❌ 刪除失敗: {str(e)}")
            return False, f"刪除失敗: {str(e)[:100]}"

    def update_expense(
        self, expense_id: int, expense_date: date, category: str, 
        amount: float, description: str
    ) -> Tuple[bool, str]:
        """
        更新支出記錄
        
        Args:
            expense_id: 支出 ID
            expense_date: 支出日期
            category: 類別
            amount: 金額
            description: 描述
            
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            if category not in self.categories:
                return False, f"無效類別: {category}"

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE expenses
                    SET expense_date = %s, category = %s, amount = %s, description = %s
                    WHERE id = %s
                    """,
                    (expense_date, category, amount, description, expense_id)
                )

                log_db_operation("UPDATE", "expenses", True, 1)
                logger.info(f"✅ 更新支出 ID: {expense_id}")
                return True, "更新成功"

        except Exception as e:
            log_db_operation("UPDATE", "expenses", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, f"更新失敗: {str(e)[:100]}"

    def get_expense_by_category(self, category: str, limit: int = 50) -> pd.DataFrame:
        """
        按類別查詢支出
        
        Args:
            category: 類別
            limit: 筆數限制
            
        Returns:
            支出 DataFrame
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, expense_date, category, amount, description, created_at
                    FROM expenses
                    WHERE category = %s
                    ORDER BY expense_date DESC
                    LIMIT %s
                    """,
                    (category, limit)
                )

                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()

                log_db_operation("SELECT", "expenses (by category)", True, len(data))
                return pd.DataFrame(data, columns=columns)

        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return pd.DataFrame()
