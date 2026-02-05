"""
備忘錄管理服務 - v4.0 Final
✅ 備忘錄 CRUD 操作
✅ 優先級管理
✅ 完整日誌記錄
"""

from typing import List, Dict, Optional, Tuple  # ✅ 加入 Tuple
from services.base_db import BaseDBService  # ✅ 修正：base_db (有底線)
from services.logger import logger, log_db_operation


class MemoService(BaseDBService):
    """備忘錄管理服務 (繼承 BaseDBService)"""

    # 優先級定義
    PRIORITY_OPTIONS = ["低", "中", "高"]
    PRIORITY_LEVELS = {
        "低": 1,
        "中": 2,
        "高": 3,
        "low": 1,
        "normal": 2,
        "high": 3
    }

    def __init__(self):
        super().__init__()

    def add_memo(self, text: str, priority: str = "中") -> Tuple[bool, str]:
        """
        新增備忘錄
        
        Args:
            text: 備忘內容
            priority: 優先級 (低/中/高)
            
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            if priority not in self.PRIORITY_OPTIONS and priority not in ["low", "normal", "high"]:
                logger.warning(f"❌ 優先級無效: {priority}")
                return False, f"無效優先級: {priority}"

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO memos (memo_text, priority) VALUES (%s, %s)",
                    (text, priority)
                )

                log_db_operation("INSERT", "memos", True, 1)
                logger.info(f"✅ 新增備忘錄 ({priority})")
                return True, "新增成功"

        except Exception as e:
            log_db_operation("INSERT", "memos", False, error=str(e))
            logger.error(f"❌ 新增失敗: {str(e)}")
            return False, f"新增失敗: {str(e)[:100]}"

    def get_memos(self, include_completed: bool = False) -> List[Dict]:
        """
        取得備忘錄列表
        
        Args:
            include_completed: 是否包含已完成項目
            
        Returns:
            備忘錄列表
        """
        def query():
            with self.get_connection() as conn:
                cursor = conn.cursor()

                condition = "" if include_completed else "WHERE is_completed = false"
                cursor.execute(
                    f"""
                    SELECT id, memo_text, priority, is_completed, created_at
                    FROM memos
                    {condition}
                    ORDER BY is_completed, 
                             CASE priority 
                               WHEN '高' THEN 1 
                               WHEN '中' THEN 2 
                               WHEN '低' THEN 3 
                               ELSE 99 
                             END, 
                             created_at DESC
                    """
                )

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                log_db_operation("SELECT", "memos", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]

        return self.retry_on_failure(query)

    def mark_memo_completed(self, memo_id: int) -> Tuple[bool, str]:
        """
        標記備忘錄為已完成
        
        Args:
            memo_id: 備忘錄 ID
            
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE memos SET is_completed = true WHERE id = %s",
                    (memo_id,)
                )

                log_db_operation("UPDATE", "memos", True, 1)
                logger.info(f"✅ 標記完成 ID: {memo_id}")
                return True, "標記成功"

        except Exception as e:
            log_db_operation("UPDATE", "memos", False, error=str(e))
            logger.error(f"❌ 標記失敗: {str(e)}")
            return False, f"標記失敗: {str(e)[:100]}"

    def delete_memo(self, memo_id: int) -> Tuple[bool, str]:
        """
        刪除備忘錄
        
        Args:
            memo_id: 備忘錄 ID
            
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memos WHERE id = %s", (memo_id,))

                log_db_operation("DELETE", "memos", True, 1)
                logger.info(f"✅ 刪除備忘錄 ID: {memo_id}")
                return True, "刪除成功"

        except Exception as e:
            log_db_operation("DELETE", "memos", False, error=str(e))
            logger.error(f"❌ 刪除失敗: {str(e)}")
            return False, f"刪除失敗: {str(e)[:100]}"

    def update_memo(
        self, memo_id: int, text: str, priority: str = "中"
    ) -> Tuple[bool, str]:
        """
        更新備忘錄
        
        Args:
            memo_id: 備忘錄 ID
            text: 新的備忘內容
            priority: 新的優先級
            
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            if priority not in self.PRIORITY_OPTIONS and priority not in ["low", "normal", "high"]:
                return False, f"無效優先級: {priority}"

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE memos 
                    SET memo_text = %s, priority = %s 
                    WHERE id = %s
                    """,
                    (text, priority, memo_id)
                )

                log_db_operation("UPDATE", "memos", True, 1)
                logger.info(f"✅ 更新備忘錄 ID: {memo_id}")
                return True, "更新成功"

        except Exception as e:
            log_db_operation("UPDATE", "memos", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, f"更新失敗: {str(e)[:100]}"

    def get_memo_by_id(self, memo_id: int) -> Optional[Dict]:
        """
        根據 ID 查詢備忘錄
        
        Args:
            memo_id: 備忘錄 ID
            
        Returns:
            備忘錄字典，如果不存在返回 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, memo_text, priority, is_completed, created_at
                    FROM memos
                    WHERE id = %s
                    """,
                    (memo_id,)
                )

                row = cursor.fetchone()
                if not row:
                    return None

                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))

        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None

    def get_pending_count(self) -> int:
        """
        取得待辦事項數量
        
        Returns:
            未完成的備忘錄數量
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM memos WHERE is_completed = false"
                )
                
                result = cursor.fetchone()
                return result[0] if result else 0

        except Exception as e:
            logger.error(f"❌ 統計失敗: {str(e)}")
            return 0

    def get_statistics(self) -> Dict:
        """
        取得備忘錄統計資訊
        
        Returns:
            統計字典 {total, pending, completed, by_priority}
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 總計
                cursor.execute("SELECT COUNT(*) FROM memos")
                total = cursor.fetchone()[0]
                
                # 待辦
                cursor.execute("SELECT COUNT(*) FROM memos WHERE is_completed = false")
                pending = cursor.fetchone()[0]
                
                # 已完成
                cursor.execute("SELECT COUNT(*) FROM memos WHERE is_completed = true")
                completed = cursor.fetchone()[0]
                
                # 按優先級統計
                cursor.execute("""
                    SELECT priority, COUNT(*) 
                    FROM memos 
                    WHERE is_completed = false
                    GROUP BY priority
                """)
                by_priority = {row[0]: row[1] for row in cursor.fetchall()}

                return {
                    "total": total,
                    "pending": pending,
                    "completed": completed,
                    "by_priority": by_priority
                }

        except Exception as e:
            logger.error(f"❌ 統計失敗: {str(e)}")
            return {
                "total": 0,
                "pending": 0,
                "completed": 0,
                "by_priority": {}
            }
