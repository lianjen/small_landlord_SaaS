"""
幸福之家 Pro - 租賃管理系統
Nordic Edition v15.0 (Service Architecture + Auth Gatekeeper + Session Refresh)
✅ 完全移除 db 依賴
✅ 使用 Service 架構
✅ 動態載入頁面模組
✅ Supabase Auth 認證系統
✅ 登入守門員機制
✅ Session 自動刷新
✅ 角色權限管理
✅ 完整錯誤處理
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

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
    "version": get_env("APP_VERSION", "v15.0"),  # ✅ 版本號升級
    "environment": get_env("ENVIRONMENT", "production"),
    "log_level": get_env("LOG_LEVEL", "INFO"),
    "dev_mode": get_env("DEV_MODE", "false").lower() == "true",
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
# 4. Session Manager & Auth Service Import
# ============================================

try:
    from utils.session_manager import session_manager  # ✅ 修正路径
    from services.auth_service import AuthService
    logger.info("✅ Session Manager 和 Auth Service 載入成功")
except ImportError as e:
    logger.error(f"❌ 無法載入 Session Manager 或 Auth Service: {e}")
    st.error(f"❌ 系統模組載入失敗: {e}")
    st.info("請確認 utils/session_manager.py 和 services/auth_service.py 已建立")
    st.stop()

# ============================================
# 5. Database Health Check
# ============================================

from services.base_db import BaseDBService  # noqa: E402


@st.cache_resource(ttl=300)  # 快取 5 分鐘
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
# 6. Session Refresh Handler
# ============================================


def handle_session_refresh() -> bool:
    """
    處理 Session 自動刷新
    
    Returns:
        bool: True=Session 有效, False=需要重新登入
    """
    try:
        # 檢查是否需要刷新
        if not session_manager.check_session_timeout():
            return True  # Session 未過期
        
        # 嘗試刷新 Session
        auth_service = AuthService()
        refresh_token = st.session_state.get("refresh_token")
        
        if not refresh_token:
            logger.warning("⚠️ 無 Refresh Token，需要重新登入")
            return False
        
        # 呼叫刷新 API
        new_session = auth_service.refresh_session(refresh_token)
        
        if new_session:
            # 更新 Session State
            st.session_state["access_token"] = new_session["access_token"]
            st.session_state["refresh_token"] = new_session["refresh_token"]
            st.session_state["expires_at"] = new_session.get("expires_at")
            st.session_state["last_activity"] = datetime.now()
            
            logger.info("✅ Session 已自動刷新")
            return True
        else:
            logger.warning("⚠️ Session 刷新失敗，需要重新登入")
            return False
    
    except Exception as e:
        logger.error(f"❌ Session 刷新異常: {e}", exc_info=True)
        return False


# ============================================
# 7. Permission Check
# ============================================


def check_page_permission(page_name: str) -> bool:
    """
    檢查當前用戶是否有權限訪問指定頁面
    
    Args:
        page_name: 頁面名稱
    
    Returns:
        bool: True=有權限, False=無權限
    """
    user_role = session_manager.get_user_role()
    
    # Admin 全權限
    if user_role == "admin":
        return True
    
    # User 限制頁面
    restricted_pages = ["用戶管理", "系統設定"]
    
    for restricted in restricted_pages:
        if restricted in page_name:
            logger.warning(f"⚠️ 用戶 {session_manager.get_user_email()} 嘗試訪問受限頁面: {page_name}")
            return False
    
    return True


# ============================================
# 8. Main Function (Gatekeeper Pattern)
# ============================================


def main() -> None:
    """主程式進入點 - 含登入守門員邏輯"""
    
    # ✅ 初始化 Session State
    session_manager.init()
    
    # ✅ 守門員：未登入 → 顯示登入頁
    if not session_manager.is_authenticated():
        render_login_page()
        return  # 🔴 重點：阻止繼續執行
    
    # ✅ 已登入：處理 Session 刷新
    if not handle_session_refresh():
        # Session 刷新失敗，強制登出
        st.warning("⏱️ 您的登入已過期，請重新登入")
        session_manager.logout()
        st.rerun()
        return
    
    # ✅ Session 有效：顯示主應用
    render_main_app()


# ============================================
# 9. Login Page Renderer
# ============================================


def render_login_page() -> None:
    """渲染登入頁面"""
    try:
        from views.login_view import render as render_login
        render_login()
    except ImportError as e:
        logger.error(f"❌ 無法載入登入頁面模組: {e}", exc_info=True)
        st.error("❌ 無法載入登入頁面模組 (views/login_view.py)")
        st.info("請確認 views/login_view.py 檔案已建立")
        
        if APP_CONFIG["dev_mode"]:
            st.exception(e)
    
    except Exception as e:
        logger.error(f"❌ 登入頁面渲染失敗: {e}", exc_info=True)
        st.error(f"❌ 登入頁面載入失敗: {e}")
        
        if APP_CONFIG["dev_mode"]:
            st.exception(e)


# ============================================
# 10. Main App Renderer
# ============================================


def render_main_app() -> None:
    """主應用 UI（已登入狀態）"""
    
    # ✅ 啟動時檢查資料庫連線
    db_healthy = False
    try:
        db_healthy = check_database_health()
        
        if not db_healthy:
            st.warning("⚠️ 資料庫連線異常，某些功能可能無法使用")
            
            if APP_CONFIG["dev_mode"]:
                if st.button("🔄 重新檢查連線"):
                    st.cache_resource.clear()
                    st.rerun()
    
    except Exception as e:
        logger.error(f"資料庫健康檢查異常: {e}", exc_info=True)

    # ============ 側邊欄 ============
    render_sidebar(db_healthy)
    
    # ============ 主內容區 ============
    render_main_content()


def render_sidebar(db_healthy: bool) -> None:
    """渲染側邊欄"""
    with st.sidebar:
        st.title(f"🏠 {APP_CONFIG['title']}")
        st.caption(f"Nordic Edition {APP_CONFIG['version']}")
        
        if APP_CONFIG["dev_mode"]:
            st.caption("🔧 開發模式")
        
        st.divider()
        
        # ✅ 用戶資訊卡片
        render_user_card()
        
        st.divider()

        # ✅ 功能選單
        menu = render_menu()
        
        # 儲存到 session_state
        st.session_state["current_menu"] = menu
        
        # ✅ 系統狀態指示器
        render_system_status(db_healthy)


def render_user_card() -> None:
    """渲染用戶資訊卡片"""
    with st.container(border=True):
        user_name = session_manager.get_user_name()
        user_email = session_manager.get_user_email()
        user_role = session_manager.get_user_role()
        
        st.markdown(f"**👤 {user_name}**")
        st.caption(f"📧 {user_email}")
        
        # 角色標籤
        if user_role == "admin":
            st.caption("🏷️ 角色: 👨‍💼 管理員")
        else:
            st.caption("🏷️ 角色: 👤 用戶")
        
        # Session 有效期
        expires_at = st.session_state.get("expires_at")
        if expires_at:
            try:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                
                remaining = expires_at - datetime.now()
                if remaining.total_seconds() > 0:
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    st.caption(f"⏱️ Session: {hours}h {minutes}m")
            except:
                pass
        
        st.divider()
        
        # 登出按鈕
        if st.button("🚪 登出", use_container_width=True, type="secondary"):
            handle_logout()


def handle_logout() -> None:
    """處理登出流程"""
    try:
        # 呼叫 Supabase 登出
        auth_service = AuthService()
        auth_service.logout()
        logger.info(f"✅ 用戶 {session_manager.get_user_email()} 已登出")
    except Exception as e:
        logger.error(f"Supabase 登出失敗: {e}")
        # 即使 Supabase 登出失敗，也要清除本地 Session
    
    # 清除本地 Session
    session_manager.logout()
    st.success("✅ 已登出")
    st.rerun()


def render_menu() -> str:
    """渲染功能選單"""
    user_role = session_manager.get_user_role()
    
    # ✅ 基礎功能（所有用戶）
    menu_items = [
        "📊 儀表板",
        "🏢 物件管理",
        "🚪 房間管理",
        "👥 房客管理",
        "💰 租金管理",
        "📋 繳費追蹤",
        "⚡ 電費管理",
        "💸 支出記錄",
        "📱 LINE 綁定",
        "📬 通知管理",
    ]
    
    # ✅ Admin 專屬功能
    if user_role == "admin":
        menu_items.extend([
            "⚙️ 系統設定",
            "👨‍💼 用戶管理",
        ])
    
    # 取得當前選擇（從 session_state 恢復）
    current_menu = st.session_state.get("current_menu", menu_items[0])
    
    # 確保當前選擇在列表中
    if current_menu not in menu_items:
        current_menu = menu_items[0]
    
    menu = st.radio(
        "功能選單",
        menu_items,
        index=menu_items.index(current_menu),
        label_visibility="collapsed",
    )
    
    return menu


def render_system_status(db_healthy: bool) -> None:
    """渲染系統狀態"""
    with st.expander("🔧 系統狀態", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # 資料庫狀態
            if db_healthy:
                st.success("✅ 資料庫", icon="🗄️")
            else:
                st.error("❌ 資料庫", icon="🗄️")
        
        with col2:
            # 環境資訊
            env = APP_CONFIG["environment"]
            env_icon = "🚀" if env == "production" else "🔧"
            st.info(f"{env_icon} {env.capitalize()}")
        
        # 版本資訊
        st.caption(f"Version: {APP_CONFIG['version']}")
        st.caption(f"Architecture: Service + Auth")
        
        # ✅ LINE 功能狀態
        line_token = get_env("LINE_CHANNEL_ACCESS_TOKEN")
        if line_token:
            st.success("✅ LINE Bot", icon="📱")
        else:
            st.warning("⚠️ LINE Bot", icon="📱")
        
        # ✅ 當前用戶
        st.caption(f"👤 {session_manager.get_user_email()}")
        
        # ✅ 開發模式工具
        if APP_CONFIG["dev_mode"]:
            st.divider()
            st.caption("🔧 開發工具")
            
            if st.button("🔄 清除快取", use_container_width=True):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("✅ 快取已清除")
                st.rerun()


def render_main_content() -> None:
    """渲染主內容區域"""
    menu = st.session_state.get("current_menu", "📊 儀表板")
    
    # ✅ 權限檢查
    if not check_page_permission(menu):
        st.error("❌ 您沒有權限訪問此頁面")
        st.info("💡 請聯繫管理員開通權限")
        logger.warning(f"權限拒絕: {session_manager.get_user_email()} 嘗試訪問 {menu}")
        return
    
    # ✅ 頁面模組映射
    PAGE_MODULES = {
        "📊 儀表板": "dashboard",
        "🏢 物件管理": "properties",
        "🚪 房間管理": "rooms",
        "👥 房客管理": "tenants",
        "💰 租金管理": "rent",
        "📋 繳費追蹤": "tracking",
        "⚡ 電費管理": "electricity",
        "💸 支出記錄": "expenses",
        "📱 LINE 綁定": "line_binding",
        "📬 通知管理": "notifications",
        "⚙️ 系統設定": "settings",
        "👨‍💼 用戶管理": "user_management",
    }
    
    page_module = PAGE_MODULES.get(menu)
    
    if not page_module:
        st.error(f"❌ 未知的頁面: {menu}")
        logger.error(f"未知的頁面選擇: {menu}")
        return
    
    # ✅ 動態載入模組
    load_page_module(page_module, menu)


def load_page_module(page_module: str, menu_name: str) -> None:
    """
    動態載入頁面模組
    
    Args:
        page_module: 模組名稱
        menu_name: 選單名稱
    """
    try:
        # 動態 import
        import importlib
        module = importlib.import_module(f"views.{page_module}")
        
        logger.info(
            f"載入頁面: {page_module} "
            f"(用戶: {session_manager.get_user_email()}, "
            f"角色: {session_manager.get_user_role()})"
        )
        
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
        
        if APP_CONFIG["dev_mode"]:
            st.exception(e)
        
        # 提供返回按鈕
        if st.button("🔙 返回儀表板"):
            st.session_state["current_menu"] = "📊 儀表板"
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ 載入頁面時發生錯誤")
        logger.error(f"頁面渲染失敗: {page_module} - {e}", exc_info=True)
        
        if APP_CONFIG["dev_mode"]:
            st.error(f"錯誤詳情: {e}")
            st.exception(e)
        else:
            st.info("💡 系統發生錯誤，請聯繫管理員或稍後再試")
        
        # 提供返回按鈕
        if st.button("🔙 返回儀表板"):
            st.session_state["current_menu"] = "📊 儀表板"
            st.rerun()


# ============================================
# 11. Entry Point
# ============================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"應用程式啟動失敗: {e}", exc_info=True)
        st.error(f"❌ 系統啟動失敗")
        
        if APP_CONFIG["dev_mode"]:
            st.error(f"錯誤詳情: {e}")
            st.exception(e)
        else:
            st.info("💡 系統發生嚴重錯誤，請聯繫管理員")
        
        # 緊急登出
        if st.button("🔄 重新啟動"):
            session_manager.logout()
            st.rerun()
