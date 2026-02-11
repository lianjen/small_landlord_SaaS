"""
向後兼容層 - v4.0
✅ 保留舊的 SupabaseDB 介面
✅ 內部調用新的模組化服務
✅ 支援漸進式遷移
"""

import streamlit as st
from services.tenant_service import TenantService
from services.payment_service import PaymentService
from services.electricity_service import ElectricityService
from services.expense_service import ExpenseService
from services.memo_service import MemoService
from services.notification_service import NotificationService


@st.cache_resource
def get_database_instance():
    """
    保留舊介面 - 向後兼容
    
    使用方式（舊程式碼不需改）:
    ```python
    from services.db_legacy import get_database_instance
    db = get_database_instance()
    db.get_tenants()  # 自動調用新服務
    ```
    """
    return SupabaseDB()


class SupabaseDB:
    """
    向後兼容的數據庫類
    
    ⚠️ 此類僅用於漸進式遷移，新程式碼請直接使用各服務類
    
    遷移建議:
    - 舊程式碼: db.get_tenants() ✅ 繼續使用
    - 新程式碼: TenantService().get_tenants() ✅ 推薦
    """
    
    def __init__(self):
        """初始化所有服務"""
        self.tenant_svc = TenantService()
        self.payment_svc = PaymentService()
        self.elec_svc = ElectricityService()
        self.expense_svc = ExpenseService()
        self.memo_svc = MemoService()
        self.notif_svc = NotificationService()
    
    def health_check(self) -> bool:
        """健康檢查"""
        return self.tenant_svc.health_check()
    
    # ==================== 租客管理 ====================
    
    def get_tenants(self, active_only: bool = True):
        """獲取租客列表"""
        return self.tenant_svc.get_tenants(active_only)
    
    def add_tenant(self, *args, **kwargs):
        """新增租客"""
        return self.tenant_svc.add_tenant(*args, **kwargs)
    
    def update_tenant(self, *args, **kwargs):
        """更新租客"""
        return self.tenant_svc.update_tenant(*args, **kwargs)
    
    def delete_tenant(self, tenant_id: int):
        """刪除租客"""
        return self.tenant_svc.delete_tenant(tenant_id)
    
    # ==================== 租金管理 ====================
    
    def get_payment_schedule(self, *args, **kwargs):
        """查詢租金排程"""
        return self.payment_svc.get_payment_schedule(*args, **kwargs)
    
    def add_payment_schedule(self, *args, **kwargs):
        """新增租金排程"""
        return self.payment_svc.add_payment_schedule(*args, **kwargs)
    
    def mark_payment_done(self, payment_id: int, paid_amount=None):
        """標記為已繳款"""
        return self.payment_svc.mark_payment_done(payment_id, paid_amount)
    
    def get_overdue_payments(self):
        """查詢逾期租金"""
        return self.payment_svc.get_overdue_payments()
    
    def check_payment_exists(self, room: str, year: int, month: int):
        """檢查租金記錄是否存在"""
        return self.payment_svc.check_payment_exists(room, year, month)
    
    def batch_create_payment_schedule(self, schedules: list):
        """批次建立租金排程"""
        return self.payment_svc.batch_create_payment_schedule(schedules)
    
    def get_payment_statistics(self, year=None, month=None):
        """取得租金統計"""
        return self.payment_svc.get_payment_statistics(year, month)
    
    def get_payment_trends(self, year: int):
        """取得租金趨勢"""
        return self.payment_svc.get_payment_trends(year)
    
    def batch_mark_paid(self, payment_ids: list):
        """批次標記為已繳款"""
        return self.payment_svc.batch_mark_paid(payment_ids)
    
    def delete_payment_schedule(self, payment_id: int):
        """刪除租金排程"""
        return self.payment_svc.delete_payment_schedule(payment_id)
    
    # ==================== 電費管理 ====================
    
    def get_latest_meter_reading(self, room: str, period_id: int):
        """取得最新電表讀數"""
        return self.elec_svc.get_latest_meter_reading(room, period_id)
    
    def save_electricity_reading(self, *args, **kwargs):
        """儲存電表讀數"""
        return self.elec_svc.save_reading(*args, **kwargs)
    
    def add_electricity_period(self, year: int, month_start: int, month_end: int):
        """新增電費期間"""
        return self.elec_svc.add_period(year, month_start, month_end)
    
    def get_all_periods(self):
        """取得所有期間"""
        return self.elec_svc.get_all_periods()
    
    def delete_electricity_period(self, period_id: int):
        """刪除期間"""
        return self.elec_svc.delete_period(period_id)
    
    def update_electricity_period_remind_date(self, period_id: int, remind_date: str):
        """更新催繳開始日"""
        return self.elec_svc.update_period_remind_date(period_id, remind_date)
    
    def save_electricity_record(self, period_id: int, calc_results: list):
        """儲存電費計算結果"""
        return self.elec_svc.save_records(period_id, calc_results)
    
    def get_electricity_payment_record(self, period_id: int):
        """查詢電費計費記錄"""
        return self.elec_svc.get_payment_record(period_id)
    
    def get_electricity_payment_summary(self, period_id: int):
        """取得電費統計摘要"""
        return self.elec_svc.get_payment_summary(period_id)
    
    def update_electricity_payment(self, *args, **kwargs):
        """更新電費繳費狀態"""
        return self.elec_svc.update_payment(*args, **kwargs)
    
    # ✨ 新增：整合通知服務（自動寫入 notification_logs）
    def trigger_auto_first_notification(self, period_id: int, remind_date: str = None):
        """
        觸發電費首次通知 + 寫入 notification_logs
        
        ✅ 這是新功能！會自動寫入 notification_logs 表
        """
        return self.notif_svc.send_electricity_bill_notification(period_id, remind_date)
    
    # ==================== 支出管理 ====================
    
    def add_expense(self, *args, **kwargs):
        """新增支出記錄"""
        return self.expense_svc.add_expense(*args, **kwargs)
    
    def get_expenses(self, limit: int = 50):
        """查詢支出記錄"""
        return self.expense_svc.get_expenses(limit)
    
    # ==================== 備忘錄管理 ====================
    
    def add_memo(self, text: str, priority: str = "normal"):
        """新增備忘錄"""
        return self.memo_svc.add_memo(text, priority)
    
    def get_memos(self, include_completed: bool = False):
        """查詢備忘錄列表"""
        return self.memo_svc.get_memos(include_completed)
    
    # ==================== 輔助方法 ====================
    
    def retry_on_failure(self, func, max_retries: int = 3):
        """重試機制（保留向後兼容）"""
        return self.tenant_svc.retry_on_failure(func, max_retries)


# ============================================================================
# 遷移助手
# ============================================================================

def print_migration_guide():
    """列印遷移指南"""
    guide = """
    ╔══════════════════════════════════════════════════════════════════╗
    ║          📦 數據庫模組化遷移指南 - v4.0                         ║
    ╚══════════════════════════════════════════════════════════════════╝
    
    ✅ 現在可用的方式：
    
    方式 1️⃣ - 向後兼容（舊程式碼不需改）
    ─────────────────────────────────────────
    from services.db_legacy import get_database_instance
    
    db = get_database_instance()
    db.get_tenants()              # ✅ 自動調用新服務
    db.add_payment_schedule(...)  # ✅ 自動調用新服務
    db.trigger_auto_first_notification(period_id)  # ✅ 新功能！
    
    
    方式 2️⃣ - 直接使用新服務（推薦）
    ─────────────────────────────────────────
    from services.tenant_service import TenantService
    from services.payment_service import PaymentService
    from services.notification_service import NotificationService
    
    tenant_svc = TenantService()
    payment_svc = PaymentService()
    notif_svc = NotificationService()
    
    tenants = tenant_svc.get_tenants()
    payments = payment_svc.get_payment_schedule(year=2026, month=1)
    
    # 電費通知（自動寫入 notification_logs）
    success, msg, count = notif_svc.send_electricity_bill_notification(period_id)
    
    
    ⚠️  遷移步驟：
    ─────────────────────────────────────────
    1. 本週：保留舊程式碼，新功能用新服務
    2. 下週：逐步替換 views/ 中的調用
    3. 完成後：刪除 services/db.py (舊檔案)
    
    
    🎯 新增功能：
    ─────────────────────────────────────────
    ✨ 電費通知現在會自動寫入 notification_logs 表
    ✨ 完整的錯誤追蹤和失敗記錄
    ✨ 支援租金催繳通知
    ✨ 支援自定義通知
    
    """
    print(guide)


if __name__ == "__main__":
    print_migration_guide()
