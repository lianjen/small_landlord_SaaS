"""
LLM 催繳文案生成助手 - v4.0 Final
✅ 使用 Claude API 根據租客特徵生成個性化催繳訊息
✅ 支援批次生成
✅ 備用模板機制
✅ 多階段語氣調整
"""

import os
from typing import Dict, Optional
from datetime import datetime

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️ anthropic 套件未安裝，將使用備用模板")

from services.logger import logger


class LLMHelper:
    """智能催繳文案生成器"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 LLM 客戶端
        
        Args:
            api_key: Anthropic API Key（可選，優先使用環境變數）
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        if ANTHROPIC_AVAILABLE and self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                self.llm_enabled = True
                logger.info("✅ LLM 客戶端初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ LLM 初始化失敗: {e}，使用備用模板")
                self.llm_enabled = False
        else:
            self.llm_enabled = False
            if not ANTHROPIC_AVAILABLE:
                logger.warning("⚠️ anthropic 套件未安裝，使用備用模板")
            elif not self.api_key:
                logger.warning("⚠️ 未設定 ANTHROPIC_API_KEY，使用備用模板")
    
    # ==================== 核心生成方法 ====================
    
    def generate_personalized_message(
        self,
        tenant_name: str,
        room_number: str,
        amount: float,
        due_date: datetime,
        days_overdue: int,
        stage: str,
        tenant_profile: Dict = None
    ) -> str:
        """
        根據租客檔案生成個性化催繳訊息
        
        Args:
            tenant_name: 租客姓名
            room_number: 房號
            amount: 應繳金額
            due_date: 到期日
            days_overdue: 逾期天數（負數表示尚未到期）
            stage: 催繳階段 (first/second/third/final)
            tenant_profile: 租客檔案（歷史行為、溝通偏好等）
        
        Returns:
            生成的催繳訊息
        """
        # 如果 LLM 可用，使用 AI 生成
        if self.llm_enabled:
            try:
                return self._generate_with_llm(
                    tenant_name, room_number, amount, due_date,
                    days_overdue, stage, tenant_profile
                )
            except Exception as e:
                logger.error(f"❌ LLM 生成失敗: {e}，使用備用模板")
        
        # 使用備用模板
        return self._fallback_template(tenant_name, amount, due_date, stage)
    
    def _generate_with_llm(
        self,
        tenant_name: str,
        room_number: str,
        amount: float,
        due_date: datetime,
        days_overdue: int,
        stage: str,
        tenant_profile: Dict = None
    ) -> str:
        """使用 Claude API 生成文案"""
        # 建構 prompt
        prompt = self._build_prompt(
            tenant_name, room_number, amount, due_date,
            days_overdue, stage, tenant_profile
        )
        
        # 呼叫 Claude API
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            temperature=0.7,  # 保持一定創造性但不過度
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        # 取得生成的文案
        generated_text = message.content[0].text
        
        # 後處理：移除多餘空白、確保格式
        return self._post_process(generated_text)
    
    def _build_prompt(
        self,
        tenant_name: str,
        room_number: str,
        amount: float,
        due_date: datetime,
        days_overdue: int,
        stage: str,
        tenant_profile: Dict = None
    ) -> str:
        """建構給 LLM 的 prompt"""
        
        # 基礎資訊
        base_info = f"""你是一位專業的房東助手，負責幫房東撰寫催繳訊息。

**租客資訊：**
- 姓名：{tenant_name}
- 房間：{room_number}
- 應繳金額：NT${amount:,.0f}
- 到期日：{due_date.strftime('%Y/%m/%d')}
- 當前狀況：{'已逾期 ' + str(days_overdue) + ' 天' if days_overdue > 0 else '即將到期'}

**催繳階段：{stage}**
"""
        
        # 根據階段調整語氣指示
        stage_instructions = {
            "first": """【第一階段：友善提醒】
- 語氣：溫和、友善、不帶壓力
- 目的：單純提醒，避免租客忘記
- 語氣範例：「親愛的」、「友善的提醒」、「感謝配合」
- 長度：3-4 句話即可""",
            
            "second": """【第二階段：禮貌催促】
- 語氣：禮貌但稍微正式，帶有輕微急迫感
- 目的：提醒租客逾期了，需要盡快處理
- 強調：已經過了到期日，希望儘快完成
- 語氣範例：「我們注意到」、「麻煩您盡快」、「避免影響」
- 長度：4-5 句話""",
            
            "third": """【第三階段：正式警告】
- 語氣：正式、嚴肅，明確後果
- 目的：讓租客知道情況嚴重，必須立即處理
- 強調：可能採取法律行動（存證信函、違約處理）
- 語氣範例：「重要提醒」、「請於 X 天內」、「否則將採取措施」
- 長度：5-6 句話""",
            
            "final": """【最終階段：最後通知】
- 語氣：非常正式、嚴厲、不留餘地
- 目的：最後機會，房東即將介入
- 強調：法律行動即將啟動、後果嚴重
- 語氣範例：「最終通知」、「將依法處理」、「立即處理」
- 長度：6-7 句話"""
        }
        
        # 如果有租客檔案，加入個性化資訊
        profile_info = ""
        if tenant_profile:
            on_time_rate = tenant_profile.get("on_time_rate", 1.0)
            
            if on_time_rate >= 0.9 and stage in ["first", "second"]:
                profile_info = """
**租客特徵：優良租客**
- 過去繳租紀錄良好，準時率 > 90%
- 可能只是忘記了，語氣可以更友善溫暖
- 可加入「相信只是忘記了」、「一向配合良好」等正面表述"""
            
            elif on_time_rate < 0.6:
                profile_info = """
**租客特徵：經常逾期**
- 過去多次逾期紀錄
- 語氣需要更明確、直接
- 強調後果，避免過度客氣"""
        
        # 組合完整 prompt
        full_prompt = f"""{base_info}

{stage_instructions[stage]}

{profile_info}

**任務要求：**
1. 根據上述資訊，撰寫一則適合的催繳訊息
2. 訊息必須包含：到期日、金額、逾期天數（如果有）
3. 語氣符合階段要求
4. 使用繁體中文（台灣用語）
5. 保持專業但有人情味
6. 結尾可加上「如有困難歡迎聯絡房東」（前兩階段）
7. 使用適當的 emoji（但不要過度）

**請直接輸出催繳訊息，不需要其他說明。**
"""
        
        return full_prompt
    
    def _post_process(self, text: str) -> str:
        """後處理生成的文案"""
        # 移除多餘空白
        text = "\n".join(line.strip() for line in text.split("\n"))
        
        # 移除前後空行
        text = text.strip()
        
        return text
    
    # ==================== 批次生成 ====================
    
    def generate_batch_messages(
        self,
        tenants: list,
        stage: str
    ) -> Dict[str, str]:
        """
        批次生成多個租客的催繳訊息
        
        Args:
            tenants: 租客列表，每個元素包含租客資訊
            stage: 催繳階段
        
        Returns:
            {tenant_id: message} 字典
        """
        results = {}
        
        for tenant in tenants:
            try:
                message = self.generate_personalized_message(
                    tenant_name=tenant["name"],
                    room_number=tenant["room_number"],
                    amount=tenant["amount"],
                    due_date=tenant["due_date"],
                    days_overdue=tenant["days_overdue"],
                    stage=stage,
                    tenant_profile=tenant.get("profile")
                )
                results[tenant["id"]] = message
            
            except Exception as e:
                logger.error(f"❌ 生成 {tenant['name']} 的訊息失敗: {e}")
                # 失敗時使用預設模板
                results[tenant["id"]] = self._fallback_template(
                    tenant["name"], 
                    tenant["amount"], 
                    tenant["due_date"], 
                    stage
                )
        
        return results
    
    # ==================== 備用模板 ====================
    
    def _fallback_template(
        self,
        name: str,
        amount: float,
        due_date: datetime,
        stage: str
    ) -> str:
        """API 失敗時的備用模板"""
        templates = {
            "first": f"""親愛的 {name} 您好，

這是一則友善的提醒：
📅 房租到期日：{due_date.strftime('%Y/%m/%d')}
💰 應繳金額：NT${amount:,.0f}

請您於到期日前完成轉帳，感謝配合！

如有任何問題，歡迎隨時聯絡房東。
祝您有美好的一天 😊""",
            
            "second": f"""{name} 您好，

我們注意到本月房租尚未收到：
💰 金額：NT${amount:,.0f}
📅 到期日：{due_date.strftime('%Y/%m/%d')}

麻煩您盡快完成轉帳，避免影響租約。
如有特殊狀況，也歡迎與房東討論。

謝謝您的配合！""",
            
            "third": f"""{name} 您好，

【重要提醒】您的房租已逾期：
💰 金額：NT${amount:,.0f}

請於 2 個工作天內完成繳納，否則房東可能需要採取進一步措施。

如有困難，請務必與房東聯絡協商。""",
            
            "final": f"""{name} 您好，

【最終通知】您的房租已嚴重逾期：
💰 欠款金額：NT${amount:,.0f}

此為系統最終通知。房東將於 3 天內直接聯絡您，
若未獲回應，將依照租賃契約採取法律行動。

請立即處理此事。"""
        }
        
        return templates.get(stage, templates["first"])


# ============================================================================
# 使用範例
# ============================================================================

if __name__ == "__main__":
    # 初始化生成器
    generator = LLMHelper()
    
    # 情境 1：生成單一訊息
    message = generator.generate_personalized_message(
        tenant_name="林小姐",
        room_number="12F-07",
        amount=12000,
        due_date=datetime(2025, 1, 15),
        days_overdue=3,
        stage="second",
        tenant_profile={
            "on_time_rate": 0.85,
            "past_issues": 1
        }
    )
    
    print("生成的催繳訊息：")
    print("=" * 50)
    print(message)
    print("=" * 50)
    
    # 情境 2：批次生成（每月初自動執行）
    tenants_to_remind = [
        {
            "id": "t001",
            "name": "王先生",
            "room_number": "12F-01",
            "amount": 12500,
            "due_date": datetime(2025, 1, 15),
            "days_overdue": 0,
            "profile": {"on_time_rate": 0.95}
        },
        {
            "id": "t002",
            "name": "李小姐",
            "room_number": "12F-02",
            "amount": 11000,
            "due_date": datetime(2025, 1, 15),
            "days_overdue": 5,
            "profile": {"on_time_rate": 0.65}
        }
    ]
    
    batch_messages = generator.generate_batch_messages(
        tenants_to_remind,
        stage="first"
    )
    
    print("\n批次生成結果：")
    for tenant_id, msg in batch_messages.items():
        print(f"\n{tenant_id}:")
        print(msg)
