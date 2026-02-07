"""
SQLite → Supabase PostgreSQL 資料遷移工具
執行方式: python migrate_to_supabase.py
"""
import sqlite3
import logging
from supabase import create_client
import streamlit as st
from datetime import datetime
from typing import List, Dict

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """資料庫遷移工具"""
    
    def __init__(self):
        # 連接 SQLite
        self.sqlite_conn = sqlite3.connect("data/rental.db")
        self.sqlite_conn.row_factory = sqlite3.Row
        
        # 連接 Supabase
        self.supabase = create_client(
            st.secrets["supabase"]["url"],
            st.secrets["supabase"]["key"]
        )
        
        # 假設你的 user_id（從 Supabase Auth 取得）
        # ⚠️ 需要手動填入你的用戶 ID
        self.user_id = "33c8c176-da01-4b12-a60e-afbd341898c7"  # TODO: 替換成真實 ID
    
    def migrate_tenants(self) -> int:
        """遷移房客資料"""
        logger.info("開始遷移房客資料...")
        
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT * FROM tenants")
        rows = cursor.fetchall()
        
        migrated_count = 0
        for row in rows:
            try:
                data = {
                    "user_id": self.user_id,
                    "name": row["name"],
                    "email": row.get("email"),
                    "phone": row.get("phone"),
                    "id_card": row.get("id_card"),
                    "room_number": row["room_number"],
                    "rent_amount": row["rent_amount"],
                    "deposit_amount": row.get("deposit_amount", 0),
                    "move_in_date": row["move_in_date"],
                    "move_out_date": row.get("move_out_date"),
                    "status": row.get("status", "active"),
                    "notes": row.get("notes"),
                }
                
                result = self.supabase.table("tenants").insert(data).execute()
                migrated_count += 1
                logger.info(f"✅ 遷移房客: {row['name']}")
                
            except Exception as e:
                logger.error(f"❌ 遷移失敗 ({row['name']}): {e}")
        
        logger.info(f"✅ 房客遷移完成: {migrated_count}/{len(rows)}")
        return migrated_count
    
    def migrate_payments(self) -> int:
        """遷移租金記錄"""
        logger.info("開始遷移租金記錄...")
        
        # 先建立 tenant_id 映射 (SQLite ID → Supabase UUID)
        tenant_map = self._build_tenant_mapping()
        
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT * FROM payments")
        rows = cursor.fetchall()
        
        migrated_count = 0
        for row in rows:
            try:
                old_tenant_id = row["tenant_id"]
                new_tenant_id = tenant_map.get(old_tenant_id)
                
                if not new_tenant_id:
                    logger.warning(f"⚠️ 找不到對應的房客 ID: {old_tenant_id}")
                    continue
                
                data = {
                    "user_id": self.user_id,
                    "tenant_id": new_tenant_id,
                    "rent_month": row["rent_month"],
                    "amount": row["amount"],
                    "status": row.get("status", "unpaid"),
                    "paid_date": row.get("paid_date"),
                    "paid_amount": row.get("paid_amount", 0),
                    "payment_method": row.get("payment_method"),
                    "notes": row.get("notes"),
                }
                
                self.supabase.table("payments").insert(data).execute()
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"❌ 租金記錄遷移失敗: {e}")
        
        logger.info(f"✅ 租金記錄遷移完成: {migrated_count}/{len(rows)}")
        return migrated_count
    
    def _build_tenant_mapping(self) -> Dict[int, str]:
        """建立 SQLite ID → Supabase UUID 映射"""
        mapping = {}
        
        # 從 SQLite 讀取
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT id, name FROM tenants")
        sqlite_tenants = cursor.fetchall()
        
        # 從 Supabase 讀取
        supabase_tenants = self.supabase.table("tenants") \
            .select("id, name") \
            .eq("user_id", self.user_id) \
            .execute()
        
        # 建立映射（根據名稱匹配）
        for sqlite_row in sqlite_tenants:
            for supabase_row in supabase_tenants.data:
                if sqlite_row["name"] == supabase_row["name"]:
                    mapping[sqlite_row["id"]] = supabase_row["id"]
                    break
        
        return mapping
    
    def run(self):
        """執行完整遷移"""
        logger.info("=" * 50)
        logger.info("開始資料庫遷移")
        logger.info("=" * 50)
        
        # 1. 遷移房客
        tenant_count = self.migrate_tenants()
        
        # 2. 遷移租金記錄
        payment_count = self.migrate_payments()
        
        # 3. 其他表格（依需求增加）
        # self.migrate_expenses()
        # self.migrate_electricity()
        
        logger.info("=" * 50)
        logger.info(f"✅ 遷移完成！")
        logger.info(f"   房客: {tenant_count} 筆")
        logger.info(f"   租金: {payment_count} 筆")
        logger.info("=" * 50)
        
        self.sqlite_conn.close()


if __name__ == "__main__":
    # ⚠️ 執行前請先：
    # 1. 在 Supabase 執行 SQL 建立資料表
    # 2. 替換上面的 YOUR_USER_ID
    # 3. 備份你的 SQLite 資料庫
    
    migrator = DatabaseMigrator()
    migrator.run()
