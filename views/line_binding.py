"""
LINE 綁定管理介面 - v1.0
✅ 綁定狀態總覽
✅ 批量解除綁定
✅ 單一房客綁定設定
"""

import streamlit as st
import pandas as pd
from services.tenant_service import TenantService
from services.tenant_contact_service import TenantContactService
import logging

logger = logging.getLogger(__name__)


def render():
    """主入口"""
    render_line_binding_page()


def show():
    """Streamlit 頁面入口"""
    render()


def render_line_binding_page():
    """LINE 綁定管理主頁面"""
    
    st.title("📱 LINE 綁定管理")
    
    tenant_svc = TenantService()
    contact_svc = TenantContactService()
    
    # === 建立 Tabs ===
    tab1, tab2 = st.tabs(["📊 綁定總覽", "🔗 綁定設定"])
    
    with tab1:
        render_binding_overview(tenant_svc, contact_svc)
    
    with tab2:
        render_binding_editor(tenant_svc, contact_svc)


# ==================== Tab 1: 綁定總覽 ====================

def render_binding_overview(tenant_svc: TenantService, contact_svc: TenantContactService):
    """綁定狀態總覽"""
    
    st.subheader("📊 LINE 綁定狀態總覽")
    
    # === 快速篩選 ===
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ 已綁定", key="filter_bound", use_container_width=True, type="primary"):
            st.session_state.line_filter = "bound"
            st.rerun()
    
    with col2:
        if st.button("📭 未綁定", key="filter_unbound", use_container_width=True):
            st.session_state.line_filter = "unbound"
            st.rerun()
    
    with col3:
        if st.button("🔄 全部", key="filter_all", use_container_width=True):
            st.session_state.line_filter = "all"
            st.rerun()
    
    if 'line_filter' not in st.session_state:
        st.session_state.line_filter = "all"
    
    current_filter = st.session_state.line_filter
    
    st.divider()
    
    # === 載入資料 ===
    try:
        # 取得所有房客
        tenants_df = tenant_svc.get_tenants(active_only=True)
        
        if tenants_df.empty:
            st.warning("⚠️ 目前沒有房客資料")
            return
        
        # 建立綁定狀態表
        binding_data = []
        
        for _, tenant in tenants_df.iterrows():
            tenant_id = tenant['id']
            room_number = tenant['roomnumber']
            tenant_name = tenant['tenantname']
            phone = tenant.get('phone', 'N/A')
            
            # 查詢綁定狀態
            contact = contact_svc.get_tenant_contact(tenant_id)
            
            if contact and contact.get('line_user_id'):
                line_id = contact['line_user_id']
                # 遮蔽部分 ID（隱私保護）
                masked_id = f"{line_id[:8]}...{line_id[-4:]}" if len(line_id) > 12 else line_id
                status = "✅ 已綁定"
                notify_rent = "✅" if contact.get('notify_rent', False) else "❌"
                notify_elec = "✅" if contact.get('notify_electricity', False) else "❌"
            else:
                masked_id = "-"
                status = "📭 未綁定"
                notify_rent = "-"
                notify_elec = "-"
            
            binding_data.append({
                'id': tenant_id,
                '房號': room_number,
                '房客': tenant_name,
                '電話': phone,
                '綁定狀態': status,
                'LINE ID': masked_id,
                '租金通知': notify_rent,
                '電費通知': notify_elec,
                '_line_user_id': contact['line_user_id'] if contact else None  # 隱藏欄位，用於解綁
            })
        
        df = pd.DataFrame(binding_data)
        
        # 篩選
        if current_filter == "bound":
            df = df[df['綁定狀態'] == '✅ 已綁定']
            st.info(f"📊 顯示：已綁定（共 {len(df)} 筆）")
        elif current_filter == "unbound":
            df = df[df['綁定狀態'] == '📭 未綁定']
            st.info(f"📊 顯示：未綁定（共 {len(df)} 筆）")
        else:
            st.info(f"📊 顯示：全部（共 {len(df)} 筆）")
        
        if df.empty:
            st.success("✅ 沒有符合條件的記錄")
            return
        
        # === 統計摘要 ===
        total_tenants = len(tenants_df)
        bound_count = len(binding_data) - df[df['綁定狀態'] == '📭 未綁定'].shape[0]
        unbound_count = total_tenants - bound_count
        binding_rate = (bound_count / total_tenants * 100) if total_tenants > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("總房客數", f"{total_tenants} 人")
        
        with col2:
            st.metric("已綁定", f"{bound_count} 人")
        
        with col3:
            st.metric("未綁定", f"{unbound_count} 人")
        
        with col4:
            st.metric("綁定率", f"{binding_rate:.1f}%")
        
        st.divider()
        
        # === 顯示表格 ===
        st.markdown("### 📋 詳細列表")
        
        # 排序：未綁定優先
        df_sorted = df.sort_values(['綁定狀態', '房號'], ascending=[True, True])
        
        # 顯示（不含隱藏欄位）
        display_cols = ['房號', '房客', '電話', '綁定狀態', 'LINE ID', '租金通知', '電費通知']
        
        st.dataframe(
            df_sorted[display_cols],
            use_container_width=True,
            hide_index=True
        )
        
        # === 批量解除綁定 ===
        bound_df = df[df['綁定狀態'] == '✅ 已綁定']
        
        if not bound_df.empty:
            st.divider()
            st.markdown("### ❌ 批量解除綁定")
            
            st.warning("⚠️ 解除綁定後，該房客將無法接收 LINE 通知")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                selected_ids = st.multiselect(
                    "選擇要解除綁定的房客（可多選）",
                    options=bound_df['id'].tolist(),
                    format_func=lambda x: (
                        f"{bound_df[bound_df['id']==x]['房號'].values[0]} - "
                        f"{bound_df[bound_df['id']==x]['房客'].values[0]}"
                    ),
                    key="unbind_multiselect"
                )
            
            with col2:
                st.write("")
                st.write("")
                if st.button(
                    f"❌ 解綁 ({len(selected_ids)})",
                    type="secondary",
                    disabled=len(selected_ids) == 0,
                    use_container_width=True,
                    key="batch_unbind"
                ):
                    with st.spinner("處理中..."):
                        success_count = 0
                        fail_count = 0
                        
                        for tenant_id in selected_ids:
                            ok, msg = contact_svc.unbind_line_user(tenant_id)
                            
                            if ok:
                                success_count += 1
                            else:
                                fail_count += 1
                                logger.error(f"解除綁定失敗: tenant_id={tenant_id}, {msg}")
                        
                        if success_count > 0:
                            st.success(f"✅ 成功解除 {success_count} 筆綁定")
                        
                        if fail_count > 0:
                            st.error(f"❌ 失敗 {fail_count} 筆")
                        
                        st.rerun()
    
    except Exception as e:
        st.error(f"❌ 載入資料失敗: {str(e)}")
        logger.error(f"綁定總覽錯誤: {str(e)}", exc_info=True)


# ==================== Tab 2: 綁定設定 ====================

def render_binding_editor(tenant_svc: TenantService, contact_svc: TenantContactService):
    """單一房客綁定設定"""
    
    st.subheader("🔗 LINE 綁定設定")
    
    try:
        # 取得所有房客
        tenants_df = tenant_svc.get_tenants(active_only=True)
        
        if tenants_df.empty:
            st.warning("⚠️ 目前沒有房客資料")
            return
        
        # 房客選擇
        tenant_options = {
            f"{row['roomnumber']} - {row['tenantname']}": row['id']
            for _, row in tenants_df.iterrows()
        }
        
        selected = st.selectbox(
            "選擇房客",
            options=list(tenant_options.keys()),
            key="line_bind_tenant_select"
        )
        
        if not selected:
            return
        
        tenant_id = tenant_options[selected]
        
        # 取得目前綁定狀態
        contact_info = contact_svc.get_tenant_contact(tenant_id)
        
        st.divider()
        
        # === 顯示目前狀態 ===
        if contact_info and contact_info.get('line_user_id'):
            st.markdown("#### ✅ 目前綁定狀態")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"**LINE ID:** `{contact_info['line_user_id']}`")
            
            with col2:
                notify_rent = contact_info.get('notify_rent', True)
                notify_elec = contact_info.get('notify_electricity', True)
                st.info(f"**通知設定:** 租金 {'✅' if notify_rent else '❌'} / 電費 {'✅' if notify_elec else '❌'}")
            
            # 更新通知設定
            with st.form(key=f"update_notify_form_{tenant_id}"):
                st.markdown("##### 🔔 更新通知設定")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    new_notify_rent = st.checkbox(
                        "接收租金通知",
                        value=notify_rent,
                        key=f"update_rent_{tenant_id}"
                    )
                
                with col2:
                    new_notify_elec = st.checkbox(
                        "接收電費通知",
                        value=notify_elec,
                        key=f"update_elec_{tenant_id}"
                    )
                
                update_submitted = st.form_submit_button(
                    "🔄 更新設定",
                    type="primary",
                    use_container_width=True
                )
                
                if update_submitted:
                    ok, msg = contact_svc.update_notification_settings(
                        tenant_id,
                        notify_rent=new_notify_rent,
                        notify_electricity=new_notify_elec
                    )
                    
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            
            st.divider()
            
            # 解除綁定
            st.markdown("##### ❌ 解除綁定")
            st.warning("⚠️ 解除綁定後，該房客將無法接收 LINE 通知")
            
            if st.button(
                "❌ 確認解除綁定",
                key=f"unbind_single_{tenant_id}",
                type="secondary"
            ):
                with st.spinner("處理中..."):
                    ok, msg = contact_svc.unbind_line_user(tenant_id)
                    
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        else:
            st.info("📭 此房客尚未綁定 LINE")
        
        st.divider()
        
        # === 新增/更新綁定 ===
        with st.form(key=f"bind_form_{tenant_id}"):
            st.markdown("#### 🔗 新增/更新 LINE 綁定")
            
            line_user_id = st.text_input(
                "LINE User ID",
                placeholder="U1234567890abcdef1234567890abcdef",
                help="從 LINE Bot Webhook 取得的 User ID（通常以 'U' 開頭，長度 33 字元）",
                key=f"line_id_input_{tenant_id}"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                bind_notify_rent = st.checkbox(
                    "接收租金通知",
                    value=True,
                    key=f"bind_rent_{tenant_id}"
                )
            
            with col2:
                bind_notify_elec = st.checkbox(
                    "接收電費通知",
                    value=True,
                    key=f"bind_elec_{tenant_id}"
                )
            
            st.caption("💡 提示：LINE User ID 可從 LINE Bot Webhook 的 `userId` 欄位取得")
            
            bind_submitted = st.form_submit_button(
                "✅ 確認綁定",
                type="primary",
                use_container_width=True
            )
            
            if bind_submitted:
                # 驗證格式
                if not line_user_id:
                    st.error("❌ 請輸入 LINE User ID")
                elif not line_user_id.startswith('U'):
                    st.error("❌ LINE User ID 格式錯誤（應以 'U' 開頭）")
                elif len(line_user_id) != 33:
                    st.warning("⚠️ LINE User ID 長度通常為 33 字元，請確認是否正確")
                    
                    # 仍然允許綁定
                    with st.spinner("綁定中..."):
                        ok, msg = contact_svc.bind_line_user(
                            tenant_id,
                            line_user_id,
                            notify_rent=bind_notify_rent,
                            notify_electricity=bind_notify_elec
                        )
                        
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    with st.spinner("綁定中..."):
                        ok, msg = contact_svc.bind_line_user(
                            tenant_id,
                            line_user_id,
                            notify_rent=bind_notify_rent,
                            notify_electricity=bind_notify_elec
                        )
                        
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
    
    except Exception as e:
        st.error(f"❌ 載入失敗: {str(e)}")
        logger.error(f"綁定設定錯誤: {str(e)}", exc_info=True)


# ==================== 輔助工具 ====================

def render_line_id_helper():
    """LINE User ID 查詢輔助工具（選用）"""
    
    st.markdown("### 🔍 LINE User ID 查詢工具")
    
    st.info("""
**如何取得 LINE User ID？**

1. **從 LINE Bot Webhook：**
   - 當使用者傳訊息給你的 Bot 時，webhook 會收到包含 `userId` 的 JSON
   - 例如：`"userId": "U1234567890abcdef1234567890abcdef"`

2. **從 LINE Official Account Manager：**
   - 無法直接查看 User ID
   - 需要透過 Webhook 或 Messaging API 取得

3. **測試方法：**
   - 讓房客傳訊息給你的 LINE Bot
   - 在 Bot 的 Webhook endpoint 記錄 `userId`
   - 複製該 ID 到此介面綁定
    """)
    
    st.code("""
# 範例 Webhook Handler (Flask)
@app.route("/webhook", methods=['POST'])
def webhook():
    body = request.get_data(as_text=True)
    events = json.loads(body)['events']
    
    for event in events:
        user_id = event['source']['userId']
        print(f"收到訊息，User ID: {user_id}")
        
        # 可以記錄到資料庫或回傳給使用者
    
    return 'OK'
    """, language="python")


# ============================================
# 本機測試入口
# ============================================
if __name__ == "__main__":
    render_line_binding_page()
