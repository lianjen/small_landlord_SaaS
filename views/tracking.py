# views/tracking.py (完整版 - 含房號篩選功能)
"""
繳費追蹤頁面
職責：追蹤租金繳費狀態，支援房號篩選與快速標記
"""
import streamlit as st
from datetime import datetime, date
from services.payment_service import PaymentService
from services.logger import logger
from repository.tenant_repository import TenantRepository
import pandas as pd

def render(db):
    """主入口函式（供 main.py 動態載入使用）"""
    render_tracking_page()

def render_tracking_page():
    """渲染繳費追蹤頁面"""
    st.title("📋 繳費追蹤")
    
    service = PaymentService()
    
    # === 快速篩選按鈕 ===
    st.subheader("🔍 快速篩選")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🚨 逾期未繳", use_container_width=True, type="primary"):
            st.session_state.tracking_filter = "overdue"
            st.rerun()
    
    with col2:
        if st.button("⚠️ 即將到期", use_container_width=True):
            st.session_state.tracking_filter = "upcoming"
            st.rerun()
    
    with col3:
        if st.button("⏳ 全部未繳", use_container_width=True):
            st.session_state.tracking_filter = "unpaid"
            st.rerun()
    
    with col4:
        if st.button("🔄 重置", use_container_width=True):
            st.session_state.tracking_filter = "all"
            st.rerun()
    
    # 取得當前篩選狀態
    if 'tracking_filter' not in st.session_state:
        st.session_state.tracking_filter = "all"
    
    current_filter = st.session_state.tracking_filter
    
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
            help="選擇一個或多個房間，留空則顯示全部"
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
            total_amount = df[df['status'] == 'unpaid']['amount'].sum()
            st.metric("待收金額", f"${total_amount:,.0f}")
        
        with col4:
            overdue_amount = df[df['days_overdue'] > 0]['amount'].sum()
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
                if 'selected_tracking' not in st.session_state:
                    st.session_state.selected_tracking = []
                
                selected_ids = st.multiselect(
                    "選擇要標記為已繳的項目（可多選）",
                    options=unpaid_df['id'].tolist(),
                    default=st.session_state.selected_tracking,
                    format_func=lambda x: (
                        f"{unpaid_df[unpaid_df['id']==x]['room_number'].values[0]} - "
                        f"{unpaid_df[unpaid_df['id']==x]['tenant_name'].values[0]} "
                        f"({unpaid_df[unpaid_df['id']==x]['payment_year'].values[0]}/"
                        f"{unpaid_df[unpaid_df['id']==x]['payment_month'].values[0]:02d}) "
                        f"${unpaid_df[unpaid_df['id']==x]['amount'].values[0]:,.0f}"
                    ),
                    key="tracking_multiselect"
                )
                
                st.session_state.selected_tracking = selected_ids
            
            with col2:
                paid_amount = st.number_input(
                    "繳款金額",
                    min_value=0.0,
                    step=100.0,
                    help="留空則使用應繳金額",
                    key="tracking_paid_amount"
                )
            
            with col3:
                st.write("")
                st.write("")
            
            # 快速選擇按鈕
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("📌 全選", use_container_width=True, key="tracking_select_all"):
                    st.session_state.selected_tracking = unpaid_df['id'].tolist()
                    st.rerun()
            
            with col_btn2:
                if st.button("🔄 清除", use_container_width=True, key="tracking_clear"):
                    st.session_state.selected_tracking = []
                    st.rerun()
            
            # 標記按鈕
            with col_btn3:
                if st.button(
                    f"✅ 標記 ({len(selected_ids)})",
                    type="primary",
                    disabled=len(selected_ids) == 0,
                    use_container_width=True,
                    key="tracking_mark_paid"
                ):
                    with st.spinner("處理中..."):
                        try:
                            results = service.batch_mark_paid(
                                selected_ids,
                                paid_amount if paid_amount > 0 else None
                            )
                            
                            if results['success'] > 0:
                                st.success(f"✅ 成功標記 {results['success']} 筆")
                                st.session_state.selected_tracking = []
                                st.rerun()
                            
                            if results['failed'] > 0:
                                st.error(f"❌ 失敗 {results['failed']} 筆")
                        except Exception as e:
                            st.error(f"❌ 標記失敗: {str(e)}")
                            logger.error(f"批量標記失敗: {str(e)}", exc_info=True)
    
    except Exception as e:
        st.error(f"❌ 載入資料失敗: {str(e)}")
        logger.error(f"追蹤頁面錯誤: {str(e)}", exc_info=True)

# ============================================
# 本機測試入口
# ============================================
if __name__ == "__main__":
    render_tracking_page()
