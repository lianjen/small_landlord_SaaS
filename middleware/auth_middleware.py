"""
認證中間件 - v1.0
✅ 全域認證檢查
✅ Session 自動刷新
✅ 權限驗證
✅ 登入/登出 UI
"""
import streamlit as st
from typing import Optional, Callable
import logging
from functools import wraps

from services.auth_service import AuthService
from utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """認證中間件"""
    
    def __init__(self):
        """初始化中間件"""
        self.auth_service = AuthService()
        self.session_manager = SessionManager()
    
    # ==================== 認證裝飾器 ====================
    
    def require_auth(self, func: Callable) -> Callable:
        """
        認證裝飾器：要求用戶必須登入
        
        使用方式：
            @auth_middleware.require_auth
            def my_protected_page():
                st.write("只有登入用戶能看到")
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.is_authenticated():
                self.show_login_page()
                return None
            
            # 自動刷新 Token
            self.refresh_token_if_needed()
            
            return func(*args, **kwargs)
        
        return wrapper
    
    def require_role(self, required_role: str):
        """
        角色權限裝飾器
        
        使用方式：
            @auth_middleware.require_role("admin")
            def admin_page():
                st.write("只有管理員能看到")
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.is_authenticated():
                    self.show_login_page()
                    return None
                
                user = self.get_current_user()
                if not user or user.get("role") != required_role:
                    st.error(f"❌ 權限不足：需要 {required_role} 權限")
                    st.stop()
                
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    # ==================== 認證檢查 ====================
    
    def is_authenticated(self) -> bool:
        """
        檢查用戶是否已登入
        
        Returns:
            bool: True=已登入, False=未登入
        """
        user = self.session_manager.get_user()
        
        if not user:
            return False
        
        # 檢查 Token 是否有效
        access_token = user.get("access_token")
        if not access_token:
            return False
        
        # 驗證 Token
        verified_user = self.auth_service.verify_token(access_token)
        if not verified_user:
            # Token 無效，清除 Session
            self.session_manager.clear()
            return False
        
        return True
    
    def get_current_user(self) -> Optional[dict]:
        """
        取得當前登入的用戶資料
        
        Returns:
            用戶資料 or None
        """
        return self.session_manager.get_user()
    
    def get_user_id(self) -> Optional[str]:
        """
        取得當前用戶 ID
        
        Returns:
            user_id or None
        """
        user = self.get_current_user()
        return user.get("id") if user else None
    
    # ==================== Token 刷新 ====================
    
    def refresh_token_if_needed(self) -> bool:
        """
        檢查並刷新 Token（如果需要）
        
        Returns:
            bool: True=刷新成功或不需要刷新, False=刷新失敗
        """
        user = self.session_manager.get_user()
        
        if not user:
            return False
        
        # 使用 AuthService 的自動刷新功能
        updated_user = self.auth_service.check_and_refresh_token(user)
        
        if updated_user and updated_user != user:
            # Token 已刷新，更新 Session
            self.session_manager.set_user(updated_user)
            logger.info("✅ Token 已自動刷新")
            return True
        
        return True  # 不需要刷新
    
    # ==================== 登入/登出 UI ====================
    
    def show_login_page(self):
        """顯示登入頁面"""
        st.title("🔐 用戶登入")
        
        # 使用 tabs 切換登入/註冊
        tab1, tab2 = st.tabs(["登入", "註冊"])
        
        with tab1:
            self._render_login_form()
        
        with tab2:
            self._render_register_form()
    
    def _render_login_form(self):
        """渲染登入表單"""
        st.markdown("### 登入到您的帳戶")
        
        with st.form("login_form"):
            email = st.text_input(
                "Email",
                placeholder="your@email.com",
                key="login_email"
            )
            
            password = st.text_input(
                "密碼",
                type="password",
                placeholder="••••••",
                key="login_password"
            )
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                submit = st.form_submit_button("🔓 登入", use_container_width=True, type="primary")
            
            with col2:
                forgot = st.form_submit_button("忘記密碼？", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("❌ 請輸入 Email 和密碼")
                    return
                
                with st.spinner("登入中..."):
                    success, message, user_data = self.auth_service.login(email, password)
                
                if success and user_data:
                    # 儲存到 Session
                    self.session_manager.set_user(user_data)
                    st.success(f"✅ {message}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
            
            if forgot:
                self._show_forgot_password_dialog(email)
    
    def _render_register_form(self):
        """渲染註冊表單"""
        st.markdown("### 建立新帳戶")
        
        with st.form("register_form"):
            name = st.text_input(
                "姓名",
                placeholder="例如: 王小明",
                key="register_name"
            )
            
            email = st.text_input(
                "Email",
                placeholder="your@email.com",
                key="register_email"
            )
            
            password = st.text_input(
                "密碼",
                type="password",
                placeholder="至少 6 個字元",
                key="register_password"
            )
            
            password_confirm = st.text_input(
                "確認密碼",
                type="password",
                placeholder="再次輸入密碼",
                key="register_password_confirm"
            )
            
            role = st.selectbox(
                "身份",
                ["landlord", "tenant"],
                format_func=lambda x: "房東" if x == "landlord" else "房客",
                key="register_role"
            )
            
            submit = st.form_submit_button("📝 註冊", use_container_width=True, type="primary")
            
            if submit:
                # 驗證
                if not name or not email or not password:
                    st.error("❌ 請填寫完整資訊")
                    return
                
                if password != password_confirm:
                    st.error("❌ 兩次密碼輸入不一致")
                    return
                
                with st.spinner("註冊中..."):
                    success, message = self.auth_service.register(
                        email=email,
                        password=password,
                        name=name,
                        role=role
                    )
                
                if success:
                    st.success(f"✅ {message}")
                    st.info("💡 請切換到「登入」分頁進行登入")
                else:
                    st.error(f"❌ {message}")
    
    def _show_forgot_password_dialog(self, email: str):
        """顯示忘記密碼對話框"""
        with st.expander("🔑 重設密碼", expanded=True):
            st.write("我們會發送重設密碼的連結到您的 Email")
            
            reset_email = st.text_input(
                "Email",
                value=email,
                key="reset_email"
            )
            
            if st.button("發送重設連結", key="send_reset"):
                if not reset_email:
                    st.error("❌ 請輸入 Email")
                    return
                
                success, message = self.auth_service.reset_password_request(reset_email)
                
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
    
    def show_logout_button(self, location: str = "sidebar"):
        """
        顯示登出按鈕
        
        Args:
            location: 'sidebar' or 'main'
        """
        user = self.get_current_user()
        
        if not user:
            return
        
        container = st.sidebar if location == "sidebar" else st
        
        with container:
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"👤 {user.get('name', 'User')}")
                st.caption(f"📧 {user.get('email', '')}")
            
            with col2:
                if st.button("🚪", key="logout_btn", help="登出"):
                    success, message = self.auth_service.logout()
                    
                    if success:
                        self.session_manager.clear()
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
    
    # ==================== 開發模式 ====================
    
    def bypass_auth_for_dev(self):
        """
        開發模式：繞過認證（僅用於測試）
        
        警告：正式環境必須關閉此功能！
        """
        if st.secrets.get("dev_mode", False):
            logger.warning("⚠️ 開發模式：已繞過認證")
            
            # 建立假的用戶 Session
            fake_user = {
                "id": "dev-user-id",
                "email": "dev@example.com",
                "name": "開發測試用戶",
                "role": "landlord"
            }
            
            self.session_manager.set_user(fake_user)
            return True
        
        return False


# ============================================
# 全域中間件實例
# ============================================
auth_middleware = AuthMiddleware()


# ============================================
# 測試程式碼
# ============================================
if __name__ == "__main__":
    print("✅ AuthMiddleware 模組載入成功")
    
    # 測試裝飾器
    @auth_middleware.require_auth
    def protected_function():
        return "這是受保護的內容"
    
    print("✅ 裝飾器測試通過")
