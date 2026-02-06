"""
租客 LINE 綁定管理（後台版） - v1.0

✅ 房東後台手動綁定 LINE User ID
✅ 直接使用 TenantContactService.bind_line_user (is_verified = true)
✅ 顯示目前所有綁定狀態（含通知偏好）
✅ 與現有 TenantService / TenantContactService 完整對齊
"""

import streamlit as st
from typing import Dict, List

from services.tenant_service import TenantService
from services.tenant_contact_service import TenantContactService
from services.logger import logger


def _load_active_tenants(tenant_svc: TenantService) -> List[Dict]:
    """
    輔助：載入啟用中的租客清單（List[Dict]）
    會優先使用 get_active_tenants()，若空再退回 get_all_tenants()
    """
    try:
        tenants = tenant_svc.get_active_tenants()  # 回傳 List[Dict][cite:50]
        if tenants:
            return tenants

        # 安全退回：如果沒有 active，就抓全部，讓你至少能選
        tenants = tenant_svc.get_all_tenants(include_inactive=False)[
            :
        ]  # List[Dict][cite:50]
        return tenants or []

    except Exception as e:
        logger.error(f"❌ 載入租客清單失敗: {e}", exc_info=True)
        return []


def render_binding_form(
    tenant_svc: TenantService, contact_svc: TenantContactService
):
    """
    主表單：選租客 + 輸入 LINE User ID + 通知設定
    """
    st.subheader("🔗 綁定 / 更新租客的 LINE 帳號")

    tenants = _load_active_tenants(tenant_svc)

    if not tenants:
        st.info("目前沒有啟用中的租客，請先在『租客管理』建立租客。")
        return

    # 轉成簡單的 options：顯示用字串 → tenant_id
    options = {
        f"{t.get('room_number', '')}｜{t.get('tenant_name', '')} (ID: {t.get('id')})": t[
            "id"
        ]
        for t in tenants
        if t.get("id") is not None
    }

    selected_label = st.selectbox("選擇要綁定的租客", list(options.keys()))
    tenant_id = options[selected_label]

    # 顯示該租客目前的聯絡狀態（如果有）
    with st.expander("目前綁定／通知狀態", expanded=False):
        contact_info = contact_svc.get_tenant_contact(tenant_id)  # Dict 或 None[cite:48]
        if not contact_info:
            st.write("此租客目前尚無任何聯絡設定紀錄。")
        else:
            st.markdown(
                f"""
**房號**：`{contact_info.get('room_number')}`  
**租客**：`{contact_info.get('tenant_name')}`  
**LINE User ID**：`{(contact_info.get('line_user_id') or '')[:12]}...`  
**是否已驗證**：`{ '✅ 已驗證' if contact_info.get('is_verified') else '❌ 未驗證' }`  
**租金通知**：`{ '✅ 開啟' if contact_info.get('notify_rent') else '❌ 關閉' }`  
**電費通知**：`{ '✅ 開啟' if contact_info.get('notify_electricity') else '❌ 關閉' }`  
"""
            )

    st.markdown("---")

    # 綁定表單
    with st.form("line_binding_form"):
        line_user_id = st.text_input(
            "貼上租客提供的 LINE User ID",
            placeholder="例：U1234567890abcdef...",
            help="請讓租客在 LINE Bot 對話中輸入「我的ID」，然後將回傳的 User ID 貼到這裡。",
        )

        col1, col2 = st.columns(2)
        with col1:
            notify_rent = st.checkbox("接收租金通知", value=True)
        with col2:
            notify_elec = st.checkbox("接收電費通知", value=True)

        submitted = st.form_submit_button("🔗 綁定 / 更新綁定", use_container_width=True)

    if submitted:
        if not line_user_id or len(line_user_id) < 10:
            st.error("❌ 請貼上有效的 LINE User ID（長度至少 10 個字元）")
            return

        try:
            ok, msg = contact_svc.bind_line_user(
                tenant_id=tenant_id,
                line_user_id=line_user_id,
                notify_rent=notify_rent,
                notify_electricity=notify_elec,
            )  # 會自動 is_verified = true[cite:48]

            if ok:
                st.success(msg)
                st.toast("綁定已更新，後續租金／電費通知會同步使用此 LINE 帳號。", icon="✅")
            else:
                st.error(msg)

        except Exception as e:
            logger.error(f"❌ 綁定過程發生例外: {e}", exc_info=True)
            st.error(f"❌ 綁定失敗：{str(e)[:100]}")


def render_binding_list(contact_svc: TenantContactService):
    """
    下方區塊：顯示目前所有綁定紀錄
    """
    st.subheader("📋 目前所有 LINE 綁定紀錄")

    try:
        bindings = contact_svc.get_all_line_bindings()  # List[Dict][cite:48]
    except Exception as e:
        logger.error(f"❌ 載入綁定紀錄失敗: {e}", exc_info=True)
        st.error("無法載入綁定紀錄，請稍後再試。")
        return

    if not bindings:
        st.info("尚無任何 LINE 綁定紀錄。")
        return

    # 轉成 DataFrame 只顯示重點欄位
    import pandas as pd

    df = pd.DataFrame(bindings)
    # 只挑幾個重點欄位，避免太雜
    display_cols = [
        "room_number",
        "tenant_name",
        "tenant_id",
        "line_user_id",
        "is_verified",
        "notify_rent",
        "notify_electricity",
        "verified_at",
    ]
    existing_cols = [c for c in display_cols if c in df.columns]
    df = df[existing_cols].copy()

    # LINE User ID 只顯示前幾碼，避免太長
    if "line_user_id" in df.columns:
        df["line_user_id"] = df["line_user_id"].apply(
            lambda x: (x[:12] + "...") if isinstance(x, str) else ""
        )

    st.dataframe(df, use_container_width=True)


def main():
    st.set_page_config(
        page_title="租客 LINE 綁定管理（後台）",
        page_icon="🔗",
        layout="wide",
    )

    st.title("租客 LINE 綁定管理（後台）")
    st.caption("透過 LINE User ID 手動綁定租客，用於啟用租金／電費 LINE 通知。")

    tenant_svc = TenantService()
    contact_svc = TenantContactService()

    # 上方：綁定表單
    render_binding_form(tenant_svc, contact_svc)

    st.markdown("---")

    # 下方：所有綁定列表
    render_binding_list(contact_svc)


if __name__ == "__main__":
    main()
