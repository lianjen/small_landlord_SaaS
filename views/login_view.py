"""
登入頁面視圖 - v2.0
✅ 登入/註冊功能
✅ 忘記密碼
✅ 完整表單驗證
✅ 美觀的 UI 設計
✅ 錯誤處理
✅ 開發模式支援
✅ 測試帳號提示
"""
import streamlit as st
from services.auth_service import AuthService
from services.session_manager import session_manager
import re
from typing import Optional


# ==================== 表單驗證 ====================

def validate_email(email: str) -> tuple[bool, Optional[str]]:
    """
    驗證 Email 格式
    
    Args:
        email: Email 地址
    
    Returns:
        (是否有效, 錯誤訊息)
    """
    if not email:
        return False, "請輸入 Email"
    
    # 簡單的 Email 正則
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, "Email 格式不正確"
    
    return True, None


def validate_password(password: str, min_length: int = 6) -> tuple[bool, Optional[str]]:
    """
    驗證密碼強度
    
    Args:
        password: 密碼
        min_length: 最小長度
    
    Returns:
        (是否有效, 錯誤訊息)
    """
    if not password:
        return False, "請輸入密碼"
    
    if len(password) < min_length:
        return False, f"密碼至少需要 {min_length} 個字元"
    
    return True, None


def validate_name(name: str) -> tuple[bool, Optional[str]]:
    """
    驗證姓名
    
    Args:
        name: 姓名
    
    Returns:
        (是否有效, 錯誤訊息)
    """
    if not name:
        return False, "請輸入姓名"
    
    if len(name.strip()) < 2:
        return False, "姓名至少需要 2 個字元"
    
    return True, None


# ==================== 登入處理 ====================

def handle_login(email: str, password: str):
    """
    處理登入邏輯
    
    Args:
        email: Email
        password: 密碼
    """
    # 驗證輸入
    email_valid, email_error = validate_email(email)
    if not email_valid:
        st.error(f"❌ {email_error}")
        return
    
    password_valid, password_error = validate_password(password)
    if not password_valid:
        st.error(f"❌ {password_error}")
        return
    
    # 顯示載入動畫
    with st.spinner("🔄 驗證中..."):
        auth_service = AuthService()
        result = auth_service.login(email, password)
    
    if result["success"]:
        # 儲存 Session
        session_manager.login(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            user_data=result["user"],
            expires_at=result["expires_at"]
        )
        
        st.success("✅ 登入成功！正在跳轉...")
        st.balloons()
        
        # 重新載入頁面（會觸發 main.py 的守門員邏輯）
        st.rerun()
    else:
        st.error(f"❌ {result['message']}")


# ==================== 註冊處理 ====================

def handle_register(email: str, password: str, confirm_password: str, name: str):
    """
    處理註冊邏輯
    
    Args:
        email: Email
        password: 密碼
        confirm_password: 確認密碼
        name: 姓名
    """
    # 驗證輸入
    email_valid, email_error = validate_email(email)
    if not email_valid:
        st.error(f"❌ {email_error}")
        return
    
    password_valid, password_error = validate_password(password)
    if not password_valid:
        st.error(f"❌ {password_error}")
        return
    
    if password != confirm_password:
        st.error("❌ 兩次密碼輸入不一致")
        return
    
    name_valid, name_error = validate_name(name)
    if not name_valid:
        st.error(f"❌ {name_error}")
        return
    
    # 顯示載入動畫
    with st.spinner("🔄 註冊中..."):
        auth_service = AuthService()
        result = auth_service.register(
            email=email,
            password=password,
            name=name,
            role="user"
        )
    
    if result["success"]:
        st.success(f"✅ {result['message']}")
        
        if result.get("requires_verification"):
            st.info("📧 請檢查您的 Email 信箱，點擊驗證連結完成註冊")
            st.caption("未收到信？請檢查垃圾郵件匣")
        else:
            st.info("💡 請使用您的帳號密碼登入")
        
        # 切換回登入模式
        st.session_state["auth_mode"] = "login"
        st.rerun()
    else:
        st.error(f"❌ {result['message']}")


# ==================== 忘記密碼處理 ====================

def handle_forgot_password(email: str):
    """
    處理忘記密碼邏輯
    
    Args:
        email: Email
    """
    # 驗證輸入
    email_valid, email_error = validate_email(email)
    if not email_valid:
        st.error(f"❌ {email_error}")
        return
    
    # 顯示載入動畫
    with st.spinner("🔄 發送中..."):
        auth_service = AuthService()
        result = auth_service.reset_password_request(email)
    
    if result["success"]:
        st.success(f"✅ {result['message']}")
        st.info("📧 請檢查您的 Email 信箱，點擊連結重設密碼")
        st.caption("未收到信？請檢查垃圾郵件匣，或稍後再試")
    else:
        st.error(f"❌ {result['message']}")


# ==================== 主渲染函數 ====================

def render():
    """渲染登入頁面"""
    
    # 初始化 auth_mode（登入/註冊/忘記密碼）
    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "login"
    
    # 置中佈局
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # ==================== 頁首 ====================
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Logo & 標題
        st.markdown(
            """
            <div style="text-align: center;">
                <h1 style="margin-bottom: 0;">🏠 幸福之家 Pro</h1>
                <h3 style="color: #666; margin-top: 0;">租賃管理系統</h3>
                <p style="color: #888;">為小房東量身定製的專業工具</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown("---")
        
        # ==================== 模式切換 ====================
        mode = st.session_state["auth_mode"]
        
        # 標籤頁
        tab_col1, tab_col2, tab_col3 = st.columns(3)
        
        with tab_col1:
            if st.button(
                "🔓 登入",
                use_container_width=True,
                type="primary" if mode == "login" else "secondary"
            ):
                st.session_state["auth_mode"] = "login"
                st.rerun()
        
        with tab_col2:
            if st.button(
                "📝 註冊",
                use_container_width=True,
                type="primary" if mode == "register" else "secondary"
            ):
                st.session_state["auth_mode"] = "register"
                st.rerun()
        
        with tab_col3:
            if st.button(
                "🔑 忘記密碼",
                use_container_width=True,
                type="primary" if mode == "forgot" else "secondary"
            ):
                st.session_state["auth_mode"] = "forgot"
                st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ==================== 登入表單 ====================
        if mode == "login":
            render_login_form()
        
        # ==================== 註冊表單 ====================
        elif mode == "register":
            render_register_form()
        
        # ==================== 忘記密碼表單 ====================
        elif mode == "forgot":
            render_forgot_password_form()
        
        # ==================== 頁尾 ====================
        st.markdown("---")
        
        # 測試帳號提示（僅開發模式）
        if session_manager.is_dev_mode():
            render_test_account_hint()
        
        # 版權資訊
        st.markdown(
            """
            <div style="text-align: center; color: #888; font-size: 0.9em;">
                <p>🔒 您的資料已加密存儲於 Supabase</p>
                <p>© 2026 幸福之家 Pro · Nordic Edition v15.0</p>
            </div>
            """,
            unsafe_allow_html=True
        )


# ==================== 登入表單 ====================

def render_login_form():
    """渲染登入表單"""
    with st.form("login_form", clear_on_submit=False):
        st.markdown("### 👋 歡迎回來")
        
        email = st.text_input(
            "📧 Email",
            placeholder="your@email.com",
            help="請輸入您的登入信箱",
            key="login_email"
        )
        
        password = st.text_input(
            "🔐 密碼",
            type="password",
            placeholder="••••••••",
            help="請輸入您的登入密碼",
            key="login_password"
        )
        
        # 記住我選項（未來實作）
        # remember_me = st.checkbox("記住我", value=False)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        submitted = st.form_submit_button(
            "🚀 立即登入",
            use_container_width=True,
            type="primary"
        )
    
    if submitted:
        handle_login(email, password)


# ==================== 註冊表單 ====================

def render_register_form():
    """渲染註冊表單"""
    with st.form("register_form", clear_on_submit=False):
        st.markdown("### 🎉 建立新帳號")
        
        name = st.text_input(
            "👤 姓名",
            placeholder="您的姓名",
            help="請輸入您的真實姓名或暱稱",
            key="register_name"
        )
        
        email = st.text_input(
            "📧 Email",
            placeholder="your@email.com",
            help="請輸入有效的 Email 地址",
            key="register_email"
        )
        
        password = st.text_input(
            "🔐 密碼",
            type="password",
            placeholder="至少 6 個字元",
            help="請設定至少 6 個字元的密碼",
            key="register_password"
        )
        
        confirm_password = st.text_input(
            "🔐 確認密碼",
            type="password",
            placeholder="再次輸入密碼",
            help="請再次輸入相同的密碼",
            key="register_confirm_password"
        )
        
        # 服務條款（未來實作）
        # agree_terms = st.checkbox(
        #     "我同意服務條款和隱私政策",
        #     value=False,
        #     key="register_agree_terms"
        # )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        submitted = st.form_submit_button(
            "🎯 建立帳號",
            use_container_width=True,
            type="primary"
        )
    
    if submitted:
        handle_register(email, password, confirm_password, name)


# ==================== 忘記密碼表單 ====================

def render_forgot_password_form():
    """渲染忘記密碼表單"""
    with st.form("forgot_password_form", clear_on_submit=False):
        st.markdown("### 🔑 重設密碼")
        st.caption("我們將發送重設密碼的連結到您的信箱")
        
        email = st.text_input(
            "📧 Email",
            placeholder="your@email.com",
            help="請輸入您註冊時使用的 Email",
            key="forgot_email"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        submitted = st.form_submit_button(
            "📧 發送重設連結",
            use_container_width=True,
            type="primary"
        )
    
    if submitted:
        handle_forgot_password(email)
    
    # 返回登入提示
    st.markdown("<br>", unsafe_allow_html=True)
    st.info("💡 記起密碼了？點擊上方「登入」按鈕返回登入頁面")


# ==================== 測試帳號提示 ====================

def render_test_account_hint():
    """渲染測試帳號提示（僅開發模式）"""
    with st.expander("🔧 開發模式 - 測試帳號", expanded=False):
        st.warning("""
        **⚠️ 開發模式已啟用**
        
        **演示帳號** (測試用):
        - Email: `demo@rental.com`
        - Password: `Demo123456`
        
        **管理員帳號** (測試用):
        - Email: `admin@rental.com`
        - Password: `Admin123456`
        
        *請在 Supabase Dashboard 手動建立這些用戶*
        """)
        
        st.code("""
# 建立測試用戶的 SQL
INSERT INTO auth.users (
    email,
    encrypted_password,
    email_confirmed_at,
    raw_user_meta_data
) VALUES (
    'demo@rental.com',
    crypt('Demo123456', gen_salt('bf')),
    NOW(),
    '{"name": "演示用戶", "role": "user"}'::jsonb
);
        """, language="sql")


# ==================== 快速登入（開發模式專用）====================

def render_quick_login_buttons():
    """渲染快速登入按鈕（僅開發模式）"""
    if not session_manager.is_dev_mode():
        return
    
    st.markdown("---")
    st.markdown("#### ⚡ 快速登入（開發模式）")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("👤 演示用戶", use_container_width=True):
            handle_login("demo@rental.com", "Demo123456")
    
    with col2:
        if st.button("👨‍💼 管理員", use_container_width=True):
            handle_login("admin@rental.com", "Admin123456")


# ==================== 進階功能（未來實作）====================

def render_social_login():
    """渲染社交登入按鈕（未來實作）"""
    st.markdown("---")
    st.markdown("### 或使用以下方式登入")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔵 Facebook", use_container_width=True):
            st.info("功能開發中...")
    
    with col2:
        if st.button("🔴 Google", use_container_width=True):
            st.info("功能開發中...")
    
    with col3:
        if st.button("⚫ LINE", use_container_width=True):
            st.info("功能開發中...")


# ==================== 主程式入口 ====================

if __name__ == "__main__":
    # 用於獨立測試
    st.set_page_config(
        page_title="登入 - 幸福之家 Pro",
        page_icon="🏠",
        layout="centered"
    )
    
    render()
