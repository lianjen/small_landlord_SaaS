"""
繳費追蹤 - 完整重構版
特性:
- 批量標記已繳
- 多維度進階篩選
- 逾期自動提醒
- 收款統計圖表
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import logging

# 安全 import
try:
    from components.cards import section_header, metric_card, empty_state, data_table, info_card
except ImportError:
    def section_header(title, icon="", divider=True):
        st.markdown(f"### {icon} {title}")
        if divider: st.divider()
    def metric_card(label, value, delta="", icon="", color="normal"):
        st.metric(label, value, delta)
    def empty_state(msg, icon="", desc=""):
        st.info(f"{icon} {msg}")
    def data_table(df, key="table"):
        st.dataframe(df, use_container_width=True, key=key)
    def info_card(title, content, icon="", type="info"):
        st.info(f"{icon} {title}: {content}")

try:
    from config.constants import ROOMS
except ImportError:
    class ROOMS:
        ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]

logger = logging.getLogger(__name__)

# ============== 輔助函數 ==============

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
    """分類繳費狀態"""
    if row['status'] == '已繳':
        return '已繳'
    
    overdue_days = get_overdue_days(row.get('due_date'))
    
    if overdue_days > 7:
        return '逾期未繳'
    elif overdue_days > 0:
        return '即將逾期'
    else:
        return '未到期'


# ============== 主視圖 ==============

def render(db):
    """主渲染函數"""
    st.title("📋 繳費追蹤")
    
    # === 篩選區域 ===
    section_header("篩選條件", "🔍")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_year = st.selectbox(
            "年份",
            [None] + list(range(2020, 2031)),
            format_func=lambda x: "全部" if x is None else str(x),
            index=date.today().year - 2020 + 1,  # 預設當前年份
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
            [None, "未繳", "已繳"],
            format_func=lambda x: "全部" if x is None else x,
            key="track_status"
        )
    
    with col4:
        filter_rooms = st.multiselect(
            "房號",
            ROOMS.ALL_ROOMS,
            key="track_rooms"
        )
    
    # 進階篩選
    with st.expander("🔍 進階篩選", expanded=False):
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            filter_amount_min = st.number_input(
                "最小金額",
                min_value=0,
                value=0,
                step=1000,
                key="track_amt_min"
            )
        
        with col_b:
            filter_amount_max = st.number_input(
                "最大金額",
                min_value=0,
                value=0,
                step=1000,
                help="0 表示不限制",
                key="track_amt_max"
            )
        
        with col_c:
            filter_overdue_only = st.checkbox(
                "僅顯示逾期",
                value=False,
                key="track_overdue"
            )
    
    st.divider()
    
    # === 查詢資料 ===
    try:
        df = db.get_payment_schedule(
            year=filter_year,
            month=filter_month,
            status=filter_status
        )
    except Exception as e:
        st.error(f"❌ 查詢失敗: {e}")
        return
    
    if df.empty:
        empty_state("沒有符合條件的記錄", "📭")
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
    df['逾期天數'] = df.apply(lambda row: get_overdue_days(row.get('due_date')), axis=1)
    
    # 逾期篩選
    if filter_overdue_only:
        df = df[(df['status'] == '未繳') & (df['逾期天數'] > 0)]
    
    # 分類狀態
    df['狀態分類'] = df.apply(categorize_payment_status, axis=1)
    
    if df.empty:
        empty_state("沒有符合條件的記錄", "📭")
        return
    
    # === 統計卡片 ===
    section_header("統計概覽", "📊")
    
    total_count = len(df)
    unpaid_df = df[df['status'] == '未繳']
    paid_df = df[df['status'] == '已繳']
    overdue_df = df[(df['status'] == '未繳') & (df['逾期天數'] > 0)]
    
    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    
    with col_s1:
        metric_card(
            "總筆數",
            str(total_count),
            icon="📋",
            color="normal"
        )
    
    with col_s2:
        metric_card(
            "已繳",
            str(len(paid_df)),
            f"${paid_df['paid_amount'].sum():,.0f}",
            "✅",
            "success"
        )
    
    with col_s3:
        metric_card(
            "未繳",
            str(len(unpaid_df)),
            f"${unpaid_df['amount'].sum():,.0f}",
            "⏳",
            "warning"
        )
    
    with col_s4:
        metric_card(
            "逾期",
            str(len(overdue_df)),
            f"${overdue_df['amount'].sum():,.0f}",
            "🚨",
            "error"
        )
    
    with col_s5:
        payment_rate = (len(paid_df) / total_count * 100) if total_count > 0 else 0
        metric_card(
            "收款率",
            f"{payment_rate:.1f}%",
            icon="📊",
            color="normal"
        )
    
    st.divider()
    
    # === 逾期警示 ===
    if not overdue_df.empty:
        st.error(f"🚨 **逾期警示**: {len(overdue_df)} 筆未繳且已逾期")
        
        with st.expander("查看逾期明細", expanded=True):
            for _, row in overdue_df.head(5).iterrows():
                st.write(
                    f"**{row['room_number']}** {row['tenant_name']} | "
                    f"{row['payment_year']}/{row['payment_month']} | "
                    f"${row['amount']:,} | "
                    f"逾期 {row['逾期天數']} 天"
                )
            
            if len(overdue_df) > 5:
                st.caption(f"... 還有 {len(overdue_df) - 5} 筆")
        
        st.divider()
    
    # === 批量操作 ===
    if not unpaid_df.empty:
        section_header("批量操作", "⚡")
        
        # 快速篩選按鈕
        col_q1, col_q2, col_q3, col_q4 = st.columns(4)
        
        with col_q1:
            if st.button("🔴 選擇所有逾期"):
                st.session_state.selected_tracking = overdue_df['id'].tolist()
                st.rerun()
        
        with col_q2:
            if st.button("🟡 選擇即將逾期"):
                soon_overdue = df[df['狀態分類'] == '即將逾期']['id'].tolist()
                st.session_state.selected_tracking = soon_overdue
                st.rerun()
        
        with col_q3:
            if st.button("🟢 選擇全部未繳"):
                st.session_state.selected_tracking = unpaid_df['id'].tolist()
                st.rerun()
        
        with col_q4:
            if st.button("🔄 清除選擇"):
                st.session_state.selected_tracking = []
                st.rerun()
        
        # 手動選擇
        if 'selected_tracking' not in st.session_state:
            st.session_state.selected_tracking = []
        
        selected_ids = st.multiselect(
            "或手動選擇要標記的項目",
            unpaid_df['id'].tolist(),
            default=st.session_state.selected_tracking,
            format_func=lambda x: f"{unpaid_df[unpaid_df['id']==x]['room_number'].values[0]} - {unpaid_df[unpaid_df['id']==x]['payment_year'].values[0]}/{unpaid_df[unpaid_df['id']==x]['payment_month'].values[0]} (${unpaid_df[unpaid_df['id']==x]['amount'].values[0]:,.0f})",
            key="manual_select"
        )
        
        st.session_state.selected_tracking = selected_ids
        
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        
        with col_btn1:
            if st.button(
                f"✅ 標記已繳 ({len(selected_ids)})",
                type="primary",
                disabled=len(selected_ids) == 0
            ):
                success, fail = db.batch_mark_paid(selected_ids)
                
                if success > 0:
                    st.success(f"✅ 成功標記 {success} 筆")
                    st.session_state.selected_tracking = []
                    st.rerun()
                
                if fail > 0:
                    st.error(f"❌ 失敗 {fail} 筆")
        
        with col_btn2:
            if st.button(
                f"📧 發送提醒 ({len(selected_ids)})",
                disabled=len(selected_ids) == 0
            ):
                st.info("💡 通知功能開發中,敬請期待！")
        
        st.divider()
    
    # === 資料表格 ===
    section_header("詳細列表", "📋")
    
    st.write(f"共 {len(df)} 筆記錄")
    
    # 格式化顯示
    display_df = df.copy()
    
    display_df['期間'] = display_df.apply(
        lambda x: f"{x['payment_year']}/{x['payment_month']}", axis=1
    )
    
    display_df['應收金額'] = display_df['amount'].apply(lambda x: f"${x:,.0f}")
    display_df['實收金額'] = display_df['paid_amount'].apply(lambda x: f"${x:,.0f}")
    
    # 狀態標記
    def status_with_icon(row):
        if row['status'] == '已繳':
            return '✅ 已繳'
        elif row['逾期天數'] > 7:
            return f'🚨 逾期 {row["逾期天數"]} 天'
        elif row['逾期天數'] > 0:
            return f'🟡 逾期 {row["逾期天數"]} 天'
        else:
            return '⏳ 未繳'
    
    display_df['狀態標記'] = display_df.apply(status_with_icon, axis=1)
    
    # 到期日格式化
    display_df['到期日'] = pd.to_datetime(display_df['due_date']).dt.strftime('%Y-%m-%d')
    
    # 選擇要顯示的欄位
    cols_to_show = [
        'id', 'room_number', 'tenant_name', '期間',
        '應收金額', '實收金額', 'payment_method',
        '到期日', '狀態標記'
    ]
    
    rename_cols = {
        'room_number': '房號',
        'tenant_name': '房客',
        'payment_method': '繳款方式'
    }
    
    display_df = display_df.rename(columns=rename_cols)
    
    # 顯示表格
    data_table(display_df[cols_to_show], key="tracking_table")
    
    # === 統計圖表 ===
    st.divider()
    section_header("統計圖表", "📊")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.write("**狀態分佈**")
        
        status_counts = df['狀態分類'].value_counts()
        
        chart_data = pd.DataFrame({
            '狀態': status_counts.index,
            '數量': status_counts.values
        })
        
        st.bar_chart(chart_data.set_index('狀態'))
    
    with col_chart2:
        st.write("**各房號繳費狀況**")
        
        room_stats = df.groupby('room_number').agg({
            'status': lambda x: (x == '已繳').sum()
        }).reset_index()
        
        room_stats.columns = ['房號', '已繳數']
        
        st.bar_chart(room_stats.set_index('房號'))
    
    # 匯出功能
    st.divider()
    section_header("匯出資料", "📥", divider=False)
    
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    
    st.download_button(
        "📥 下載 CSV",
        csv,
        f"tracking_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )
