"""
房客管理 - v3.0 (Service 架構完全重構)
✅ 完全移除 db 依賴
✅ 使用 TenantService
✅ 完整表單驗證
✅ 租約衝突檢查
✅ 刪除確認優化
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Optional, Tuple
import logging

# ✅ 使用 Service 架構
from services.tenant_service import TenantService

# 統一常數
from config.constants import ROOMS, PAYMENT

# 組件
try:
    from components.cards import section_header, empty_state, data_table
except ImportError:
    def section_header(title, icon="", divider=True):
        st.markdown(f"### {icon} {title}")
        if divider: st.divider()
    
    def empty_state(msg, icon="", desc=""):
        st.info(f"{icon} {msg}")
        if desc: st.caption(desc)
    
    def data_table(df, key="table"):
        st.dataframe(df, use_container_width=True, key=key, hide_index=True)

logger = logging.getLogger(__name__)


# ============== 驗證函數 ==============

def validate_phone(phone: str) -> Tuple[bool, str]:
    """驗證電話格式"""
    if not phone:
        return True, ""  # 允許空值
    
    # 移除常見分隔符
    clean_phone = phone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    
    # 檢查是否為數字
    if not clean_phone.isdigit():
        return False, "電話號碼只能包含數字"
    
    # 檢查長度 (台灣電話 8-10 碼)
    if len(clean_phone) < 8 or len(clean_phone) > 10:
        return False, "電話號碼長度應為 8-10 碼"
    
    return True, ""


def validate_date_range(start: date, end: date) -> Tuple[bool, str]:
    """驗證日期範圍"""
    if start >= end:
        return False, "租約結束日期必須晚於開始日期"
    
    # 檢查租約長度是否合理 (至少 1 個月)
    delta = (end - start).days
    if delta < 30:
        return False, "租約期間至少需要 30 天"
    
    return True, ""


def check_room_conflict(
    tenant_service: TenantService,
    room: str,
    start: date,
    end: date,
    exclude_tenant_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    檢查房號是否與現有租約衝突
    Args:
        tenant_service: 房客服務實例
        room: 房號
        start: 租約開始日
        end: 租約結束日
        exclude_tenant_id: 排除的房客 ID (編輯時使用)
    Returns:
        (是否衝突, 訊息)
    """
    try:
        tenants = tenant_service.get_all_tenants()
        
        if not tenants:
            return False, ""
        
        # 過濾同房號的房客
        same_room = [t for t in tenants if t['room_number'] == room]
        
        if exclude_tenant_id:
            same_room = [t for t in same_room if t['id'] != exclude_tenant_id]
        
        for tenant in same_room:
            existing_start = pd.to_datetime(tenant['lease_start']).date()
            existing_end = pd.to_datetime(tenant['lease_end']).date()
            
            # 檢查日期是否重疊
            if not (end <= existing_start or start >= existing_end):
                return True, f"與現有房客 {tenant['tenant_name']} 的租約期間衝突"
        
        return False, ""
    
    except Exception as e:
        logger.error(f"檢查房號衝突失敗: {e}", exc_info=True)
        return False, ""


# ============== Tab 1: 新增房客 ==============

def render_add_tab(tenant_service: TenantService):
    """新增房客 Tab"""
    section_header("新增房客", "➕")
    
    with st.form("add_tenant_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            room = st.selectbox(
                "房號 *",
                ROOMS.ALL_ROOMS,
                key="add_room"
            )
            name = st.text_input(
                "姓名 *",
                placeholder="例如: 王小明",
                key="add_name"
            )
            phone = st.text_input(
                "電話",
                placeholder="例如: 0912345678",
                key="add_phone"
            )
            deposit = st.number_input(
                "押金 *",
                min_value=0,
                value=10000,
                step=1000,
                key="add_deposit"
            )
        
        with col2:
            base_rent = st.number_input(
                "月租 *",
                min_value=0,
                value=8000,
                step=500,
                key="add_rent"
            )
            lease_start = st.date_input(
                "租約開始 *",
                value=date.today(),
                key="add_start"
            )
            lease_end = st.date_input(
                "租約到期 *",
                value=date.today().replace(year=date.today().year + 1),
                key="add_end"
            )
            payment_method = st.selectbox(
                "繳款方式 *",
                PAYMENT.METHODS,
                key="add_method"
            )
        
        st.divider()
        col3, col4 = st.columns(2)
        
        with col3:
            has_water_fee = st.checkbox(
                "包含水費折扣",
                value=False,
                help="勾選後會在租金中扣除 100 元水費",
                key="add_water"
            )
        
        with col4:
            annual_discount_months = st.number_input(
                "年繳折扣月數",
                min_value=0,
                max_value=12,
                value=0,
                help="年繳時可享有的免租月數",
                key="add_discount"
            )
        
        discount_notes = st.text_area(
            "折扣說明",
            placeholder="例如: 年繳送 1 個月",
            key="add_notes"
        )
        
        submitted = st.form_submit_button("✅ 新增房客", type="primary", use_container_width=True)
        
        if submitted:
            # 驗證必填欄位
            if not name.strip():
                st.error("❌ 請輸入姓名")
                return
            
            # 驗證電話
            phone_valid, phone_msg = validate_phone(phone)
            if not phone_valid:
                st.error(f"❌ {phone_msg}")
                return
            
            # 驗證日期
            date_valid, date_msg = validate_date_range(lease_start, lease_end)
            if not date_valid:
                st.error(f"❌ {date_msg}")
                return
            
            # 檢查房號衝突
            conflict, conflict_msg = check_room_conflict(
                tenant_service, room, lease_start, lease_end
            )
            if conflict:
                st.error(f"❌ {conflict_msg}")
                return
            
            # ✅ 使用 TenantService 新增房客
            try:
                tenant_data = {
                    'room_number': room,
                    'tenant_name': name,
                    'phone': phone,
                    'deposit': deposit,
                    'base_rent': base_rent,
                    'lease_start': lease_start,
                    'lease_end': lease_end,
                    'payment_method': payment_method,
                    'has_water_fee': has_water_fee,
                    'annual_discount_months': annual_discount_months,
                    'discount_notes': discount_notes
                }
                
                tenant_id = tenant_service.create_tenant(tenant_data)
                
                if tenant_id:
                    st.success(f"✅ 房客 {name} 新增成功！")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ 新增失敗")
            
            except Exception as e:
                st.error(f"❌ 新增失敗: {str(e)}")
                logger.error(f"新增房客失敗: {str(e)}", exc_info=True)


# ============== Tab 2: 房客列表 ==============

def render_list_tab(tenant_service: TenantService):
    """房客列表 Tab"""
    section_header("所有房客", "👥")
    
    try:
        tenants = tenant_service.get_all_tenants()
        
        if not tenants:
            empty_state(
                "目前沒有房客資料",
                "👥",
                "點擊「新增房客」開始管理"
            )
            return
        
        df = pd.DataFrame(tenants)
        
        # 篩選控制
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_room = st.multiselect(
                "篩選房號",
                ROOMS.ALL_ROOMS,
                key="filter_room"
            )
        
        with col2:
            filter_method = st.multiselect(
                "篩選繳款方式",
                PAYMENT.METHODS,
                key="filter_method"
            )
        
        with col3:
            search_name = st.text_input(
                "搜尋姓名",
                placeholder="輸入姓名關鍵字",
                key="search_name"
            )
        
        # 應用篩選
        filtered_df = df.copy()
        if filter_room:
            filtered_df = filtered_df[filtered_df['room_number'].isin(filter_room)]
        if filter_method:
            filtered_df = filtered_df[filtered_df['payment_method'].isin(filter_method)]
        if search_name:
            filtered_df = filtered_df[
                filtered_df['tenant_name'].str.contains(search_name, case=False, na=False)
            ]
        
        st.write(f"**共 {len(filtered_df)} 筆資料**")
        st.divider()
        
        # 顯示資料表
        if not filtered_df.empty:
            display_cols = ['room_number', 'tenant_name', 'phone', 'base_rent', 'lease_start', 'lease_end', 'payment_method']
            available_cols = [col for col in display_cols if col in filtered_df.columns]
            
            display_df = filtered_df[available_cols].copy()
            display_df.columns = ['房號', '姓名', '電話', '月租', '租約開始', '租約到期', '繳款方式']
            
            # 格式化日期
            if '租約開始' in display_df.columns:
                display_df['租約開始'] = pd.to_datetime(display_df['租約開始']).dt.strftime('%Y-%m-%d')
            if '租約到期' in display_df.columns:
                display_df['租約到期'] = pd.to_datetime(display_df['租約到期']).dt.strftime('%Y-%m-%d')
            
            data_table(display_df, key="tenant_list")
        else:
            st.info("📭 沒有符合條件的資料")
    
    except Exception as e:
        st.error(f"❌ 載入房客列表失敗: {str(e)}")
        logger.error(f"載入房客列表失敗: {str(e)}", exc_info=True)


# ============== Tab 3: 編輯房客 ==============

def render_edit_tab(tenant_service: TenantService):
    """編輯房客 Tab"""
    section_header("編輯房客", "✏️")
    
    try:
        tenants = tenant_service.get_all_tenants()
        
        if not tenants:
            empty_state("沒有可編輯的房客", "👥")
            return
        
        df = pd.DataFrame(tenants)
        
        # 選擇房客
        tenant_options = {
            f"{row['room_number']} - {row['tenant_name']}": row['id']
            for _, row in df.iterrows()
        }
        
        selected = st.selectbox(
            "選擇要編輯的房客",
            list(tenant_options.keys()),
            key="edit_select"
        )
        
        if not selected:
            return
        
        tenant_id = tenant_options[selected]
        tenant_data = df[df['id'] == tenant_id].iloc[0]
        
        st.divider()
        
        # ✅ 給 form 加上動態 key
        with st.form(key=f"edit_tenant_form_{tenant_id}"):
            col1, col2 = st.columns(2)
            
            with col1:
                room = st.selectbox(
                    "房號 *",
                    ROOMS.ALL_ROOMS,
                    index=ROOMS.ALL_ROOMS.index(tenant_data['room_number']),
                    key=f"edit_room_{tenant_id}"
                )
                name = st.text_input(
                    "姓名 *",
                    value=tenant_data['tenant_name'],
                    key=f"edit_name_{tenant_id}"
                )
                phone = st.text_input(
                    "電話",
                    value=tenant_data['phone'] or "",
                    key=f"edit_phone_{tenant_id}"
                )
                deposit = st.number_input(
                    "押金 *",
                    min_value=0,
                    max_value=1000000,
                    value=int(tenant_data['deposit'] or 0),
                    step=100,
                    key=f"edit_deposit_{tenant_id}",
                )
            
            with col2:
                base_rent = st.number_input(
                    "月租 *",
                    min_value=0,
                    value=int(tenant_data['base_rent']),
                    step=500,
                    key=f"edit_rent_{tenant_id}"
                )
                lease_start = st.date_input(
                    "租約開始 *",
                    value=pd.to_datetime(tenant_data['lease_start']).date(),
                    key=f"edit_start_{tenant_id}"
                )
                lease_end = st.date_input(
                    "租約到期 *",
                    value=pd.to_datetime(tenant_data['lease_end']).date(),
                    key=f"edit_end_{tenant_id}"
                )
                payment_method = st.selectbox(
                    "繳款方式 *",
                    PAYMENT.METHODS,
                    index=PAYMENT.METHODS.index(tenant_data['payment_method']),
                    key=f"edit_method_{tenant_id}"
                )
            
            st.divider()
            col3, col4 = st.columns(2)
            
            with col3:
                has_water_fee = st.checkbox(
                    "包含水費折扣",
                    value=bool(tenant_data.get('has_water_fee', False)),
                    key=f"edit_water_{tenant_id}"
                )
            
            with col4:
                annual_discount_months = st.number_input(
                    "年繳折扣月數",
                    min_value=0,
                    max_value=12,
                    value=int(tenant_data.get('annual_discount_months', 0)),
                    key=f"edit_discount_{tenant_id}"
                )
            
            discount_notes = st.text_area(
                "折扣說明",
                value=tenant_data.get('discount_notes', ''),
                key=f"edit_notes_{tenant_id}"
            )
            
            st.divider()
            col_update, col_delete = st.columns([3, 1])
            
            with col_update:
                update_btn = st.form_submit_button("💾 儲存變更", type="primary", use_container_width=True)
            
            with col_delete:
                delete_btn = st.form_submit_button("🗑️ 刪除", type="secondary", use_container_width=True)
            
            if update_btn:
                # 驗證
                if not name.strip():
                    st.error("❌ 請輸入姓名")
                    return
                
                phone_valid, phone_msg = validate_phone(phone)
                if not phone_valid:
                    st.error(f"❌ {phone_msg}")
                    return
                
                date_valid, date_msg = validate_date_range(lease_start, lease_end)
                if not date_valid:
                    st.error(f"❌ {date_msg}")
                    return
                
                conflict, conflict_msg = check_room_conflict(
                    tenant_service, room, lease_start, lease_end, tenant_id
                )
                if conflict:
                    st.error(f"❌ {conflict_msg}")
                    return
                
                # ✅ 使用 TenantService 更新房客
                try:
                    updated_data = {
                        'room_number': room,
                        'tenant_name': name,
                        'phone': phone,
                        'deposit': deposit,
                        'base_rent': base_rent,
                        'lease_start': lease_start,
                        'lease_end': lease_end,
                        'payment_method': payment_method,
                        'has_water_fee': has_water_fee,
                        'annual_discount_months': annual_discount_months,
                        'discount_notes': discount_notes
                    }
                    
                    ok = tenant_service.update_tenant(tenant_id, updated_data)
                    
                    if ok:
                        st.success(f"✅ 房客 {name} 已更新")
                        st.rerun()
                    else:
                        st.error("❌ 更新失敗")
                
                except Exception as e:
                    st.error(f"❌ 更新失敗: {str(e)}")
                    logger.error(f"更新房客失敗: {str(e)}", exc_info=True)
            
            if delete_btn:
                # ✅ 使用 session_state 實作二次確認
                if not st.session_state.get(f'confirm_delete_{tenant_id}'):
                    st.session_state[f'confirm_delete_{tenant_id}'] = True
                    st.warning("⚠️ 再次點擊「刪除」確認刪除房客")
                else:
                    try:
                        ok = tenant_service.delete_tenant(tenant_id)
                        
                        if ok:
                            st.success(f"✅ 房客 {tenant_data['tenant_name']} 已刪除")
                            # 清除確認狀態
                            del st.session_state[f'confirm_delete_{tenant_id}']
                            st.rerun()
                        else:
                            st.error("❌ 刪除失敗")
                    
                    except Exception as e:
                        st.error(f"❌ 刪除失敗: {str(e)}")
                        logger.error(f"刪除房客失敗: {str(e)}", exc_info=True)
    
    except Exception as e:
        st.error(f"❌ 載入編輯頁面失敗: {str(e)}")
        logger.error(f"載入編輯頁面失敗: {str(e)}", exc_info=True)


# ============== 主函數 ==============

def render():
    """主渲染函數（供 main.py 動態載入使用）"""
    st.title("👥 房客管理")
    
    # ✅ 初始化 Service
    tenant_service = TenantService()
    
    tab1, tab2, tab3 = st.tabs(["➕ 新增房客", "📋 房客列表", "✏️ 編輯房客"])
    
    with tab1:
        render_add_tab(tenant_service)
    
    with tab2:
        render_list_tab(tenant_service)
    
    with tab3:
        render_edit_tab(tenant_service)


# ✅ Streamlit 頁面入口
def show():
    """Streamlit 頁面入口"""
    render()


if __name__ == "__main__":
    show()
