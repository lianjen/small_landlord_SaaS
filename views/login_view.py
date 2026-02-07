"""
登入頁面視圖
"""
import streamlit as st
from services.auth_service import AuthService
from services.session_manager import SessionManager


def render():
    """渲染登入頁面"""
    
    # 置中佈局
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Logo & 標題
        st.markdown("---")
        st.markdown("# 🏠 幸福之家 Pro")
        st.markdown("## 租賃管理系統")
        st.caption("**為小房東量身定製的專業工具**")
        st.markdown("---")
        
        # 登入表單
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "📧 Email",
                placeholder="demo@rental.com",
                help="請輸入您的登入信箱"
            )
            
            password = st.text_input(
                "🔐 密碼",
                type="password",
                placeholder="••••••••",
                help="請輸入您的登入密碼"
            )
            
            # 記住我選項（未來實作）
            # remember_me = st.checkbox("記住我", value=False)
            
            submitted = st.form_submit_button(
                "🔓 登入",
                use_container_width=True,
                type="primary"
            )
        
        # 處理登入
        if submitted:
            if not email or not password:
                st.error("❌ 請輸入信箱和密碼")
            else:
                with st.spinner("🔄 驗證中..."):
                    auth_service = AuthService()
                    success, message, user_data = auth_service.login(email, password)
                
                if success and user_data:
                    # 設定會話狀態
                    SessionManager.login(user_data)
                    
                    st.success("✅ 登入成功！正在跳轉...")
                    st.balloons()
                    
                    # 重新載入頁面（會觸發 main.py 的守門員邏輯）
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
        
        st.markdown("---")
        
        # 測試帳號提示
        with st.expander("💡 測試帳號"):
            st.info("""
            **演示帳號** (開發/測試用):
            - Email: `demo@rental.com`
            - Password: `Test1234!`
            
            *請在 Supabase Dashboard 手動建立此用戶*
            """)
        
        # 註冊連結（未來功能）
        # st.markdown("還沒有帳號？[立即註冊](#)")
        
        st.markdown("---")
        st.caption("🔒 您的資料已加密存儲於 Supabase")
        st.caption("© 2026 幸福之家 Pro · Nordic Edition")
