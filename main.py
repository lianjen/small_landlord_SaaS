"""
幸福之家 Pro - 租賃管理系統
Nordic Edition v14.5 (Service Architecture + Auth Gatekeeper)
✅ 完全移除 db 依賴
✅ 使用 Service 架構
✅ 動態載入頁面模組
✅ 新增 Supabase Auth 認證系統
✅ 登入守門員機制
✅ Session 管理與自動刷新
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


# 驗證必要環境變數（支援兩種命名方式）
def get_supabase_url():
    return get_env("SUPABASE_URL") or get_env("url")

def get_supabase_key():
    return get_env("SUPABASE_KEY") or get_env("key")

SUPABASE_URL = get_supabase_url()
SUPABASE_KEY = get_supabase_key()

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ 缺少必要環境變數: SUPABASE_URL 或 SUPABASE_KEY")
    st.info("請在 .streamlit/secrets.toml 中設定 [supabase] 區塊")
    st.code("""
[supabase]
url = "https://xxxxx.supabase.co"
key = "eyJhbGciOi..."
    """)
    st.stop()

# 讀取全域配置（允許從 env / secrets 覆蓋預設值）
APP_CONFIG = {
    "title": get_env("APP_TITLE", "幸福之家 Pro"),
    "version": get_env("APP_VERSION", "v14.5"),  # ✅ 版本號升級
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


css_path = os.path.join("assets", "style.css")
load_css(css_path)

# ============================================
# 4. Session Manager Import
# ============================================

try:
    from services.session_manager import SessionManager
    from services.auth_service import AuthService
    logger.info("✅ Session Manager 和 Auth Service 載入成功")
except ImportError as e:
    logger.error(f"❌ 無法載入 Session Manager 或 Auth Service: {e}")
    st.error(f"❌ 系統模組載入失敗: {e}")
    st.info("請確認 services/session_manager.py 和 services/auth_service.py 已建立")
    st.stop()

# ============================================
# 5. Database Health Check (Optional)
# ============================================

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
# 6. Main Function (Gatekeeper Pattern)
# ============================================


def main() -> None:
    """主程式進入點 - 含登入守門員邏輯"""
    
    # ✅ 初始化 Session State
    SessionManager.init()
    
    # ✅ 檢查 Session 是否過期並自動刷新
    if SessionManager.check_session_timeout():
        try:
            auth_service = AuthService()
            refresh_token = st.session_state.get(SessionManager.REFRESH_TOKEN)
            
            if refresh_token:
                new_session = auth_service.refresh_session(refresh_token)
                if new_session:
                    # 更新 Token
                    st.session_state[SessionManager.ACCESS_TOKEN] = new_session["access_token"]
                    st.session_state[SessionManager.REFRESH_TOKEN] = new_session["refresh_token"]
                    st.session_state[SessionManager.EXPIRES_AT] = new_session.get("expires_at")
                    logger.info("✅ Session 已自動刷新")
                else:
                    # 刷新失敗，強制登出
                    st.warning("⏱️ 您的登入已過期，請重新登入")
                    SessionManager.logout()
                    st.rerun()
        except Exception as e:
            logger.error(f"Session 刷新失敗: {e}")
            SessionManager.logout()
            st.rerun()
    
    # ✅ 守門員：未登入 → 顯示登入頁
    if not SessionManager.is_authenticated():
        try:
            from views.login_view import render as render_login
            render_login()
        except ImportError:
            st.error("❌ 無法載入登入頁面模組 (views/login_view.py)")
            st.info("請確認 views/login_view.py 檔案已建立")
        return  # 🔴 重點：阻止繼續執行
    
    # ✅ 已登入：顯示主應用
    render_main_app()


def render_main_app() -> None:
    """主應用 UI（已登入狀態）"""
    
    # ✅ 可選：啟動時檢查資料庫連線
    try:
        db_healthy = check_database_health()
        
        if not db_healthy:
            st.warning("⚠️ 資料庫連線異常，某些功能可能無法使用")
            
            if APP_CONFIG["environment"] == "development":
                if st.button("🔄 重新檢查連線"):
                    st.cache_resource.clear()
                    st.rerun()
    
    except Exception as e:
        logger.error(f"資料庫健康檢查異常: {e}", exc_info=True)

    # ============ 側邊欄 ============
    with st.sidebar:
        st.title(f"🏠 {APP_CONFIG['title']}")
        st.caption(f"Nordic Edition {APP_CONFIG['version']} · {APP_CONFIG['environment']}")
        
        st.divider()
        
        # ✅ 用戶資訊卡片
        with st.container(border=True):
            st.markdown(f"**👤 {SessionManager.get_user_name()}**")
            st.caption(f"📧 {SessionManager.get_user_email()}")
            st.caption(f"🏷️ 角色: {SessionManager.get_user_role().upper()}")
            
            # 登出按鈕
            if st.button("🚪 登出", use_container_width=True, type="secondary"):
                try:
                    auth_service = AuthService()
                    auth_service.logout()
                except:
                    pass  # 即使 Supabase 登出失敗，也清除本地 Session
                
                SessionManager.logout()
                st.success("✅ 已登出")
                st.rerun()
        
        st.divider()

        # ✅ 功能選單（根據角色動態顯示）
        menu_items = [
            "📊 儀表板",
            "👥 房客管理",
            "💰 租金管理",
            "📋 繳費追蹤",
            "⚡ 電費管理",
            "💸 支出記錄",
            "📱 LINE 綁定",
            "📬 通知管理",
            "⚙️ 系統設定",
        ]
        
        # Admin 專屬功能（未來擴充）
        if SessionManager.get_user_role() == "admin":
            menu_items.append("👨‍💼 用戶管理")
        
        menu = st.radio(
            "功能選單",
            menu_items,
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
            st.caption(f"Architecture: Service + Auth")
            
            # ✅ 顯示 LINE 功能狀態
            line_token = get_env("LINE_CHANNEL_ACCESS_TOKEN")
            if line_token:
                st.success("✅ LINE Bot", icon="📱")
            else:
                st.warning("⚠️ LINE Bot", icon="📱")
            
            # ✅ 顯示當前登入用戶
            st.caption(f"👤 {SessionManager.get_user_email()}")

    # ============ 動態載入 Views ============
    
    PAGE_MODULES = {
        "📊 儀表板": "dashboard",
        "👥 房客管理": "tenants",
        "💰 租金管理": "rent",
        "📋 繳費追蹤": "tracking",
        "⚡ 電費管理": "electricity",
        "💸 支出記錄": "expenses",
        "📱 LINE 綁定": "line_binding",
        "📬 通知管理": "notifications",
        "⚙️ 系統設定": "settings",
        "👨‍💼 用戶管理": "user_management",  # Admin only
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
        
        logger.info(f"載入頁面模組: {page_module} (用戶: {SessionManager.get_user_email()})")
        
        # ✅ 呼叫 render() 或 show() 函數
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
# 7. Entry Point
# ============================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"應用程式啟動失敗: {e}", exc_info=True)
        st.error(f"❌ 系統啟動失敗: {e}")
        
        if APP_CONFIG.get("environment") == "development":
            st.exception(e)
