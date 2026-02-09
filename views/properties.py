"""
物件管理頁面 (Properties Management)
支援多棟建築物的管理與視覺化
"""
import streamlit as st
from typing import Optional
from services.property_service import PropertyService
from services.room_service import RoomService
from schemas.property import PropertyCreate, PropertyUpdate
from services.session_manager import session_manager


def render():
    """渲染物件管理頁面"""
    
    st.title("🏢 物件管理")
    st.caption("管理您的建築物與房源")
    
    # 初始化服務
    property_service = PropertyService()
    room_service = RoomService()
    
    # 取得當前用戶 ID
    user_id = session_manager.get_user_id()
    if not user_id:
        st.error("請先登入")
        return
    
    # 上方操作列
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.subheader("我的物件")
    with col3:
        if st.button("➕ 新增物件", type="primary", use_container_width=True):
            st.session_state.show_create_form = True
    
    st.divider()
    
    # 新增物件表單（Modal）
    if st.session_state.get("show_create_form", False):
        render_create_property_form(property_service, user_id)
        return
    
    # 取得物件列表（帶統計）
    properties = property_service.get_properties_with_stats(user_id)
    
    if not properties:
        render_empty_state()
        return
    
    # 卡片式列表
    for prop in properties:
        render_property_card(prop, property_service, room_service)


def render_property_card(prop, property_service, room_service):
    """
    渲染物件卡片
    
    Args:
        prop: PropertyWithStats 物件
        property_service: PropertyService 實例
        room_service: RoomService 實例
    """
    with st.container():
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        with col1:
            st.markdown(f"### 🏢 {prop.name}")
            if prop.address:
                st.caption(f"📍 {prop.address}")
        
        with col2:
            occupancy_pct = prop.occupancy_rate * 100 if prop.occupancy_rate else 0
            st.metric(
                label="出租率",
                value=f"{occupancy_pct:.0f}%",
                delta=f"{prop.occupied_rooms}/{prop.total_rooms} 已租"
            )
        
        with col3:
            monthly_income = prop.monthly_income or 0
            st.metric(
                label="本月收入",
                value=f"${monthly_income:,.0f}"
            )
        
        with col4:
            if st.button("查看詳情", key=f"view_{prop.id}", use_container_width=True):
                st.session_state.selected_property_id = prop.id
                st.session_state.show_property_detail = True
                st.rerun()
        
        # 快速資訊列
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.caption(f"🏠 總房間數：{prop.total_rooms}")
        with col_b:
            st.caption(f"✅ 已出租：{prop.occupied_rooms}")
        with col_c:
            st.caption(f"🔓 空房：{prop.vacant_rooms}")
        
        if prop.notes:
            with st.expander("📝 備註"):
                st.write(prop.notes)
        
        st.divider()


def render_create_property_form(property_service, owner_id):
    """
    渲染新增物件表單
    
    Args:
        property_service: PropertyService 實例
        owner_id: 房東 ID
    """
    st.subheader("➕ 新增物件")
    
    with st.form("create_property_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("物件名稱*", placeholder="例如：A棟、台北中山社區")
            property_type = st.selectbox(
                "物件類型",
                options=["apartment", "house", "building", "mixed"],
                format_func=lambda x: {
                    "apartment": "公寓/套房",
                    "house": "透天厝",
                    "building": "整棟大樓",
                    "mixed": "混合型"
                }[x]
            )
        
        with col2:
            city = st.text_input("城市", placeholder="例如：台北市")
            district = st.text_input("區域", placeholder="例如：中山區")
        
        address = st.text_input("地址", placeholder="詳細地址")
        notes = st.text_area("備註", placeholder="其他需要記錄的資訊")
        
        col_submit, col_cancel = st.columns(2)
        
        with col_submit:
            submitted = st.form_submit_button("✅ 建立物件", type="primary", use_container_width=True)
        
        with col_cancel:
            cancelled = st.form_submit_button("❌ 取消", use_container_width=True)
        
        if submitted:
            if not name:
                st.error("請輸入物件名稱")
                return
            
            # 建立物件
            property_data = PropertyCreate(
                owner_id=owner_id,
                name=name,
                type=property_type,
                city=city,
                district=district,
                address=address,
                notes=notes
            )
            
            result = property_service.create_property(property_data)
            
            if result:
                st.success(f"✅ 物件「{name}」建立成功！")
                st.session_state.show_create_form = False
                st.rerun()
            else:
                st.error("建立物件失敗，請稍後再試")
        
        if cancelled:
            st.session_state.show_create_form = False
            st.rerun()


def render_empty_state():
    """渲染空狀態"""
    st.info("🌱 目前還沒有物件，點擊「新增物件」開始建立您的第一棟房源！")
    
    with st.expander("💡 使用提示"):
        st.markdown("""
        ### 什麼是「物件」？
        - 物件代表一棟建築物或一個社區
        - 例如：A棟、台北中山社區、板橋套房大樓
        
        ### 為什麼要建立物件？
        - 方便管理多棟房源
        - 清楚掌握每棟的出租狀況
        - 快速查看每棟的收入統計
        """)


# 初始化 session state
if "show_create_form" not in st.session_state:
    st.session_state.show_create_form = False
