"""
智能催繳引擎 - v4.0 Final
✅ 根據租客歷史行為動態調整提醒策略
✅ 多階段催繳（溫和→友善→正式→最終）
✅ 自動學習和優化
✅ 完整的行為追蹤
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


class ReminderStage(Enum):
    """催繳階段"""
    FIRST = "first"      # 第一次提醒（溫和）
    SECOND = "second"    # 第二次提醒（友善催促）
    THIRD = "third"      # 第三次提醒（正式警告）
    FINAL = "final"      # 最終通知（需人工介入）


@dataclass
class TenantBehaviorProfile:
    """租客行為檔案"""
    tenant_id: str
    avg_payment_delay: float  # 平均延遲天數
    on_time_rate: float       # 準時率 (0-1)
    total_reminders: int      # 歷史催繳次數
    response_rate: float      # 催繳回應率
    risk_score: int          # 風險分數 (0-100)
    preferred_reminder_days: List[int]  # 最有效的提醒天數


class ReminderService(BaseDBService):
    """智能催繳引擎"""
    
    def __init__(self):
        super().__init__()
        self._init_tables()
    
    def _init_tables(self):
        """初始化資料表"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tenant_behavior (
                        tenant_id TEXT PRIMARY KEY,
                        avg_payment_delay REAL DEFAULT 0,
                        on_time_rate REAL DEFAULT 1.0,
                        total_reminders INTEGER DEFAULT 0,
                        response_rate REAL DEFAULT 0,
                        risk_score INTEGER DEFAULT 50,
                        preferred_reminder_days TEXT DEFAULT '[1, 5, 10]',
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reminder_history (
                        id SERIAL PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        rent_month TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        due_date DATE NOT NULL,
                        days_before_due INTEGER,
                        responded BOOLEAN DEFAULT FALSE,
                        paid_at TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reminder_tenant 
                    ON reminder_history(tenant_id, rent_month)
                """)
                
                logger.info("✅ 催繳表初始化完成")
        
        except Exception as e:
            logger.error(f"❌ 初始化失敗: {str(e)}")
    
    # ==================== 核心催繳邏輯 ====================
    
    def calculate_optimal_reminder_days(self, tenant_id: str) -> List[int]:
        """
        根據租客歷史行為計算最佳提醒時間點
        
        邏輯：
        1. 新租客：使用預設 [1, 5, 10]
        2. 優良租客（準時率 > 90%）：僅 [1] 天提醒
        3. 偶爾遲交（準時率 60-90%）：[0, 3, 7]（提前一天）
        4. 經常遲交（準時率 < 60%）：[-1, 2, 5, 8]（提前兩天+密集）
        
        Args:
            tenant_id: 租客 ID
        
        Returns:
            最佳提醒天數列表
        """
        profile = self._get_tenant_profile(tenant_id)
        
        if profile.total_reminders < 3:
            # 新租客：標準流程
            return [1, 5, 10]
        
        if profile.on_time_rate >= 0.9:
            # 優良租客：只需輕微提醒
            return [1]
        
        elif profile.on_time_rate >= 0.6:
            # 偶爾遲交：稍微提前
            return [0, 3, 7]  # 到期當天、3天後、7天後
        
        else:
            # 高風險租客：提前+密集
            avg_delay = int(profile.avg_payment_delay)
            return [
                -1,  # 提前一天預警
                2,   # 逾期2天
                5,   # 逾期5天
                min(8, avg_delay - 2)  # 根據平均延遲調整
            ]
    
    def should_send_reminder(
        self, 
        tenant_id: str, 
        due_date: datetime,
        current_date: datetime = None
    ) -> Optional[ReminderStage]:
        """
        判斷是否應該發送提醒及階段
        
        Args:
            tenant_id: 租客 ID
            due_date: 到期日
            current_date: 當前日期（可選）
        
        Returns:
            ReminderStage: 應發送的階段，None 表示無需發送
        """
        if current_date is None:
            current_date = datetime.now()
        
        # 計算距離到期日天數（負數 = 已逾期）
        days_diff = (due_date.date() - current_date.date()).days
        
        # 取得最佳提醒時間點
        optimal_days = self.calculate_optimal_reminder_days(tenant_id)
        
        # 查詢本月已發送的提醒
        rent_month = due_date.strftime('%Y-%m')
        sent_stages = self._get_sent_reminders(tenant_id, rent_month)
        
        # 判斷邏輯
        if len(optimal_days) >= 1 and days_diff == optimal_days[0] and ReminderStage.FIRST not in sent_stages:
            return ReminderStage.FIRST
        
        elif len(optimal_days) >= 2 and days_diff <= optimal_days[1] and ReminderStage.SECOND not in sent_stages:
            if ReminderStage.FIRST in sent_stages:  # 必須先發過第一次
                return ReminderStage.SECOND
        
        elif len(optimal_days) >= 3 and days_diff <= optimal_days[2] and ReminderStage.THIRD not in sent_stages:
            if ReminderStage.SECOND in sent_stages:
                return ReminderStage.THIRD
        
        elif days_diff <= -7 and ReminderStage.FINAL not in sent_stages:
            # 逾期 7 天，發最終通知
            return ReminderStage.FINAL
        
        return None
    
    def generate_reminder_message(
        self,
        tenant_name: str,
        room_number: str,
        amount: float,
        due_date: datetime,
        stage: ReminderStage
    ) -> str:
        """
        根據階段生成不同語氣的催繳訊息
        
        Args:
            tenant_name: 租客姓名
            room_number: 房號
            amount: 金額
            due_date: 到期日
            stage: 催繳階段
        
        Returns:
            催繳訊息文字
        """
        templates = {
            ReminderStage.FIRST: f"""親愛的 {tenant_name} 您好，

這是一則友善的提醒：
📅 房租到期日：{due_date.strftime('%Y/%m/%d')}
💰 應繳金額：NT${amount:,.0f}
🏠 房間：{room_number}

請您於到期日前完成轉帳，感謝配合！

如有任何問題，歡迎隨時聯絡房東。
祝您有美好的一天 😊""",
            
            ReminderStage.SECOND: f"""{tenant_name} 您好，

我們注意到本月房租尚未收到：
💰 金額：NT${amount:,.0f}
📅 到期日：{due_date.strftime('%Y/%m/%d')}（已過 {(datetime.now().date() - due_date.date()).days} 天）

麻煩您盡快完成轉帳，避免影響租約。
如有特殊狀況，也歡迎與房東討論。

謝謝您的配合！""",
            
            ReminderStage.THIRD: f"""{tenant_name} 您好，

【重要提醒】您的房租已逾期：
💰 金額：NT${amount:,.0f}
⏰ 逾期天數：{(datetime.now().date() - due_date.date()).days} 天

請於 2 個工作天內完成繳納，否則房東可能需要採取進一步措施（如寄送存證信函）。

如有困難，請務必與房東聯絡協商。""",
            
            ReminderStage.FINAL: f"""{tenant_name} 您好，

【最終通知】您的房租已嚴重逾期：
💰 欠款金額：NT${amount:,.0f}
⏰ 逾期天數：{(datetime.now().date() - due_date.date()).days} 天

此為系統最終通知。房東將於 3 天內直接聯絡您，
若未獲回應，將依照租賃契約採取法律行動。

請立即處理此事。"""
        }
        
        return templates[stage].strip()
    
    # ==================== 記錄管理 ====================
    
    def record_reminder_sent(
        self,
        tenant_id: str,
        rent_month: str,
        stage: ReminderStage,
        due_date: datetime
    ) -> bool:
        """
        記錄已發送的提醒
        
        Args:
            tenant_id: 租客 ID
            rent_month: 租金月份（格式：YYYY-MM）
            stage: 催繳階段
            due_date: 到期日
        
        Returns:
            bool: 成功/失敗
        """
        try:
            days_before_due = (due_date.date() - datetime.now().date()).days
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO reminder_history 
                    (tenant_id, rent_month, stage, due_date, days_before_due)
                    VALUES (%s, %s, %s, %s, %s)
                """, (tenant_id, rent_month, stage.value, due_date, days_before_due))
                
                log_db_operation("INSERT", "reminder_history", True, 1)
                logger.info(f"✅ 記錄催繳: {tenant_id} - {stage.value}")
                return True
        
        except Exception as e:
            log_db_operation("INSERT", "reminder_history", False, error=str(e))
            logger.error(f"❌ 記錄失敗: {str(e)}")
            return False
    
    def update_tenant_behavior_on_payment(
        self,
        tenant_id: str,
        due_date: datetime,
        paid_date: datetime
    ):
        """
        租客繳款後更新行為檔案
        用於機器學習：持續優化提醒策略
        
        Args:
            tenant_id: 租客 ID
            due_date: 到期日
            paid_date: 繳款日
        """
        try:
            delay_days = (paid_date.date() - due_date.date()).days
            is_on_time = delay_days <= 0
            
            # 取得當前檔案
            profile = self._get_tenant_profile(tenant_id)
            
            # 更新統計數據（移動平均）
            alpha = 0.3  # 平滑係數
            new_avg_delay = (
                profile.avg_payment_delay * (1 - alpha) + 
                max(0, delay_days) * alpha
            )
            new_on_time_rate = (
                profile.on_time_rate * (1 - alpha) + 
                (1.0 if is_on_time else 0.0) * alpha
            )
            
            # 計算新的風險分數
            risk_score = self._calculate_risk_score(
                new_avg_delay, 
                new_on_time_rate,
                profile.response_rate
            )
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO tenant_behavior (tenant_id, avg_payment_delay, on_time_rate, risk_score)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        avg_payment_delay = EXCLUDED.avg_payment_delay,
                        on_time_rate = EXCLUDED.on_time_rate,
                        risk_score = EXCLUDED.risk_score,
                        last_updated = CURRENT_TIMESTAMP
                """, (tenant_id, new_avg_delay, new_on_time_rate, risk_score))
                
                log_db_operation("UPDATE", "tenant_behavior", True, 1)
                logger.info(f"✅ 更新行為檔案: {tenant_id} (風險: {risk_score})")
        
        except Exception as e:
            log_db_operation("UPDATE", "tenant_behavior", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
    
    # ==================== 輔助方法 ====================
    
    def _get_tenant_profile(self, tenant_id: str) -> TenantBehaviorProfile:
        """取得租客行為檔案"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT tenant_id, avg_payment_delay, on_time_rate, total_reminders,
                           response_rate, risk_score, preferred_reminder_days
                    FROM tenant_behavior 
                    WHERE tenant_id = %s
                """, (tenant_id,))
                
                row = cursor.fetchone()
                
                if row is None:
                    # 新租客：建立預設檔案
                    cursor.execute("""
                        INSERT INTO tenant_behavior (tenant_id) 
                        VALUES (%s)
                    """, (tenant_id,))
                    
                    return TenantBehaviorProfile(
                        tenant_id=tenant_id,
                        avg_payment_delay=0.0,
                        on_time_rate=1.0,
                        total_reminders=0,
                        response_rate=0.0,
                        risk_score=50,
                        preferred_reminder_days=[1, 5, 10]
                    )
                
                import json
                return TenantBehaviorProfile(
                    tenant_id=row[0],
                    avg_payment_delay=row[1],
                    on_time_rate=row[2],
                    total_reminders=row[3],
                    response_rate=row[4],
                    risk_score=row[5],
                    preferred_reminder_days=json.loads(row[6])
                )
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            # 返回預設檔案
            return TenantBehaviorProfile(
                tenant_id=tenant_id,
                avg_payment_delay=0.0,
                on_time_rate=1.0,
                total_reminders=0,
                response_rate=0.0,
                risk_score=50,
                preferred_reminder_days=[1, 5, 10]
            )
    
    def _get_sent_reminders(self, tenant_id: str, rent_month: str) -> List[ReminderStage]:
        """查詢本月已發送的提醒階段"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT stage FROM reminder_history
                    WHERE tenant_id = %s AND rent_month = %s
                """, (tenant_id, rent_month))
                
                return [ReminderStage(row[0]) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return []
    
    def _calculate_risk_score(
        self,
        avg_delay: float,
        on_time_rate: float,
        response_rate: float
    ) -> int:
        """
        計算租客風險分數 (0-100)
        100 = 極高風險，0 = 零風險
        
        Args:
            avg_delay: 平均延遲天數
            on_time_rate: 準時率
            response_rate: 回應率
        
        Returns:
            風險分數 (0-100)
        """
        # 權重設計
        delay_weight = 0.4
        on_time_weight = 0.4
        response_weight = 0.2
        
        # 延遲天數轉分數（10天以上 = 滿分）
        delay_score = min(100, (avg_delay / 10) * 100)
        
        # 準時率轉分數（反向：準時率低 = 分數高）
        on_time_score = (1 - on_time_rate) * 100
        
        # 回應率轉分數（反向）
        response_score = (1 - response_rate) * 100
        
        total_score = (
            delay_score * delay_weight +
            on_time_score * on_time_weight +
            response_score * response_weight
        )
        
        return int(total_score)
    
    # ==================== 批次操作 ====================
    
    def get_tenants_needing_reminder(self, due_date: datetime = None) -> List[Dict]:
        """
        取得需要催繳的租客列表
        
        Args:
            due_date: 到期日（可選，默認為今天）
        
        Returns:
            需要催繳的租客列表
        """
        if due_date is None:
            due_date = datetime.now()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 查詢未繳款的租金記錄
                cursor.execute("""
                    SELECT 
                        ps.id,
                        t.id as tenant_id,
                        t.tenant_name,
                        t.room_number,
                        ps.amount,
                        ps.due_date,
                        ps.payment_year,
                        ps.payment_month
                    FROM payment_schedule ps
                    LEFT JOIN tenants t ON ps.room_number = t.room_number AND t.is_active = true
                    WHERE ps.status = 'unpaid' AND ps.due_date <= %s
                """, (due_date,))
                
                tenants = []
                for row in cursor.fetchall():
                    payment_id, tenant_id, name, room, amount, due, year, month = row
                    
                    # 檢查是否需要發送提醒
                    stage = self.should_send_reminder(str(tenant_id), due, due_date)
                    
                    if stage:
                        tenants.append({
                            'payment_id': payment_id,
                            'tenant_id': str(tenant_id),
                            'tenant_name': name,
                            'room_number': room,
                            'amount': amount,
                            'due_date': due,
                            'year': year,
                            'month': month,
                            'reminder_stage': stage
                        })
                
                logger.info(f"✅ 找到 {len(tenants)} 位需要催繳的租客")
                return tenants
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return []
