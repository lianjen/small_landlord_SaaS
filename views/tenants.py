"""
房客管理 - v5.0 (Pydantic + Service 架構 + Auth)
✅ 整合認證系統
✅ 登入保護
✅ 整合 Pydantic 驗證層
✅ 完全移除 db 依賴
✅ 使用 TenantService v5.0
✅ 完整表單驗證
✅ 租約衝突檢查
✅ 刪除確認優化
✅ 適配 Supabase 欄位
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Optional, Tuple
import logging
from pydantic import ValidationError

# ✅ 導入認證管理
try:
    from utils.session_manager import session_manager
    HAS_SESSION_MANAGER = True
except ImportError:
    HAS_SESSION_MANAGER = False
    import warnings
    warnings.warn("⚠️ session_manager 未載入，認證功能將受限")

# ✅ 導入 Pydantic Schemas
from schemas.tenant import TenantCreate, TenantUpdate

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


# ============== 認證檢查 ==============

def check_authentication() -> bool:
    """
    檢查用戶是否已登入
    
    Returns:
        bool: True=已登入, False=未登入
    """
    if not HAS_SESSION_MANAGER:
        # 如果沒有 session_manager，檢查開發模式
        return st.secrets.get("dev_mode", False)
    
    return session_manager.is_authenticated()


def render_login_required():
    """渲染登入提示頁面"""
    st.warning("🔒 此頁面需要登入才能使用")
    st.info("👉 請先前往「登入」頁面完成登入")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔑 前往登入", use_container_width=True, type="primary"):
            st.switch_page("pages/login.py")


# ============== 輔助函數 ==============

def format_validation_error(error: ValidationError) -> str:
    """
    格式化 Pydantic 驗證錯誤訊息
    
    Args:
        error: ValidationError 物件
    
    Returns:
        格式化的錯誤訊息
    """
    errors = []
    for err in error.errors():
        field = err['loc'][0] if err['loc'] else 'unknown'
        message = err['msg']
        
        # 翻譯欄位名稱
        field_names = {
            'name': '姓名',
            'room_number': '房號',
            'phone': '電話',
            'email': 'Email',
            'id_number': '身分證字號',
            'rent_amount': '月租',
            'rent_due_day': '繳租日',
            'deposit_amount': '押金',
            'move_in_date': '入住日期',
            'move_out_date': '退租日期',
            'status': '狀態',
            'notes': '備註'
        }
        
        field_cn = field_names.get(field, field)
        errors.append(f"{field_cn}: {message}")
    
    return "\n".join(errors)


def check_room_conflict(
    tenant_service: TenantService,
    room: str,
    start: date,
    end: date,
    exclude_tenant_id: Optional[str] = None
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
        # 檢查房間是否可用
        if exclude_tenant_id:
            # 編輯模式：允許自己的房號
            existing_tenant = tenant_service.get_tenant_by_room(room)
            if existing_tenant and existing_tenant['id'] != exclude_tenant_id:
                return True, f"房間 {room} 已有其他租客 {existing_tenant['name']}"
        else:
            # 新增模式：房間必須完全空閒
            if not tenant_service.check_room_availability(room):
                existing_tenant = tenant_service.get_tenant_by_room(room)
                if existing_tenant:
                    return True, f"房間 {room} 已有租客 {existing_tenant['name']}"
        
        return False, ""
    
    except Exception as e:
        logger.error(f"檢查房號衝突失敗: {e}", exc_info=True)
        return False, ""


# ============== Tab 1: 新增房客（整合 Pydantic）==============

def render_add_tab(tenant_service: TenantService):
    """新增房客 Tab（整合 Pydantic 驗證）"""
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
                placeholder="例如: 0912-345-678",
                key="add_phone"
            )
            email = st.text_input(
                "Email",
                placeholder="例如: tenant@example.com",
                key="add_email"
            )
        
        with col2:
            rent_amount = st.number_input(
                "月租 *",
                min_value=0,
                value=6000,
                step=500,
                key="add_rent"
            )
            deposit_amount = st.number_input(
                "押金 *",
                min_value=0,
                value=12000,
                step=1000,
                key="add_deposit"
            )
            move_in_date = st.date_input(
                "入住日期 *",
                value=date.today(),
                key="add_start"
            )
            move_out_date = st.date_input(
                "退租日期",
                value=date.today().replace(year=date.today().year + 1),
                key="add_end"
            )
        
        st.divider()
        
        col3, col4 = st.columns(2)
        
        with col3:
            rent_due_day = st.number_input(
                "每月繳租日",
                min_value=1,
                max_value=31,
                value=5,
                help="每月的第幾天繳租金",
                key="add_due_day"
            )
        
        with col4:
            id_number = st.text_input(
                "身分證字號",
                placeholder="例如: A123456789",
                key="add_id_number"
            )
        
        notes = st.text_area(
            "備註",
            placeholder="例如: 優良房客、特殊需求等",
            key="add_notes"
        )
        
        submitted = st.form_submit_button("✅ 新增房客", type="primary", use_container_width=True)
        
        if submitted:
            try:
                # ==================== Pydantic 驗證 ====================
                
                tenant_data = TenantCreate(
                    name=name,
                    room_number=room,
                    phone=phone if phone else None,
                    email=email if email else None,
                    id_number=id_number if id_number else None,
                    rent_amount=float(rent_amount),
                    rent_due_day=rent_due_day,
                    deposit_amount=float(deposit_amount),
                    move_in_date=move_in_date,
                    move_out_date=move_out_date if move_out_date else None,
                    notes=notes if notes else None
                )
                
                # ==================== 額外業務驗證 ====================
                
                # 檢查房號衝突
                conflict, conflict_msg = check_room_conflict(
                    tenant_service, room, move_in_date, move_out_date or date(2099, 12, 31)
                )
                if conflict:
                    st.error(f"❌ {conflict_msg}")
                    return
                
                # ==================== 呼叫 Service ====================
                
                success, message = tenant_service.add_tenant(tenant_data=tenant_data)
                
                if success:
                    st.success(f"✅ {message}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
            
            except ValidationError as e:
                # Pydantic 驗證錯誤
                error_msg = format_validation_error(e)
                st.error(f"❌ 資料驗證失敗:\n{error_msg}")
            
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
            filter_status = st.multiselect(
                "篩選狀態",
                ["active", "inactive"],
                default=["active"],
                key="filter_status"
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
        
        if filter_status:
            filtered_df = filtered_df[filtered_df['status'].isin(filter_status)]
        
        if search_name:
            filtered_df = filtered_df[
                filtered_df['name'].str.contains(search_name, case=False, na=False)
            ]
        
        st.write(f"**共 {len(filtered_df)} 筆資料**")
        st.divider()
        
        # 顯示資料表
        if not filtered_df.empty:
            # ✅ 使用正確的欄位名稱
            display_cols = [
                'room_number', 'name', 'phone', 'rent_amount', 
                'move_in_date', 'move_out_date', 'status'
            ]
            available_cols = [col for col in display_cols if col in filtered_df.columns]
            
            display_df = filtered_df[available_cols].copy()
            display_df.columns = ['房號', '姓名', '電話', '月租', '入住日期', '退租日期', '狀態']
            
            # 格式化日期
            if '入住日期' in display_df.columns:
                display_df['入住日期'] = pd.to_datetime(display_df['入住日期']).dt.strftime('%Y-%m-%d')
            if '退租日期' in display_df.columns:
                display_df['退租日期'] = pd.to_datetime(display_df['退租日期'], errors='coerce').dt.strftime('%Y-%m-%d')
            
            # 格式化狀態
            if '狀態' in display_df.columns:
                display_df['狀態'] = display_df['狀態'].replace({
                    'active': '✅ 活躍',
                    'inactive': '❌ 已退租'
                })
            
            data_table(display_df, key="tenant_list")
        else:
            st.info("📭 沒有符合條件的資料")
    
    except Exception as e:
        st.error(f"❌ 載入房客列表失敗: {str(e)}")
        logger.error(f"載入房客列表失敗: {str(e)}", exc_info=True)


# ============== Tab 3: 編輯房客（整合 Pydantic）==============

def render_edit_tab(tenant_service: TenantService):
    """編輯房客 Tab（整合 Pydantic 驗證）"""
    section_header("編輯房客", "✏️")
    
    try:
        tenants = tenant_service.get_all_tenants()
        
        if not tenants:
            empty_state("沒有可編輯的房客", "👥")
            return
        
        df = pd.DataFrame(tenants)
        
        # 選擇房客
        tenant_options = {
            f"{row['room_number']} - {row['name']} ({row['status']})": row['id']
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
                    value=tenant_data['name'],
                    key=f"edit_name_{tenant_id}"
                )
                phone = st.text_input(
                    "電話",
                    value=tenant_data.get('phone') or "",
                    key=f"edit_phone_{tenant_id}"
                )
                email = st.text_input(
                    "Email",
                    value=tenant_data.get('email') or "",
                    key=f"edit_email_{tenant_id}"
                )
            
            with col2:
                rent_amount = st.number_input(
                    "月租 *",
                    min_value=0,
                    value=float(tenant_data['rent_amount']),
                    step=500,
                    key=f"edit_rent_{tenant_id}"
                )
                deposit_amount = st.number_input(
                    "押金 *",
                    min_value=0,
                    value=float(tenant_data['deposit_amount']),
                    step=1000,
                    key=f"edit_deposit_{tenant_id}"
                )
                move_in_date = st.date_input(
                    "入住日期 *",
                    value=pd.to_datetime(tenant_data['move_in_date']).date(),
                    key=f"edit_start_{tenant_id}"
                )
                move_out_date_value = tenant_data.get('move_out_date')
                move_out_date = st.date_input(
                    "退租日期",
                    value=pd.to_datetime(move_out_date_value).date() if move_out_date_value else None,
                    key=f"edit_end_{tenant_id}"
                )
            
            st.divider()
            
            col3, col4 = st.columns(2)
            
            with col3:
                rent_due_day = st.number_input(
                    "每月繳租日",
                    min_value=1,
                    max_value=31,
                    value=int(tenant_data.get('rent_due_day', 5)),
                    key=f"edit_due_day_{tenant_id}"
                )
            
            with col4:
                id_number = st.text_input(
                    "身分證字號",
                    value=tenant_data.get('id_number') or "",
                    key=f"edit_id_number_{tenant_id}"
                )
            
            status = st.selectbox(
                "狀態",
                ["active", "inactive"],
                index=0 if tenant_data['status'] == 'active' else 1,
                format_func=lambda x: "✅ 活躍" if x == "active" else "❌ 已退租",
                key=f"edit_status_{tenant_id}"
            )
            
            notes = st.text_area(
                "備註",
                value=tenant_data.get('notes') or "",
                key=f"edit_notes_{tenant_id}"
            )
            
            st.divider()
            col_update, col_delete = st.columns([3, 1])
            
            with col_update:
                update_btn = st.form_submit_button("💾 儲存變更", type="primary", use_container_width=True)
            
            with col_delete:
                delete_btn = st.form_submit_button("🗑️ 刪除", type="secondary", use_container_width=True)
            
            if update_btn:
                try:
                    # ==================== Pydantic 驗證 ====================
                    
                    update_data = TenantUpdate(
                        name=name,
                        room_number=room,
                        phone=phone if phone else None,
                        email=email if email else None,
                        id_number=id_number if id_number else None,
                        rent_amount=float(rent_amount),
                        rent_due_day=rent_due_day,
                        deposit_amount=float(deposit_amount),
                        move_in_date=move_in_date,
                        move_out_date=move_out_date if move_out_date else None,
                        status=status,
                        notes=notes if notes else None
                    )
                    
                    # ==================== 額外業務驗證 ====================
                    
                    # 檢查房號衝突
                    conflict, conflict_msg = check_room_conflict(
                        tenant_service, 
                        room, 
                        move_in_date, 
                        move_out_date or date(2099, 12, 31),
                        tenant_id
                    )
                    if conflict:
                        st.error(f"❌ {conflict_msg}")
                        return
                    
                    # ==================== 呼叫 Service ====================
                    
                    success, message = tenant_service.update_tenant(
                        tenant_id=tenant_id,
                        tenant_data=update_data
                    )
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                
                except ValidationError as e:
                    # Pydantic 驗證錯誤
                    error_msg = format_validation_error(e)
                    st.error(f"❌ 資料驗證失敗:\n{error_msg}")
                
                except Exception as e:
                    st.error(f"❌ 更新失敗: {str(e)}")
                    logger.error(f"更新房客失敗: {str(e)}", exc_info=True)
            
            if delete_btn:
                # ✅ 使用 session_state 實作二次確認
                confirm_key = f'confirm_delete_{tenant_id}'
                
                if not st.session_state.get(confirm_key):
                    st.session_state[confirm_key] = True
                    st.warning("⚠️ 再次點擊「刪除」確認刪除房客")
                    st.rerun()
                else:
                    try:
                        success, message = tenant_service.delete_tenant(tenant_id)
                        
                        if success:
                            st.success(f"✅ {message}")
                            # 清除確認狀態
                            if confirm_key in st.session_state:
                                del st.session_state[confirm_key]
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    
                    except Exception as e:
                        st.error(f"❌ 刪除失敗: {str(e)}")
                        logger.error(f"刪除房客失敗: {str(e)}", exc_info=True)
    
    except Exception as e:
        st.error(f"❌ 載入編輯頁面失敗: {str(e)}")
        logger.error(f"載入編輯頁面失敗: {str(e)}", exc_info=True)


# ============== Tab 4: 統計資訊 ==============

def render_stats_tab(tenant_service: TenantService):
    """統計資訊 Tab"""
    section_header("統計資訊", "📊")
    
    try:
        stats = tenant_service.get_tenant_statistics()
        
        # 顯示統計卡片
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "總房客數",
                stats['total_tenants'],
                f"{stats['occupancy_rate']}% 出租率"
            )
        
        with col2:
            st.metric(
                "已出租房間",
                stats['occupied_rooms'],
                f"共 {stats['total_rooms']} 間"
            )
        
        with col3:
            st.metric(
                "月租總額",
                f"NT$ {stats['total_rent']:,.0f}",
                f"平均 NT$ {stats['avg_rent']:,.0f}"
            )
        
        with col4:
            st.metric(
                "押金總額",
                f"NT$ {stats['total_deposit']:,.0f}"
            )
        
        st.divider()
        
        # 空房列表
        section_header("空房列表", "🏠", divider=False)
        vacant_rooms = tenant_service.get_available_rooms()
        
        if vacant_rooms:
            st.success(f"✅ 目前有 {len(vacant_rooms)} 間空房")
            cols = st.columns(6)
            for idx, room in enumerate(vacant_rooms):
                with cols[idx % 6]:
                    st.button(room, key=f"vacant_{room}", use_container_width=True)
        else:
            st.info("📭 目前沒有空房")
        
        st.divider()
        
        # 即將到期租約
        section_header("即將到期租約（45天內）", "⏰", divider=False)
        expiring = tenant_service.get_expiring_leases(days=45)
        
        if expiring:
            st.warning(f"⚠️ 有 {len(expiring)} 筆租約即將到期")
            
            expiring_df = pd.DataFrame(expiring)
            display_df = expiring_df[['room_number', 'name', 'phone', 'move_out_date', 'days_remaining']].copy()
            display_df.columns = ['房號', '姓名', '電話', '退租日期', '剩餘天數']
            
            # 格式化日期
            display_df['退租日期'] = pd.to_datetime(display_df['退租日期']).dt.strftime('%Y-%m-%d')
            
            data_table(display_df, key="expiring_leases")
        else:
            st.success("✅ 近期沒有租約到期")
    
    except Exception as e:
        st.error(f"❌ 載入統計資訊失敗: {str(e)}")
        logger.error(f"載入統計資訊失敗: {str(e)}", exc_info=True)


# ============== 主函數（整合認證）==============

def render():
    """主渲染函數（供 main.py 動態載入使用）"""
    
    # ✅ 認證檢查
    if not check_authentication():
        render_login_required()
        return
    
    st.title("👥 房客管理")
    
    # ✅ 顯示當前用戶資訊（可選）
    if HAS_SESSION_MANAGER:
        user_info = session_manager.get_user_info()
        if user_info:
            with st.sidebar:
                st.caption(f"👤 {user_info.get('email', '未知用戶')}")
    
    # ✅ 初始化 Service
    try:
        tenant_service = TenantService()
        
        # 健康檢查
        if not tenant_service.health_check():
            st.error("❌ 資料庫連接失敗，請稍後再試")
            return
    
    except Exception as e:
        st.error(f"❌ 初始化服務失敗: {str(e)}")
        logger.error(f"初始化 TenantService 失敗: {str(e)}", exc_info=True)
        return
    
    # ✅ 渲染 Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["➕ 新增房客", "📋 房客列表", "✏️ 編輯房客", "📊 統計資訊"])
    
    with tab1:
        render_add_tab(tenant_service)
    
    with tab2:
        render_list_tab(tenant_service)
    
    with tab3:
        render_edit_tab(tenant_service)
    
    with tab4:
        render_stats_tab(tenant_service)


# ✅ Streamlit 頁面入口
def show():
    """Streamlit 頁面入口"""
    render()


if __name__ == "__main__":
    show()
