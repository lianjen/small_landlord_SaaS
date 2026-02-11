"""
系統服務 - v1.0
職責：處理系統參數設定、資料匯出、系統資訊查詢
"""
import logging
from typing import Dict, Optional
from datetime import datetime
from services.base_db import BaseDBService

logger = logging.getLogger(__name__)


class SystemService(BaseDBService):
    """系統服務類別"""
    
    def __init__(self):
        super().__init__()
        self._init_settings_table()
    
    def _init_settings_table(self):
        """初始化系統設定表（如果不存在）"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 建立系統設定表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key VARCHAR(100) PRIMARY KEY,
                        value TEXT NOT NULL,
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_by VARCHAR(100)
                    )
                """)
                
                # 插入預設設定（如果不存在）
                default_settings = [
                    ('water_fee', '100', '每月水費金額'),
                    ('remind_days', '45', '租約到期提醒天數'),
                    ('overdue_days', '7', '逾期天數門檻'),
                    ('items_per_page', '50', '每頁顯示筆數')
                ]
                
                for key, value, desc in default_settings:
                    cursor.execute("""
                        INSERT INTO system_settings (key, value, description)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (key) DO NOTHING
                    """, (key, value, desc))
                
                logger.info("系統設定表初始化完成")
        
        except Exception as e:
            logger.error(f"初始化系統設定表失敗: {str(e)}", exc_info=True)
    
    def get_setting(self, key: str) -> Optional[str]:
        """取得單一設定值"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT value FROM system_settings
                    WHERE key = %s
                """, (key,))
                
                result = cursor.fetchone()
                return result[0] if result else None
        
        except Exception as e:
            logger.error(f"取得設定失敗 [{key}]: {str(e)}", exc_info=True)
            return None
    
    def get_all_settings(self) -> Dict[str, str]:
        """取得所有設定"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT key, value FROM system_settings
                """)
                
                return {row[0]: row[1] for row in cursor.fetchall()}
        
        except Exception as e:
            logger.error(f"取得所有設定失敗: {str(e)}", exc_info=True)
            return {}
    
    def save_setting(self, key: str, value: str, updated_by: str = 'system') -> bool:
        """儲存設定"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO system_settings (key, value, updated_at, updated_by)
                    VALUES (%s, %s, NOW(), %s)
                    ON CONFLICT (key) 
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                """, (key, value, updated_by))
                
                logger.info(f"設定已儲存: {key} = {value}")
                return True
        
        except Exception as e:
            logger.error(f"儲存設定失敗 [{key}]: {str(e)}", exc_info=True)
            return False
    
    def delete_setting(self, key: str) -> bool:
        """刪除設定"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM system_settings
                    WHERE key = %s
                """, (key,))
                
                logger.info(f"設定已刪除: {key}")
                return True
        
        except Exception as e:
            logger.error(f"刪除設定失敗 [{key}]: {str(e)}", exc_info=True)
            return False
    
    def get_database_stats(self) -> Dict[str, int]:
        """取得資料庫統計資訊"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # 房客數
                cursor.execute("SELECT COUNT(*) FROM tenants")
                stats['tenants'] = cursor.fetchone()[0]
                
                # 應收單數
                cursor.execute("SELECT COUNT(*) FROM payment_schedule")
                stats['payments'] = cursor.fetchone()[0]
                
                # 支出記錄數
                cursor.execute("SELECT COUNT(*) FROM expenses")
                stats['expenses'] = cursor.fetchone()[0]
                
                # 電費期間數
                cursor.execute("SELECT COUNT(*) FROM electricity_periods")
                stats['electricity_periods'] = cursor.fetchone()[0]
                
                return stats
        
        except Exception as e:
            logger.error(f"取得資料庫統計失敗: {str(e)}", exc_info=True)
            return {}
    
    def check_database_connection(self) -> bool:
        """檢查資料庫連線"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                logger.info(f"資料庫連線正常: {version}")
                return True
        
        except Exception as e:
            logger.error(f"資料庫連線失敗: {str(e)}", exc_info=True)
            return False
    
    def get_database_version(self) -> Optional[str]:
        """取得資料庫版本"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version()")
                return cursor.fetchone()[0]
        
        except Exception as e:
            logger.error(f"取得資料庫版本失敗: {str(e)}", exc_info=True)
            return None
    
    def check_table_exists(self, table_name: str) -> bool:
        """檢查資料表是否存在"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                """, (table_name,))
                
                return cursor.fetchone()[0]
        
        except Exception as e:
            logger.error(f"檢查資料表失敗 [{table_name}]: {str(e)}", exc_info=True)
            return False
    
    def run_system_diagnostics(self) -> Dict[str, Dict]:
        """執行系統診斷"""
        results = {}
        
        # 資料庫連線檢查
        results['database_connection'] = {
            'status': 'success' if self.check_database_connection() else 'failed',
            'name': '資料庫連線'
        }
        
        # 檢查必要資料表
        required_tables = [
            'tenants',
            'payment_schedule',
            'expenses',
            'electricity_periods',
            'electricity_records'
        ]
        
        for table in required_tables:
            exists = self.check_table_exists(table)
            results[f'table_{table}'] = {
                'status': 'success' if exists else 'failed',
                'name': f'{table} 資料表'
            }
        
        return results
    
    def export_system_info(self) -> Dict:
        """匯出系統資訊"""
        return {
            'app_name': '租屋管理系統',
            'version': 'v3.0',
            'framework': 'Streamlit',
            'database': 'PostgreSQL (Supabase)',
            'python_version': '3.9+',
            'export_time': datetime.now().isoformat(),
            'database_version': self.get_database_version(),
            'stats': self.get_database_stats()
        }


# ============================================
# 本機測試
# ============================================
if __name__ == "__main__":
    service = SystemService()
    
    print("=== 測試系統服務 ===\n")
    
    # 測試取得所有設定
    print("1. 所有設定:")
    settings = service.get_all_settings()
    for key, value in settings.items():
        print(f"   {key}: {value}")
    
    print("\n2. 資料庫統計:")
    stats = service.get_database_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n3. 系統診斷:")
    diagnostics = service.run_system_diagnostics()
    for key, info in diagnostics.items():
        status_icon = "✅" if info['status'] == 'success' else "❌"
        print(f"   {status_icon} {info['name']}: {info['status']}")
    
    print("\n4. 系統資訊:")
    sys_info = service.export_system_info()
    for key, value in sys_info.items():
        print(f"   {key}: {value}")
