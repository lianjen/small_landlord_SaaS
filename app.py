import streamlit as st
import pandas as pd
from services.tenant_service import TenantService

# 設定頁面資訊
st.set_page_config(
    page_title="租屋管理 SaaS 2026",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入自定義 CSS
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 初始化服務
tenant_service = TenantService()

def main():
    # 側邊欄導覽
    st.sidebar.title("🏠 租屋管理系統")
    page = st.sidebar.radio("導覽", ["儀表板", "房客管理", "房源管理", "財務報表"])

    st.markdown(f"# {page}")

    if page == "儀表板":
        show_dashboard()
    elif page == "房客管理":
        st.info("功能開發中...")
    elif page == "房源管理":
        st.info("功能開發中...")
    else:
        st.info("功能開發中...")

def show_dashboard():
    # 這裡未來會接真實數據
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="總房客數", value="0", delta="0")
    with col2:
        st.metric(label="本月預計租金", value="$0", delta="0")
    with col3:
        st.metric(label="待繳費房客", value="0", delta="0", delta_color="inverse")
    with col4:
        st.metric(label="空房率", value="0%", delta="0%")

    st.divider()
    st.subheader("💡 系統提示")
    st.write("目前還沒有房客資料，點擊下方按鈕新增第一位房客吧！🌱")
    if st.button("新增第一位房客", type="primary"):
        st.toast("跳轉至房客管理頁面...")

if __name__ == "__main__":
    main()
