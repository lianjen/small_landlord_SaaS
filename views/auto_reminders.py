"""
自動催繳設定 (Auto Reminders View) - MicroRent Edition
提供房東設定催繳規則與手動觸發通知
"""
import streamlit as st
import pandas as pd
from services.notification_service import NotificationService
from services.reminder_service import ReminderService
from services.session_manager import session_manager

def render():
    st.title("⏰ 自動催繳設定")
    
    # 權限檢查
    if not session_manager.is_authenticated():
        st.warning("🔒 請先登入")
        return

    notification_service = NotificationService()
    reminder_service = ReminderService()
    
    # 讀取現有設定
    settings = notification_service.get_all_settings()
    
    # --- 設定區塊 ---
    with st.container():
        st.subheader("⚙️ 催繳規則設定")
        
        with st.form("reminder_settings_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📅 提醒時機")
                remind_days = st.multiselect(
                    "租金到期前幾天發送提醒？",
                    options=[1, 3, 5, 7, 10, 14],
                    default=[int(d) for d in settings.get("reminder_days_before", "7,3").split(",")]
                )
                
                overdue_days = st.multiselect(
                    "逾期後幾天發送通知？",
                    options=[1, 3, 5, 7, 10, 15, 30],
                    default=[int(d) for d in settings.get("overdue_days_notify", "1,3,7").split(",")]
                )
            
            with col2:
                st.markdown("#### 🔔 通知開關")
                enable_auto = st.checkbox(
                    "啟用自動排程發送",
                    value=settings.get("enable_auto_reminder", "false").lower() == "true",
                    help="若啟用，系統將每天自動檢查並發送（需搭配排程服務）"
                )
                
                enable_line = st.checkbox(
                    "啟用 LINE 通知",
                    value=settings.get("enable_line_notify", "true").lower() == "true"
                )
                
                enable_email = st.checkbox(
                    "啟用 Email 通知",
                    value=settings.get("enable_email_notify", "false").lower() == "true"
                )

            st.markdown("---")
            st.markdown("#### 📝 訊息範本預覽")
            st.info("親愛的 {房客} 您好，本月房租 NT$ {金額} 即將於 {日期} 到期，請記得繳款。")
            
            if st.form_submit_button("💾 儲存設定", type="primary"):
                try:
                    # 儲存設定
                    notification_service.save_setting("reminder_days_before", ",".join(map(str, remind_days)))
                    notification_service.save_setting("overdue_days_notify", ",".join(map(str, overdue_days)))
                    notification_service.save_setting("enable_auto_reminder", str(enable_auto))
                    notification_service.save_setting("enable_line_notify", str(enable_line))
                    notification_service.save_setting("enable_email_notify", str(enable_email))
                    
                    st.success("✅ 設定已更新！")
                    st.rerun()
                except Exception as e:
                    st.error(f"儲存失敗: {e}")

    st.divider()

    # --- 手動執行區塊 ---
    st.subheader("⚡ 手動執行")
    st.caption("您可以隨時手動觸發檢查，系統會根據上述規則發送通知。")
    
    col_check, col_log = st.columns([1, 2])
    
    with col_check:
        if st.button("🚀 立即檢查並發送通知", type="primary", use_container_width=True):
            with st.status("正在執行催繳檢查...", expanded=True) as status:
                st.write("🔍 正在掃描未繳費租客...")
                
                try:
                    # 1. 取得需要催繳的名單
                    targets = reminder_service.get_tenants_needing_reminder()
                    
                    if not targets:
                        st.write("✅ 目前沒有需要催繳的對象。")
                        status.update(label="檢查完成", state="complete")
                    else:
                        st.write(f"⚠️ 發現 {len(targets)} 位租客需要提醒")
                        
                        # 2. 逐一發送 (這裡可以優化為批次)
                        success_count = 0
                        for target in targets:
                            # 呼叫 NotificationService 發送
                            if target['reminder_stage']:
                                st.write(f"📤 發送給 {target['tenant_name']} ({target['room_number']})...")
                                result, msg = notification_service.send_rent_reminder(
                                    target['payment_id'], 
                                    target['reminder_stage']
                                )
                                if result:
                                    success_count += 1
                        
                        st.write(f"✅ 成功發送: {success_count} 筆")
                        status.update(label="發送完成", state="complete")
                        
                except Exception as e:
                    st.error(f"❌ 執行失敗: {str(e)}")
                    status.update(label="發生錯誤", state="error")

    # --- 記錄區塊 ---
    with st.container():
        st.subheader("📜 最近發送記錄")
        logs = notification_service.get_recent_notifications(limit=10)
        
        if logs:
            df_logs = pd.DataFrame(logs)
            
            # 格式化顯示
            display_cols = ['sent_at', 'room_number', 'title', 'status', 'channel']
            if not df_logs.empty and all(col in df_logs.columns for col in display_cols):
                df_display = df_logs[display_cols].copy()
                df_display.columns = ['時間', '房號', '標題', '狀態', '管道']
                
                st.dataframe(
                    df_display, 
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "時間": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
                        "狀態": st.column_config.TextColumn(help="發送狀態"),
                    }
                )
        else:
            st.info("尚無發送記錄")

