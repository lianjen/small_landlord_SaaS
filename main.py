import streamlit as st
import os

# Page Config
st.set_page_config(
    page_title="幸福之家 Pro | 租務管理系統",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 強制展開側邊欄的 JavaScript
def inject_sidebar_toggle():
    st.markdown("""
        <style>
        /* 確保側邊欄按鈕可見 */
        [data-testid="collapsedControl"] {
            display: block !important;
            position: fixed;
            top: 0.5rem;
            left: 0.5rem;
            z-index: 999999;
            background: #FF4B4B;
            color: white;
            padding: 0.5rem;
            border-radius: 0.5rem;
            cursor: pointer;
        }
        
        /* 漢堡選單圖示更明顯 */
        button[kind="header"] {
            background-color: #FF4B4B !important;
        }
        </style>
        
        <script>
        // 自動展開側邊欄（首次載入）
        const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
        if (sidebar && sidebar.getAttribute('aria-expanded') === 'false') {
            const toggleButton = window.parent.document.querySelector('[data-testid="collapsedControl"]');
            if (toggleButton) {
                toggleButton.click();
            }
        }
        </script>
    """, unsafe_allow_html=True)

# 執行注入
inject_sidebar_toggle()

# Load CSS
def load_css(filename):
    try:
        with open(filename) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass

css_path = os.path.join('assets', 'style.css')
load_css(css_path)

# Database
from services.db import SupabaseDB

@st.cache_resource
def get_db():
    return SupabaseDB()

db = get_db()

# Import views
from views import dashboard, tenants, rent, electricity, expenses, tracking, settings

def main():
    with st.sidebar:
        st.title("🏠 幸福之家 Pro")
        st.markdown(
            '<div style="font-size: 0.8rem; color: #888; margin-bottom: 20px;">Nordic Edition v14.2</div>',
            unsafe_allow_html=True
        )
        
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
    
    # Views
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
