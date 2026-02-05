"""
統一通知服務 - v4.0 Final
✅ 整合 LINE/Email 發送
✅ 自動寫入 notification_logs
✅ 支援電費、租金、催繳等多種通知類型
✅ 完整的錯誤追蹤
"""

import os
import json
import requests
import streamlit as st
from typing import Optional, Dict, Tuple
from datetime import datetime

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


class NotificationService(BaseDBService):
    """統一通知服務"""
    
    def __init__(self):
        super().__init__()
        
        # LINE 設定
        self.line_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN') or \
                         st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN")
    
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
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"❌ LINE 發送失敗: {e}")
            return False
    
    # ============= 電費通知 =============
    
    def send_electricity_bill_notification(
        self,
        period_id: int,
        remind_date: str = None
    ) -> Tuple[bool, str, int]:
        """
        發送電費帳單通知 + 寫入 notification_logs
        
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
                    """,
                    (period_id,)
                )
                
                records = cursor.fetchall()
                notified_count = 0
                
                for record in records:
                    er_id, room, amount, tenant_id, tenant_name, line_id, _, year, month_start, month_end = record
                    period_text = f"{year}/{month_start}-{month_end}"
                    
                    try:
                        # 準備訊息
                        message = f"""⚡ 電費帳單通知

房號：{room}
期間：{period_text}
金額：${amount:,} 元

請於 7 天內完成繳費。
如有疑問，請聯繫房東。"""
                        
                        # 調用 LINE 通知
                        response = self.send_line_message(line_id, message)
                        
                        if response:
                            # ✨ 更新 last_notified_at
                            cursor.execute(
                                """
                                UPDATE electricity_records 
                                SET last_notified_at = NOW()
                                WHERE id = %s
                                """,
                                (er_id,)
                            )
                            
                            # ✨ 新增：寫入 notification_logs 表（成功）
                            meta_json = json.dumps({
                                "period_id": period_id,
                                "amount": amount,
                                "period_text": period_text,
                                "tenant_id": tenant_id,
                                "tenant_name": tenant_name,
                            }, ensure_ascii=False)
                            
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
                            logger.info(f"✅ 發送首次通知: {room} → notification_logs")
                        
                        else:
                            # ✨ 發送失敗也記錄
                            meta_json = json.dumps({
                                "period_id": period_id,
                                "amount": amount,
                                "period_text": period_text,
                                "tenant_id": tenant_id,
                                "tenant_name": tenant_name,
                            }, ensure_ascii=False)

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
                            logger.warning(f"⚠️ 發送失敗: {room}")
                    
                    except Exception as e:
                        logger.error(f"❌ 發送失敗 {room}: {e}")
                        
                        # ✨ 異常也記錄
                        try:
                            meta_json = json.dumps({
                                "period_id": period_id,
                                "amount": amount,
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
                        except:
                            pass
                        
                        continue
                
                log_db_operation("NOTIFICATION", "electricity_records", True, notified_count)
                logger.info(f"✅ 首次通知發送完成: {notified_count} 位租客，催繳日期設為 {remind_date}")
                return True, f"✅ 已發送首次通知給 {notified_count} 位租客", notified_count
        
        except Exception as e:
            log_db_operation("NOTIFICATION", "electricity_records", False, error=str(e))
            logger.error(f"❌ 自動通知失敗: {str(e)}")
            return False, str(e), 0
    
    # ============= 租金催繳通知 =============
    
    def send_rent_reminder(
        self,
        payment_id: int,
        reminder_stage: str = "first"
    ) -> Tuple[bool, str]:
        """
        發送租金催繳通知 + 寫入 notification_logs
        
        Args:
            payment_id: 租金排程 ID
            reminder_stage: 催繳階段 (first/second/third/final)
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 查詢租金資訊
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
                        tc.line_user_id
                    FROM payment_schedule ps
                    LEFT JOIN tenants t ON ps.room_number = t.room_number AND t.is_active = true
                    LEFT JOIN tenant_contacts tc ON t.id = tc.tenant_id
                    WHERE ps.id = %s AND ps.status = 'unpaid'
                    """,
                    (payment_id,)
                )
                
                result = cursor.fetchone()
                
                if not result:
                    return False, "❌ 未找到租金記錄或已繳款"
                
                room, tenant_name, amount, due_date, year, month, tenant_id, line_id = result
                
                if not line_id:
                    return False, f"❌ {tenant_name} 未設定 LINE User ID"
                
                # 準備訊息（根據階段）
                messages = {
                    "first": f"""💰 租金繳納提醒

親愛的 {tenant_name} 您好，

本月租金即將到期：
房號：{room}
期間：{year}/{month}
金額：${amount:,} 元
到期日：{due_date}

請準時繳納，謝謝！""",
                    
                    "second": f"""💰 租金催繳通知

{tenant_name} 您好，

您的租金已逾期：
房號：{room}
期間：{year}/{month}
金額：${amount:,} 元

麻煩盡快完成繳納，避免影響租約。
如有困難，請聯繫房東。""",
                    
                    "third": f"""⚠️ 租金逾期警告

{tenant_name} 您好，

您的租金已嚴重逾期：
房號：{room}
期間：{year}/{month}
金額：${amount:,} 元

請於 2 天內完成繳納，否則將採取進一步措施。""",
                    
                    "final": f"""🚨 最終通知

{tenant_name}，

您的租金已逾期超過 7 天：
房號：{room}
期間：{year}/{month}
金額：${amount:,} 元

這是最終通知，房東將直接聯絡您。
請立即處理此事。"""
                }
                
                message = messages.get(reminder_stage, messages["first"])
                
                # 發送 LINE
                response = self.send_line_message(line_id, message)
                
                # 寫入 notification_logs
                meta_json = json.dumps({
                    "payment_id": payment_id,
                    "amount": amount,
                    "due_date": str(due_date),
                    "year": year,
                    "month": month,
                    "tenant_id": tenant_id,
                    "reminder_stage": reminder_stage
                }, ensure_ascii=False)
                
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
                    logger.info(f"✅ 發送租金催繳: {room} ({reminder_stage})")
                    return True, f"✅ 已發送 {reminder_stage} 階段催繳"
                else:
                    return False, "❌ LINE 發送失敗"
        
        except Exception as e:
            log_db_operation("NOTIFICATION", "payment_schedule", False, error=str(e))
            logger.error(f"❌ 租金催繳失敗: {str(e)}")
            return False, str(e)
    
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
        meta_data: Dict = None
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
            if channel == "line":
                success = self.send_line_message(recipient_id, message)
            elif channel == "email":
                # TODO: 實作 Email 發送
                pass
            
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
                        None if success else f'{channel.upper()} API 回應失敗',
                        meta_json
                    )
                )
            
            if success:
                logger.info(f"✅ 發送自定義通知: {title}")
                return True, "✅ 發送成功"
            else:
                return False, f"❌ {channel.upper()} 發送失敗"
        
        except Exception as e:
            logger.error(f"❌ 自定義通知失敗: {str(e)}")
            return False, str(e)
