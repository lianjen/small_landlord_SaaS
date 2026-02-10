"""
房客專屬入口 (Tenant Portal)
無需登入，通過 URL 參數或簡易驗證進入
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from services.payment_service import PaymentService
from services.tenant_service import TenantService

def render():
    st.set_page_config(page_title="房客專區", page_icon="🏠", layout="centered")
    
    st.title("🏠 我的租屋資訊")
    
    # 自定義 CSS 隱藏側邊欄
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            .block-container {padding-top: 2rem;}
        </style>
    """, unsafe_allow_html=True)

    # 簡易登入 (如果 Session 沒有 tenant_id)
    if "tenant_id" not in st.session_state:
        render_login()
    else:
        render_dashboard()

def render_login():
    st.markdown("### 房客查詢與繳費")
    
    with st.form("tenant_login"):
        phone = st.text_input("手機號碼", placeholder="0912345678")
        room_number = st.text_input("房號", placeholder="例如: 101")
        
        if st.form_submit_button("🔍 查詢", type="primary", use_container_width=True):
            tenant_service = TenantService()
            # 這裡需要一個 verify_tenant 方法，暫時模擬
            tenant = tenant_service.get_tenant_by_room(room_number)
            
            if tenant and tenant.get('phone') == phone:
                st.session_state.tenant_id = tenant['id']
                st.session_state.tenant_name = tenant['name']
                st.success(f"歡迎回來，{tenant['name']}")
                st.rerun()
            else:
                st.error("查無資料，請確認手機號碼與房號是否正確。")

def render_dashboard():
    tenant_id = st.session_state.tenant_id
    name = st.session_state.get('tenant_name', '房客')
    
    st.markdown(f"👋 Hi, **{name}**")
    
    if st.button("登出"):
        del st.session_state.tenant_id
        st.rerun()
        
    tab1, tab2, tab3 = st.tabs(["待繳費用", "繳費紀錄", "租約資訊"])
    
    payment_service = PaymentService()
    
    with tab1:
        st.subheader("💰 待繳費用")
        # 這裡應該呼叫 payment_service.get_unpaid_by_tenant(tenant_id)
        # 暫時用模擬數據或現有 API
        st.info("目前沒有待繳費用 🎉")
        
    with tab2:
        st.subheader("📋 繳費紀錄")
        st.caption("顯示最近 6 個筆紀錄")
        
    with tab3:
        st.subheader("📝 租約詳情")
        st.caption("租約期間: 2025/01/01 - 2026/01/01")
        st.caption("房東電話: 0987-654-321")

# 獨立入口支持
if __name__ == "__main__":
    render()
