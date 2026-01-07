import streamlit as st
import os

# 1. Page Config 必須是第一個指令
st.set_page_config(
    page_title="幸福之家 Pro | 租務管理系統",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded" # 預設展開，但允許收合
)

# 2. CSS 載入函數
def load_css(filename):
    if os.path.exists(filename):
        with open(filename) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# 載入 CSS
css_path = os.path.join('assets', 'style.css')
load_css(css_path)

# 3. 初始化 DB (模擬)
from services.db import SupabaseDB

@st.cache_resource
def get_db():
    return SupabaseDB()

db = get_db()

# 4. 引入 Views
from views import dashboard, tenants, rent, electricity, expenses, tracking, settings

def main():
    # ============ 側邊欄區域 ============
    with st.sidebar:
        st.title("🏠 幸福之家 Pro )
        st.markdown(
            '<div style="font-size: 0.8rem; color: #888; margin-bottom: 20px;">Nordic Edition v14.1</div>',
            unsafe_allow_html=True
        )
        
        # 選單
        menu = st.radio(
            "功能選單",
            [
                "📊 儀表板",
                "💰 租金管理",
                "📝 追蹤功能",
                "👥 房客管理",
                "⚡ 電費管理",
                "💸 支出記錄",
                "⚙️ 系統設定"
            ],
            label_visibility="collapsed"
        )
        
        st.divider()
        st.caption("© 幸福之家 Pro | 租務管理系統")

    # ============ 主內容區域 (注意縮排，這是在 sidebar 之外) ============
    
    # 這裡顯示當前頁面標題，讓使用者知道自己在透過哪個頁面
    # st.header(menu) 
    
    # 路由邏輯
    if menu == "📊 儀表板":
        dashboard.render(db)
    elif menu == "💰 租金管理":
        rent.render(db)
    elif menu == "📝 追蹤功能":
        tracking.render(db)
    elif menu == "👥 房客管理":
        tenants.render(db)
    elif menu == "⚡ 電費管理":
        electricity.render(db)
    elif menu == "💸 支出記錄":
        expenses.render(db)
    elif menu == "⚙️ 系統設定":
        settings.render(db)

if __name__ == "__main__":
    main()
