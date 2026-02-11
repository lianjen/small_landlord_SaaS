import sqlite3
from typing import List, Dict, Any, Optional
import os

class DatabaseService:
    def __init__(self, db_path: str = 'data/rental.db'):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """執行查詢並返回結果清單 (字典格式)"""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                if query.strip().upper().startswith("SELECT"):
                    return [dict(row) for row in cursor.fetchall()]
                conn.commit()
                return []
        except Exception as e:
            print(f"Database Error: {e}")
            raise e

    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """執行插入並返回最後插入的 ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Database Error: {e}")
            raise e
