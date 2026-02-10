"""
房客管理介面 (Tenants View) - MicroRent Edition
整合 PropertyService 與 RoomService，實現動態房間選擇
"""
import streamlit as st
import pandas as pd
from datetime import date
from services.tenant_service import TenantService
from services.property_service import PropertyService
from services.room_service import RoomService
from services.session_manager import session_manager
from utils.formatters import format_currency

def render():
    st.title("👥 房客管理")
    
    # 初始化服務
    tenant_service = TenantService()
    property_service = PropertyService()
    room_service = RoomService()
    
    user_id = session_manager.get_user_id()
    if not user_id:
        st.error("請先登入")
        return

    # 初始化 Session State
    if "show_add_tenant_form" not in st.session_state:
        st.session_state.show_add_tenant_form = False
    
    # 上方操作列
    col1, col2 = st.columns([4, 1])
    with col1:
        # 篩選器（可選）
        pass
    with col2:
        if st.button("➕ 新增房客", type="primary", use_container_width=True):
            st.session_state.show_add_tenant_form = True
            st.rerun()

    st.divider()

    # 處理新增/編輯表單
    if st.session_state.show_add_tenant_form:
        render_tenant_form(tenant_service, property_service, room_service, user_id)
        return

    # 顯示房客列表
    tenants = tenant_service.get_all_tenants()
    
    if not tenants:
        st.info("目前沒有房客資料。點擊上方按鈕新增第一位房客！")
        return

    # 轉換為 DataFrame 方便顯示（可選，或直接用卡片）
    # 這裡示範使用卡片式列表，符合現代化 UI
    for tenant in tenants:
        render_tenant_card(tenant, tenant_service)


def render_tenant_card(tenant, tenant_service):
    """渲染房客卡片"""
    with st.container():
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
        
        with col1:
            st.markdown(f"### 👤 {tenant.get('name')}")
            # 顯示物件與房號
            property_name = tenant.get("property_name", "未知物件")
            room_number = tenant.get("room_number", "未知房號")
            st.caption(f"🏠 {property_name} - {room_number}")
        
        with col2:
            st.markdown(f"**📞 {tenant.get('phone')}**")
            st.caption(f"LINE: {tenant.get('line_id', '未綁定')}")
            
        with col3:
            rent = tenant.get('rent_amount', 0)
            st.markdown(f"💰 租金: **{format_currency(rent)}**")
            deposit = tenant.get('deposit', 0)
            st.caption(f"押金: {format_currency(deposit)}")
            
        with col4:
            # 租約狀態
            lease_end = tenant.get('move_out_date') # Schema 欄位名稱確認
            if lease_end:
                 st.caption(f"到期: {lease_end}")
            else:
                 st.caption("無租約期限")
                 
        with col5:
             if st.button("管理", key=f"manage_{tenant['id']}", use_container_width=True):
                 st.warning("編輯功能開發中")
                 
        st.divider()


def render_tenant_form(tenant_service, property_service, room_service, user_id):
    """渲染新增/編輯房客表單"""
    st.subheader("➕ 新增房客")
    
    with st.form("tenant_form"):
        # 1. 選擇房間 (關鍵整合點)
        st.markdown("#### 1. 選擇房源")
        
        # 取得房東的所有物件
        properties = property_service.get_properties_by_owner(user_id)
        property_options = {p.id: p.name for p in properties}
        
        selected_property_id = st.selectbox(
            "選擇物件",
            options=list(property_options.keys()),
            format_func=lambda x: property_options[x]
        )
        
        # 根據選擇的物件，取得「空房」列表
        rooms = []
        if selected_property_id:
            # 這裡可以過濾只顯示 status='vacant' 的房間
            all_rooms = room_service.get_rooms_by_property(selected_property_id)
            rooms = [r for r in all_rooms if r.status == 'vacant']
            
        if not rooms:
            st.warning("⚠️ 該物件目前沒有空房，無法新增房客。請先至「房間管理」新增房間或確認房間狀態。")
            if st.form_submit_button("取消"):
                st.session_state.show_add_tenant_form = False
                st.rerun()
            return

        room_options = {r.id: f"{r.room_number} ({format_currency(r.base_rent)})" for r in rooms}
        selected_room_id = st.selectbox(
            "選擇房間",
            options=list(room_options.keys()),
            format_func=lambda x: room_options[x]
        )
        
        # 預填租金
        selected_room = next((r for r in rooms if r.id == selected_room_id), None)
        default_rent = int(selected_room.base_rent) if selected_room else 0
        default_deposit = int(selected_room.deposit) if selected_room and selected_room.deposit else 0

        st.markdown("#### 2. 房客資料")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("姓名*", placeholder="王小明")
            phone = st.text_input("電話*", placeholder="0912-345-678")
            line_id = st.text_input("LINE ID", placeholder="選填")
        
        with col2:
            id_number = st.text_input("身分證字號", placeholder="選填")
            email = st.text_input("Email", placeholder="選填")
            job_title = st.text_input("職業", placeholder="選填")

        st.markdown("#### 3. 租約內容")
        col3, col4 = st.columns(2)
        with col3:
            move_in_date = st.date_input("起租日期*", value=date.today())
            rent_amount = st.number_input("月租金*", value=default_rent, step=1000)
        
        with col4:
            move_out_date = st.date_input("退租日期 (選填)", value=None)
            deposit = st.number_input("押金*", value=default_deposit, step=1000)
            payment_day = st.number_input("繳租日*", min_value=1, max_value=31, value=5)

        memo = st.text_area("備註")

        # 按鈕區
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("✅ 確認新增", type="primary", use_container_width=True)
        with col_cancel:
            cancelled = st.form_submit_button("❌ 取消", use_container_width=True)

        if submitted:
            if not name or not phone or not selected_room_id:
                st.error("請填寫必填欄位 (姓名、電話、房間)")
                return

            # 組裝資料
            tenant_data = {
                "room_id": selected_room_id,
                "name": name,
                "phone": phone,
                "line_id": line_id,
                "id_number": id_number,
                "email": email,
                "job_title": job_title,
                "move_in_date": move_in_date.isoformat(),
                "move_out_date": move_out_date.isoformat() if move_out_date else None,
                "rent_amount": rent_amount,
                "deposit": deposit,
                "rent_payment_day": payment_day,
                "memo": memo,
                "status": "active"
            }
            
            # 呼叫 Service 建立房客 (會自動更新房間狀態)
            result = tenant_service.create_tenant(tenant_data)
            
            if result:
                st.success(f"✅ 房客 {name} 新增成功！")
                st.session_state.show_add_tenant_form = False
                st.rerun()
            else:
                st.error("新增失敗，請稍後再試")

        if cancelled:
            st.session_state.show_add_tenant_form = False
            st.rerun()
