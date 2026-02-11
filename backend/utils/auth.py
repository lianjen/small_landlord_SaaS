"""
權限管理系統 - 認證與授權
"""

import streamlit as st
import hashlib
import secrets
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ============== 會話管理 ==============

def init_session_state():
    """初始化 Session State"""
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'user_name' not in st.session_state:
        st.session_state.user_name = None
    if 'session_token' not in st.session_state:
        st.session_state.session_token = None
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False


def is_authenticated() -> bool:
    """檢查是否已登入"""
    return st.session_state.get('is_authenticated', False)


def get_current_user():
    """取得當前使用者資訊"""
    if not is_authenticated():
        return None
    
    return {
        'email': st.session_state.user_email,
        'role': st.session_state.user_role,
        'name': st.session_state.user_name
    }


def logout():
    """登出"""
    # 清除 Session Token
    if st.session_state.session_token:
        try:
            # TODO: 從資料庫刪除 session
            pass
        except Exception as e:
            logger.error(f"登出時清除 session 失敗: {e}")
    
    # 清除 Session State
    st.session_state.user_email = None
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.session_token = None
    st.session_state.is_authenticated = False


# ============== 簡易密碼驗證 (Streamlit 版) ==============

def simple_login(db, email: str, password: str) -> tuple:
    """
    簡易登入驗證
    
    注意: 這是簡化版本,生產環境建議使用 Supabase Auth
    
    Args:
        db: 資料庫實例
        email: Email
        password: 密碼（明文）
    
    Returns:
        (成功與否, 錯誤訊息, 使用者資訊)
    """
    try:
        with db._get_connection() as conn:
            cur = conn.cursor()
            
            # 查詢使用者
            cur.execute("""
                SELECT email, role, display_name, is_active
                FROM user_roles
                WHERE email = %s AND is_active = TRUE
            """, (email,))
            
            user = cur.fetchone()
            
            if not user:
                return (False, "使用者不存在或已停用", None)
            
            # ⚠️ 簡化版本：僅檢查 email 存在
            # 生產環境應該使用 Supabase Auth 或加密密碼驗證
            
            user_email, role, display_name, is_active = user
            
            # 建立 Session Token
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=24)
            
            # 儲存 Session
            cur.execute("""
                INSERT INTO user_sessions 
                (user_email, session_token, expires_at, ip_address)
                VALUES (%s, %s, %s, %s)
            """, (user_email, session_token, expires_at, 'streamlit'))
            
            # 更新 Session State
            st.session_state.user_email = user_email
            st.session_state.user_role = role
            st.session_state.user_name = display_name
            st.session_state.session_token = session_token
            st.session_state.is_authenticated = True
            
            # 記錄登入日誌
            log_action(db, user_email, 'login', 'auth', None, {'success': True})
            
            return (True, "登入成功", {
                'email': user_email,
                'role': role,
                'name': display_name
            })
    
    except Exception as e:
        logger.error(f"登入失敗: {e}")
        return (False, f"登入失敗: {str(e)}", None)


# ============== 權限檢查 ==============

def check_permission(db, module: str, action: str) -> bool:
    """
    檢查當前使用者是否有權限
    
    Args:
        db: 資料庫實例
        module: 模組名稱 (tenants, rent, electricity 等)
        action: 動作 (view, create, edit, delete)
    
    Returns:
        是否有權限
    """
    if not is_authenticated():
        return False
    
    user_email = st.session_state.user_email
    
    try:
        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT check_permission(%s, %s, %s)
            """, (user_email, module, action))
            
            result = cur.fetchone()
            return result[0] if result else False
    
    except Exception as e:
        logger.error(f"權限檢查失敗: {e}")
        return False


def require_permission(db, module: str, action: str):
    """
    裝飾器：要求特定權限
    
    使用方式:
    @require_permission(db, 'tenants', 'delete')
    def delete_tenant():
        ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not check_permission(db, module, action):
                st.error(f"❌ 您沒有權限執行此操作 ({module} - {action})")
                st.info("💡 請聯繫管理員取得權限")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_user_permissions(db, email: str = None) -> dict:
    """
    取得使用者所有權限
    
    Args:
        db: 資料庫實例
        email: 使用者 email (None 表示當前使用者)
    
    Returns:
        權限字典
    """
    if email is None:
        if not is_authenticated():
            return {}
        email = st.session_state.user_email
    
    try:
        with db._get_connection() as conn:
            cur = conn.cursor()
            
            # 取得角色
            cur.execute("""
                SELECT role FROM user_roles
                WHERE email = %s AND is_active = TRUE
            """, (email,))
            
            role_row = cur.fetchone()
            if not role_row:
                return {}
            
            role = role_row[0]
            
            # 取得權限
            cur.execute("""
                SELECT module, can_view, can_create, can_edit, can_delete
                FROM role_permissions
                WHERE role = %s
            """, (role,))
            
            permissions = {}
            for row in cur.fetchall():
                module, can_view, can_create, can_edit, can_delete = row
                permissions[module] = {
                    'view': can_view,
                    'create': can_create,
                    'edit': can_edit,
                    'delete': can_delete
                }
            
            return permissions
    
    except Exception as e:
        logger.error(f"取得權限失敗: {e}")
        return {}


# ============== 操作日誌 ==============

def log_action(db, user_email: str, action: str, module: str, 
               resource_id: int = None, details: dict = None):
    """
    記錄操作日誌
    
    Args:
        db: 資料庫實例
        user_email: 使用者 email
        action: 動作 (create, update, delete, view)
        module: 模組名稱
        resource_id: 資源 ID
        details: 詳細資訊
    """
    try:
        with db._get_connection() as conn:
            cur = conn.cursor()
            
            import json
            details_json = json.dumps(details) if details else None
            
            cur.execute("""
                INSERT INTO audit_logs 
                (user_email, action, module, resource_id, details, ip_address)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_email, action, module, resource_id, details_json, 'streamlit'))
    
    except Exception as e:
        logger.error(f"記錄日誌失敗: {e}")


# ============== UI 元件 ==============

def show_user_info():
    """在側邊欄顯示使用者資訊"""
    if is_authenticated():
        user = get_current_user()
        
        with st.sidebar:
            st.divider()
            
            role_emoji = {
                'OWNER': '👑',
                'STAFF': '👤',
                'VIEWER': '👁️'
            }
            
            role_text = {
                'OWNER': '擁有者',
                'STAFF': '員工',
                'VIEWER': '訪客'
            }
            
            st.markdown(f"""
            **{role_emoji.get(user['role'], '👤')} {user['name']}**  
            <small>{role_text.get(user['role'], user['role'])}</small>
            """, unsafe_allow_html=True)
            
            if st.button("🚪 登出", key="logout_btn"):
                logout()
                st.rerun()


def render_login_page(db):
    """渲染登入頁面"""
    st.title("🔐 系統登入")
    
    st.info("""
    💡 **測試帳號**
    - Email: owner@example.com
    - 密碼: (任意,簡化版無密碼驗證)
    """)
    
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="user@example.com")
        password = st.text_input("密碼", type="password", placeholder="password")
        
        submitted = st.form_submit_button("登入", type="primary")
        
        if submitted:
            if not email:
                st.error("請輸入 Email")
            else:
                with st.spinner("登入中..."):
                    success, msg, user_info = simple_login(db, email, password)
                    
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    
    st.divider()
    
    st.caption("💡 提示：生產環境建議使用 Supabase Auth 進行完整的身份驗證")


# ============== 權限控制裝飾器 (for Streamlit) ==============

def require_auth(func):
    """
    要求登入的裝飾器
    
    使用方式:
    @require_auth
    def my_page(db):
        ...
    """
    def wrapper(*args, **kwargs):
        init_session_state()
        
        if not is_authenticated():
            st.warning("⚠️ 請先登入")
            render_login_page(args[0] if args else None)
            st.stop()
        
        return func(*args, **kwargs)
    return wrapper
