"""
系統設定 - v3.0 (Service 架構完全重構)
✅ 完全移除 db 依賴
✅ 使用 Service 架構
✅ 資料匯出優化
✅ 系統診斷增強
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import logging

# ✅ 使用 Service 架構
from services.tenant_service import TenantService
from services.payment_service import PaymentService
from services.expense_service import ExpenseService
from services.electricity_service import ElectricityService
from services.system_service import SystemService

# 安全 import
try:
    from components.cards import section_header, metric_card, empty_state, info_card
except ImportError:
    def section_header(title, icon="", divider=True):
        st.markdown(f"### {icon} {title}")
        if divider: st.divider()
    
    def metric_card(label, value, delta="", icon="", color="normal"):
        st.metric(label, value, delta)
    
    def empty_state(msg, icon="", desc=""):
        st.info(f"{icon} {msg}")
    
    def info_card(title, content, icon="", type="info"):
        st.info(f"{icon} {title}\n\n{content}")

logger = logging.getLogger(__name__)


# ============== Tab 1: 系統參數 ==============

def render_params_tab(system_service: SystemService):
    """系統參數設定"""
    section_header("系統參數", "⚙️")
    
    info_card(
        "💡 功能說明",
        "系統參數儲存在資料庫中，修改後立即生效。建議謹慎操作。",
        "💡",
        "info"
    )
    
    st.divider()
    
    # 取得當前設定
    try:
        settings = system_service.get_all_settings()
    except Exception as e:
        st.error(f"❌ 載入設定失敗: {e}")
        logger.error(f"載入系統設定失敗: {e}", exc_info=True)
        settings = {}
    
    # === 水費設定 ===
    with st.expander("💧 水費設定", expanded=True):
        water_fee = st.number_input(
            "每月水費金額 (元)",
            min_value=0,
            value=int(settings.get('water_fee', 100)),
            step=10,
            help="房客若選擇「包含水費」，將扣除此金額",
            key="water_fee"
        )
        
        if st.button("💾 儲存水費設定", key="save_water_fee"):
            try:
                system_service.save_setting('water_fee', str(water_fee))
                st.success("✅ 水費設定已更新")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 儲存失敗: {e}")
                logger.error(f"儲存水費設定失敗: {e}", exc_info=True)
    
    # === 租金到期提醒 ===
    with st.expander("📅 租金到期提醒", expanded=False):
        remind_days = st.number_input(
            "提前幾天提醒租約到期",
            min_value=0,
            max_value=90,
            value=int(settings.get('remind_days', 45)),
            step=5,
            key="remind_days"
        )
        
        if st.button("💾 儲存提醒設定", key="save_remind"):
            try:
                system_service.save_setting('remind_days', str(remind_days))
                st.success("✅ 提醒設定已更新")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 儲存失敗: {e}")
                logger.error(f"儲存提醒設定失敗: {e}", exc_info=True)
    
    # === 繳費逾期設定 ===
    with st.expander("⏰ 繳費逾期設定", expanded=False):
        overdue_days = st.number_input(
            "逾期天數門檻",
            min_value=1,
            max_value=30,
            value=int(settings.get('overdue_days', 7)),
            step=1,
            help="超過此天數標記為逾期",
            key="overdue_days"
        )
        
        if st.button("💾 儲存逾期設定", key="save_overdue"):
            try:
                system_service.save_setting('overdue_days', str(overdue_days))
                st.success("✅ 逾期設定已更新")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 儲存失敗: {e}")
                logger.error(f"儲存逾期設定失敗: {e}", exc_info=True)
    
    # === 顯示設定 ===
    with st.expander("🎨 顯示設定", expanded=False):
        items_per_page = st.number_input(
            "每頁顯示筆數",
            min_value=10,
            max_value=200,
            value=int(settings.get('items_per_page', 50)),
            step=10,
            key="items_per_page"
        )
        
        if st.button("💾 儲存顯示設定", key="save_display"):
            try:
                system_service.save_setting('items_per_page', str(items_per_page))
                st.success("✅ 顯示設定已更新")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 儲存失敗: {e}")
                logger.error(f"儲存顯示設定失敗: {e}", exc_info=True)


# ============== Tab 2: 資料匯出 ==============

def render_export_tab(
    tenant_service: TenantService,
    payment_service: PaymentService,
    expense_service: ExpenseService,
    electricity_service: ElectricityService
):
    """資料匯出"""
    section_header("資料匯出", "📥")
    
    info_card(
        "💡 功能說明",
        "匯出系統資料為 CSV 格式，可用於備份或匯入 Excel 分析。",
        "💡",
        "info"
    )
    
    st.divider()
    
    # === 房客資料 ===
    with st.expander("👥 房客資料", expanded=True):
        st.write("匯出所有房客資訊 (含已停用)")
        
        if st.button("📥 匯出房客資料", key="export_tenants"):
            try:
                tenants = tenant_service.get_all_tenants()
                
                if not tenants:
                    st.warning("⚠️ 沒有房客資料")
                else:
                    df = pd.DataFrame(tenants)
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    
                    st.download_button(
                        "💾 下載 CSV",
                        csv,
                        f"tenants_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv",
                        key="download_tenants"
                    )
                    
                    st.success(f"✅ 已準備 {len(tenants)} 筆房客資料")
            except Exception as e:
                st.error(f"❌ 匯出失敗: {e}")
                logger.error(f"匯出房客資料失敗: {e}", exc_info=True)
    
    # === 應收單 ===
    with st.expander("💰 應收單資料", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            export_year = st.selectbox(
                "年份",
                range(2020, 2031),
                index=datetime.now().year - 2020,
                key="export_year"
            )
        
        with col2:
            export_month = st.selectbox(
                "月份 (可選)",
                [None] + list(range(1, 13)),
                format_func=lambda x: "全年" if x is None else str(x),
                key="export_month"
            )
        
        if st.button("📥 匯出應收單", key="export_payments"):
            try:
                if export_month:
                    payments = payment_service.get_payments_by_period(export_year, export_month)
                else:
                    payments = payment_service.get_payments_by_year(export_year)
                
                if not payments:
                    st.warning("⚠️ 沒有應收單資料")
                else:
                    df = pd.DataFrame(payments)
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    
                    filename = f"payments_{export_year}"
                    if export_month:
                        filename += f"{export_month:02d}"
                    filename += f"_{datetime.now().strftime('%Y%m%d')}.csv"
                    
                    st.download_button(
                        "💾 下載 CSV",
                        csv,
                        filename,
                        "text/csv",
                        key="download_payments"
                    )
                    
                    st.success(f"✅ 已準備 {len(payments)} 筆應收單")
            except Exception as e:
                st.error(f"❌ 匯出失敗: {e}")
                logger.error(f"匯出應收單失敗: {e}", exc_info=True)
    
    # === 支出記錄 ===
    with st.expander("💸 支出記錄", expanded=False):
        export_limit = st.number_input(
            "匯出筆數",
            min_value=10,
            max_value=1000,
            value=100,
            step=10,
            key="export_expense_limit"
        )
        
        if st.button("📥 匯出支出記錄", key="export_expenses"):
            try:
                expenses = expense_service.get_expenses(limit=export_limit)
                
                if not expenses:
                    st.warning("⚠️ 沒有支出記錄")
                else:
                    df = pd.DataFrame(expenses)
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    
                    st.download_button(
                        "💾 下載 CSV",
                        csv,
                        f"expenses_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv",
                        key="download_expenses"
                    )
                    
                    st.success(f"✅ 已準備 {len(expenses)} 筆支出記錄")
            except Exception as e:
                st.error(f"❌ 匯出失敗: {e}")
                logger.error(f"匯出支出記錄失敗: {e}", exc_info=True)
    
    # === 電費記錄 ===
    with st.expander("⚡ 電費記錄", expanded=False):
        try:
            periods = electricity_service.get_all_periods()
            
            if not periods:
                st.info("ℹ️ 尚未建立電費期間")
            else:
                period_options = {
                    f"{p['period_year']}/{p['period_month_start']:02d}-{p['period_month_end']:02d}": p['id']
                    for p in periods
                }
                
                selected_period = st.selectbox(
                    "選擇期間",
                    list(period_options.keys()),
                    key="export_elec_period"
                )
                
                if st.button("📥 匯出電費記錄", key="export_electricity"):
                    try:
                        period_id = period_options[selected_period]
                        records = electricity_service.get_period_records(period_id)
                        
                        if not records:
                            st.warning("⚠️ 該期間沒有電費記錄")
                        else:
                            df = pd.DataFrame(records)
                            csv = df.to_csv(index=False, encoding='utf-8-sig')
                            
                            st.download_button(
                                "💾 下載 CSV",
                                csv,
                                f"electricity_{period_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                                "text/csv",
                                key="download_electricity"
                            )
                            
                            st.success(f"✅ 已準備 {len(records)} 筆電費記錄")
                    except Exception as e:
                        st.error(f"❌ 匯出失敗: {e}")
                        logger.error(f"匯出電費記錄失敗: {e}", exc_info=True)
        except Exception as e:
            st.error(f"❌ 載入電費期間失敗: {e}")
            logger.error(f"載入電費期間失敗: {e}", exc_info=True)


# ============== Tab 3: 系統資訊 ==============

def render_info_tab(
    tenant_service: TenantService,
    payment_service: PaymentService,
    expense_service: ExpenseService,
    electricity_service: ElectricityService,
    system_service: SystemService
):
    """系統資訊"""
    section_header("系統資訊", "ℹ️")
    
    # === 資料庫統計 ===
    st.write("**📊 資料庫統計**")
    
    try:
        # 房客數
        tenants = tenant_service.get_all_tenants()
        tenants_count = len(tenants) if tenants else 0
        
        # 應收單數
        payments = payment_service.get_all_payments()
        payments_count = len(payments) if payments else 0
        
        # 支出記錄數
        expenses = expense_service.get_expenses(limit=10000)
        expenses_count = len(expenses) if expenses else 0
        
        # 電費期間數
        periods = electricity_service.get_all_periods()
        periods_count = len(periods) if periods else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            metric_card("房客數", str(tenants_count), icon="👥")
        
        with col2:
            metric_card("應收單", str(payments_count), icon="💰")
        
        with col3:
            metric_card("支出記錄", str(expenses_count), icon="💸")
        
        with col4:
            metric_card("電費期間", str(periods_count), icon="⚡")
    
    except Exception as e:
        st.error(f"❌ 統計失敗: {e}")
        logger.error(f"系統統計失敗: {e}", exc_info=True)
    
    st.divider()
    
    # === 系統版本 ===
    st.write("**🔧 系統版本**")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.info("""
**應用資訊**
- 名稱: 租屋管理系統
- 版本: v3.0.0
- 框架: Streamlit 1.52+
- 資料庫: PostgreSQL (Supabase)
""")
    
    with col_b:
        st.info(f"""
**環境資訊**
- Python: 3.9+
- 架構: Service Layer
- 部署: Streamlit Cloud
- 更新: {datetime.now().strftime('%Y-%m-%d')}
""")
    
    st.divider()
    
    # === 連線狀態 ===
    st.write("**🔌 連線狀態**")
    
    try:
        db_status = system_service.check_database_connection()
        
        if db_status['connected']:
            st.success("✅ 資料庫連線正常")
            st.caption(f"PostgreSQL 版本: {db_status.get('version', 'Unknown')}")
        else:
            st.error(f"❌ 資料庫連線失敗: {db_status.get('error', 'Unknown error')}")
    except Exception as e:
        st.error(f"❌ 資料庫連線失敗: {e}")
        logger.error(f"檢查資料庫連線失敗: {e}", exc_info=True)
    
    st.divider()
    
    # === 快速診斷 ===
    st.write("**🔍 快速診斷**")
    
    if st.button("🔍 執行系統檢查", key="system_check"):
        with st.spinner("檢查中..."):
            try:
                checks = system_service.run_system_diagnostics()
                
                # 顯示結果
                for check in checks:
                    icon = "✅" if check['status'] == 'ok' else "❌"
                    st.write(f"{icon} **{check['name']}**: {check['message']}")
            except Exception as e:
                st.error(f"❌ 系統檢查失敗: {e}")
                logger.error(f"系統診斷失敗: {e}", exc_info=True)


# ============== Tab 4: 關於系統 ==============

def render_about_tab():
    """關於系統"""
    section_header("關於系統", "📖")
    
    st.markdown("""
## 🏠 租屋管理系統 v3.0

### 功能模組
- **📊 儀表板**: 關鍵指標、租約警示、房間狀態
- **👥 房客管理**: 新增、編輯、刪除房客資訊
- **💰 租金管理**: 單筆/批量預填、繳費確認、財報統計
- **📋 繳費追蹤**: 批量標記、進階篩選、逾期提醒
- **⚡ 電費管理**: 計費期間、計算電費、繳費記錄
- **💸 支出管理**: 新增、編輯、刪除、統計分析
- **📬 通知管理**: LINE 通知、自動提醒、記錄查詢
- **⚙️ 系統設定**: 參數設定、資料匯出、系統資訊

### 技術棧
- **前端**: Streamlit 1.52+
- **後端**: Service Layer 架構
- **資料庫**: PostgreSQL (Supabase)
- **語言**: Python 3.9+
- **部署**: Streamlit Cloud

### 版本歷史
- **v3.0.0** (2026-02): Service 架構重構，完全移除直接 DB 依賴
- **v2.0.0** (2026-01): 完整重構，新增批量操作、統計圖表
- **v1.5.0** (2025-12): 新增電費管理、繳費追蹤
- **v1.0.0** (2025-11): 初版發布

### 架構特色
- **Service Layer**: 業務邏輯與資料訪問分離
- **Repository Pattern**: 統一資料存取介面
- **錯誤處理**: 完整的異常處理與日誌記錄
- **可測試性**: 易於單元測試與整合測試

### 開發團隊
- **專案**: rental_saas2026
- **GitHub**: [https://github.com/lianjen/rental_saas2026](https://github.com/lianjen/rental_saas2026)

### 意見回饋
如有任何問題或建議，歡迎透過 GitHub Issues 回報。

### 授權
© 2025-2026 租屋管理系統. All rights reserved.
""")


# ============== 主函數 ==============

def render():
    """主渲染函數（供 main.py 動態載入使用）"""
    st.title("⚙️ 系統設定")
    
    # ✅ 初始化 Services
    tenant_service = TenantService()
    payment_service = PaymentService()
    expense_service = ExpenseService()
    electricity_service = ElectricityService()
    system_service = SystemService()
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "⚙️ 系統參數",
        "📥 資料匯出",
        "ℹ️ 系統資訊",
        "📖 關於"
    ])
    
    with tab1:
        render_params_tab(system_service)
    
    with tab2:
        render_export_tab(
            tenant_service,
            payment_service,
            expense_service,
            electricity_service
        )
    
    with tab3:
        render_info_tab(
            tenant_service,
            payment_service,
            expense_service,
            electricity_service,
            system_service
        )
    
    with tab4:
        render_about_tab()


# ✅ Streamlit 頁面入口
def show():
    """Streamlit 頁面入口"""
    render()


if __name__ == "__main__":
    show()
