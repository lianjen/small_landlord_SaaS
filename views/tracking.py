"""
追蹤功能頁面
- 租金繳費追蹤
- 批量標記已付款
- 統計與圖表
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import logging

# 導入組件
try:
    from components.cards import section_header, metric_card, empty_state, data_table, info_card
except ImportError:
    def section_header(title, icon, divider=True):
        st.markdown(f"{icon} {title}")
        if divider:
            st.divider()
    
    def metric_card(label, value, delta, icon, color="normal"):
        st.metric(label, value, delta)
    
    def empty_state(msg, icon, desc):
        st.info(f"{icon} {msg}")
    
    def data_table(df, key="table"):
        st.dataframe(df, use_container_width=True, key=key)
    
    def info_card(title, content, icon, type="info"):
        st.info(f"{icon} {title}\n\n{content}")

try:
    from config.constants import ROOMS
except ImportError:
    class ROOMS:
        ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]

logger = logging.getLogger(__name__)


def get_overdue_days(due_date) -> int:
    """計算逾期天數"""
    if pd.isna(due_date):
        return 0
    
    try:
        if isinstance(due_date, str):
            due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
        elif isinstance(due_date, datetime):
            due_date = due_date.date()
        
        today = date.today()
        delta = (today - due_date).days
        return max(0, delta)
    except:
        return 0


def categorize_payment_status(row) -> str:
    """分類付款狀態"""
    if row['status'] == 'paid':
        return '已繳費'
    
    overdue_days = get_overdue_days(row.get('due_date'))
    
    if overdue_days >= 7:
        return '嚴重逾期'
    elif overdue_days > 0:
        return '逾期'
    else:
        return '未繳費'


def render(db):
    st.title("📝 追蹤功能")
    
    # 篩選條件
    section_header("🔍 篩選條件", "", divider=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_year = st.selectbox(
            "年份",
            [None] + list(range(2020, 2031)),
            format_func=lambda x: "全部" if x is None else str(x),
            index=(date.today().year - 2020 + 1) if date.today().year >= 2020 else 0,
            key="track_year"
        )
    
    with col2:
        filter_month = st.selectbox(
            "月份",
            [None] + list(range(1, 13)),
            format_func=lambda x: "全部" if x is None else str(x),
            key="track_month"
        )
    
    with col3:
        filter_status = st.selectbox(
            "狀態",
            [None, "unpaid", "paid"],
            format_func=lambda x: "全部" if x is None else "未付款" if x == "unpaid" else "已付款",
            key="track_status"
        )
    
    with col4:
        filter_rooms = st.multiselect(
            "房號",
            ROOMS.ALL_ROOMS,
            key="track_rooms"
        )
    
    # 進階篩選
    with st.expander("📊 進階篩選", expanded=False):
        cola, colb, colc = st.columns(3)
        
        with cola:
            filter_amount_min = st.number_input("最低金額", min_value=0, value=0, step=1000, key="track_amt_min")
        
        with colb:
            filter_amount_max = st.number_input("最高金額", min_value=0, value=0, step=1000, help="0 表示不限", key="track_amt_max")
        
        with colc:
            filter_overdue_only = st.checkbox("只顯示逾期", value=False, key="track_overdue")
    
    st.divider()
    
    # 查詢資料
    try:
        df = db.get_payment_schedule(year=filter_year, month=filter_month, status=filter_status)
    except Exception as e:
        st.error(f"查詢失敗: {e}")
        return
    
    if df.empty:
        empty_state("查無資料", "📭", "")
        return
    
    # 應用房號篩選
    if filter_rooms:
        df = df[df['room_number'].isin(filter_rooms)]
    
    # 應用金額篩選
    if filter_amount_min > 0:
        df = df[df['amount'] >= filter_amount_min]
    if filter_amount_max > 0:
        df = df[df['amount'] <= filter_amount_max]
    
    # 計算逾期天數
    df['overdue_days'] = df.apply(lambda row: get_overdue_days(row.get('due_date')), axis=1)
    
    # 應用逾期篩選
    if filter_overdue_only:
        df = df[(df['status'] == 'unpaid') & (df['overdue_days'] > 0)]
    
    # 分類狀態
    df['payment_category'] = df.apply(categorize_payment_status, axis=1)
    
    if df.empty:
        empty_state("查無符合條件的資料", "📭", "")
        return
    
    # 統計卡片
    section_header("📊 統計總覽", "", divider=True)
    
    total_count = len(df)
    unpaid_df = df[df['status'] == 'unpaid']
    paid_df = df[df['status'] == 'paid']
    overdue_df = df[(df['status'] == 'unpaid') & (df['overdue_days'] > 0)]
    
    cols1, cols2, cols3, cols4, cols5 = st.columns(5)
    
    with cols1:
        metric_card("總筆數", str(total_count), None, "📊", color="normal")
    
    with cols2:
        metric_card("已繳", str(len(paid_df)), f"${paid_df['paid_amount'].sum():,.0f}", "✅", color="success")
    
    with cols3:
        metric_card("未繳", str(len(unpaid_df)), f"${unpaid_df['amount'].sum():,.0f}", "⏳", color="warning")
    
    with cols4:
        metric_card("逾期", str(len(overdue_df)), f"${overdue_df['amount'].sum():,.0f}", "🚨", color="error")
    
    with cols5:
        payment_rate = (len(paid_df) / total_count * 100) if total_count > 0 else 0
        metric_card("繳費率", f"{payment_rate:.1f}%", None, "📈", color="normal")
    
    st.divider()
    
    # 逾期警示
    if not overdue_df.empty:
        st.error(f"🚨 有 {len(overdue_df)} 筆逾期未繳！")
        
        with st.expander("查看逾期清單", expanded=True):
            for _, row in overdue_df.head(5).iterrows():
                st.write(f"- {row['room_number']} {row['tenant_name']} | {row['payment_year']}/{row['payment_month']} | ${row['amount']:,} | 逾期 {row['overdue_days']} 天")
            
            if len(overdue_df) > 5:
                st.caption(f"... 還有 {len(overdue_df) - 5} 筆")
    
    st.divider()
    
    # 批量操作
    if not unpaid_df.empty:
        section_header("⚡ 批量操作", "", divider=True)
        
        # 快速選擇按鈕
        colq1, colq2, colq3, colq4 = st.columns(4)
        
        with colq1:
            if st.button("選擇所有逾期"):
                st.session_state.selected_tracking = overdue_df['id'].tolist()
                st.rerun()
        
        with colq2:
            if st.button("選擇即將逾期"):
                soon_overdue = df[(df['status'] == 'unpaid') & (df['overdue_days'] == 0) & 
                                  (pd.to_datetime(df['due_date']) - pd.Timestamp.now()).dt.days <= 3]['id'].tolist()
                st.session_state.selected_tracking = soon_overdue
                st.rerun()
        
        with colq3:
            if st.button("選擇所有未繳"):
                st.session_state.selected_tracking = unpaid_df['id'].tolist()
                st.rerun()
        
        with colq4:
            if st.button("清除選擇"):
                st.session_state.selected_tracking = []
                st.rerun()
        
        # 手動選擇
        if 'selected_tracking' not in st.session_state:
            st.session_state.selected_tracking = []
        
        selected_ids = st.multiselect(
            "選擇要標記為已付款的項目",
            unpaid_df['id'].tolist(),
            default=st.session_state.selected_tracking,
            format_func=lambda x: f"{unpaid_df[unpaid_df['id']==x]['room_number'].values[0]} - {unpaid_df[unpaid_df['id']==x]['payment_year'].values[0]}/{unpaid_df[unpaid_df['id']==x]['payment_month'].values[0]} (${unpaid_df[unpaid_df['id']==x]['amount'].values[0]:,})",
            key="manual_select"
        )
        
        st.session_state.selected_tracking = selected_ids
        
        # 執行按鈕
        colbtn1, colbtn2, colbtn3 = st.columns([1, 1, 2])
        
        with colbtn1:
            if st.button(f"✅ 標記已付款 ({len(selected_ids)} 筆)", type="primary", disabled=len(selected_ids) == 0):
                success, fail = db.batch_mark_paid(selected_ids)
                
                if success > 0:
                    st.success(f"✅ 成功標記 {success} 筆")
                    st.session_state.selected_tracking = []
                    st.rerun()
                
                if fail > 0:
                    st.error(f"❌ 失敗 {fail} 筆")
        
        with colbtn2:
            if st.button(f"📤 匯出選中項目 ({len(selected_ids)} 筆)", disabled=len(selected_ids) == 0):
                st.info("匯出功能開發中")
        
        st.divider()
    
    # 資料表格
    section_header("📋 付款記錄", "", divider=True)
    
    st.write(f"**共 {len(df)} 筆記錄**")
    
    # 準備顯示資料
    display_df = df.copy()
    
    # 格式化期數
    display_df['period'] = display_df.apply(lambda x: f"{x['payment_year']}/{x['payment_month']}", axis=1)
    
    # 格式化金額
    display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:,.0f}")
    display_df['paid_amount'] = display_df['paid_amount'].apply(lambda x: f"${x:,.0f}")
    
    # 狀態圖標
    def status_with_icon(row):
        if row['status'] == 'paid':
            return "✅ 已繳"
        elif row['overdue_days'] >= 7:
            return f"🚨 逾期 {row['overdue_days']} 天"
        elif row['overdue_days'] > 0:
            return f"⚠️ 逾期 {row['overdue_days']} 天"
        else:
            return "⏳ 未繳"
    
    display_df['status_display'] = display_df.apply(status_with_icon, axis=1)
    
    # 格式化到期日
    display_df['due_date'] = pd.to_datetime(display_df['due_date']).dt.strftime("%Y-%m-%d")
    
    # 選擇要顯示的欄位（✅ 修正：只選擇存在的欄位）
    available_cols = display_df.columns.tolist()
    preferred_cols = ['id', 'room_number', 'tenant_name', 'period', 'amount', 'due_date', 'status_display']
    cols_to_show = [col for col in preferred_cols if col in available_cols]
    
    # 重新命名欄位
    rename_cols = {
        'room_number': '房號',
        'tenant_name': '房客',
        'period': '期數',
        'amount': '金額',
        'due_date': '到期日',
        'status_display': '狀態'
    }
    
    display_df = display_df.rename(columns=rename_cols)
    
    # 顯示表格
    final_cols = [rename_cols.get(col, col) for col in cols_to_show]
    st.dataframe(display_df[final_cols], use_container_width=True, hide_index=True, key="tracking_table")
    
    st.divider()
    
    # 統計圖表
    section_header("📈 統計圖表", "", divider=False)
    
    colchart1, colchart2 = st.columns(2)
    
    with colchart1:
        st.write("**狀態分布**")
        status_counts = df['payment_category'].
    with colchart1:
        st.write("**狀態分布**")
        status_counts = df['payment_category'].value_counts()
        chart_data = pd.DataFrame({'狀態': status_counts.index, '數量': status_counts.values})
        st.bar_chart(chart_data.set_index('狀態'))
    
    with colchart2:
        st.write("**房號統計**")
        room_stats = df.groupby('room_number').agg({
            'status': lambda x: (x == 'paid').sum(),
            'amount': 'sum'
        }).reset_index()
        room_stats.columns = ['房號', '已繳筆數', '總金額']
        st.bar_chart(room_stats.set_index('房號')['已繳筆數'])
    
    st.divider()
    
    # 匯出功能
    section_header("💾 資料匯出", "", divider=False)
    
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        "📥 下載 CSV",
        csv,
        f"tracking_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )
