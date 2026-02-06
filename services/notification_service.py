"""
統一通知服務 - v4.2
✅ 整合 LINE/Email 發送
✅ 自動寫入 notification_logs
✅ 支援電費、租金、催繳等多種通知類型
✅ 完整的錯誤追蹤
✅ 系統設定管理 (新增)
✅ 僅對已驗證的 LINE 綁定 (is_verified) 發送租金 / 電費通知
"""

import os
import json
import requests
import streamlit as st
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timedelta

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


class NotificationService(BaseDBService):
    """統一通知服務 (繼承 BaseDBService)"""
    
    def __init__(self):
        super().__init__()
        
        # LINE 設定
        self.line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN') or \
                         st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN")
        
        if not self.line_token:
            logger.warning("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN，LINE 通知功能將無法使用")
    
    # ============= 系統設定管理 (新增) =============
    
    def get_all_settings(self) -> Dict[str, str]:
        """
        獲取所有系統設定
        
        Returns:
            Dict: {key: value} 設定字典
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT setting_key, setting_value
                    FROM system_settings
                    WHERE is_active = true
                """)
                
                rows = cursor.fetchall()
                
                settings = {row[0]: row[1] for row in rows}
                
                log_db_operation("SELECT", "system_settings", True, len(settings))
                logger.info(f"✅ 載入系統設定: {len(settings)} 筆")
                
                return settings
        
        except Exception as e:
            log_db_operation("SELECT", "system_settings", False, error=str(e))
            logger.error(f"❌ 載入系統設定失敗: {str(e)}")
            return {}
    
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        獲取單個系統設定
        
        Args:
            key: 設定鍵名
            default: 預設值
        
        Returns:
            設定值或預設值
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT setting_value
                    FROM system_settings
                    WHERE setting_key = %s AND is_active = true
                """, (key,))
                
                result = cursor.fetchone()
                
                if result:
                    log_db_operation("SELECT", "system_settings", True, 1)
                    return result[0]
                else:
                    logger.info(f"⚠️ 設定 {key} 不存在，使用預設值: {default}")
                    return default
        
        except Exception as e:
            log_db_operation("SELECT", "system_settings", False, error=str(e))
            logger.error(f"❌ 讀取設定失敗 ({key}): {str(e)}")
            return default
    
    def save_setting(self, key: str, value: str) -> Tuple[bool, str]:
        """
        儲存或更新系統設定
        
        Args:
            key: 設定鍵名
            value: 設定值
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 使用 UPSERT (ON CONFLICT)
                cursor.execute("""
                    INSERT INTO system_settings 
                    (setting_key, setting_value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (setting_key)
                    DO UPDATE SET 
                        setting_value = EXCLUDED.setting_value,
                        updated_at = NOW()
                """, (key, value))
                
                log_db_operation("UPSERT", "system_settings", True, 1)
                logger.info(f"✅ 儲存設定: {key} = {value[:50]}...")
                
                return True, f"✅ 設定 {key} 已儲存"
        
        except Exception as e:
            log_db_operation("UPSERT", "system_settings", False, error=str(e))
            logger.error(f"❌ 儲存設定失敗 ({key}): {str(e)}")
            return False, f"❌ 儲存失敗: {str(e)[:100]}"
    
    def delete_setting(self, key: str) -> Tuple[bool, str]:
        """
        刪除系統設定（軟刪除）
        
        Args:
            key: 設定鍵名
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE system_settings
                    SET is_active = false, updated_at = NOW()
                    WHERE setting_key = %s
                """, (key,))
                
                log_db_operation("UPDATE", "system_settings", True, 1)
                logger.info(f"✅ 刪除設定: {key}")
                
                return True, f"✅ 設定 {key} 已刪除"
        
        except Exception as e:
            log_db_operation("UPDATE", "system_settings", False, error=str(e))
            logger.error(f"❌ 刪除設定失敗 ({key}): {str(e)}")
            return False, f"❌ 刪除失敗: {str(e)[:100]}"
    
    # ============= 通知記錄查詢 (新增) =============
    
    def get_recent_notifications(self, limit: int = 10) -> List[Dict]:
        """
        獲取最近的通知記錄
        
        Args:
            limit: 筆數限制
        
        Returns:
            通知記錄列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        id, category, recipient_type, room_number,
                        notification_type, title, channel, status,
                        sent_at, created_at, error_message
                    FROM notification_logs
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                log_db_operation("SELECT", "notification_logs", True, len(rows))
                
                return [dict(zip(columns, row)) for row in rows]
        
        except Exception as e:
            log_db_operation("SELECT", "notification_logs", False, error=str(e))
            logger.error(f"❌ 查詢最近通知失敗: {str(e)}")
            return []
    
    def get_notification_logs(
        self,
        days: int = 7,
        recipient_type: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        獲取通知日誌（帶篩選）
        
        Args:
            days: 查詢天數
            recipient_type: 接收者類型 (landlord/tenant)
            status: 狀態 (sent/failed/pending)
            category: 類別 (rent/electricity/system)
            limit: 筆數限制
        
        Returns:
            通知日誌列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 建立篩選條件
                conditions = ["created_at >= NOW() - INTERVAL '%s days'"]
                params = [days]
                
                if recipient_type:
                    conditions.append("recipient_type = %s")
                    params.append(recipient_type)
                
                if status:
                    conditions.append("status = %s")
                    params.append(status)
                
                if category:
                    conditions.append("category = %s")
                    params.append(category)
                
                params.append(limit)
                
                query = f"""
                    SELECT 
                        id, category, recipient_type, recipient_id, room_number,
                        notification_type, title, message, channel, status,
                        sent_at, created_at, error_message, meta_json
                    FROM notification_logs
                    WHERE {' AND '.join(conditions)}
                    ORDER BY created_at DESC
                    LIMIT %s
                """
                
                cursor.execute(query, params)
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                log_db_operation("SELECT", "notification_logs", True, len(rows))
                logger.info(f"✅ 查詢通知日誌: {len(rows)} 筆")
                
                return [dict(zip(columns, row)) for row in rows]
        
        except Exception as e:
            log_db_operation("SELECT", "notification_logs", False, error=str(e))
            logger.error(f"❌ 查詢通知日誌失敗: {str(e)}")
            return []
    
    # ============= 核心發送方法 =============
    
    def send_line_message(
        self,
        user_id: str,
        message: str
    ) -> bool:
        """
        發送 LINE 訊息
        
        Args:
            user_id: LINE User ID
            message: 訊息內容
        
        Returns:
            bool: 成功/失敗
        """
        if not self.line_token:
            logger.warning("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN")
            return False
        
        if not user_id:
            logger.warning("⚠️ LINE User ID 為空")
            return False
        
        try:
            payload = {
                'to': user_id,
                'messages': [{
                    'type': 'text',
                    'text': message
                }]
            }
            
            response = requests.post(
                'https://api.line.me/v2/bot/message/push',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.line_token}'
                },
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ LINE 發送成功: {user_id}")
                return True
            else:
                logger.error(f"❌ LINE 發送失敗: {response.status_code} - {response.text}")
                return False
        
        except requests.exceptions.Timeout:
            logger.error(f"❌ LINE 發送逾時: {user_id}")
            return False
        except Exception as e:
            logger.error(f"❌ LINE 發送失敗: {e}")
            return False
    
    # ============= 電費通知 =============
    
    def send_electricity_bill_notification(
        self,
        period_id: int,
        remind_date: Optional[str] = None
    ) -> Tuple[bool, str, int]:
        """
        發送電費帳單通知 + 寫入 notification_logs
        
        僅對 tenant_contacts 中 line_user_id 不為空、notify_electricity = true、
        且 is_verified = true 的房客發送通知。
        
        Args:
            period_id: 期間 ID
            remind_date: 催繳開始日期 (可選，默認下月1號)
        
        Returns:
            (bool, str, notified_count): 成功/失敗訊息 + 通知數量
        """
        try:
            # 如果沒提供催繳日期，自動設為下個月 1 號
            if not remind_date:
                today = datetime.now()
                next_month = today.month + 1 if today.month < 12 else 1
                next_year = today.year if today.month < 12 else today.year + 1
                remind_date = f"{next_year:04d}-{next_month:02d}-01"
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 更新催繳日期
                cursor.execute(
                    """
                    UPDATE electricity_periods 
                    SET remind_start_date = %s
                    WHERE id = %s
                    """,
                    (remind_date, period_id)
                )
                
                # 2. 取得該期間的未繳記錄 + 租客信息
                cursor.execute(
                    """
                    SELECT 
                        er.id,
                        er.room_number,
                        er.amount_due,
                        er.tenant_id,
                        t.tenant_name,
                        tc.line_user_id,
                        tc.notify_electricity,
                        COALESCE(tc.is_verified, false) AS is_verified,
                        ep.period_year,
                        ep.period_month_start,
                        ep.period_month_end
                    FROM electricity_records er
                    LEFT JOIN tenants t ON er.tenant_id = t.id
                    LEFT JOIN tenant_contacts tc ON t.id = tc.tenant_id
                    LEFT JOIN electricity_periods ep ON er.period_id = ep.id
                    WHERE er.period_id = %s 
                        AND er.status = 'unpaid'
                        AND tc.line_user_id IS NOT NULL
                        AND tc.notify_electricity = true
                        AND COALESCE(tc.is_verified, false) = true
                    """,
                    (period_id,)
                )
                
                records = cursor.fetchall()
                notified_count = 0
                failed_count = 0
                
                if not records:
                    logger.info("📭 沒有需要通知的租客（無已驗證綁定）")
                    return True, "📭 沒有需要通知的租客（無已驗證綁定）", 0
                
                for record in records:
                    (
                        er_id,
                        room,
                        amount,
                        tenant_id,
                        tenant_name,
                        line_id,
                        _notify_elec,
                        _is_verified,
                        year,
                        month_start,
                        month_end,
                    ) = record
                    period_text = f"{year}/{month_start}-{month_end}"
                    
                    try:
                        # 準備訊息
                        message = f"""⚡ 電費帳單通知

房號：{room}
租客：{tenant_name}
期間：{period_text}
金額：NT${amount:,}

請於 7 天內完成繳費。
如有疑問，請聯繫房東。"""
                        
                        # 調用 LINE 通知
                        response = self.send_line_message(line_id, message)
                        
                        # 準備 meta_json
                        meta_json = json.dumps({
                            "period_id": period_id,
                            "electricity_record_id": er_id,
                            "amount": float(amount),
                            "period_text": period_text,
                            "tenant_id": tenant_id,
                            "tenant_name": tenant_name,
                        }, ensure_ascii=False)
                        
                        if response:
                            # ✅ 更新 last_notified_at
                            cursor.execute(
                                """
                                UPDATE electricity_records 
                                SET last_notified_at = NOW()
                                WHERE id = %s
                                """,
                                (er_id,)
                            )
                            
                            # ✅ 寫入 notification_logs（成功）
                            cursor.execute(
                                """
                                INSERT INTO notification_logs
                                (category, recipient_type, recipient_id, room_number, 
                                 notification_type, title, message, channel, status, 
                                 sent_at, meta_json)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb)
                                """,
                                (
                                    'electricity',              # category
                                    'tenant',                   # recipient_type
                                    line_id,                    # recipient_id (LINE User ID)
                                    room,                       # room_number
                                    'first_bill',               # notification_type
                                    f'{period_text} 電費帳單',  # title
                                    message,                    # message
                                    'line',                     # channel
                                    'sent',                     # status
                                    meta_json                   # meta_json
                                )
                            )
                            
                            notified_count += 1
                            logger.info(f"✅ 發送電費通知: {room} ({tenant_name})")
                        
                        else:
                            # ❌ 發送失敗也記錄
                            cursor.execute(
                                """
                                INSERT INTO notification_logs
                                (category, recipient_type, recipient_id, room_number,
                                 notification_type, title, message, channel, status, 
                                 error_message, created_at, meta_json)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb)
                                """,
                                (
                                    'electricity',
                                    'tenant',
                                    line_id,
                                    room,
                                    'first_bill',
                                    f'{period_text} 電費帳單',
                                    message,
                                    'line',
                                    'failed',
                                    'LINE API 回應失敗',
                                    meta_json
                                )
                            )
                            failed_count += 1
                            logger.warning(f"⚠️ 發送失敗: {room} ({tenant_name})")
                    
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"❌ 發送失敗 {room}: {e}")
                        
                        # ✅ 異常也記錄
                        try:
                            meta_json = json.dumps({
                                "period_id": period_id,
                                "electricity_record_id": er_id,
                                "amount": float(amount) if amount else 0,
                                "period_text": period_text,
                                "tenant_id": tenant_id,
                                "tenant_name": tenant_name,
                                "error": str(e)[:500],
                            }, ensure_ascii=False)

                            cursor.execute(
                                """
                                INSERT INTO notification_logs
                                (category, recipient_type, recipient_id, room_number,
                                 notification_type, title, channel, status, error_message, created_at, meta_json)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb)
                                """,
                                (
                                    'electricity',
                                    'tenant',
                                    line_id or 'unknown',
                                    room,
                                    'first_bill',
                                    f'{period_text} 電費帳單',
                                    'line',
                                    'failed',
                                    str(e)[:500],
                                    meta_json
                                )
                            )
                        except Exception as log_error:
                            logger.error(f"❌ 寫入失敗日誌失敗: {log_error}")
                        
                        continue
                
                log_db_operation("NOTIFICATION", "electricity_records", True, notified_count)
                
                summary = f"✅ 電費通知完成: 成功 {notified_count} 位"
                if failed_count > 0:
                    summary += f", 失敗 {failed_count} 位"
                
                logger.info(f"{summary}，催繳日期設為 {remind_date}")
                return True, summary, notified_count
        
        except Exception as e:
            log_db_operation("NOTIFICATION", "electricity_records", False, error=str(e))
            logger.error(f"❌ 電費通知失敗: {str(e)}")
            return False, f"❌ 電費通知失敗: {str(e)[:100]}", 0
    
    # ============= 租金催繳通知 =============
    
    def send_rent_reminder(
        self,
        payment_id: int,
        reminder_stage: str = "first"
    ) -> Tuple[bool, str]:
        """
        發送租金催繳通知 + 寫入 notification_logs
        
        僅在 tenant_contacts 有 line_user_id 且 is_verified = true 的情況下發送。
        
        Args:
            payment_id: 租金排程 ID
            reminder_stage: 催繳階段 (first/second/third/final)
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 查詢租金資訊 + 綁定狀態
                cursor.execute(
                    """
                    SELECT 
                        ps.room_number,
                        ps.tenant_name,
                        ps.amount,
                        ps.due_date,
                        ps.payment_year,
                        ps.payment_month,
                        t.id as tenant_id,
                        tc.line_user_id,
                        tc.notify_rent,
                        COALESCE(tc.is_verified, false) AS is_verified
                    FROM payment_schedule ps
                    LEFT JOIN tenants t ON ps.room_number = t.room_number AND t.is_active = true
                    LEFT JOIN tenant_contacts tc ON t.id = tc.tenant_id
                    WHERE ps.id = %s AND ps.status = 'unpaid'
                    """,
                    (payment_id,)
                )
                
                result = cursor.fetchone()
                
                if not result:
                    logger.warning(f"⚠️ 租金記錄 {payment_id} 不存在或已繳款")
                    return False, "❌ 未找到租金記錄或已繳款"
                
                (
                    room,
                    tenant_name,
                    amount,
                    due_date,
                    year,
                    month,
                    tenant_id,
                    line_id,
                    notify_rent,
                    is_verified,
                ) = result
                
                if not line_id:
                    logger.warning(f"⚠️ {tenant_name} 未設定 LINE User ID")
                    return False, f"❌ {tenant_name} 未設定 LINE User ID"
                
                if not is_verified:
                    logger.info(f"ℹ️ {tenant_name} 尚未完成 LINE 綁定驗證，略過催繳")
                    return False, f"ℹ️ {tenant_name} 尚未完成 LINE 綁定驗證"
                
                if not notify_rent:
                    logger.info(f"ℹ️ {tenant_name} 已關閉租金通知")
                    return False, f"ℹ️ {tenant_name} 已關閉租金通知"
                
                # 計算逾期天數
                overdue_days = (
                    (datetime.now().date() - due_date).days
                    if isinstance(due_date, datetime)
                    else (datetime.now().date() - due_date).days
                )
                
                # 準備訊息（根據階段）
                messages = {
                    "first": f"""💰 租金繳納提醒

親愛的 {tenant_name} 您好，

本月租金即將到期：
房號：{room}
期間：{year}/{month}
金額：NT${amount:,}
到期日：{due_date}

請準時繳納，謝謝！""",
                    
                    "second": f"""💰 租金催繳通知

{tenant_name} 您好，

您的租金已逾期：
房號：{room}
期間：{year}/{month}
金額：NT${amount:,}
逾期天數：{max(0, overdue_days)} 天

麻煩盡快完成繳納，避免影響租約。
如有困難，請聯繫房東。""",
                    
                    "third": f"""⚠️ 租金逾期警告

{tenant_name} 您好，

您的租金已嚴重逾期：
房號：{room}
期間：{year}/{month}
金額：NT${amount:,}
逾期天數：{max(0, overdue_days)} 天

請於 2 天內完成繳納，否則將採取進一步措施。""",
                    
                    "final": f"""🚨 最終通知

{tenant_name}，

您的租金已逾期超過 7 天：
房號：{room}
期間：{year}/{month}
金額：NT${amount:,}
逾期天數：{max(0, overdue_days)} 天

這是最終通知，房東將直接聯絡您。
請立即處理此事。"""
                }
                
                message = messages.get(reminder_stage, messages["first"])
                
                # 發送 LINE
                response = self.send_line_message(line_id, message)
                
                # 準備 meta_json
                meta_json = json.dumps({
                    "payment_id": payment_id,
                    "amount": float(amount),
                    "due_date": str(due_date),
                    "year": year,
                    "month": month,
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "reminder_stage": reminder_stage,
                    "overdue_days": max(0, overdue_days)
                }, ensure_ascii=False)
                
                # 寫入 notification_logs
                cursor.execute(
                    """
                    INSERT INTO notification_logs
                    (category, recipient_type, recipient_id, room_number,
                     notification_type, title, message, channel, status, 
                     sent_at, error_message, meta_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s::jsonb)
                    """,
                    (
                        'rent',
                        'tenant',
                        line_id,
                        room,
                        f'{reminder_stage}_reminder',
                        f'{year}/{month} 租金提醒',
                        message,
                        'line',
                        'sent' if response else 'failed',
                        None if response else 'LINE API 回應失敗',
                        meta_json
                    )
                )
                
                if response:
                    log_db_operation("NOTIFICATION", "payment_schedule", True, 1)
                    logger.info(f"✅ 發送租金催繳: {room} ({tenant_name}) - {reminder_stage}")
                    return True, f"✅ 已發送 {reminder_stage} 階段催繳"
                else:
                    log_db_operation("NOTIFICATION", "payment_schedule", False, error="LINE API 失敗")
                    return False, "❌ LINE 發送失敗"
        
        except Exception as e:
            log_db_operation("NOTIFICATION", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 租金催繳失敗: {str(e)}")
            return False, f"❌ 租金催繳失敗: {str(e)[:100]}"
    
    # ============= 批次租金催繳 =============
    
    def batch_send_rent_reminders(
        self,
        payment_ids: List[int],
        reminder_stage: str = "first"
    ) -> Tuple[int, int, int]:
        """
        批次發送租金催繳
        
        Args:
            payment_ids: 租金排程 ID 列表
            reminder_stage: 催繳階段
        
        Returns:
            (success_count, skip_count, fail_count)
        """
        success_count = 0
        skip_count = 0
        fail_count = 0
        
        for payment_id in payment_ids:
            try:
                success, msg = self.send_rent_reminder(payment_id, reminder_stage)
                
                if success:
                    success_count += 1
                elif (
                    "已關閉" in msg
                    or "已繳款" in msg
                    or "尚未完成 LINE 綁定驗證" in msg
                ):
                    # 已關閉通知、已繳款、尚未完成驗證 => 視為跳過
                    skip_count += 1
                else:
                    fail_count += 1
            
            except Exception as e:
                logger.error(f"❌ 批次催繳失敗 ID {payment_id}: {e}")
                fail_count += 1
        
        logger.info(f"✅ 批次租金催繳: 成功 {success_count}, 跳過 {skip_count}, 失敗 {fail_count}")
        return success_count, skip_count, fail_count
    
    # ============= 通用通知方法 =============
    
    def send_custom_notification(
        self,
        category: str,
        recipient_type: str,
        recipient_id: str,
        room_number: str,
        title: str,
        message: str,
        channel: str = "line",
        meta_data: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        發送自定義通知 + 寫入 notification_logs
        
        Args:
            category: 通知類別 (rent/electricity/system/custom)
            recipient_type: 接收者類型 (tenant/landlord)
            recipient_id: 接收者 ID (LINE User ID / Email)
            room_number: 房號
            title: 通知標題
            message: 通知內容
            channel: 通道 (line/email/sms)
            meta_data: 額外元數據
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            # 發送通知
            success = False
            error_msg = None
            
            if channel == "line":
                success = self.send_line_message(recipient_id, message)
                error_msg = None if success else "LINE API 回應失敗"
            elif channel == "email":
                # TODO: 實作 Email 發送
                error_msg = "Email 功能尚未實作"
                logger.warning("⚠️ Email 功能尚未實作")
            elif channel == "sms":
                # TODO: 實作 SMS 發送
                error_msg = "SMS 功能尚未實作"
                logger.warning("⚠️ SMS 功能尚未實作")
            else:
                error_msg = f"不支援的通道: {channel}"
            
            # 寫入 notification_logs
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                meta_json = json.dumps(meta_data or {}, ensure_ascii=False)
                
                cursor.execute(
                    """
                    INSERT INTO notification_logs
                    (category, recipient_type, recipient_id, room_number,
                     notification_type, title, message, channel, status, 
                     sent_at, error_message, meta_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s::jsonb)
                    """,
                    (
                        category,
                        recipient_type,
                        recipient_id,
                        room_number,
                        'custom',
                        title,
                        message,
                        channel,
                        'sent' if success else 'failed',
                        error_msg,
                        meta_json
                    )
                )
            
            if success:
                log_db_operation("NOTIFICATION", "custom", True, 1)
                logger.info(f"✅ 發送自定義通知: {title}")
                return True, "✅ 發送成功"
            else:
                log_db_operation("NOTIFICATION", "custom", False, error=error_msg)
                return False, f"❌ {error_msg or '發送失敗'}"
        
        except Exception as e:
            log_db_operation("NOTIFICATION", "custom", False, error=str(e))
            logger.error(f"❌ 自定義通知失敗: {str(e)}")
            return False, f"❌ {str(e)[:100]}"
    
    # ============= 查詢通知歷史 (保留舊方法以兼容) =============
    
    def get_notification_history(
        self,
        category: Optional[str] = None,
        room_number: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        查詢通知歷史（舊方法，保留兼容性）
        
        Args:
            category: 類別篩選
            room_number: 房號篩選
            status: 狀態篩選 (sent/failed/pending)
            limit: 筆數限制
        
        Returns:
            通知歷史列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                conditions = ["1=1"]
                params = []
                
                if category:
                    conditions.append("category = %s")
                    params.append(category)
                if room_number:
                    conditions.append("room_number = %s")
                    params.append(room_number)
                if status:
                    conditions.append("status = %s")
                    params.append(status)
                
                params.append(limit)
                
                cursor.execute(f"""
                    SELECT 
                        id, category, recipient_type, room_number,
                        notification_type, title, channel, status,
                        sent_at, error_message, meta_json
                    FROM notification_logs
                    WHERE {' AND '.join(conditions)}
                    ORDER BY sent_at DESC, created_at DESC
                    LIMIT %s
                """, params)
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                log_db_operation("SELECT", "notification_logs", True, len(rows))
                return [dict(zip(columns, row)) for row in rows]
        
        except Exception as e:
            log_db_operation("SELECT", "notification_logs", False, error=str(e))
            logger.error(f"❌ 查詢通知歷史失敗: {str(e)}")
            return []
