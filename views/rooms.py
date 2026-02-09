"""
房間管理頁面 (Rooms Management)
支援房號靈活編號與狀態管理
"""
import streamlit as st
from typing import Optional
from services.property_service import PropertyService
from services.room_service import RoomService
from schemas.room import RoomCreate, RoomUpdate
from services.session_manager import session_manager


def render():
    """渲染房間管理頁面"""
    
    st.title("🚪 房間管理")
    st.caption("管理您的房間與房號")
    
    # 初始化服務
    property_service = PropertyService()
    room_service = RoomService()
    
    # 取得當前用戶 ID
    user_id = session_manager.get_user_id()
    if not user_id:
        st.error("請先登入")
        return
    
    # 取得物件列表
    properties = property_service.get_properties_by_owner(user_id)
    
    if not properties:
        st.info("📢 請先在「物件管理」頁面新增物件，再新增房間")
        return
    
    # 選擇物件
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_property_name = st.selectbox(
            "選擇物件",
            options=[p.name for p in properties],
            key="selected_property_name"
        )
    
    # 取得選中的物件
    selected_property = next((p for p in properties if p.name == selected_property_name), None)
    
    if not selected_property:
        return
    
    with col2:
        if st.button("➕ 新增房間", type="primary", use_container_width=True):
            st.session_state.show_create_room_form = True
    
    st.divider()
    
    # 新增房間表單
    if st.session_state.get("show_create_room_form", False):
        render_create_room_form(room_service, selected_property, user_id)
        return
    
    # 取得房間列表（帶房客資訊）
    rooms = room_service.get_rooms_with_tenants(selected_property.id)
    
    if not rooms:
        render_empty_state(selected_property.name)
        return
    
    # 顯示房間統計
    render_room_stats(rooms)
    
    st.divider()
    
    # 房間卡片列表
    for room in rooms:
        render_room_card(room, room_service)


def render_room_stats(rooms):
    """
    渲染房間統計卡片
    
    Args:
        rooms: List[RoomWithTenant]
    """
    col1, col2, col3, col4 = st.columns(4)
    
    total_rooms = len(rooms)
    occupied_rooms = sum(1 for r in rooms if r.status == "occupied")
    vacant_rooms = sum(1 for r in rooms if r.status == "vacant")
    avg_rent = sum(r.base_rent for r in rooms) / total_rooms if total_rooms > 0 else 0
    
    with col1:
        st.metric("總房間數", total_rooms)
    
    with col2:
        st.metric("已出租", occupied_rooms, delta=f"{occupied_rooms/total_rooms*100:.0f}%" if total_rooms > 0 else "0%")
    
    with col3:
        st.metric("空房", vacant_rooms)
    
    with col4:
        st.metric("平均租金", f"${avg_rent:,.0f}")


def render_room_card(room, room_service):
    """
    渲染房間卡片
    
    Args:
        room: RoomWithTenant
        room_service: RoomService 實例
    """
    # 狀態顏色映射
    status_color = {
        "vacant": "🔓",
        "occupied": "✅",
        "maintenance": "🔧",
        "reserved": "📌"
    }
    
    status_text = {
        "vacant": "空房",
        "occupied": "已出租",
        "maintenance": "維修中",
        "reserved": "已預訂"
    }
    
    with st.container():
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        
        with col1:
            st.markdown(f"### {status_color.get(room.status, '🚪')} {room.room_number}")
            if room.floor:
                st.caption(f"樓層：{room.floor}F")
        
        with col2:
            if room.tenant_name:
                st.write(f"👤 **房客**：{room.tenant_name}")
                if room.tenant_phone:
                    st.caption(f"📞 {room.tenant_phone}")
            else:
                st.caption(f"狀態：{status_text.get(room.status, room.status)}")
        
        with col3:
            st.metric("租金", f"${room.base_rent:,.0f}")
        
        with col4:
            if st.button("編輯", key=f"edit_{room.id}", use_container_width=True):
                st.session_state.edit_room_id = room.id
                st.rerun()
        
        # 詳細資訊（可展開）
        with st.expander("📋 詳細資訊"):
            info_col1, info_col2 = st.columns(2)
            
            with info_col1:
                if room.area_sqm:
                    st.write(f"🏠 坪數：{room.area_sqm} m²")
                st.write(f"🛏️ 臥室：{room.bedrooms} 間")
                st.write(f"🚿 浴室：{room.bathrooms} 間")
            
            with info_col2:
                if room.deposit:
                    st.write(f"💰 押金：${room.deposit:,.0f}")
                
                if room.amenities:
                    st.write("**設施**：")
                    for key, value in room.amenities.items():
                        if value:
                            st.caption(f"✓ {key}")
            
            if room.notes:
                st.write(f"**備註**：{room.notes}")
        
        st.divider()


def render_create_room_form(room_service, property_obj, owner_id):
    """
    渲染新增房間表單
    
    Args:
        room_service: RoomService 實例
        property_obj: Property 物件
        owner_id: 房東 ID
    """
    st.subheader(f"➕ 新增房間 - {property_obj.name}")
    
    with st.form("create_room_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            room_number = st.text_input("房號*", placeholder="例如：101、A1-客房、套房-201")
            floor = st.number_input("樓層", min_value=1, max_value=50, value=1)
            area_sqm = st.number_input("坪數 (m²)", min_value=0.0, value=20.0, step=0.5)
        
        with col2:
            base_rent = st.number_input("月租金*", min_value=0, value=10000, step=1000)
            deposit = st.number_input("押金", min_value=0, value=20000, step=1000)
            bedrooms = st.number_input("臥室數", min_value=1, max_value=10, value=1)
        
        bathrooms = st.number_input("浴室數", min_value=1, max_value=5, value=1)
        
        # 設施選項
        st.write("**設施**")
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            has_ac = st.checkbox("冷氣", value=True)
            has_wifi = st.checkbox("Wi-Fi", value=True)
        
        with col_b:
            has_balcony = st.checkbox("陽台")
            has_parking = st.checkbox("車位")
        
        with col_c:
            has_furniture = st.checkbox("家具")
            has_washer = st.checkbox("洗衣機")
        
        notes = st.text_area("備註")
        
        col_submit, col_cancel = st.columns(2)
        
        with col_submit:
            submitted = st.form_submit_button("✅ 建立房間", type="primary", use_container_width=True)
        
        with col_cancel:
            cancelled = st.form_submit_button("❌ 取消", use_container_width=True)
        
        if submitted:
            if not room_number:
                st.error("請輸入房號")
                return
            
            # 建立房間
            room_data = RoomCreate(
                property_id=property_obj.id,
                owner_id=owner_id,
                room_number=room_number,
                floor=floor,
                area_sqm=area_sqm,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                base_rent=base_rent,
                deposit=deposit,
                amenities={
                    "air_conditioner": has_ac,
                    "wifi": has_wifi,
                    "balcony": has_balcony,
                    "parking": has_parking,
                    "furniture": has_furniture,
                    "washer": has_washer
                },
                notes=notes
            )
            
            result = room_service.create_room(room_data)
            
            if result:
                st.success(f"✅ 房間「{room_number}」建立成功！")
                st.session_state.show_create_room_form = False
                st.rerun()
            else:
                st.error("建立房間失敗，請稍後再試")
        
        if cancelled:
            st.session_state.show_create_room_form = False
            st.rerun()


def render_empty_state(property_name):
    """渲染空狀態"""
    st.info(f"🌱「{property_name}」目前還沒有房間，點擊「新增房間」開始新增！")


# 初始化 session state
if "show_create_room_form" not in st.session_state:
    st.session_state.show_create_room_form = False
