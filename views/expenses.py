"""
支出管理 - 完整重構版
特性:
- 新增/編輯/刪除
- 分類統計圖表
- 月度/年度趨勢
- 預算管理
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
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
    from config.constants import EXPENSE
except ImportError:
    class EXPENSE:
        CATEGORIES = ["維修", "雜項", "貸款", "水電費", "網路費", "保險", "稅金", "其他"]

logger = logging.getLogger(__name__)

# ============== Tab 1: 新增支出 ==============

def render_add_tab(db):
    """新增支出"""
    section_header("新增支出", "➕")
    
    with st.form("add_expense_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            expense_date = st.date_input(
                "日期 *",
                value=date.today(),
                key="add_date"
            )
            
            category = st.selectbox(
                "分類 *",
                EXPENSE.CATEGORIES,
                key="add_category"
            )
        
        with col2:
            amount = st.number_input(
                "金額 *",
                min_value=0,
                value=0,
                step=100,
                key="add_amount"
            )
            
            # 預算提醒
            if amount > 0 and category:
                st.caption(f"💡 {category} 本月已支出查詢中...")
        
        description = st.text_area(
            "說明",
            placeholder="例如: 維修 2A 房間冷氣",
            key="add_desc"
        )
        
        submitted = st.form_submit_button("💾 新增", type="primary")
        
        if submitted:
            if amount <= 0:
                st.error("❌ 請輸入金額")
            elif not description.strip():
                st.warning("⚠️ 建議填寫說明")
                
                if st.button("仍要新增"):
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


# ============== Tab 2: 支出列表 ==============

def render_list_tab(db):
    """支出列表"""
    section_header("支出列表", "📋")
    
    # 篩選
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_year = st.selectbox(
            "年份",
            [None] + list(range(2020, 2031)),
            format_func=lambda x: "全部" if x is None else str(x),
            index=date.today().year - 2020 + 1,
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
        filter_category = st.multiselect(
            "分類",
            EXPENSE.CATEGORIES,
            key="list_category"
        )
    
    with col4:
        limit = st.number_input(
            "顯示筆數",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            key="list_limit"
        )
    
    st.divider()
    
    # 查詢
    try:
        df = db.get_expenses(limit=limit)
    except Exception as e:
        st.error(f"❌ 查詢失敗: {e}")
        return
    
    if df.empty:
        empty_state("尚無支出記錄", "📭")
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
        empty_state("沒有符合條件的記錄", "📭")
        return
    
    # 統計
    total_amount = df['amount'].sum()
    avg_amount = df['amount'].mean()
    
    col_s1, col_s2, col_s3 = st.columns(3)
    
    with col_s1:
        metric_card("總支出", f"${total_amount:,.0f}", icon="💰", color="normal")
    
    with col_s2:
        metric_card("筆數", str(len(df)), icon="📋", color="normal")
    
    with col_s3:
        metric_card("平均", f"${avg_amount:,.0f}", icon="📊", color="normal")
    
    st.divider()
    
    # 顯示列表
    st.write(f"共 {len(df)} 筆記錄")
    
    # 格式化
    display_df = df.copy()
    display_df['日期'] = pd.to_datetime(display_df['expense_date']).dt.strftime('%Y-%m-%d')
    display_df['金額'] = display_df['amount'].apply(lambda x: f"${x:,.0f}")
    
    cols_to_show = ['id', '日期', 'category', '金額', 'description']
    rename = {'category': '分類', 'description': '說明'}
    
    display_df = display_df.rename(columns=rename)
    
    # 可選擇的表格
    selected_expense = st.selectbox(
        "選擇要編輯/刪除的項目",
        [None] + display_df['id'].tolist(),
        format_func=lambda x: "請選擇..." if x is None else f"ID {x} - {display_df[display_df['id']==x]['分類'].values[0]} ${display_df[display_df['id']==x]['amount'].values[0]:,.0f}",
        key="selected_expense"
    )
    
    if selected_expense:
        expense_row = df[df['id'] == selected_expense].iloc[0]
        
        col_edit, col_delete = st.columns([3, 1])
        
        with col_edit:
            with st.expander("✏️ 編輯此項目", expanded=True):
                with st.form("edit_expense_form"):
                    edit_date = st.date_input(
                        "日期",
                        value=pd.to_datetime(expense_row['expense_date']).date(),
                        key="edit_date"
                    )
                    
                    col_e1, col_e2 = st.columns(2)
                    
                    with col_e1:
                        edit_category = st.selectbox(
                            "分類",
                            EXPENSE.CATEGORIES,
                            index=EXPENSE.CATEGORIES.index(expense_row['category']) if expense_row['category'] in EXPENSE.CATEGORIES else 0,
                            key="edit_category"
                        )
                    
                    with col_e2:
                        edit_amount = st.number_input(
                            "金額",
                            min_value=0,
                            value=int(expense_row['amount']),
                            step=100,
                            key="edit_amount"
                        )
                    
                    edit_desc = st.text_area(
                        "說明",
                        value=expense_row.get('description', ''),
                        key="edit_desc"
                    )
                    
                    if st.form_submit_button("💾 儲存變更", type="primary"):
                        # 更新 (需要在 db.py 新增此方法)
                        try:
                            with db._get_connection() as conn:
                                cur = conn.cursor()
                                cur.execute("""
                                    UPDATE expenses
                                    SET expense_date = %s,
                                        category = %s,
                                        amount = %s,
                                        description = %s
                                    WHERE id = %s
                                """, (edit_date, edit_category, edit_amount, edit_desc, selected_expense))
                                
                                st.success("✅ 更新成功")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ 更新失敗: {e}")
        
        with col_delete:
            st.write("")
            st.write("")
            if st.button("🗑️ 刪除", type="secondary"):
                if st.session_state.get('confirm_delete_expense'):
                    try:
                        with db._get_connection() as conn:
                            cur = conn.cursor()
                            cur.execute("DELETE FROM expenses WHERE id = %s", (selected_expense,))
                            
                            st.success("✅ 已刪除")
                            del st.session_state.confirm_delete_expense
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ 刪除失敗: {e}")
                else:
                    st.session_state.confirm_delete_expense = True
                    st.warning("⚠️ 再按一次確認")
    
    st.divider()
    
    # 顯示表格
    data_table(display_df[cols_to_show], key="expense_list")


# ============== Tab 3: 統計分析 ==============

def render_stats_tab(db):
    """統計分析"""
    section_header("統計分析", "📊")
    
    # 選擇期間
    col1, col2 = st.columns(2)
    
    with col1:
        stats_year = st.selectbox(
            "年份",
            range(2020, 2031),
            index=date.today().year - 2020,
            key="stats_year"
        )
    
    with col2:
        stats_type = st.radio(
            "類型",
            ["月度分析", "年度趨勢", "分類統計"],
            horizontal=True,
            key="stats_type"
        )
    
    st.divider()
    
    # 取得資料
    df = db.get_expenses(limit=1000)
    
    if df.empty:
        empty_state("尚無支出記錄", "📭")
        return
    
    # 轉換日期
    df['date'] = pd.to_datetime(df['expense_date'])
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    
    # 篩選年份
    df_year = df[df['year'] == stats_year]
    
    if df_year.empty:
        empty_state(f"{stats_year} 年沒有支出記錄", "📭")
        return
    
    if stats_type == "月度分析":
        # 月度分析
        month = st.selectbox("月份", range(1, 13), index=date.today().month - 1, key="stats_month")
        
        df_month = df_year[df_year['month'] == month]
        
        if df_month.empty:
            empty_state(f"{stats_year}/{month} 沒有支出", "📭")
            return
        
        # 統計
        total = df_month['amount'].sum()
        count = len(df_month)
        avg = df_month['amount'].mean()
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            metric_card("總支出", f"${total:,.0f}", icon="💰")
        
        with col_b:
            metric_card("筆數", str(count), icon="📋")
        
        with col_c:
            metric_card("平均", f"${avg:,.0f}", icon="📊")
        
        st.divider()
        
        # 分類圖表
        st.write("**分類佔比**")
        
        category_sum = df_month.groupby('category')['amount'].sum().reset_index()
        category_sum.columns = ['分類', '金額']
        category_sum = category_sum.sort_values('金額', ascending=False)
        
        st.bar_chart(category_sum.set_index('分類'))
        
        # 明細表
        st.divider()
        st.write("**明細**")
        data_table(category_sum, key="month_category")
    
    elif stats_type == "年度趨勢":
        # 年度趨勢
        total_year = df_year['amount'].sum()
        count_year = len(df_year)
        avg_month = total_year / 12
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            metric_card("年度總支出", f"${total_year:,.0f}", icon="💰")
        
        with col_b:
            metric_card("總筆數", str(count_year), icon="📋")
        
        with col_c:
            metric_card("月均支出", f"${avg_month:,.0f}", icon="📊")
        
        st.divider()
        
        # 月度趨勢
        st.write("**月度趨勢**")
        
        monthly = df_year.groupby('month')['amount'].sum().reset_index()
        monthly.columns = ['月份', '支出']
        
        # 補全 12 個月
        all_months = pd.DataFrame({'月份': range(1, 13)})
        monthly = all_months.merge(monthly, on='月份', how='left').fillna(0)
        
        st.line_chart(monthly.set_index('月份'))
        
        st.divider()
        
        # 表格
        monthly['支出'] = monthly['支出'].apply(lambda x: f"${x:,.0f}")
        data_table(monthly, key="monthly_trend")
    
    else:
        # 分類統計
        total_year = df_year['amount'].sum()
        
        st.write(f"**{stats_year} 年度總支出: ${total_year:,.0f}**")
        
        st.divider()
        
        # 分類統計
        category_stats = df_year.groupby('category').agg({
            'amount': ['sum', 'count', 'mean']
        }).reset_index()
        
        category_stats.columns = ['分類', '總額', '筆數', '平均']
        category_stats['佔比'] = (category_stats['總額'] / total_year * 100).round(1)
        category_stats = category_stats.sort_values('總額', ascending=False)
        
        # 圓餅圖
        st.write("**分類佔比**")
        st.bar_chart(category_stats.set_index('分類')['佔比'])
        
        st.divider()
        
        # 表格
        category_stats['總額'] = category_stats['總額'].apply(lambda x: f"${x:,.0f}")
        category_stats['平均'] = category_stats['平均'].apply(lambda x: f"${x:,.0f}")
        category_stats['佔比'] = category_stats['佔比'].apply(lambda x: f"{x}%")
        
        data_table(category_stats, key="category_stats")


# ============== 主函數 ==============

def render(db):
    """主渲染函數"""
    st.title("💸 支出管理")
    
    tab1, tab2, tab3 = st.tabs(["➕ 新增支出", "📋 支出列表", "📊 統計分析"])
    
    with tab1:
        render_add_tab(db)
    
    with tab2:
        render_list_tab(db)
    
    with tab3:
        render_stats_tab(db)
