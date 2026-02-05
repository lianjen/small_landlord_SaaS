"""
租金管理頁面 v3.0 (Service 架構完全重構)
✅ 完全移除 db 依賴
✅ 使用正確的 Service 方法
✅ 優化錯誤處理
✅ 統一入口函數
"""
import streamlit as st
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from services.payment_service import PaymentService
from services.tenant_service import TenantService
from typing import List, Dict
import pandas as pd
import logging

logger = logging.getLogger(__name__)


# ============================================
# 主入口
# ============================================
def render():
    """主入口函式（供 main.py 動態載入使用）"""
    render_rent_page()


def show():
    """Streamlit 頁面入口"""
    render()


def render_rent_page():
    """渲染租金管理主頁面"""
    st.title("💰 租金管理")
    
    # ✅ 初始化 Services
    payment_service = PaymentService()
    tenant_service = TenantService()
    
    # 頁籤
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 批量建立排程",
        "📊 本月摘要", 
        "💳 收款管理",
        "📈 報表分析"
    ])
    
    with tab1:
        render_batch_schedule_tab(payment_service, tenant_service)
    with tab2:
        render_monthly_summary_tab(payment_service, tenant_service)
    with tab3:
        render_payment_management_tab(payment_service, tenant_service)
    with tab4:
        render_reports_tab(payment_service, tenant_service)


# ==================== Tab 1: 批量建立排程 ====================
def render_batch_schedule_tab(payment_service: PaymentService, tenant_service: TenantService):
    """批量建立排程頁籤 v3.0"""
    
    st.subheader("📅 批量建立月租金排程 v3.0")
    st.caption("💡 選擇特定房間，一次建立多個月份的租金記錄")
    
    st.divider()
    
    # === 載入房客資料 ===
    try:
        tenants = tenant_service.get_all_tenants()
        
        if not tenants:
            st.warning("⚠️ 尚無房客資料，請先前往「👥 房客管理」新增房客")
            return
        
        # 按房號分組
        tenants_by_room = {t['room_number']: t for t in tenants}
        room_list = sorted(tenants_by_room.keys())
    
    except Exception as e:
        st.error(f"❌ 載入房客資料失敗: {str(e)}")
        logger.error(f"載入房客資料錯誤: {str(e)}", exc_info=True)
        return
    
    # === 選擇模式 ===
    st.markdown("### 🎯 選擇建立模式")
    
    col_mode1, col_mode2 = st.columns(2)
    
    with col_mode1:
        mode_all = st.button(
            "🏘️ 全部房間",
            use_container_width=True,
            help="為所有現有房客建立租金記錄"
        )
    
    with col_mode2:
        mode_select = st.button(
            "🏠 選擇房間",
            use_container_width=True,
            type="primary",
            help="選擇特定房間建立租金記錄"
        )
    
    # 初始化 session state
    if 'batch_mode' not in st.session_state:
        st.session_state.batch_mode = 'select'
    
    if mode_all:
        st.session_state.batch_mode = 'all'
        st.rerun()
    
    if mode_select:
        st.session_state.batch_mode = 'select'
        st.rerun()
    
    st.divider()
    
    # === 房間選擇 ===
    selected_rooms = []
    
    if st.session_state.batch_mode == 'select':
        st.markdown("### 🏠 選擇房間")
        
        selected_rooms = st.multiselect(
            "請選擇要建立租金記錄的房間（可多選）",
            options=room_list,
            default=[],
            format_func=lambda x: f"{x} - {tenants_by_room[x]['tenant_name']} (${tenants_by_room[x]['base_rent']:,.0f}/月)",
            key="selected_rooms_for_batch"
        )
        
        if not selected_rooms:
            st.info("👆 請先選擇至少一個房間")
            return
        
        # 顯示選中的房客資訊
        st.caption("**已選擇：**")
        cols = st.columns(min(len(selected_rooms), 4))
        
        for idx, room in enumerate(selected_rooms):
            tenant = tenants_by_room[room]
            with cols[idx % 4]:
                st.metric(
                    label=f"房間 {room}",
                    value=f"${tenant['base_rent']:,.0f}",
                    delta=tenant['tenant_name']
                )
        
        st.divider()
    
    else:
        # 全部房間模式
        selected_rooms = room_list
        st.info(f"📊 將為 **{len(selected_rooms)}** 個房間建立租金記錄")
        st.divider()
    
    # === 設定時間範圍 ===
    st.markdown("### 📅 設定時間範圍")
    
    col1, col2 = st.columns([2, 2])
    
    with col1:
        start_year = st.number_input(
            "起始年份",
            min_value=2020,
            max_value=2030,
            value=date.today().year,
            step=1,
            key="batch_start_year"
        )
    
    with col2:
        start_month = st.selectbox(
            "起始月份",
            range(1, 13),
            index=date.today().month - 1,
            key="batch_start_month"
        )
    
    st.divider()
    
    # === 批量建立月份數 ===
    st.markdown("### 🗓️ 批量建立月份數")
    
    col_month1, col_month2 = st.columns([3, 1])
    
    with col_month1:
        num_months = st.slider(
            "一次建立幾個月？",
            min_value=1,
            max_value=12,
            value=1,
            help="例如：選擇 3，則會建立連續 3 個月的租金記錄",
            key="batch_num_months"
        )
    
    with col_month2:
        st.write("")
        st.write("")
        st.metric("建立月數", f"{num_months} 個月")
    
    # 計算月份範圍
    start_date = date(start_year, start_month, 1)
    month_range = []
    
    for i in range(num_months):
        target_date = start_date + relativedelta(months=i)
        month_range.append({
            'year': target_date.year,
            'month': target_date.month,
            'display': f"{target_date.year}/{target_date.month:02d}"
        })
    
    # 顯示將建立的月份
    st.caption("**將建立以下月份：**")
    month_display = " → ".join([m['display'] for m in month_range])
    st.info(f"📅 {month_display}")
    
    st.divider()
    
    # === 預覽建立項目 ===
    st.markdown("### 👀 預覽建立項目")
    
    total_records = len(selected_rooms) * num_months
    
    st.metric(
        label="預計建立記錄",
        value=f"{total_records} 筆",
        delta=f"{len(selected_rooms)} 房間 × {num_months} 月"
    )
    
    # 明細表格
    with st.expander("📋 查看詳細明細", expanded=False):
        preview_data = []
        
        for room in selected_rooms:
            tenant = tenants_by_room[room]
            
            for month_info in month_range:
                preview_data.append({
                    '房號': room,
                    '房客': tenant['tenant_name'],
                    '年份': month_info['year'],
                    '月份': f"{month_info['month']:02d}",
                    '租金': f"${tenant['base_rent']:,.0f}"
                })
        
        st.dataframe(
            preview_data,
            use_container_width=True,
            hide_index=True
        )
    
    st.divider()
    
    # === 建立按鈕 ===
    col_btn1, col_btn2 = st.columns([3, 1])
    
    with col_btn1:
        if st.button(
            f"🚀 一鍵建立排程（{total_records} 筆）",
            type="primary",
            use_container_width=True,
            key="batch_create_btn"
        ):
            with st.spinner("正在建立租金記錄..."):
                try:
                    success_count = 0
                    fail_count = 0
                    skip_count = 0
                    error_messages = []
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total_items = len(selected_rooms) * num_months
                    current = 0
                    
                    for room in selected_rooms:
                        tenant = tenants_by_room[room]
                        
                        for month_info in month_range:
                            current += 1
                            progress = current / total_items
                            progress_bar.progress(progress)
                            status_text.text(f"處理中... {current}/{total_items} ({room} - {month_info['display']})")
                            
                            try:
                                # ✅ 使用 PaymentService 建立排程
                                ok, msg = payment_service.create_monthly_schedule(
                                    room_number=room,
                                    year=month_info['year'],
                                    month=month_info['month']
                                )
                                
                                if ok:
                                    if "已存在" in msg:
                                        skip_count += 1
                                    else:
                                        success_count += 1
                                else:
                                    fail_count += 1
                                    error_messages.append(f"{room} ({month_info['display']}): {msg}")
                            
                            except Exception as e:
                                fail_count += 1
                                error_messages.append(f"{room} ({month_info['display']}): {str(e)}")
                                logger.error(f"建立排程失敗: {room} - {month_info['display']}: {str(e)}", exc_info=True)
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ 完成！")
                    
                    # 顯示結果
                    st.divider()
                    
                    col_result1, col_result2, col_result3 = st.columns(3)
                    
                    with col_result1:
                        st.metric("✅ 成功建立", f"{success_count} 筆")
                    
                    with col_result2:
                        st.metric("⏭️ 已存在（跳過）", f"{skip_count} 筆")
                    
                    with col_result3:
                        st.metric("❌ 失敗", f"{fail_count} 筆")
                    
                    if success_count > 0:
                        st.success(f"🎉 成功建立 {success_count} 筆租金記錄！")
                        logger.info(f"批量建立租金記錄成功: {success_count} 筆")
                    
                    if skip_count > 0:
                        st.info(f"⏭️ 跳過 {skip_count} 筆已存在的記錄")
                    
                    if fail_count > 0:
                        st.error(f"❌ {fail_count} 筆建立失敗")
                        
                        with st.expander("查看錯誤詳情"):
                            for msg in error_messages:
                                st.text(f"• {msg}")
                        
                        logger.error(f"批量建立租金記錄部分失敗: {fail_count} 筆")
                
                except Exception as e:
                    st.error(f"❌ 批量建立失敗: {str(e)}")
                    logger.error(f"批量建立租金記錄異常: {str(e)}", exc_info=True)
    
    with col_btn2:
        if st.button("🔄 重置", use_container_width=True):
            # 清除 session state
            if 'selected_rooms_for_batch' in st.session_state:
                del st.session_state['selected_rooms_for_batch']
            st.session_state.batch_mode = 'select'
            st.rerun()


# ==================== Tab 2: 本月摘要 ====================
def render_monthly_summary_tab(payment_service: PaymentService, tenant_service: TenantService):
    """本月摘要頁籤"""
    st.subheader("📊 本月租金收款摘要")
    
    # === 期間與篩選 ===
    col1, col2, col3 = st.columns([2, 2, 3])
    
    with col1:
        year = st.selectbox("年份", range(2020, 2031), index=date.today().year - 2020, key="summary_year")
    
    with col2:
        month = st.selectbox("月份", range(1, 13), index=date.today().month - 1, key="summary_month")
    
    with col3:
        # 取得所有房間列表
        try:
            tenants = tenant_service.get_all_tenants()
            room_list = sorted(set([t['room_number'] for t in tenants]))
            
            selected_room = st.selectbox(
                "🏠 房號篩選",
                options=["全部"] + room_list,
                key="monthly_room_filter"
            )
        except Exception as e:
            st.error(f"❌ 載入房間列表失敗: {str(e)}")
            selected_room = "全部"
    
    # === 取得資料 ===
    try:
        # 根據篩選條件取得資料
        if selected_room == "全部":
            summary = payment_service.get_monthly_summary(year, month)
            payments = payment_service.get_payments_by_period(year, month)
        else:
            payments = payment_service.get_room_payments(selected_room, year, month)
            
            # 計算單一房間的摘要
            df = pd.DataFrame(payments) if payments else pd.DataFrame()
            if not df.empty:
                total_expected = df['amount'].sum()
                paid_df = df[df['status'] == 'paid']
                total_received = paid_df['paid_amount'].sum() if not paid_df.empty and 'paid_amount' in paid_df.columns else 0
                unpaid_count = len(df[df['status'] == 'unpaid'])
                overdue_count = len(df[df['status'] == 'overdue'])
                collection_rate = total_received / total_expected if total_expected > 0 else 0
                
                # 創建簡單的摘要對象
                summary = {
                    'total_expected': total_expected,
                    'total_received': total_received,
                    'unpaid_count': unpaid_count,
                    'overdue_count': overdue_count,
                    'collection_rate': collection_rate
                }
            else:
                summary = {
                    'total_expected': 0,
                    'total_received': 0,
                    'unpaid_count': 0,
                    'overdue_count': 0,
                    'collection_rate': 0
                }
        
        # === 顯示指標 ===
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "應收總額",
                f"${summary['total_expected']:,.0f}" if isinstance(summary, dict) else f"${summary.total_expected:,.0f}",
                help="本月應繳租金總額"
            )
        
        with col2:
            total_received = summary['total_received'] if isinstance(summary, dict) else summary.total_received
            collection_rate = summary['collection_rate'] if isinstance(summary, dict) else summary.collection_rate
            st.metric(
                "實收總額",
                f"${total_received:,.0f}",
                delta=f"{collection_rate:.1%}",
                help="已收到的租金金額與收款率"
            )
        
        with col3:
            unpaid_count = summary['unpaid_count'] if isinstance(summary, dict) else summary.unpaid_count
            st.metric(
                "待收",
                f"{unpaid_count} 筆",
                help="尚未繳款的租金記錄數"
            )
        
        with col4:
            overdue_count = summary['overdue_count'] if isinstance(summary, dict) else summary.overdue_count
            st.metric(
                "逾期",
                f"{overdue_count} 筆",
                delta="-" if overdue_count > 0 else "正常",
                delta_color="inverse",
                help="已超過到期日的未繳款記錄"
            )
        
        # 進度條
        st.progress(collection_rate)
        st.caption(f"收款進度：{collection_rate:.1%}")
        
        st.divider()
        
        # === 詳細列表 ===
        if selected_room == "全部":
            st.subheader("📋 本月繳費明細")
        else:
            st.subheader(f"📋 {selected_room} 房繳費明細")
        
        if not payments:
            st.info("📭 本月尚無租金記錄")
            return
        
        # 轉換為 DataFrame
        df = pd.DataFrame(payments)
        
        # 格式化日期
        if 'due_date' in df.columns:
            df['due_date'] = pd.to_datetime(df['due_date']).dt.strftime('%Y-%m-%d')
        if 'paid_date' in df.columns:
            df['paid_date'] = pd.to_datetime(df['paid_date'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 狀態標記
        status_map = {'unpaid': '⏳ 未繳', 'paid': '✅ 已繳', 'overdue': '🚨 逾期'}
        df['status_display'] = df['status'].map(status_map).fillna(df['status'])
        
        # 顯示表格
        display_cols = ['room_number', 'tenant_name', 'amount', 'due_date', 'status_display']
        if 'payment_method' in df.columns:
            display_cols.append('payment_method')
        
        st.dataframe(
            df[display_cols].rename(columns={
                'room_number': '房號',
                'tenant_name': '房客',
                'amount': '應繳金額',
                'due_date': '到期日',
                'status_display': '狀態',
                'payment_method': '繳款方式'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # === 標記功能 ===
        unpaid_df = df[df['status'] == 'unpaid']
        
        if not unpaid_df.empty:
            st.divider()
            st.subheader(f"✅ {'批量標記已繳' if selected_room == '全部' else f'{selected_room} 房標記已繳'}")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                selected_ids = st.multiselect(
                    "選擇要標記為已繳的項目（可多選）",
                    options=unpaid_df['id'].tolist(),
                    format_func=lambda x: (
                        f"{unpaid_df[unpaid_df['id']==x]['room_number'].values[0]} - "
                        f"{unpaid_df[unpaid_df['id']==x]['tenant_name'].values[0]} "
                        f"(${unpaid_df[unpaid_df['id']==x]['amount'].values[0]:,.0f})"
                    ),
                    key="monthly_multiselect"
                )
            
            with col2:
                st.write("")
                st.write("")
                if st.button(
                    f"✅ 標記 ({len(selected_ids)})",
                    type="primary",
                    disabled=len(selected_ids) == 0,
                    use_container_width=True,
                    key="monthly_mark_paid"
                ):
                    with st.spinner("處理中..."):
                        try:
                            results = payment_service.batch_mark_paid(selected_ids)
                            
                            if results['success'] > 0:
                                st.success(f"✅ 成功標記 {results['success']} 筆")
                                st.rerun()
                            
                            if results['failed'] > 0:
                                st.error(f"❌ 失敗 {results['failed']} 筆")
                        except Exception as e:
                            st.error(f"❌ 標記失敗: {str(e)}")
                            logger.error(f"批量標記失敗: {str(e)}", exc_info=True)
    
    except Exception as e:
        st.error(f"❌ 載入摘要失敗: {str(e)}")
        logger.error(f"載入摘要錯誤: {str(e)}", exc_info=True)


# ==================== Tab 3: 收款管理 ====================
def render_payment_management_tab(payment_service: PaymentService, tenant_service: TenantService):
    """收款管理頁籤"""
    st.subheader("💳 收款管理")
    
    # === 篩選條件 ===
    col1, col2 = st.columns([3, 3])
    
    with col1:
        status_filter = st.radio(
            "篩選狀態",
            ["全部", "未繳", "已繳", "逾期"],
            horizontal=True
        )
    
    with col2:
        try:
            tenants = tenant_service.get_all_tenants()
            room_list = sorted(set([t['room_number'] for t in tenants]))
            
            selected_room = st.selectbox(
                "🏠 房號篩選",
                options=["全部"] + room_list,
                key="management_room_filter"
            )
        except Exception as e:
            st.error(f"❌ 載入房間列表失敗: {str(e)}")
            selected_room = "全部"
    
    # === 載入資料 ===
    try:
        # 根據狀態取得資料
        if status_filter == "未繳":
            payments = payment_service.get_unpaid_payments()
        elif status_filter == "逾期":
            payments = payment_service.get_overdue_payments()
        elif status_filter == "已繳":
            payments = payment_service.get_paid_payments()
        else:
            payments = payment_service.get_all_payments()
        
        # 根據房號篩選
        if selected_room != "全部":
            payments = [p for p in payments if p['room_number'] == selected_room]
        
        if not payments:
            st.info("✅ 沒有符合條件的記錄")
            return
        
        # 轉換為 DataFrame
        df = pd.DataFrame(payments)
        if 'due_date' in df.columns:
            df['due_date'] = pd.to_datetime(df['due_date']).dt.strftime('%Y-%m-%d')
        
        # 狀態顯示
        status_map = {'unpaid': '⏳ 未繳', 'paid': '✅ 已繳', 'overdue': '🚨 逾期'}
        df['status_display'] = df['status'].map(status_map).fillna(df['status'])
        
        # 顯示表格
        display_cols = ['room_number', 'tenant_name', 'payment_year', 'payment_month', 'amount', 'due_date', 'status_display']
        available_cols = [col for col in display_cols if col in df.columns]
        
        st.dataframe(
            df[available_cols].rename(columns={
                'room_number': '房號',
                'tenant_name': '房客',
                'payment_year': '年份',
                'payment_month': '月份',
                'amount': '金額',
                'due_date': '到期日',
                'status_display': '狀態'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # === 批量標記功能 ===
        if status_filter in ["未繳", "逾期"]:
            st.divider()
            st.subheader("✅ 批量標記已繳")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                selected_ids = st.multiselect(
                    "選擇要標記的記錄（可多選）",
                    options=df['id'].tolist(),
                    format_func=lambda x: (
                        f"{df[df['id']==x]['room_number'].values[0]} - "
                        f"{df[df['id']==x]['payment_year'].values[0]}/"
                        f"{df[df['id']==x]['payment_month'].values[0]:02d}"
                    ),
                    key="management_multiselect"
                )
            
            with col2:
                st.write("")
                st.write("")
                if st.button(
                    f"✅ 標記 ({len(selected_ids)})",
                    type="primary",
                    disabled=len(selected_ids) == 0,
                    use_container_width=True
                ):
                    with st.spinner("處理中..."):
                        try:
                            results = payment_service.batch_mark_paid(selected_ids)
                            st.success(f"✅ 完成！成功 {results['success']} 筆，失敗 {results['failed']} 筆")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 標記失敗: {str(e)}")
                            logger.error(f"批量標記失敗: {str(e)}", exc_info=True)
    
    except Exception as e:
        st.error(f"❌ 載入資料失敗: {str(e)}")
        logger.error(f"收款管理錯誤: {str(e)}", exc_info=True)


# ==================== Tab 4: 報表分析 ====================
def render_reports_tab(payment_service: PaymentService, tenant_service: TenantService):
    """報表分析頁籤"""
    st.subheader("📈 報表分析")
    
    report_type = st.selectbox(
        "報表類型",
        ["月度收款趨勢", "房客繳款歷史", "年度統計"]
    )
    
    if report_type == "月度收款趨勢":
        render_monthly_trend_report(payment_service)
    elif report_type == "房客繳款歷史":
        render_tenant_history_report(payment_service, tenant_service)
    elif report_type == "年度統計":
        render_annual_report(payment_service)


def render_monthly_trend_report(payment_service: PaymentService):
    """月度趨勢報表"""
    st.info("🚧 月度趨勢報表開發中...")


def render_tenant_history_report(payment_service: PaymentService, tenant_service: TenantService):
    """房客繳款歷史"""
    try:
        tenants = tenant_service.get_all_tenants()
        
        if not tenants:
            st.warning("沒有活躍房客")
            return
        
        # 選擇房客
        tenant_options = {
            t['room_number']: f"{t['room_number']} - {t['tenant_name']}"
            for t in tenants
        }
        
        selected_room = st.selectbox(
            "選擇房客",
            options=list(tenant_options.keys()),
            format_func=lambda x: tenant_options[x]
        )
        
        # 載入歷史
        history = payment_service.get_tenant_history(selected_room, limit=12)
        
        if history:
            df = pd.DataFrame(history)
            
            available_cols = ['payment_year', 'payment_month', 'amount', 'status', 'paid_date', 'due_date']
            display_cols = [col for col in available_cols if col in df.columns]
            
            st.dataframe(
                df[display_cols],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("此房客尚無繳款記錄")
    
    except Exception as e:
        st.error(f"❌ 載入失敗: {str(e)}")
        logger.error(f"房客歷史報表錯誤: {str(e)}", exc_info=True)


def render_annual_report(payment_service: PaymentService):
    """年度統計報表"""
    st.info("🚧 年度統計報表開發中...")


# ============================================
# 本機測試入口
# ============================================
if __name__ == "__main__":
    render_rent_page()
