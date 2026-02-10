"""
儀表板 (Dashboard) - MicroRent Edition
現代化卡片式設計，以物件為核心視角
"""
import streamlit as st
from services.property_service import PropertyService
from services.payment_service import PaymentService
from services.session_manager import session_manager
import pandas as pd
from typing import Dict, Any

def render():
    st.title("📊 儀表板")
    st.caption("MicroRent - 您的智慧租屋管家")

    # 初始化服務
    property_service = PropertyService()
    payment_service = PaymentService()
    user_id = session_manager.get_user_id()

    if not user_id:
        st.warning("請先登入")
        return

    # 1. 頂部 KPI 卡片 (全域統計)
    render_global_kpi(property_service, payment_service, user_id)

    st.divider()

    # 2. 物件概況 (Properties Overview)
    st.subheader("🏢 物件概況")
    
    properties = property_service.get_properties_with_stats(user_id)
    
    if not properties:
        st.info("👋 歡迎使用 MicroRent！請先前往「物件管理」建立您的第一棟房源。")
        if st.button("🚀 立即建立物件", type="primary"):
            st.session_state["current_menu"] = "🏢 物件管理"
            st.rerun()
        return

    # 渲染物件卡片
    for prop in properties:
        render_property_dashboard_card(prop)

    st.divider()

    # 3. 待辦事項與通知 (簡易版)
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📝 待辦事項")
        st.info("✅ 目前沒有緊急待辦事項 (功能開發中)")
    
    with col2:
        st.subheader("🔔 最新通知")
        st.caption("暫無新通知")


def render_global_kpi(property_service, payment_service, user_id):
    """渲染全域 KPI 指標列"""
    
    # 這裡未來可以用 AnalyticsService 優化效能
    properties = property_service.get_properties_with_stats(user_id)
    
    total_rooms = sum(p.total_rooms for p in properties)
    occupied_rooms = sum(p.occupied_rooms for p in properties)
    vacant_rooms = total_rooms - occupied_rooms
    occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
    
    # TODO: 整合 PaymentService 取得真實金額
    # 目前先用模擬數據或暫時顯示 0
    total_expected_income = sum((p.monthly_income or 0) for p in properties)
    actual_income = 0  # 需實作 PaymentService 統計
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "總收入 (本月)", 
            f"${actual_income:,.0f}", 
            delta=f"目標 ${total_expected_income:,.0f}",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "總出租率", 
            f"{occupancy_rate:.1f}%", 
            delta=f"{occupied_rooms}/{total_rooms} 房"
        )
    
    with col3:
        # TODO: 取得真實逾期數
        overdue_count = 0 
        st.metric(
            "逾期未繳", 
            f"{overdue_count} 筆", 
            delta="需立即處理" if overdue_count > 0 else "狀況良好",
            delta_color="inverse"
        )
    
    with col4:
        st.metric("空房數", f"{vacant_rooms} 間", delta="可招租")


def render_property_dashboard_card(prop):
    """
    渲染單一物件的儀表板卡片
    顯示：出租率進度條、財務摘要、快速操作
    """
    with st.container():
        # 自定義 CSS 樣式讓它看起來像卡片
        st.markdown(f"""
        <div style="
            padding: 1.5rem; 
            border-radius: 12px; 
            border: 1px solid #e0e0e0; 
            background-color: white; 
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="display: flex; justify_content: space-between; align_items: center; margin-bottom: 10px;">
                <h3 style="margin: 0; color: #333;">🏢 {prop.name}</h3>
                <span style="background-color: #f3f4f6; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; color: #666;">
                    {prop.city} {prop.district}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # 出租率進度條
            occupancy = prop.occupancy_rate or 0.0
            st.progress(occupancy, text=f"出租率 {occupancy*100:.0f}% ({prop.occupied_rooms}/{prop.total_rooms})")
            
            # 房間狀態微型燈號 (這裡簡化顯示)
            st.caption(f"空房: {prop.vacant_rooms} | 已租: {prop.occupied_rooms}")

        with col2:
            income = prop.monthly_income or 0
            st.metric("本月預收", f"${income:,.0f}")

        with col3:
            # 快速操作按鈕
            if st.button("管理房間", key=f"manage_{prop.id}", use_container_width=True):
                st.session_state["current_menu"] = "🚪 房間管理"
                # TODO: 傳遞 default_property_id
                st.rerun()
            
            if st.button("新增房客", key=f"add_tenant_{prop.id}", use_container_width=True):
                st.session_state["current_menu"] = "👥 房客管理"
                st.rerun()

def show():
    render()
