"""
電費管理 - v2.3 完整版
支援 1F / 2F / 3F / 4F 分開計算
修復：首次輸入可編輯上期，第二次後自動鎖定
"""

import streamlit as st
import pandas as pd
from datetime import date
from typing import Dict, List
import logging

# 安全 import
try:
    from components.cards import section_header, metric_card, empty_state, data_table, info_card
except ImportError:
    def section_header(title, icon="", divider=True):
        st.markdown(f"### {icon} {title}")
        if divider:
            st.divider()
    
    def metric_card(label, value, icon="", color="normal"):
        st.metric(label, value)
    
    def empty_state(msg, icon="", desc=""):
        st.info(f"{icon} {msg}")
    
    def data_table(df, key="table"):
        st.dataframe(df, width='stretch', key=key)
    
    def info_card(title, content, icon="", type="info"):
        st.info(f"{icon} {title}: {content}")

try:
    from config.constants import ROOMS
except ImportError:
    class ROOMS:
        ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
        SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
        EXCLUSIVE_ROOMS = ["1A", "1B"]

logger = logging.getLogger(__name__)

# ============== 樓層配置 ==============

FLOOR_CONFIG = {
    '1F': {
        'label': '1F 台電單',
        'rooms': ['1A', '1B']
    },
    '2F': {
        'label': '2F 台電單',
        'rooms': ['2A', '2B']
    },
    '3F': {
        'label': '3F 台電單',
        'rooms': ['3A', '3B', '3C', '3D']
    },
    '4F': {
        'label': '4F 台電單',
        'rooms': ['4A', '4B', '4C', '4D']
    }
}

# ============== 計算邏輯 ==============

def calculate_electricity_charges(
    taipower_bills: List[Dict],
    room_readings: Dict[str, float]
) -> Dict:
    """
    計算電費 - 改良版：支援多樓層獨立計算
    
    Args:
        taipower_bills: [{'floor_label': '1F', 'amount': 1000, 'kwh': 100}, ...]
        room_readings: {'1A': 50.5, '2A': 30.2, ...}
    
    Returns:
        計費結果字典
    """
    # 計算總計
    total_amount = sum(bill['amount'] for bill in taipower_bills)
    total_kwh = sum(bill['kwh'] for bill in taipower_bills)
    
    if total_kwh <= 0:
        return None
    
    # 按樓層分組計算
    results = []
    floor_summaries = []
    
    for bill in taipower_bills:
        floor_label = bill['floor_label']
        floor_amount = bill['amount']
        floor_kwh = bill['kwh']
        
        if floor_kwh <= 0:
            continue
        
        # 該樓層的房間
        floor_rooms = FLOOR_CONFIG[floor_label]['rooms']
        
        # 該樓層房間的總度數
        floor_room_kwh = sum(room_readings.get(room, 0) for room in floor_rooms)
        
        # 公用電
        public_kwh = max(0, floor_kwh - floor_room_kwh)
        
        # 單位電價
        unit_price = round(floor_amount / floor_kwh, 2)
        
        # 分攤房間數（只計算該樓層有讀數的房間）
        sharing_rooms = [r for r in floor_rooms if room_readings.get(r, 0) > 0 and r in ROOMS.SHARING_ROOMS]
        sharing_count = len(sharing_rooms)
        
        # 每間分攤
        shared_per_room = round(public_kwh / sharing_count, 2) if sharing_count > 0 else 0
        
        # 計算該樓層各房間
        floor_total_charge = 0
        for room in floor_rooms:
            kwh = room_readings.get(room, 0)
            
            if kwh <= 0:
                continue
            
            is_sharing = room in ROOMS.SHARING_ROOMS
            room_type = "分攤房間" if is_sharing else "獨立房間"
            shared_kwh = shared_per_room if is_sharing else 0
            total_room_kwh = kwh + shared_kwh
            charge = round(total_room_kwh * unit_price)
            
            floor_total_charge += charge
            
            results.append({
                '樓層': floor_label,
                '房號': room,
                '類型': room_type,
                '使用度數': round(kwh, 2),
                '公用分攤': round(shared_kwh, 2),
                '總度數': round(total_room_kwh, 2),
                '應繳金額': charge
            })
        
        # 記錄樓層摘要
        floor_summaries.append({
            'floor': floor_label,
            'bill_amount': floor_amount,
            'bill_kwh': floor_kwh,
            'room_kwh': floor_room_kwh,
            'public_kwh': public_kwh,
            'unit_price': unit_price,
            'total_charge': floor_total_charge,
            'difference': floor_total_charge - floor_amount
        })
    
    total_charge = sum(r['應繳金額'] for r in results)
    
    return {
        'total_charge': total_charge,
        'taipower_amount': total_amount,
        'difference': total_charge - total_amount,
        'details': results,
        'floor_summaries': floor_summaries
    }

# ============== Tab 1: 計費期間 ==============

def render_period_tab(db):
    """計費期間管理"""
    section_header("計費期間管理", "📅")
    
    # 建立新期間
    col1, col2, col3, col4 = st.columns(4)
    
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
            "開始月",
            range(1, 13),
            index=date.today().month - 1,
            key="period_start"
        )
    
    with col3:
        month_end = st.selectbox(
            "結束月",
            range(1, 13),
            index=date.today().month % 12,
            key="period_end"
        )
    
    with col4:
        st.write("")
        st.write("")
        if st.button("➕ 建立", type="primary"):
            if month_end <= month_start:
                st.error("❌ 結束月必須大於開始月")
            else:
                ok, msg, period_id = db.add_electricity_period(year, month_start, month_end)
                if ok:
                    st.success(msg)
                    st.session_state.current_period_id = period_id
                    st.rerun()
                else:
                    st.error(msg)
    
    st.divider()
    
    # 顯示期間列表
    section_header("現有期間", "📋", divider=False)
    periods = db.get_all_periods()
    
    if not periods:
        empty_state("尚未建立期間", "📅", "請先建立一個計費期間")
        return
    
    # 選擇期間
    period_options = {
        f"{p['period_year']}/{p['period_month_start']}-{p['period_month_end']} (ID: {p['id']})": p['id']
        for p in periods
    }
    
    selected = st.selectbox(
        "選擇計費期間",
        list(period_options.keys()),
        key="selected_period"
    )
    
    if selected:
        period_id = period_options[selected]
        st.session_state.current_period_id = period_id
        
        col_del, col_info = st.columns([1, 3])
        
        with col_del:
            if st.button("🗑️ 刪除期間", type="secondary"):
                if st.session_state.get('confirm_delete_period'):
                    ok, msg = db.delete_electricity_period(period_id)
                    if ok:
                        st.success(msg)
                        if 'current_period_id' in st.session_state:
                            del st.session_state.current_period_id
                        del st.session_state.confirm_delete_period
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.session_state.confirm_delete_period = True
                    st.warning("⚠️ 再按一次確認刪除")
        
        with col_info:
            st.info(f"✅ 當前選中: ID {period_id}")

# ============== Tab 2: 計算電費 ==============

def render_calculation_tab(db):
    """計算電費"""
    if 'current_period_id' not in st.session_state:
        info_card("請先選擇期間", "請前往「計費期間」Tab 選擇一個期間", "⚠️", "warning")
        return
    
    period_id = st.session_state.current_period_id
    st.info(f"📅 當前期間 ID: {period_id}")
    st.divider()
    
    # === 步驟 1: 台電帳單（4 個獨立台電單） ===
    section_header("步驟 1: 輸入台電帳單", "📄")
    
    st.caption("💡 提示：每個樓層分別輸入台電單，公用電會自動分攤到該樓層房間")
    
    # 使用 2x2 排列
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)
    
    cols_map = {
        '1F': row1_col1,
        '2F': row1_col2,
        '3F': row2_col1,
        '4F': row2_col2
    }
    
    floor_data = {}
    
    for floor_key, config in FLOOR_CONFIG.items():
        with cols_map[floor_key]:
            st.markdown(f"**{config['label']}**")
            st.caption(f"房間：{', '.join(config['rooms'])}")
            
            amount = st.number_input(
                "金額 (元)", 
                min_value=0, 
                value=0, 
                step=100, 
                key=f"{floor_key}_amt",
                label_visibility="visible"
            )
            
            kwh = st.number_input(
                "度數", 
                min_value=0.0, 
                value=0.0, 
                step=10.0, 
                format="%.2f",
                key=f"{floor_key}_kwh",
                label_visibility="visible"
            )
            
            floor_data[floor_key] = {
                'amount': amount,
                'kwh': kwh
            }
    
    # 儲存台電單
    if 'taipower_bills' not in st.session_state:
        st.session_state.taipower_bills = {}
    
    if st.button("💾 儲存台電單", type="primary"):
        bills = [
            {
                'floor_label': floor_key,
                'amount': data['amount'],
                'kwh': data['kwh']
            }
            for floor_key, data in floor_data.items()
            if data['amount'] > 0 or data['kwh'] > 0  # 只儲存有輸入的
        ]
        
        if not bills:
            st.error("❌ 請至少輸入一個樓層的台電單")
        else:
            st.session_state.taipower_bills[period_id] = bills
            st.success(f"✅ 已儲存 {len(bills)} 個台電單")
    
    # 顯示已儲存的摘要
    if period_id in st.session_state.get('taipower_bills', {}):
        bills = st.session_state.taipower_bills[period_id]
        total_amt = sum(b['amount'] for b in bills)
        total_kwh = sum(b['kwh'] for b in bills)
        
        st.divider()
        st.write("**已儲存摘要:**")
        
        summary_cols = st.columns(len(bills) + 1)
        
        # 各樓層摘要
        for idx, bill in enumerate(bills):
            with summary_cols[idx]:
                st.metric(
                    label=f"{bill['floor_label']}",
                    value=f"${bill['amount']:,}",
                    delta=f"{bill['kwh']:.0f} 度"
                )
        
        # 總計
        with summary_cols[-1]:
            st.metric(
                label="**總計**",
                value=f"${total_amt:,}",
                delta=f"{total_kwh:.0f} 度"
            )
    
    st.divider()
    
    # === 步驟 2: 房間讀數（智能鎖定版） ===
    section_header("步驟 2: 輸入房間讀數", "🔢")
    
    st.caption("💡 提示：首次輸入時上期可編輯，之後自動帶入上次讀數並鎖定。")
    
    room_readings = {}
    raw_readings = {}
    
    # 按樓層分組顯示
    for floor_key, config in FLOOR_CONFIG.items():
        st.markdown(f"### {config['label']}")
        
        floor_rooms = config['rooms']
        cols = st.columns(len(floor_rooms))
        
        for col, room in zip(cols, floor_rooms):
            with col:
                st.markdown(f"**{room}**")
                
                # 🔍 取得上次讀數（作為本次的上期）
                last_reading = db.get_latest_meter_reading(room, period_id)
                
                # 🎯 判斷是否為首次輸入
                is_first_time = (last_reading is None or last_reading == 0)
                
                if is_first_time:
                    # 🆕 首次輸入：上期可編輯
                    previous = st.number_input(
                        "上期 📊",
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                        key=f"prev_{room}",
                        help="首次輸入，請輸入起始讀數",
                        disabled=False  # ✅ 可編輯
                    )
                else:
                    # 🔒 非首次：上期鎖定
                    previous_value = float(last_reading)
                    st.number_input(
                        "上期 📊",
                        min_value=0.0,
                        value=previous_value,
                        step=1.0,
                        key=f"prev_{room}",
                        help="自動帶入上次讀數（不可修改）",
                        disabled=True  # 🔒 鎖定
                    )
                    previous = previous_value
                
                # 本期讀數（必須 >= 上期）
                current = st.number_input(
                    "本期 📈",
                    min_value=previous,
                    value=previous,
                    step=1.0,
                    key=f"curr_{room}",
                    help="本次抄表的讀數"
                )
                
                # 計算用電度數
                usage = current - previous
                
                # 顯示狀態
                if usage > 0:
                    st.success(f"⚡ 用電 {usage:.1f} 度")
                elif usage == 0 and current > 0:
                    st.info("📊 讀數無變化")
                else:
                    st.caption("⚪ 等待輸入")
                
                # 儲存數據
                room_readings[room] = usage
                raw_readings[room] = {
                    'previous': previous,
                    'current': current
                }
        
        st.divider()
    
    # 儲存讀數
    if st.button("💾 儲存讀數", type="primary"):
        if 'room_readings' not in st.session_state:
            st.session_state.room_readings = {}
        if 'raw_readings' not in st.session_state:
            st.session_state.raw_readings = {}
        
        st.session_state.room_readings[period_id] = room_readings
        st.session_state.raw_readings[period_id] = raw_readings
        
        # 儲存到資料庫
        save_count = 0
        for room, usage in room_readings.items():
            raw = raw_readings[room]
            ok, msg = db.save_electricity_reading(
                period_id, room, raw['previous'], raw['current'], usage
            )
            if ok:
                save_count += 1
        
        st.success(f"✅ 已儲存 {save_count} 筆讀數")
    
    st.divider()
    
    # === 步驟 3: 計算 ===
    section_header("步驟 3: 計算電費", "🧮")
    
    if st.button("🚀 開始計算", type="primary"):
        bills = st.session_state.get('taipower_bills', {}).get(period_id)
        readings = st.session_state.get('room_readings', {}).get(period_id)
        raw = st.session_state.get('raw_readings', {}).get(period_id)
        
        if not bills:
            st.error("❌ 請先輸入台電帳單")
            return
        
        if not readings or all(v == 0 for v in readings.values()):
            st.error("❌ 請先輸入房間讀數")
            return
        
        # 計算
        result = calculate_electricity_charges(bills, readings)
        
        if not result:
            st.error("❌ 計算失敗")
            return
        
        # 顯示樓層摘要
        st.markdown("### 📊 各樓層摘要")
        
        for floor_summary in result['floor_summaries']:
            with st.expander(f"**{floor_summary['floor']}** - 台電: ${floor_summary['bill_amount']:,} | 收費: ${floor_summary['total_charge']:,}", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("台電度數", f"{floor_summary['bill_kwh']:.0f} 度")
                
                with col2:
                    st.metric("房間用電", f"{floor_summary['room_kwh']:.0f} 度")
                
                with col3:
                    st.metric("公用電", f"{floor_summary['public_kwh']:.0f} 度")
                
                with col4:
                    st.metric("單價", f"${floor_summary['unit_price']:.2f}/度")
                
                st.caption(f"收費差異: ${floor_summary['difference']:+,.0f}")
        
        st.divider()
        
        # 顯示總計
        st.markdown(f"""
### 💰 總計

- **台電總金額**: ${result['taipower_amount']:,} 元
- **收費總金額**: ${result['total_charge']:,} 元
- **差異**: ${result['difference']:+,.0f} 元
""")
        
        st.divider()
        
        # 顯示明細
        st.write("**各房間明細**")
        
        # 加入原始讀數
        enriched_details = []
        for detail in result['details']:
            room = detail['房號']
            detail['previous_reading'] = raw[room]['previous']
            detail['current_reading'] = raw[room]['current']
            enriched_details.append(detail)
        
        details_df = pd.DataFrame(enriched_details)
        
        # 重新排序欄位
        column_order = ['樓層', '房號', '類型', 'previous_reading', 'current_reading', 
                       '使用度數', '公用分攤', '總度數', '應繳金額']
        details_df = details_df[column_order]
        details_df.columns = ['樓層', '房號', '類型', '上期讀數', '本期讀數', 
                             '使用度數', '公用分攤', '總度數', '應繳金額']
        
        data_table(details_df, key="calc_details")
        
        # 儲存結果
        st.divider()
        if st.button("💾 儲存計費結果", type="primary"):
            ok, msg = db.save_electricity_record(period_id, enriched_details)
            if ok:
                st.success(msg)
                st.balloons()
            else:
                st.error(msg)
        
        # 匯出
        csv = details_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 下載 CSV",
            csv,
            f"electricity_{period_id}.csv",
            "text/csv"
        )

# ============== Tab 3: 繳費記錄 ==============

def render_records_tab(db):
    """繳費記錄"""
    section_header("繳費記錄", "📜")
    
    if 'current_period_id' not in st.session_state:
        info_card("請先選擇期間", "請前往「計費期間」Tab 選擇一個期間", "⚠️", "warning")
        return
    
    period_id = st.session_state.current_period_id
    
    # 取得記錄
    df = db.get_electricity_payment_record(period_id)
    
    if df is None or df.empty:
        empty_state("尚無記錄", "📭", "請先在「計算電費」Tab 完成計算並儲存")
        return
    
    # 顯示統計
    summary = db.get_electricity_payment_summary(period_id)
    
    if summary:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            metric_card("應收總額", f"${summary.get('total_due', 0):,}", "💰", "normal")
        
        with col2:
            metric_card("已收金額", f"${summary.get('total_paid', 0):,}", "✅", "success")
        
        with col3:
            metric_card("未收金額", f"${summary.get('total_balance', 0):,}", "⚠️", "warning")
    
    st.divider()
    
    # 顯示記錄
    st.write(f"共 {len(df)} 筆記錄")
    data_table(df, key="payment_records")
    
    # 快速更新
    st.divider()
    section_header("快速標記", "⚡", divider=False)
    
    unpaid_df = df[df['payment_status'] == 'unpaid']
    
    if not unpaid_df.empty:
        for idx, row in unpaid_df.iterrows():
            col_info, col_btn = st.columns([4, 1])
            
            with col_info:
                st.write(f"**{row['room_number']}** | ${row['amount_due']:,} 元")
            
            with col_btn:
                if st.button("✅", key=f"pay_{idx}"):
                    ok, msg = db.update_electricity_payment(
                        period_id,
                        row['room_number'],
                        'paid',
                        row['amount_due'],
                        date.today().isoformat()
                    )
                    if ok:
                        st.success("✅")
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        st.success("✅ 全部已繳清")

# ============== 主函數 ==============

def render(db):
    """主渲染函數"""
    st.title("⚡ 電費管理")
    
    tab1, tab2, tab3 = st.tabs(["📅 計費期間", "🧮 計算電費", "📜 繳費記錄"])
    
    with tab1:
        render_period_tab(db)
    
    with tab2:
        render_calculation_tab(db)
    
    with tab3:
        render_records_tab(db)
