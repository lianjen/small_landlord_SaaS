"""
支出記錄頁面
- 新增支出
- 支出列表
- 統計分析
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
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
    from config.constants import EXPENSE
except ImportError:
    class EXPENSE:
        CATEGORIES = ["維修", "水電", "清潔", "管理費", "保險", "稅金", "其他"]

logger = logging.getLogger(__name__)


def render_add_tab(db):
    """新增支出"""
    section_header("➕ 新增支出", "", divider=True)
    
    with st.form("add_expense_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            expense_date = st.date_input("日期", value=date.today(), key="add_date")
            category = st.selectbox("類別", EXPENSE.CATEGORIES, key="add_category")
        
        with col2:
            amount = st.number_input("金額", min_value=0, value=0, step=100, key="add_amount")
            
            # 計算建議金額
            if amount > 0 and category:
                st.caption(f"💡 {category} 支出：${amount:,}")
        
        description = st.text_area("說明", placeholder="例如：2A 房間水龍頭維修", key="add_desc")
        
        submitted = st.form_submit_button("💾 新增支出", type="primary")
        
        if submitted:
            if amount <= 0:
                st.error("⚠️ 請輸入金額")
            elif not description.strip():
                st.warning("⚠️ 請輸入說明")
                
                if st.button("🚀 忽略警告並新增"):
                    if db.add_expense(expense_date, category, amount, description):
                        st.success("✅ 新增成功")
                        st.rerun()
            else:
                if db.add_expense(expense_date, category, amount, description):
                    st.success("✅ 新增成功")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ 新增失敗")


def render_list_tab(db):
    """支出列表"""
    section_header("📋 支出列表", "", divider=True)
    
    # 篩選條件
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_year = st.selectbox(
            "年份",
            [None] + list(range(2020, 2031)),
            format_func=lambda x: "全部" if x is None else str(x),
            index=(date.today().year - 2020 + 1) if date.today().year >= 2020 else 0,
            key="list_year"
        )
    
    with col2:
        filter_month = st.selectbox(
            "月份",
            [None] + list(range(1, 13)),
            format_func=lambda x: "全部" if x is None else str(x),
            key="list_month"
        )
    
    with col3:
        filter_category = st.multiselect("類別", EXPENSE.CATEGORIES, key="list_category")
    
    with col4:
        limit = st.number_input("顯示筆數", min_value=10, max_value=500, value=100, step=10, key="list_limit")
    
    st.divider()
    
    # 查詢資料
    try:
        df = db.get_expenses(limit=limit)
    except Exception as e:
        st.error(f"查詢失敗: {e}")
        return
    
    if df.empty:
        empty_state("暫無支出記錄", "📭", "")
        return
    
    # 應用篩選
    if filter_year:
        df['year'] = pd.to_datetime(df['expense_date']).dt.year
        df = df[df['year'] == filter_year]
    
    if filter_month:
        df['month'] = pd.to_datetime(df['expense_date']).dt.month
        df = df[df['month'] == filter_month]
    
    if filter_category:
        df = df[df['category'].isin(filter_category)]
    
    if df.empty:
        empty_state("查無符合條件的記錄", "📭", "")
        return
    
    # 統計
    total_amount = df['amount'].sum()
    avg_amount = df['amount'].mean()
    
    cols1, cols2, cols3 = st.columns(3)
    
    with cols1:
        metric_card("總金額", f"${total_amount:,.0f}", None, "💰", color="normal")
    
    with cols2:
        metric_card("總筆數", str(len(df)), None, "📊", color="normal")
    
    with cols3:
        metric_card("平均金額", f"${avg_amount:,.0f}", None, "📈", color="normal")
    
    st.divider()
    
    # 顯示列表
    st.write(f"**共 {len(df)} 筆支出記錄**")
    
    # 準備顯示資料
    display_df = df.copy()
    display_df['expense_date'] = pd.to_datetime(display_df['expense_date']).dt.strftime("%Y-%m-%d")
    display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:,.0f}")
    
    # ✅ 修正：只顯示存在的欄位
    available_cols = display_df.columns.tolist()
    preferred_cols = ['id', 'expense_date', 'category', 'amount', 'description']
    cols_to_show = [col for col in preferred_cols if col in available_cols]
    
    rename = {
        'expense_date': '日期',
        'category': '類別',
        'amount': '金額',
        'description': '說明'
    }
    
    display_df = display_df.rename(columns=rename)
    final_cols = [rename.get(col, col) for col in cols_to_show]
    
    # 選擇支出項目進行編輯/刪除
    selected_expense = st.selectbox(
        "選擇支出項目",
        [None] + display_df['id'].tolist() if 'id' in display_df.columns else [None],
        format_func=lambda x: "-- 請選擇 --" if x is None else f"ID {x} - {display_df[display_df['id']==x][rename.get('category', 'category')].values[0]} (${display_df[display_df['id']==x][rename.get('amount', 'amount')].values[0]})",
        key="selected_expense"
    )
    
    if selected_expense:
        expense_row = df[df['id'] == selected_expense].iloc[0]
        
        col_edit, col_delete = st.columns([3, 1])
        
        with col_edit:
            with st.expander("✏️ 編輯支出", expanded=True):
                with st.form("edit_expense_form"):
                    edit_date = st.date_input("日期", value=pd.to_datetime(expense_row['expense_date']).date(), key="edit_date")
                    
                    cole1, cole2 = st.columns(2)
                    
                    with cole1:
                        edit_category = st.selectbox(
                            "類別",
                            EXPENSE.CATEGORIES,
                            index=EXPENSE.CATEGORIES.index(expense_row['category']) if expense_row['category'] in EXPENSE.CATEGORIES else 0,
                            key="edit_category"
                        )
                    
                    with cole2:
                        edit_amount = st.number_input("金額", min_value=0, value=int(expense_row['amount']), step=100, key="edit_amount")
                    
                    edit_desc = st.text_area("說明", value=expense_row.get('description', ''), key="edit_desc")
                    
                    if st.form_submit_button("💾 儲存變更", type="primary"):
                        try:
                            with db.get_connection() as conn:
                                cur = conn.cursor()
                                cur.execute("""
                                    UPDATE expenses 
                                    SET expense_date = %s, category = %s, amount = %s, description = %s
                                    WHERE id = %s
                                """, (edit_date, edit_category, edit_amount, edit_desc, selected_expense))
                                conn.commit()
                            st.success("✅ 更新成功")
                            st.rerun()
                        except Exception as e:
                            st.error(f"更新失敗: {e}")
        
        with col_delete:
            st.write("")
            st.write("")
            
            if st.button("🗑️ 刪除", type="secondary"):
                if st.session_state.get('confirm_delete_expense'):
                    try:
                        with db.get_connection() as conn:
                            cur = conn.cursor()
                            cur.execute("DELETE FROM expenses WHERE id = %s", (selected_expense,))
                            conn.commit()
                        st.success("✅ 刪除成功")
                        del st.session_state.confirm_delete_expense
                        st.rerun()
                    except Exception as e:
                        st.error(f"刪除失敗: {e}")
                else:
                    st.session_state.confirm_delete_expense = True
                    st.warning("⚠️ 再次點擊確認刪除")
        
        st.divider()
    
    # 顯示表格
    st.dataframe(display_df[final_cols], use_container_width=True, hide_index=True, key="expense_list")


def render_stats_tab(db):
    """統計分析"""
    section_header("📊 統計分析", "", divider=True)
    
    # 選擇統計類型
    col1, col2 = st.columns(2)
    
    with col1:
        stats_year = st.selectbox("年份", range(2020, 2031), index=(date.today().year - 2020), key="stats_year")
    
    with col2:
        stats_type = st.radio("統計類型", ["月度分析", "年度總覽", "類別分析"], horizontal=True, key="stats_type")
    
    st.divider()
    
    # 查詢資料
    df = db.get_expenses(limit=1000)
    
    if df.empty:
        empty_state("暫無資料", "📭", "")
        return
    
    # 處理日期
    df['date'] = pd.to_datetime(df['expense_date'])
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    
    # 篩選年份
    df_year = df[df['year'] == stats_year]
    
    if df_year.empty:
        empty_state(f"{stats_year} 年無支出記錄", "📭", "")
        return
    
    if stats_type == "月度分析":
        # 月度分析
        month = st.selectbox("月份", range(1, 13), index=(date.today().month - 1), key="stats_month")
        
        df_month = df_year[df_year['month'] == month]
        
        if df_month.empty:
            empty_state(f"{stats_year} 年 {month} 月無支出記錄", "📭", "")
            return
        
        # 月度統計
        total = df_month['amount'].sum()
        count = len(df_month)
        avg = df_month['amount'].mean()
        
        cola, colb, colc = st.columns(3)
        
        with cola:
            metric_card("總支出", f"${total:,.0f}", None, "💰", "normal")
        
        with colb:
            metric_card("筆數", str(count), None, "📊", "normal")
        
        with colc:
            metric_card("平均", f"${avg:,.0f}", None, "📈", "normal")
        
        st.divider()
        
        # 類別分布
        st.write("**類別分布**")
        category_sum = df_month.groupby('category')['amount'].sum
        # 類別分布
        st.write("**類別分布**")
        category_sum = df_month.groupby('category')['amount'].sum().reset_index()
        category_sum.columns = ['類別', '金額']
        category_sum = category_sum.sort_values('金額', ascending=False)
        st.bar_chart(category_sum.set_index('類別'))
        
        st.divider()
        st.write("**明細**")
        st.dataframe(category_sum, use_container_width=True, hide_index=True, key="month_category")
    
    elif stats_type == "年度總覽":
        # 年度總覽
        total_year = df_year['amount'].sum()
        count_year = len(df_year)
        avg_month = total_year / 12
        
        cola, colb, colc = st.columns(3)
        
        with cola:
            metric_card("年度總支出", f"${total_year:,.0f}", None, "💰", "normal")
        
        with colb:
            metric_card("總筆數", str(count_year), None, "📊", "normal")
        
        with colc:
            metric_card("月平均", f"${avg_month:,.0f}", None, "📈", "normal")
        
        st.divider()
        
        # 月度趨勢
        st.write("**月度趨勢**")
        monthly = df_year.groupby('month')['amount'].sum().reset_index()
        monthly.columns = ['月份', '金額']
        
        # 補齊所有月份
        all_months = pd.DataFrame({'月份': range(1, 13)})
        monthly = all_months.merge(monthly, on='月份', how='left').fillna(0)
        
        st.line_chart(monthly.set_index('月份'))
        
        st.divider()
        
        # 12個月明細
        monthly['金額'] = monthly['金額'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(monthly, use_container_width=True, hide_index=True, key="monthly_trend")
    
    else:
        # 類別分析
        total_year = df_year['amount'].sum()
        
        st.write(f"**{stats_year} 年總支出：${total_year:,.0f}**")
        st.divider()
        
        # 類別統計
        category_stats = df_year.groupby('category').agg({
            'amount': ['sum', 'count', 'mean']
        }).reset_index()
        category_stats.columns = ['類別', '總金額', '筆數', '平均']
        category_stats['佔比'] = (category_stats['總金額'] / total_year * 100).round(1)
        category_stats = category_stats.sort_values('總金額', ascending=False)
        
        # 類別圖表
        st.write("**類別分布圖**")
        st.bar_chart(category_stats.set_index('類別')['總金額'])
        
        st.divider()
        
        # 類別明細表
        category_stats['總金額'] = category_stats['總金額'].apply(lambda x: f"${x:,.0f}")
        category_stats['平均'] = category_stats['平均'].apply(lambda x: f"${x:,.0f}")
        category_stats['佔比'] = category_stats['佔比'].apply(lambda x: f"{x}%")
        
        st.dataframe(category_stats, use_container_width=True, hide_index=True, key="category_stats")


def render(db):
    """支出記錄主頁面"""
    st.title("💸 支出記錄")
    
    tab1, tab2, tab3 = st.tabs(["➕ 新增支出", "📋 支出列表", "📊 統計分析"])
    
    with tab1:
        render_add_tab(db)
    
    with tab2:
        render_list_tab(db)
    
    with tab3:
        render_stats_tab(db)
