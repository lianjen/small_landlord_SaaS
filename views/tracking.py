# views/tracking.py v2.0.1 - 修復類型轉換錯誤
"""
繳費追蹤頁面 v2.0.1
職責：追蹤租金與電費繳費狀態，支援房號篩選與快速標記
✅ 保留：原有租金追蹤功能
✅ 新增：電費追蹤功能
✅ 新增：綜合追蹤視圖（租金+電費）
✅ 修復：Decimal 與 float 類型轉換錯誤
"""
import streamlit as st
from datetime import datetime, date
from services.payment_service import PaymentService
from services.logger import logger
from repository.tenant_repository import TenantRepository
import pandas as pd
from decimal import Decimal

def render(db):
    """主入口函式（供 main.py 動態載入使用）"""
    render_tracking_page(db)

def render_tracking_page(db):
    """渲染繳費追蹤頁面 - v2.0.1"""
    st.title("📋 繳費追蹤")
    
    # === 建立 Tabs ===
    tab1, tab2, tab3 = st.tabs(["🏠 租金追蹤", "⚡ 電費追蹤", "📊 綜合追蹤"])
    
    # === Tab 1: 租金追蹤（保留原功能）===
    with tab1:
        render_rent_tracking()
    
    # === Tab 2: 電費追蹤（新功能）===
    with tab2:
        render_electricity_tracking(db)
    
    # === Tab 3: 綜合追蹤（整合視圖）===
    with tab3:
        render_combined_tracking(db)


# ==================== 輔助函數：統一金額轉換 ====================
def safe_float(value):
    """安全地將任何類型轉換為 float"""
    try:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, str):
            # 移除 $, 逗號, 空格
            clean_value = str(value).replace('$', '').replace(',', '').replace(' ', '')
            return float(clean_value) if clean_value else 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0


# ==================== Tab 1: 租金追蹤（原功能保留）====================
def render_rent_tracking():
    """租金追蹤（原有功能）"""
    service = PaymentService()
    
    # === 快速篩選按鈕 ===
    st.subheader("🔍 快速篩選")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🚨 逾期未繳", key="rent_overdue", use_container_width=True, type="primary"):
            st.session_state.rent_filter = "overdue"
            st.rerun()
    
    with col2:
        if st.button("⚠️ 即將到期", key="rent_upcoming", use_container_width=True):
            st.session_state.rent_filter = "upcoming"
            st.rerun()
    
    with col3:
        if st.button("⏳ 全部未繳", key="rent_unpaid", use_container_width=True):
            st.session_state.rent_filter = "unpaid"
            st.rerun()
    
    with col4:
        if st.button("🔄 重置", key="rent_reset", use_container_width=True):
            st.session_state.rent_filter = "all"
            st.rerun()
    
    # 取得當前篩選狀態
    if 'rent_filter' not in st.session_state:
        st.session_state.rent_filter = "all"
    
    current_filter = st.session_state.rent_filter
    
    st.divider()
    
    # === 房號篩選 ===
    try:
        tenant_repo = TenantRepository()
        tenants = tenant_repo.get_active_tenants()
        room_list = sorted(set([t['room_number'] for t in tenants]))
        
        # 支援多房號選擇
        selected_rooms = st.multiselect(
            "🏠 房號篩選（可多選）",
            options=room_list,
            default=[],
            help="選擇一個或多個房間，留空則顯示全部",
            key="rent_room_filter"
        )
    except Exception as e:
        st.error(f"❌ 載入房間列表失敗: {str(e)}")
        selected_rooms = []
    
    # === 載入資料 ===
    try:
        # 根據篩選條件載入
        if current_filter == "overdue":
            payments = service.get_overdue_payments()
            st.info(f"📊 顯示：逾期未繳（共 {len(payments)} 筆）")
        
        elif current_filter == "upcoming":
            # 即將到期：未來 3 天內到期
            all_unpaid = service.get_unpaid_payments()
            today = date.today()
            payments = []
            
            for p in all_unpaid:
                due_date = pd.to_datetime(p['due_date']).date()
                days_until_due = (due_date - today).days
                
                if 0 <= days_until_due <= 3:
                    payments.append(p)
            
            st.info(f"📊 顯示：3 天內到期（共 {len(payments)} 筆）")
        
        elif current_filter == "unpaid":
            payments = service.get_unpaid_payments()
            st.info(f"📊 顯示：全部未繳（共 {len(payments)} 筆）")
        
        else:
            payments = service.payment_repo.get_all_payments()
            st.info(f"📊 顯示：全部記錄（共 {len(payments)} 筆）")
        
        # 根據房號篩選
        if selected_rooms:
            payments = [p for p in payments if p['room_number'] in selected_rooms]
            st.caption(f"🔎 已篩選房號：{', '.join(selected_rooms)}")
        
        if not payments:
            st.success("✅ 沒有符合條件的記錄")
            return
        
        # === 轉換為 DataFrame ===
        df = pd.DataFrame(payments)
        
        # 計算逾期天數
        today = pd.Timestamp.now().normalize()
        df['due_date_dt'] = pd.to_datetime(df['due_date'])
        df['days_overdue'] = (today - df['due_date_dt']).dt.days
        df['days_overdue'] = df['days_overdue'].apply(lambda x: max(0, x))
        
        # 格式化日期
        df['due_date'] = df['due_date_dt'].dt.strftime('%Y-%m-%d')
        
        # 狀態顯示
        status_map = {'unpaid': '⏳ 未繳', 'paid': '✅ 已繳', 'overdue': '🚨 逾期'}
        df['status_display'] = df['status'].map(status_map).fillna(df['status'])
        
        # 添加逾期標記
        df['overdue_display'] = df.apply(
            lambda row: f"🚨 逾期 {row['days_overdue']} 天" if row['days_overdue'] > 0 else "-",
            axis=1
        )
        
        # === 統計摘要 ===
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_unpaid = len(df[df['status'] == 'unpaid'])
            st.metric("待繳款", f"{total_unpaid} 筆")
        
        with col2:
            total_overdue = len(df[df['days_overdue'] > 0])
            st.metric("逾期", f"{total_overdue} 筆", delta="-" if total_overdue > 0 else "正常", delta_color="inverse")
        
        with col3:
            # ✅ 修復：統一轉換為 float
            total_amount = sum(safe_float(amount) for amount in df[df['status'] == 'unpaid']['amount'])
            st.metric("待收金額", f"${total_amount:,.0f}")
        
        with col4:
            # ✅ 修復：統一轉換為 float
            overdue_amount = sum(safe_float(amount) for amount in df[df['days_overdue'] > 0]['amount'])
            st.metric("逾期金額", f"${overdue_amount:,.0f}")
        
        st.divider()
        
        # === 顯示表格 ===
        st.subheader("📋 詳細列表")
        
        # 排序：逾期天數 > 到期日
        df_sorted = df.sort_values(['days_overdue', 'due_date_dt'], ascending=[False, True])
        
        st.dataframe(
            df_sorted[[
                'room_number', 'tenant_name', 'payment_year', 'payment_month',
                'amount', 'due_date', 'overdue_display', 'status_display'
            ]].rename(columns={
                'room_number': '房號',
                'tenant_name': '房客',
                'payment_year': '年份',
                'payment_month': '月份',
                'amount': '金額',
                'due_date': '到期日',
                'overdue_display': '逾期狀態',
                'status_display': '繳款狀態'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # === 批量標記功能 ===
        unpaid_df = df[df['status'] == 'unpaid']
        
        if not unpaid_df.empty:
            st.divider()
            st.subheader("✅ 批量標記已繳")
            
            col1, col2, col3 = st.columns([4, 2, 2])
            
            with col1:
                # 初始化 session state
                if 'selected_rent' not in st.session_state:
                    st.session_state.selected_rent = []
                
                selected_ids = st.multiselect(
                    "選擇要標記為已繳的項目（可多選）",
                    options=unpaid_df['id'].tolist(),
                    default=st.session_state.selected_rent,
                    format_func=lambda x: (
                        f"{unpaid_df[unpaid_df['id']==x]['room_number'].values[0]} - "
                        f"{unpaid_df[unpaid_df['id']==x]['tenant_name'].values[0]} "
                        f"({unpaid_df[unpaid_df['id']==x]['payment_year'].values[0]}/"
                        f"{unpaid_df[unpaid_df['id']==x]['payment_month'].values[0]:02d}) "
                        f"${safe_float(unpaid_df[unpaid_df['id']==x]['amount'].values[0]):,.0f}"
                    ),
                    key="rent_multiselect"
                )
                
                st.session_state.selected_rent = selected_ids
            
            with col2:
                paid_amount = st.number_input(
                    "繳款金額",
                    min_value=0.0,
                    step=100.0,
                    help="留空則使用應繳金額",
                    key="rent_paid_amount"
                )
            
            with col3:
                st.write("")
                st.write("")
            
            # 快速選擇按鈕
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("📌 全選", use_container_width=True, key="rent_select_all"):
                    st.session_state.selected_rent = unpaid_df['id'].tolist()
                    st.rerun()
            
            with col_btn2:
                if st.button("🔄 清除", use_container_width=True, key="rent_clear"):
                    st.session_state.selected_rent = []
                    st.rerun()
            
            # 標記按鈕
            with col_btn3:
                if st.button(
                    f"✅ 標記 ({len(selected_ids)})",
                    type="primary",
                    disabled=len(selected_ids) == 0,
                    use_container_width=True,
                    key="rent_mark_paid"
                ):
                    with st.spinner("處理中..."):
                        try:
                            results = service.batch_mark_paid(
                                selected_ids,
                                paid_amount if paid_amount > 0 else None
                            )
                            
                            if results['success'] > 0:
                                st.success(f"✅ 成功標記 {results['success']} 筆")
                                st.session_state.selected_rent = []
                                st.rerun()
                            
                            if results['failed'] > 0:
                                st.error(f"❌ 失敗 {results['failed']} 筆")
                        except Exception as e:
                            st.error(f"❌ 標記失敗: {str(e)}")
                            logger.error(f"批量標記失敗: {str(e)}", exc_info=True)
    
    except Exception as e:
        st.error(f"❌ 載入資料失敗: {str(e)}")
        logger.error(f"租金追蹤錯誤: {str(e)}", exc_info=True)


# ==================== Tab 2: 電費追蹤（新功能）====================
def render_electricity_tracking(db):
    """電費追蹤（新功能）- v2.0.1"""
    
    st.subheader("⚡ 電費繳費追蹤")
    
    # === 快速篩選按鈕 ===
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("⏳ 未繳電費", key="elec_unpaid", use_container_width=True, type="primary"):
            st.session_state.elec_filter = "unpaid"
            st.rerun()
    
    with col2:
        if st.button("✅ 已繳電費", key="elec_paid", use_container_width=True):
            st.session_state.elec_filter = "paid"
            st.rerun()
    
    with col3:
        if st.button("📜 全部電費", key="elec_all", use_container_width=True):
            st.session_state.elec_filter = "all"
            st.rerun()
    
    with col4:
        if st.button("🔄 重置", key="elec_reset", use_container_width=True):
            st.session_state.elec_filter = "unpaid"
            st.rerun()
    
    if 'elec_filter' not in st.session_state:
        st.session_state.elec_filter = "unpaid"
    
    current_filter = st.session_state.elec_filter
    
    st.divider()
    
    # === 選擇計費期間 ===
    periods = db.get_all_periods()
    
    if not periods:
        st.warning("⚠️ 尚未建立電費計費期間，請前往「⚡ 電費管理」建立")
        return
    
    # 期間選擇
    period_options = {
        f"{p['period_year']}/{p['period_month_start']}-{p['period_month_end']} (ID: {p['id']})": p['id']
        for p in periods
    }
    
    selected_period = st.selectbox(
        "📅 選擇計費期間",
        options=list(period_options.keys()),
        key="elec_period_select"
    )
    
    if not selected_period:
        return
    
    period_id = period_options[selected_period]
    st.info(f"📅 當前期間 ID: {period_id}")
    
    # === 房號篩選 ===
    try:
        tenant_repo = TenantRepository()
        tenants = tenant_repo.get_active_tenants()
        room_list = sorted(set([t['room_number'] for t in tenants]))
        
        selected_rooms = st.multiselect(
            "🏠 房號篩選（可多選）",
            options=room_list,
            default=[],
            help="選擇一個或多個房間，留空則顯示全部",
            key="elec_room_filter"
        )
    except Exception as e:
        st.error(f"❌ 載入房間列表失敗: {str(e)}")
        selected_rooms = []
    
    st.divider()
    
    # === 載入電費記錄 ===
    try:
        with st.spinner("正在載入電費記錄..."):
            df = db.get_electricity_payment_record(period_id)
            
            if df is None or df.empty:
                st.warning(f"📭 期間 ID {period_id} 尚無電費記錄，請前往「⚡ 電費管理」完成計算並儲存")
                return
            
            # 根據篩選條件過濾
            if current_filter == "unpaid":
                df = df[df['繳費狀態'] == '⏳ 未繳']
                st.info(f"📊 顯示：未繳電費（共 {len(df)} 筆）")
            
            elif current_filter == "paid":
                df = df[df['繳費狀態'] == '✅ 已繳']
                st.info(f"📊 顯示：已繳電費（共 {len(df)} 筆）")
            
            else:
                st.info(f"📊 顯示：全部電費（共 {len(df)} 筆）")
            
            # 根據房號篩選
            if selected_rooms:
                df = df[df['房號'].isin(selected_rooms)]
                st.caption(f"🔎 已篩選房號：{', '.join(selected_rooms)}")
            
            if df.empty:
                st.success("✅ 沒有符合條件的記錄")
                return
            
            # === 統計摘要 ===
            col1, col2, col3, col4 = st.columns(4)
            
            # ✅ 修復：使用 safe_float 統一轉換
            df['應繳金額_數值'] = df['應繳金額'].apply(safe_float)
            df['已繳金額_數值'] = df['已繳金額'].apply(safe_float)
            
            with col1:
                unpaid_count = len(df[df['繳費狀態'] == '⏳ 未繳'])
                st.metric("待繳款", f"{unpaid_count} 筆")
            
            with col2:
                paid_count = len(df[df['繳費狀態'] == '✅ 已繳'])
                st.metric("已繳", f"{paid_count} 筆")
            
            with col3:
                total_due = df['應繳金額_數值'].sum()
                st.metric("應收總額", f"${total_due:,.0f}")
            
            with col4:
                total_paid = df['已繳金額_數值'].sum()
                st.metric("已收金額", f"${total_paid:,.0f}")
            
            st.divider()
            
            # === 顯示表格 ===
            st.subheader("📋 電費明細")
            
            st.dataframe(
                df[[
                    '房號', '類型', '使用度數', '公用分攤', '總度數', 
                    '單價', '應繳金額', '已繳金額', '繳費狀態', '繳費日期'
                ]],
                use_container_width=True,
                hide_index=True
            )
            
            # === 快速標記功能 ===
            unpaid_df = df[df['繳費狀態'] == '⏳ 未繳']
            
            if not unpaid_df.empty:
                st.divider()
                st.subheader("⚡ 快速標記已繳")
                
                st.caption("💡 點擊房間旁的「✅」按鈕，即可快速更新繳費狀態")
                
                # 建立選擇列表
                for idx, row in unpaid_df.iterrows():
                    col_info, col_btn = st.columns([4, 1])
                    
                    with col_info:
                        amount = row['應繳金額_數值']
                        st.write(f"**{row['房號']}** | {row['類型']} | {row['總度數']} 度 | ${amount:,.0f} 元")
                    
                    with col_btn:
                        if st.button("✅", key=f"elec_pay_{period_id}_{idx}"):
                            with st.spinner(f"正在標記 {row['房號']}..."):
                                try:
                                    ok, msg = db.update_electricity_payment(
                                        period_id,
                                        row['房號'],
                                        'paid',
                                        int(amount),
                                        date.today().isoformat()
                                    )
                                    
                                    if ok:
                                        st.success(f"✅ {row['房號']} 已標記為已繳")
                                        logger.info(f"電費標記成功: {row['房號']} - ${amount:,.0f}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ 標記失敗: {msg}")
                                        logger.error(f"電費標記失敗: {row['房號']} - {msg}")
                                
                                except Exception as e:
                                    st.error(f"❌ 標記時發生錯誤: {str(e)}")
                                    logger.error(f"電費標記異常: {str(e)}", exc_info=True)
            
            else:
                st.success("✅ 全部已繳清")
    
    except Exception as e:
        st.error(f"❌ 載入電費記錄失敗: {str(e)}")
        logger.error(f"電費追蹤錯誤: {str(e)}", exc_info=True)


# ==================== Tab 3: 綜合追蹤（整合視圖）====================
def render_combined_tracking(db):
    """綜合追蹤（租金 + 電費整合視圖）- v2.0.1"""
    
    st.subheader("📊 綜合繳費追蹤")
    st.caption("💡 查看租金與電費的整體繳費狀況")
    
    st.divider()
    
    # === 載入租金數據 ===
    try:
        service = PaymentService()
        rent_unpaid = service.get_unpaid_payments()
        rent_df = pd.DataFrame(rent_unpaid) if rent_unpaid else pd.DataFrame()
        
        # ✅ 修復：統一轉換為 float
        rent_total = sum(safe_float(amount) for amount in rent_df['amount']) if not rent_df.empty else 0.0
        rent_count = len(rent_df)
    
    except Exception as e:
        st.error(f"❌ 載入租金數據失敗: {str(e)}")
        logger.error(f"租金數據載入錯誤: {str(e)}", exc_info=True)
        rent_total = 0.0
        rent_count = 0
        rent_df = pd.DataFrame()
    
    # === 載入電費數據 ===
    try:
        periods = db.get_all_periods()
        
        if periods:
            # 取最新期間
            latest_period = periods[0]
            period_id = latest_period['id']
            
            st.info(f"📅 電費期間: {latest_period['period_year']}/{latest_period['period_month_start']}-{latest_period['period_month_end']}")
            
            elec_df = db.get_electricity_payment_record(period_id)
            
            if elec_df is not None and not elec_df.empty:
                # ✅ 修復：使用 safe_float 統一轉換
                elec_df['應繳金額_數值'] = elec_df['應繳金額'].apply(safe_float)
                elec_unpaid_df = elec_df[elec_df['繳費狀態'] == '⏳ 未繳']
                
                elec_total = elec_unpaid_df['應繳金額_數值'].sum()
                elec_count = len(elec_unpaid_df)
            else:
                elec_total = 0.0
                elec_count = 0
                elec_unpaid_df = pd.DataFrame()
        else:
            st.warning("⚠️ 尚未建立電費期間")
            elec_total = 0.0
            elec_count = 0
            elec_unpaid_df = pd.DataFrame()
    
    except Exception as e:
        st.error(f"❌ 載入電費數據失敗: {str(e)}")
        logger.error(f"電費數據載入錯誤: {str(e)}", exc_info=True)
        elec_total = 0.0
        elec_count = 0
        elec_unpaid_df = pd.DataFrame()
    
    # === 整體統計 ===
    st.markdown("### 💰 整體待收摘要")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🏠 租金待收",
            f"${rent_total:,.0f}",
            delta=f"{rent_count} 筆"
        )
    
    with col2:
        st.metric(
            "⚡ 電費待收",
            f"${elec_total:,.0f}",
            delta=f"{elec_count} 筆"
        )
    
    with col3:
        # ✅ 修復：確保都是 float 再相加
        total_amount = float(rent_total) + float(elec_total)
        st.metric(
            "💵 總待收金額",
            f"${total_amount:,.0f}",
            delta=f"{rent_count + elec_count} 筆"
        )
    
    with col4:
        total_items = rent_count + elec_count
        st.metric(
            "📊 收繳概況",
            f"{total_items} 筆待繳"
        )
    
    st.divider()
    
    # === 分類明細 ===
    col_rent, col_elec = st.columns(2)
    
    with col_rent:
        st.markdown("#### 🏠 租金明細（未繳）")
        
        if not rent_df.empty:
            # 只顯示關鍵欄位
            display_df = rent_df[['room_number', 'tenant_name', 'payment_year', 'payment_month', 'amount']].copy()
            display_df['payment_period'] = display_df.apply(
                lambda row: f"{row['payment_year']}/{row['payment_month']:02d}",
                axis=1
            )
            
            # ✅ 修復：格式化金額
            display_df['amount_display'] = display_df['amount'].apply(lambda x: f"${safe_float(x):,.0f}")
            
            st.dataframe(
                display_df[['room_number', 'tenant_name', 'payment_period', 'amount_display']].rename(columns={
                    'room_number': '房號',
                    'tenant_name': '房客',
                    'payment_period': '期間',
                    'amount_display': '金額'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ 全部已繳清")
    
    with col_elec:
        st.markdown("#### ⚡ 電費明細（未繳）")
        
        if elec_count > 0:
            st.dataframe(
                elec_unpaid_df[['房號', '類型', '總度數', '應繳金額']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ 全部已繳清")
    
    st.divider()
    
    # === 快速操作提示 ===
    st.markdown("### 🚀 快速操作")
    
    col_hint1, col_hint2 = st.columns(2)
    
    with col_hint1:
        st.info("""
**📝 標記租金已繳：**
1. 前往「🏠 租金追蹤」Tab
2. 使用快速篩選找到未繳項目
3. 勾選項目後點擊「✅ 標記」
        """)
    
    with col_hint2:
        st.info("""
**⚡ 標記電費已繳：**
1. 前往「⚡ 電費追蹤」Tab
2. 選擇計費期間
3. 點擊房間旁的「✅」按鈕快速標記
        """)


# ============================================
# 本機測試入口
# ============================================
if __name__ == "__main__":
    from services.db import get_db
    db = get_db()
    render_tracking_page(db)
