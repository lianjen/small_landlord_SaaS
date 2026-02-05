"""
幸福之家 Pro - 租賃管理系統
Nordic Edition v3.0 (Service Architecture)
✅ 完全移除 db 依賴
✅ 使用 Service 架構
✅ 動態載入頁面模組
✅ 修正模組名稱映射
"""

import os
import logging
from typing import Optional

from dotenv import load_dotenv
import streamlit as st

# ============================================
# 0. Environment Variables
# ============================================

# 載入 .env（本機開發用；Streamlit Cloud 主要用 Secrets）
load_dotenv()


def get_env(var: str, default: Optional[str] = None) -> Optional[str]:
    """統一從 os.environ、st.secrets root 和 st.secrets['supabase'] 讀環境變數。"""
    # 1. 系統環境變數
    value = os.getenv(var)
    if value:
        return value

    # 2. Streamlit Secrets 根層
    try:
        value = st.secrets[var]  # type: ignore[index]
        if value:
            return value
    except Exception:
        pass

    # 3. Streamlit Secrets 裡的 [supabase] 區塊
    try:
        supa_cfg = st.secrets["supabase"]  # type: ignore[index]
        value = supa_cfg.get(var)  # type: ignore[union-attr]
        if value:
            return value
    except Exception:
        pass

    return default


# 驗證必要環境變數
REQUIRED_VARS = ["SUPABASE_URL", "SUPABASE_KEY"]

missing_vars = [var for var in REQUIRED_VARS if not get_env(var)]

if missing_vars:
    st.error(f"❌ 缺少必要環境變數: {', '.join(missing_vars)}")
    st.info("請在 Streamlit Cloud 的 Secrets 或本機 .env 中設定這些變數（可參考 .env.example）")
    st.stop()

# 讀取全域配置（允許從 env / secrets 覆蓋預設值）
APP_CONFIG = {
    "title": get_env("APP_TITLE", "幸福之家 Pro"),
    "version": get_env("APP_VERSION", "v14.3"),
    "environment": get_env("ENVIRONMENT", "production"),
    "log_level": get_env("LOG_LEVEL", "INFO"),
}

# ============================================
# 1. Page Config - 必須是第一個 Streamlit 命令
# ============================================
st.set_page_config(
    page_title=APP_CONFIG["title"],
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================
# 2. Logging Configuration
# ============================================

logging.basicConfig(
    level=getattr(logging, APP_CONFIG["log_level"].upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"啟動應用程式: {APP_CONFIG['title']} {APP_CONFIG['version']}")

# ============================================
# 3. Load CSS
# ============================================


def load_css(filename: str) -> None:
    """載入外部 CSS 檔案。"""
    try:
        with open(filename, encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
        logger.info(f"成功載入 CSS: {filename}")
    except FileNotFoundError:
        logger.warning(f"CSS 檔案不存在: {filename}")
    except Exception as e:
        logger.error(f"載入 CSS 時發生錯誤: {e}", exc_info=True)
        st.warning(f"載入 CSS 時發生錯誤: {e}")


css_path = os.path.join("assets", "style.css")
load_css(css_path)

# ============================================
# 4. Database Health Check (Optional)
# ============================================

# ✅ 可選：在啟動時檢查資料庫連線
# 注意：Service 架構中，每個 Service 內部會自行管理連線
from services.base_db import BaseDBService  # noqa: E402


@st.cache_resource
def check_database_health() -> bool:
    """檢查資料庫連線健康狀態"""
    try:
        db_service = BaseDBService()
        with db_service.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            if result and result[0] == 1:
                logger.info("✅ 資料庫連線健康檢查通過")
                return True
            else:
                logger.error("❌ 資料庫健康檢查失敗：查詢結果異常")
                return False
    
    except Exception as e:
        logger.error(f"❌ 資料庫健康檢查失敗: {e}", exc_info=True)
        return False


# ============================================
# 5. Main Function
# ============================================


def main() -> None:
    """主程式進入點"""
    
    # ✅ 可選：啟動時檢查資料庫連線
    try:
        db_healthy = check_database_health()
        
        if not db_healthy:
            st.error("⚠️ 資料庫連線異常，某些功能可能無法使用")
            st.info("💡 請確認 Streamlit Secrets 中已正確設定 SUPABASE_URL 和 SUPABASE_KEY")
            
            if APP_CONFIG["environment"] == "development":
                if st.button("🔄 重新檢查"):
                    st.cache_resource.clear()
                    st.rerun()
    
    except Exception as e:
        logger.error(f"資料庫健康檢查異常: {e}", exc_info=True)

    # ============ 側邊欄 ============
    with st.sidebar:
        st.title(f"🏠 {APP_CONFIG['title']}")
        st.caption(f"Nordic Edition {APP_CONFIG['version']} · {APP_CONFIG['environment']}")
        
        st.divider()

        menu = st.radio(
            "功能選單",
            [
                "📊 儀表板",
                "👥 房客管理",
                "💰 租金管理",
                "📋 繳費追蹤",
                "⚡ 電費管理",
                "💸 支出記錄",
                "📬 通知管理",
                "⚙️ 系統設定",
            ],
            label_visibility="collapsed",
        )
        
        # 系統狀態指示器
        with st.expander("🔧 系統狀態", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                # 資料庫狀態
                try:
                    if check_database_health():
                        st.success("✅ 資料庫", icon="🗄️")
                    else:
                        st.error("❌ 資料庫", icon="🗄️")
                except:
                    st.error("❌ 資料庫", icon="🗄️")
            
            with col2:
                # 環境資訊
                env_icon = "🚀" if APP_CONFIG["environment"] == "production" else "🔧"
                st.info(f"{env_icon} {APP_CONFIG['environment']}")
            
            # 版本資訊
            st.caption(f"Version: {APP_CONFIG['version']}")
            st.caption(f"Architecture: Service Layer")

    # ============ 動態載入 Views (無 db 參數) ============
    
    # ✅ 修正：頁面模組映射（對應實際檔案名稱）
    PAGE_MODULES = {
        "📊 儀表板": "dashboard",
        "👥 房客管理": "tenants",        # ✅ 修正為 tenants
        "💰 租金管理": "rent",           # ✅ 修正為 rent
        "📋 繳費追蹤": "tracking",
        "⚡ 電費管理": "electricity",
        "💸 支出記錄": "expenses",
        "📬 通知管理": "notifications",
        "⚙️ 系統設定": "settings",
    }
    
    page_module = PAGE_MODULES.get(menu)
    
    if not page_module:
        st.error(f"❌ 未知的頁面: {menu}")
        logger.error(f"未知的頁面選擇: {menu}")
        return
    
    try:
        # ✅ 動態載入模組
        import importlib
        module = importlib.import_module(f"views.{page_module}")
        
        logger.info(f"載入頁面模組: {page_module}")
        
        # ✅ 呼叫 render() 或 show() 函數（不傳入任何參數）
        if hasattr(module, 'render'):
            module.render()
        elif hasattr(module, 'show'):
            module.show()
        else:
            st.error(f"❌ 模組 {page_module} 缺少 render() 或 show() 函數")
            logger.error(f"模組 {page_module} 缺少入口函數")
            
    except ImportError as e:
        st.error(f"❌ 無法載入頁面模組: {page_module}")
        st.info("💡 請確認 views/ 目錄下對應的模組檔案存在")
        logger.error(f"載入模組失敗: {page_module} - {e}", exc_info=True)
        
        if APP_CONFIG["environment"] == "development":
            st.exception(e)
            
    except Exception as e:
        st.error(f"❌ 載入頁面時發生錯誤: {e}")
        logger.error(f"頁面渲染失敗: {page_module} - {e}", exc_info=True)
        
        if APP_CONFIG["environment"] == "development":
            st.exception(e)
        else:
            st.info("💡 系統發生錯誤，請聯繫管理員或稍後再試")


# ============================================
# 6. Entry Point
# ============================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"應用程式啟動失敗: {e}", exc_info=True)
        st.error(f"❌ 系統啟動失敗: {e}")
        
        if APP_CONFIG.get("environment") == "development":
            st.exception(e)
