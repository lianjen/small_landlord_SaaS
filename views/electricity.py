"""
电费管理 - v3.0 完整版

✅ v2.9 修复：
  - 公用分摊显示为整数
  - 楼层摘要移除单价栏位
  - 增强储存提示

✅ v3.0 新增：
  - 电费账单通知功能（首次通知 + 自动催缴）
  - 催缴日期设定
  - LINE 通知发送
"""

import streamlit as st
import pandas as pd
from datetime import date
from typing import Dict, List
import logging
import requests

# 安全 import components
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
        if desc:
            st.caption(desc)
    
    def data_table(df, key="table"):
        st.dataframe(df, use_container_width=True, key=key)
    
    def info_card(title, content, icon="", type="info"):
        st.info(f"{icon} {title}: {content}")

# 安全 import constants
try:
    from config.constants import ROOMS
except ImportError:
    class ROOMS:
        ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
        SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
        EXCLUSIVE_ROOMS = ["1A", "1B"]

logger = logging.getLogger(__name__)


# ============== 楼层配置 ==============
FLOOR_CONFIG = {
    '1F': {
        'label': '1F 台电单',
        'rooms': ['1A', '1B'],
        'is_independent': True
    },
    '2F': {
        'label': '2F 台电单',
        'rooms': ['2A', '2B'],
        'is_independent': False
    },
    '3F': {
        'label': '3F 台电单',
        'rooms': ['3A', '3B', '3C', '3D'],
        'is_independent': False
    },
    '4F': {
        'label': '4F 台电单',
        'rooms': ['4A', '4B', '4C', '4D'],
        'is_independent': False
    }
}


# ============== 计算逻辑 ==============
def calculate_electricity_charges(
    taipower_bills: List[Dict],
    room_readings: Dict[str, float]
) -> Dict:
    """
    计算电费 - v3.0
    
    Args:
        taipower_bills: [{'floor_label': '1F', 'amount': 1000, 'kwh': 100}, ...]
        room_readings: {'1A': 50.5, '2A': 30.2, ...}
    
    Returns:
        计费结果字典
    """
    # === Step 1: 分离 1F 和 2F~4F ===
    floor_1f = None
    floors_2f_4f = []
    
    for bill in taipower_bills:
        if bill['floor_label'] == '1F':
            floor_1f = bill
        else:
            floors_2f_4f.append(bill)
    
    # === Step 2: 计算 2F~4F 合并数据 ===
    if floors_2f_4f:
        merged_amount = sum(bill['amount'] for bill in floors_2f_4f)
        merged_kwh = sum(bill['kwh'] for bill in floors_2f_4f)
        merged_unit_price = round(merged_amount / merged_kwh, 2) if merged_kwh > 0 else 0
    else:
        merged_amount = 0
        merged_kwh = 0
        merged_unit_price = 0
    
    # === Step 3: 计算 2A~4D 私用电与公用电 ===
    sharing_rooms_usage = sum(
        room_readings.get(room, 0)
        for room in ROOMS.SHARING_ROOMS
    )
    
    public_kwh = max(0, merged_kwh - sharing_rooms_usage)
    
    # === Step 4: 计算分摊（10间）===
    sharing_rooms_with_reading = [
        room for room in ROOMS.SHARING_ROOMS
        if room_readings.get(room, 0) > 0
    ]
    
    sharing_count = len(sharing_rooms_with_reading)
    shared_per_room = int(round(public_kwh / sharing_count)) if sharing_count > 0 else 0
    
    # === Step 5: 处理结果 ===
    results = []
    
    # --- 处理 1F (1A/1B) 完全独立 ---
    if floor_1f and floor_1f['kwh'] > 0:
        floor_1f_unit_price = round(floor_1f['amount'] / floor_1f['kwh'], 2)
        
        for room in ROOMS.EXCLUSIVE_ROOMS:
            kwh = room_readings.get(room, 0)
            if kwh <= 0:
                continue
            
            charge = round(kwh * floor_1f_unit_price)
            
            results.append({
                '楼层': '1F',
                '房号': room,
                '类型': '独立房间',
                '使用度数': round(kwh, 2),
                '公用分摊': 0,
                '总度数': round(kwh, 2),
                '单价': floor_1f_unit_price,
                '应缴金额': charge
            })
    
    # --- 处理 2F~4F (2A~4D) 分摊房间 ---
    for room in ROOMS.SHARING_ROOMS:
        kwh = room_readings.get(room, 0)
        if kwh <= 0:
            continue
        
        # 判断楼层
        if room in ['2A', '2B']:
            floor = '2F'
        elif room in ['3A', '3B', '3C', '3D']:
            floor = '3F'
        elif room in ['4A', '4B', '4C', '4D']:
            floor = '4F'
        else:
            floor = None
        
        shared_kwh = shared_per_room
        total_room_kwh = kwh + shared_kwh
        charge = round(total_room_kwh * merged_unit_price)
        
        results.append({
            '楼层': floor,
            '房号': room,
            '类型': '分摊房间',
            '使用度数': round(kwh, 2),
            '公用分摊': int(shared_kwh),
            '总度数': round(total_room_kwh, 2),
            '单价': merged_unit_price,
            '应缴金额': charge
        })
    
    # === Step 6: 计算总计 ===
    total_charge = sum(r['应缴金额'] for r in results)
    total_taipower = sum(bill['amount'] for bill in taipower_bills)
    
    # === Step 7: 生成楼层摘要 ===
    floor_summaries = []
    
    # 1F 摘要
    if floor_1f:
        floor_1f_results = [r for r in results if r['房号'] in ['1A', '1B']]
        if floor_1f_results:
            floor_summaries.append({
                'floor': '1F',
                'bill_amount': floor_1f['amount'],
                'bill_kwh': floor_1f['kwh'],
                'room_kwh': sum(r['使用度数'] for r in floor_1f_results),
                'unit_price': round(floor_1f['amount'] / floor_1f['kwh'], 2),
                'total_charge': sum(r['应缴金额'] for r in floor_1f_results)
            })
    
    # 2F~4F 摘要
    for bill in floors_2f_4f:
        floor_label = bill['floor_label']
        floor_rooms = FLOOR_CONFIG[floor_label]['rooms']
        floor_results = [r for r in results if r['房号'] in floor_rooms]
        
        if floor_results:
            floor_room_kwh = sum(r['使用度数'] for r in floor_results)
            floor_total_charge = sum(r['应缴金额'] for r in floor_results)
            
            floor_summaries.append({
                'floor': floor_label,
                'bill_amount': bill['amount'],
                'bill_kwh': bill['kwh'],
                'room_kwh': floor_room_kwh,
                'unit_price': merged_unit_price,
                'total_charge': floor_total_charge
            })
    
    return {
        'total_charge': total_charge,
        'taipower_amount': total_taipower,
        'difference': total_charge - total_taipower,
        'details': results,
        'floor_summaries': floor_summaries,
        'merged_unit_price': merged_unit_price,
        'total_public_kwh': public_kwh,
        'shared_per_room': shared_per_room,
        'merged_kwh': merged_kwh,
        'merged_amount': merged_amount
    }


# ============== Tab 1: 计费期间 ==============
def render_period_tab(db):
    """计费期间管理"""
    section_header("计费期间管理", "📅")
    
    # 建立新期间
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
            "开始月",
            range(1, 13),
            index=date.today().month - 1,
            key="period_start"
        )
    
    with col3:
        month_end = st.selectbox(
            "结束月",
            range(1, 13),
            index=date.today().month % 12,
            key="period_end"
        )
    
    with col4:
        st.write("")
        st.write("")
        if st.button("➕ 建立", type="primary"):
            if month_end <= month_start:
                st.error("❌ 结束月必须大于开始月")
            else:
                ok, msg, period_id = db.add_electricity_period(year, month_start, month_end)
                if ok:
                    st.success(msg)
                    st.session_state.current_period_id = period_id
                    st.rerun()
                else:
                    st.error(msg)
    
    st.divider()
    
    # 显示期间列表
    section_header("现有期间", "📋", divider=False)
    
    periods = db.get_all_periods()
    if not periods:
        empty_state("尚未建立期间", "📅", "请先建立一个计费期间")
        return
    
    # 选择期间
    period_options = {
        f"{p['period_year']}/{p['period_month_start']}-{p['period_month_end']} (ID: {p['id']})": p['id']
        for p in periods
    }
    
    selected = st.selectbox(
        "选择计费期间",
        list(period_options.keys()),
        key="selected_period"
    )
    
    if selected:
        period_id = period_options[selected]
        st.session_state.current_period_id = period_id
        
        col_del, col_info = st.columns([1, 3])
        
        with col_del:
            if st.button("🗑️ 删除期间", type="secondary"):
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
                    st.warning("⚠️ 再按一次确认删除")
        
        with col_info:
            st.info(f"✅ 当前选中: ID {period_id}")


# ============== Tab 2: 计算电费 ==============
def render_calculation_tab(db):
    """计算电费"""
    if 'current_period_id' not in st.session_state:
        info_card("请先选择期间", "请前往「计费期间」Tab 选择一个期间", "⚠️", "warning")
        return
    
    period_id = st.session_state.current_period_id
    st.info(f"📅 当前期间 ID: {period_id}")
    
    # 检查是否已有储存记录
    existing_records = db.get_electricity_payment_record(period_id)
    if existing_records is not None and not existing_records.empty:
        st.success(f"✅ 此期间已有 {len(existing_records)} 笔储存记录，可前往「📜 缴费记录」Tab 查看")
    
    st.divider()
    
    # === 步骤 1: 台电账单 ===
    section_header("步骤 1: 输入台电账单", "📄")
    st.caption("💡 提示：1F 独立计算 | 2F~4F 合并计算公用电并分摊给 2A~4D")
    
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
            
            if config['is_independent']:
                st.caption(f"🔒 独立：{', '.join(config['rooms'])}")
            else:
                st.caption(f"🔗 分摊：{', '.join(config['rooms'])}")
            
            amount = st.number_input(
                "金额 (元)",
                min_value=0,
                value=0,
                step=100,
                key=f"{floor_key}_amt",
                label_visibility="visible"
            )
            
            kwh = st.number_input(
                "度数",
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
    
    # 储存台电单
    if 'taipower_bills' not in st.session_state:
        st.session_state.taipower_bills = {}
    
    if st.button("💾 储存台电单", type="primary"):
        bills = [
            {
                'floor_label': floor_key,
                'amount': data['amount'],
                'kwh': data['kwh']
            }
            for floor_key, data in floor_data.items()
            if data['amount'] > 0 or data['kwh'] > 0
        ]
        
        if not bills:
            st.error("❌ 请至少输入一个楼层的台电单")
        else:
            st.session_state.taipower_bills[period_id] = bills
            st.success(f"✅ 已储存 {len(bills)} 个台电单")
            logger.info(f"Saved {len(bills)} taipower bills for period {period_id}")
    
    # 显示已储存的摘要
    if period_id in st.session_state.get('taipower_bills', {}):
        bills = st.session_state.taipower_bills[period_id]
        
        # 分离显示
        floor_1f_bill = next((b for b in bills if b['floor_label'] == '1F'), None)
        floors_2f_4f_bills = [b for b in bills if b['floor_label'] != '1F']
        
        st.divider()
        st.write("**已储存摘要:**")
        
        # 1F 独立显示
        if floor_1f_bill:
            col_1f = st.columns(1)[0]
            with col_1f:
                st.metric(
                    label="1F (独立)",
                    value=f"${floor_1f_bill['amount']:,}",
                    delta=f"{floor_1f_bill['kwh']:.0f} 度"
                )
        
        # 2F~4F 合并显示
        if floors_2f_4f_bills:
            merged_amt = sum(b['amount'] for b in floors_2f_4f_bills)
            merged_kwh = sum(b['kwh'] for b in floors_2f_4f_bills)
            
            summary_cols = st.columns(len(floors_2f_4f_bills) + 1)
            
            for idx, bill in enumerate(floors_2f_4f_bills):
                with summary_cols[idx]:
                    st.metric(
                        label=f"{bill['floor_label']}",
                        value=f"${bill['amount']:,}",
                        delta=f"{bill['kwh']:.0f} 度"
                    )
            
            with summary_cols[-1]:
                st.metric(
                    label="**2-4F 合计**",
                    value=f"${merged_amt:,}",
                    delta=f"{merged_kwh:.0f} 度"
                )
    
    st.divider()
    
    # === 步骤 2: 房间读数 ===
    section_header("步骤 2: 输入房间读数", "🔢")
    st.caption("💡 提示：首次输入时上期可编辑，之后自动带入上次读数并锁定。")
    
    room_readings = {}
    raw_readings = {}
    
    # 按楼层分组显示
    for floor_key, config in FLOOR_CONFIG.items():
        st.markdown(f"### {config['label']}")
        
        floor_rooms = config['rooms']
        cols = st.columns(len(floor_rooms))
        
        for col, room in zip(cols, floor_rooms):
            with col:
                st.markdown(f"**{room}**")
                
                # 取得上次读数
                last_reading = db.get_latest_meter_reading(room, period_id)
                is_first_time = (last_reading is None or last_reading == 0)
                
                if is_first_time:
                    previous = st.number_input(
                        "上期 📊",
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                        key=f"prev_{room}",
                        help="首次输入，请输入起始读数",
                        disabled=False
                    )
                else:
                    previous_value = float(last_reading)
                    st.number_input(
                        "上期 📊",
                        min_value=0.0,
                        value=previous_value,
                        step=1.0,
                        key=f"prev_{room}",
                        help="自动带入上次读数（不可修改）",
                        disabled=True
                    )
                    previous = previous_value
                
                current = st.number_input(
                    "本期 📈",
                    min_value=previous,
                    value=previous,
                    step=1.0,
                    key=f"curr_{room}",
                    help="本次抄表的读数"
                )
                
                usage = current - previous
                
                if usage > 0:
                    st.success(f"⚡ 用电 {usage:.1f} 度")
                elif usage == 0 and current > 0:
                    st.info("📊 读数无变化")
                else:
                    st.caption("⚪ 等待输入")
                
                room_readings[room] = usage
                raw_readings[room] = {
                    'previous': previous,
                    'current': current
                }
        
        st.divider()
    
    # 储存读数
    if st.button("💾 储存读数", type="primary"):
        if 'room_readings' not in st.session_state:
            st.session_state.room_readings = {}
        if 'raw_readings' not in st.session_state:
            st.session_state.raw_readings = {}
        
        st.session_state.room_readings[period_id] = room_readings
        st.session_state.raw_readings[period_id] = raw_readings
        
        save_count = 0
        for room, usage in room_readings.items():
            raw = raw_readings[room]
            ok, msg = db.save_electricity_reading(
                period_id, room, raw['previous'], raw['current'], usage
            )
            if ok:
                save_count += 1
        
        st.success(f"✅ 已储存 {save_count} 笔读数到数据库")
        logger.info(f"Saved {save_count} meter readings for period {period_id}")
    
    st.divider()
    
    # === 步骤 3: 计算 ===
    section_header("步骤 3: 计算电费", "🧮")
    
    # 计算按钮
    if st.button("🚀 开始计算", type="primary"):
        bills = st.session_state.get('taipower_bills', {}).get(period_id)
        readings = st.session_state.get('room_readings', {}).get(period_id)
        raw = st.session_state.get('raw_readings', {}).get(period_id)
        
        if not bills:
            st.error("❌ 请先输入台电账单")
            return
        
        if not readings or all(v == 0 for v in readings.values()):
            st.error("❌ 请先输入房间读数")
            return
        
        # 计算
        result = calculate_electricity_charges(bills, readings)
        
        if not result:
            st.error("❌ 计算失败")
            return
        
        # 储存计算结果到 session_state
        enriched_details = []
        for detail in result['details']:
            room = detail['房号']
            detail['previous_reading'] = raw[room]['previous']
            detail['current_reading'] = raw[room]['current']
            
            # 添加简体中文栏位别名（兼容 db.py）
            detail['房號'] = detail.get('房号', '')
            detail['楼层'] = detail.get('楼层', '')
            detail['類型'] = detail.get('类型', '')
            detail['使用度数'] = detail.get('使用度数', 0)
            detail['使用度數'] = detail.get('使用度数', 0)
            detail['公用分摊'] = detail.get('公用分摊', 0)
            detail['公用分攤'] = detail.get('公用分摊', 0)
            detail['总度数'] = detail.get('总度数', 0)
            detail['總度數'] = detail.get('总度数', 0)
            detail['单价'] = detail.get('单价', 0)
            detail['單價'] = detail.get('单价', 0)
            detail['应缴金额'] = detail.get('应缴金额', 0)
            detail['應繳金額'] = detail.get('应缴金额', 0)
            
            enriched_details.append(detail)
        
        # 储存到 session_state
        st.session_state[f'calc_result_{period_id}'] = result
        st.session_state[f'calc_details_{period_id}'] = enriched_details
        
        logger.info(f"Calculated electricity for period {period_id}: {len(enriched_details)} rooms")
        st.success("✅ 计算完成！结果已生成")
        st.rerun()
    
    # 显示计算结果（从 session_state 读取）
    result = st.session_state.get(f'calc_result_{period_id}')
    enriched_details = st.session_state.get(f'calc_details_{period_id}')
    
    if result and enriched_details:
        # 显示关键资讯
        st.markdown("### 📊 计算摘要")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("2-4F 合计", f"{result['merged_kwh']:.0f} 度")
        with col2:
            st.metric("总公用电", f"{result['total_public_kwh']:.0f} 度")
        with col3:
            st.metric("每间分摊", f"{result['shared_per_room']} 度")
        with col4:
            st.metric("2-4F 单价", f"${result['merged_unit_price']:.2f}/度")
        
        st.divider()
        
        # 显示楼层摘要（移除单价栏位）
        st.markdown("### 📊 各楼层摘要")
        for floor_summary in result['floor_summaries']:
            with st.expander(
                f"**{floor_summary['floor']}** - 台电: ${floor_summary['bill_amount']:,} | 收费: ${floor_summary['total_charge']:,}",
                expanded=True
            ):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("台电度数", f"{floor_summary['bill_kwh']:.0f} 度")
                
                with col2:
                    st.metric("房间用电", f"{floor_summary['room_kwh']:.0f} 度")
        
        st.divider()
        
        # 显示总计
        st.markdown(f"""
### 💰 总计
- **台电总金额**: ${result['taipower_amount']:,} 元
- **收费总金额**: ${result['total_charge']:,} 元
- **差异**: ${result['difference']:+,.0f} 元
        """)
        
        st.divider()
        
        # 显示明细
        st.write("**各房间明细**")
        details_df = pd.DataFrame(enriched_details)
        
        column_order = ['楼层', '房号', '类型', 'previous_reading', 'current_reading',
                       '使用度数', '公用分摊', '总度数', '单价', '应缴金额']
        details_df = details_df[column_order]
        
        # 格式化公用分摊为整数显示
        details_df['公用分摊'] = details_df['公用分摊'].astype(int)
        
        details_df.columns = ['楼层', '房号', '类型', '上期读数', '本期读数',
                             '使用度数', '公用分摊', '总度数', '单价', '应缴金额']
        
        data_table(details_df, key="calc_details")
        
        # 储存和下载按钮
        st.divider()
        col_save, col_download = st.columns([1, 1])
        
        with col_save:
            if st.button("💾 储存计费结果到数据库", type="primary"):
                try:
                    logger.info(f"Starting save for period {period_id}, {len(enriched_details)} records")
                    
                    ok, msg = db.save_electricity_record(period_id, enriched_details)
                    
                    if ok:
                        st.success("✅ " + msg)
                        
                        # 增强提示讯息
                        st.info(f"""
📍 **储存位置说明：**
- **数据库表格**: `electricity_records` (计费记录)
- **数据库表格**: `electricity_readings` (电表读数)
- **期间ID**: {period_id}
- **记录笔数**: {len(enriched_details)} 笔

🔍 **查看方式：**
1. 点击上方「📜 缴费记录」Tab
2. 确认当前期间 ID: {period_id}
3. 即可查看所有储存的计费记录
                        """)
                        
                        st.balloons()
                        logger.info(f"Successfully saved {len(enriched_details)} records to database")
                        
                        # 清除计算结果
                        if f'calc_result_{period_id}' in st.session_state:
                            del st.session_state[f'calc_result_{period_id}']
                        if f'calc_details_{period_id}' in st.session_state:
                            del st.session_state[f'calc_details_{period_id}']
                    else:
                        st.error(f"❌ 储存失败：{msg}")
                        logger.error(f"Save failed: {msg}")
                        
                except Exception as e:
                    st.error(f"❌ 储存时发生错误：{str(e)}")
                    logger.exception(f"Exception during save: {e}")
        
        with col_download:
            csv = details_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "📥 下载 CSV 备份",
                csv,
                f"electricity_{period_id}.csv",
                "text/csv"
            )
        
        # ===== ✨ v3.0 新增：账单通知功能 =====
        st.divider()
        st.markdown("### 📢 账单通知设定")
        
        col_settings, col_notify = st.columns([2, 1])
        
        with col_settings:
            # 自动计算预设的催缴日期 (下个月 1 号)
            today = date.today()
            next_month = today.month + 1 if today.month < 12 else 1
            next_year = today.year if today.month < 12 else today.year + 1
            default_remind_start = date(next_year, next_month, 1)
            
            remind_date = st.date_input(
                "📅 自动催缴开始日期 (从这天起每天通知)", 
                value=default_remind_start,
                help="设定后，系统会从这天开始自动发送催缴通知给未缴租客",
                key="remind_date_input"
            )
            
            st.caption(f"💡 系统将于 **{remind_date.strftime('%Y年%m月%d日')}** 开始自动发送催缴通知")
        
        with col_notify:
            st.write("")
            st.write("")
            if st.button("📨 发送首次账单通知", type="primary", help="立即发送 LINE 通知给所有租客"):
                # 1. 更新 DB 的催缴开始日
                ok, msg = db.update_electricity_period_remind_date(period_id, remind_date.isoformat())
                if ok:
                    st.success(f"✅ 已设定催缴日期: {remind_date.strftime('%Y-%m-%d')}")
                else:
                    st.warning(f"⚠️ 催缴日期设定: {msg}")
                
                # 2. 呼叫 Edge Function 发送通知
                try:
                    # 检查是否有 Supabase 配置
                    if 'SUPABASE_URL' not in st.secrets or 'SUPABASE_ANON_KEY' not in st.secrets:
                        st.error("❌ 缺少 Supabase 配置（SUPABASE_URL 或 SUPABASE_ANON_KEY）")
                    else:
                        with st.spinner("正在发送 LINE 通知..."):
                            API_URL = f"{st.secrets['SUPABASE_URL']}/functions/v1/send-electricity-bill"
                            headers = {
                                "Authorization": f"Bearer {st.secrets['SUPABASE_ANON_KEY']}",
                                "Content-Type": "application/json"
                            }
                            payload = {
                                "period_id": period_id,
                                "action": "first_notify"
                            }
                            
                            response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
                            
                            if response.status_code == 200:
                                result_data = response.json()
                                notified = result_data.get('notified_count', 0)
                                st.success(f"✅ 发送成功！已通知 {notified} 位租客")
                                st.balloons()
                                logger.info(f"Sent {notified} notifications for period {period_id}")
                            else:
                                st.error(f"❌ 发送失败: {response.text}")
                                logger.error(f"Notification failed: {response.text}")
                
                except requests.exceptions.Timeout:
                    st.error("❌ 连线逾时，请稍后再试")
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ 连线错误: {e}")
                except Exception as e:
                    st.error(f"❌ 发生错误: {e}")
                    logger.exception(f"Exception during notification: {e}")


# ============== Tab 3: 缴费记录 ==============
def render_records_tab(db):
    """缴费记录"""
    section_header("缴费记录", "📜")
    
    if 'current_period_id' not in st.session_state:
        info_card("请先选择期间", "请前往「计费期间」Tab 选择一个期间", "⚠️", "warning")
        return
    
    period_id = st.session_state.current_period_id
    
    # 显示当前期间资讯
    st.info(f"📅 当前查询期间 ID: {period_id}")
    
    # 加入 debug 资讯
    with st.spinner("正在从数据库查询记录..."):
        df = db.get_electricity_payment_record(period_id)
        logger.info(f"Query result for period {period_id}: {len(df) if df is not None else 0} records")
    
    if df is None or df.empty:
        empty_state(
            "尚无记录",
            "📭",
            f"请先在「计算电费」Tab 完成计算并按「💾 储存计费结果到数据库」\n\n当前期间 ID: {period_id}"
        )
        return
    
    # 显示记录数量
    st.success(f"✅ 已找到 {len(df)} 笔计费记录")
    
    summary = db.get_electricity_payment_summary(period_id)
    if summary:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            metric_card("应收总额", f"${summary.get('total_due', 0):,}", "💰", "normal")
        
        with col2:
            metric_card("已收金额", f"${summary.get('total_paid', 0):,}", "✅", "success")
        
        with col3:
            metric_card("未收金额", f"${summary.get('total_balance', 0):,}", "⚠️", "warning")
    
    st.divider()
    
    st.write(f"**共 {len(df)} 笔记录**")
    data_table(df, key="payment_records")
    
    st.divider()
    
    section_header("快速标记", "⚡", divider=False)
    
    unpaid_df = df[df['缴费状态'] == '⏳ 未缴']
    
    if not unpaid_df.empty:
        for idx, row in unpaid_df.iterrows():
            col_info, col_btn = st.columns([4, 1])
            
            with col_info:
                # 提取金额数字
                amount_str = str(row.get('应缴金额', '0'))
                amount = int(amount_str.replace('$', '').replace(',', ''))
                st.write(f"**{row['房号']}** | ${amount:,} 元")
            
            with col_btn:
                if st.button("✅", key=f"pay_{idx}"):
                    ok, msg = db.update_electricity_payment(
                        period_id,
                        row['房号'],
                        'paid',
                        amount,
                        date.today().isoformat()
                    )
                    if ok:
                        st.success("✅ 已标记为已缴")
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        st.success("✅ 全部已缴清")


# ============== 主函数 ==============
def render(db):
    """主渲染函数"""
    st.title("⚡ 电费管理")
    
    tab1, tab2, tab3 = st.tabs(["📅 计费期间", "🧮 计算电费", "📜 缴费记录"])
    
    with tab1:
        render_period_tab(db)
    
    with tab2:
        render_calculation_tab(db)
    
    with tab3:
        render_records_tab(db)
