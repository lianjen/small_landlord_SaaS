"""
電費管理 - 簡化版 (直接使用 db 方法)
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Dict, Optional
import sys

from components.cards import (
    section_header, metric_card, empty_state,
    data_table, info_card, loading_spinner
)
from config.constants import ROOMS

# ============== 主渲染函數 ==============

def render(db):
    """主渲染函數"""
    st.title("⚡ 電費管理")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📅 計費期間", "🧮 計算電費", "📜 歷史記錄"])
    
    with tab1:
        render_period_tab(db)
    
    with tab2:
        render_calculation_tab(db)
    
    with tab3:
        render_records_tab(db)

# ============== Tab 1: 計費期間管理 ==============

def render_period_tab(db):
    """計費期間 Tab"""
    section_header("建立計費期間", "📅")
    
    # 建立新期間
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        year = st.number_input(
            "年份",
            min_value=2020,
            max_value=2030,
            value=date.today().year,
            key="period_year"
        )
    
    with col2:
        month_start = st.selectbox(
            "開始月份",
            list(range(1, 13)),
            key="period_month_start"
        )
    
    with col3:
        month_end = st.selectbox(
            "結束月份",
            list(range(1, 13)),
            index=1,
            key="period_month_end"
        )
    
    with col4:
        st.write("")
        st.write("")
        if st.button("➕ 建立期間", type="primary"):
            if month_end <= month_start:
                st.error("❌ 結束月份必須大於開始月份")
            else:
                ok, msg, period_id = db.add_electricity_period(year, month_start, month_end)
                if ok:
                    st.success(msg)
                    st.session_state.current_period_id = period_id
                    st.rerun()
                else:
                    st.warning(msg)
    
    st.divider()
    
    # 顯示期間列表
    section_header("歷史期間", "📋", divider=False)
    
    try:
        periods = db.get_all_periods()
        
        if not periods:
            empty_state(
                "尚未建立計費期間",
                "📅",
                "請先建立一個計費期間"
            )
        else:
            # 格式化顯示
            period_options = [
                f"{p['period_year']}/{p['period_month_start']}-{p['period_month_end']} (ID:{p['id']})"
                for p in periods
            ]
            
            selected = st.selectbox(
                "選擇計費期間",
                period_options,
                key="selected_period_display"
            )
            
            # 提取 ID
            selected_id = int(selected.split("ID:")[1].replace(")", ""))
            st.session_state.current_period_id = selected_id
            st.info(f"✅ 當前期間: {selected}")
            
            # 刪除期間
            if st.button("🗑️ 刪除此期間", type="secondary"):
                if st.session_state.get("confirm_delete"):
                    ok, msg = db.delete_electricity_period(selected_id)
                    if ok:
                        st.success(msg)
                        del st.session_state.current_period_id
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.session_state.confirm_delete = True
                    st.warning("⚠️ 再按一次確認刪除")
    
    except Exception as e:
        st.error(f"❌ 載入期間失敗: {e}")

# ============== Tab 2: 計算電費 ==============

def render_calculation_tab(db):
    """計算 Tab - 簡化版"""
    
    # 檢查是否已選擇期間
    if 'current_period_id' not in st.session_state:
        info_card(
            "請先建立計費期間",
            "請前往「計費期間」Tab 建立或選擇一個期間",
            "⚠️",
            "warning"
        )
        return
    
    period_id = st.session_state.current_period_id
    st.info(f"📅 計費期間 ID: {period_id}")
    
    st.divider()
    
    # ====== 簡化輸入區 ======
    section_header("電費資料輸入", "📝")
    
    st.markdown("### 📄 台電總帳單")
    col1, col2 = st.columns(2)
    
    with col1:
        total_amount = st.number_input(
            "台電總金額 (元)",
            min_value=0,
            value=0,
            step=100,
            key="total_amount"
        )
    
    with col2:
        total_kwh = st.number_input(
            "台電總度數",
            min_value=0.0,
            value=0.0,
            step=10.0,
            key="total_kwh"
        )
    
    st.divider()
    
    st.markdown("### 🔢 各房間電錶讀數")
    
    # 分 4 列顯示
    room_readings = {}
    rows = [ROOMS.ALL_ROOMS[i:i+3] for i in range(0, len(ROOMS.ALL_ROOMS), 3)]
    
    for row_rooms in rows:
        cols = st.columns(3)
        for col, room in zip(cols, row_rooms):
            with col:
                reading = st.number_input(
                    f"**{room}** 讀數",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    key=f"reading_{room}"
                )
                room_readings[room] = reading
    
    st.divider()
    
    # ====== 計算按鈕 ======
    if st.button("🚀 計算電費", type="primary"):
        # 驗證資料
        if total_amount <= 0 or total_kwh <= 0:
            st.error("❌ 請輸入台電帳單資料")
            return
        
        if sum(room_readings.values()) <= 0:
            st.error("❌ 請輸入至少一個房間的電錶讀數")
            return
        
        # 簡易計算 (平均分攤)
        try:
            total_rooms_kwh = sum(room_readings.values())
            unit_price = total_amount / total_kwh if total_kwh > 0 else 0
            
            results = []
            for room, kwh in room_readings.items():
                if kwh > 0:
                    room_type = "分攤" if room in ROOMS.SHARING_ROOMS else "獨享"
                    charge = round(kwh * unit_price, 0)
                    results.append({
                        '房號': room,
                        '類型': room_type,
                        '使用度數': kwh,
                        '公用分攤': 0,  # 簡化版不計算
                        '總度數': kwh,
                        '應繳金額': charge
                    })
            
            # 顯示結果
            st.success("✅ 計算完成")
            
            df_results = pd.DataFrame(results)
            st.dataframe(df_results, use_container_width=True)
            
            # 統計資訊
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                metric_card("總應收", f"${df_results['應繳金額'].sum():,.0f}", icon="💰")
            with col_b:
                metric_card("單位電價", f"${unit_price:.2f}/度", icon="⚡")
            with col_c:
                metric_card("房間數", f"{len(results)} 間", icon="🏠")
            
            # 儲存結果
            st.divider()
            if st.button("💾 儲存計費結果"):
                ok, msg = db.save_electricity_record(period_id, results)
                if ok:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
            
            # 匯出 CSV
            csv = df_results.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "📥 下載 CSV",
                csv,
                f"electricity_{period_id}.csv",
                "text/csv"
            )
        
        except Exception as e:
            st.error(f"❌ 計算失敗: {e}")

# ============== Tab 3: 歷史記錄 ==============

def render_records_tab(db):
    """記錄 Tab"""
    section_header("繳費記錄", "📜")
    
    if 'current_period_id' not in st.session_state:
        info_card(
            "請先選擇計費期間",
            "請前往「計費期間」Tab 選擇一個期間",
            "⚠️",
            "warning"
        )
        return
    
    period_id = st.session_state.current_period_id
    
    try:
        # 取得繳費記錄
        df_records = db.get_electricity_payment_record(period_id)
        
        if df_records.empty:
            empty_state(
                "尚無繳費記錄",
                "📜",
                "完成計費後會顯示在這裡"
            )
        else:
            # 顯示記錄
            st.dataframe(df_records, use_container_width=True)
            
            # 繳費統計
            summary = db.get_electricity_payment_summary(period_id)
            
            st.divider()
            section_header("繳費統計", "📊", divider=False)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                metric_card("應收總額", f"${summary['total_due']:,.0f}", icon="💰")
            with col2:
                metric_card("已收金額", f"${summary['total_paid']:,.0f}", icon="✅")
            with col3:
                metric_card("未收金額", f"${summary['total_balance']:,.0f}", icon="⏳")
            with col4:
                metric_card("收款率", f"{summary['collection_rate']:.1f}%", icon="📈")
            
            # 更新繳費狀態
            st.divider()
            section_header("更新繳費狀態", "✏️", divider=False)
            
            col_room, col_status, col_btn = st.columns([2, 2, 1])
            with col_room:
                selected_room = st.selectbox(
                    "選擇房間",
                    df_records['房號'].tolist(),
                    key="update_room"
                )
            with col_status:
                new_status = st.selectbox(
                    "繳費狀態",
                    ["未繳", "已繳"],
                    key="update_status"
                )
            with col_btn:
                st.write("")
                st.write("")
                if st.button("💾 更新", type="primary"):
                    # 取得應繳金額
                    room_data = df_records[df_records['房號'] == selected_room].iloc[0]
                    paid_amount = room_data['應繳金額'] if new_status == "已繳" else 0
                    payment_date = date.today().strftime('%Y-%m-%d') if new_status == "已繳" else None
                    
                    ok, msg = db.update_electricity_payment(
                        period_id, 
                        selected_room, 
                        new_status,
                        paid_amount,
                        payment_date
                    )
                    
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    
    except Exception as e:
        st.error(f"❌ 載入記錄失敗: {e}")
