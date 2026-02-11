"""
交易自動分類引擎 - v4.0 Final
✅ 規則 + ML 混合模型進行費用分類
✅ 持續學習優化
✅ 自動提取關鍵字
✅ 支援使用者反饋
"""

import re
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from datetime import datetime

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


@dataclass
class TransactionClassification:
    """分類結果"""
    category: str
    confidence: float  # 0-1
    reasoning: str     # 分類理由
    suggested_action: Optional[str] = None  # 低信心度時的建議
    category_display: Optional[str] = None  # 類別顯示名稱


class ClassificationService(BaseDBService):
    """交易分類器 (繼承 BaseDBService)"""
    
    # 預設分類類別
    CATEGORIES = {
        "rent": "租金",
        "deposit": "押金",
        "water": "水費",
        "electricity": "電費",
        "management": "管理費",
        "maintenance": "維修費",
        "internet": "網路費",
        "cleaning": "清潔費",
        "other": "其他"
    }
    
    def __init__(self):
        super().__init__()
        self._init_tables()
        self._load_patterns()
    
    def _init_tables(self):
        """初始化機器學習記錄表"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS classification_feedback (
                        id SERIAL PRIMARY KEY,
                        description TEXT NOT NULL,
                        amount REAL NOT NULL,
                        predicted_category TEXT NOT NULL,
                        actual_category TEXT NOT NULL,
                        confidence REAL,
                        corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # ✅ 新增索引以加速查詢
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_classification_description 
                    ON classification_feedback(description)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_classification_date 
                    ON classification_feedback(corrected_at DESC)
                """)
                
                log_db_operation("CREATE TABLE", "classification_feedback", True, 1)
                logger.info("✅ 分類表初始化完成")
        
        except Exception as e:
            log_db_operation("CREATE TABLE", "classification_feedback", False, error=str(e))
            logger.error(f"❌ 初始化失敗: {str(e)}")
    
    def _load_patterns(self):
        """載入關鍵字模式（從歷史修正中學習）"""
        # 初始規則庫
        self.keyword_patterns = {
            "rent": [
                r"房租", r"租金", r"rent", r"月租",
                r"\d+月.*租", r"租.*\d+月"
            ],
            "deposit": [
                r"押金", r"deposit", r"保證金", r"擔保"
            ],
            "water": [
                r"水費", r"水電.*水", r"自來水", r"water"
            ],
            "electricity": [
                r"電費", r"水電.*電", r"台電", r"electricity"
            ],
            "management": [
                r"管理費", r"管委會", r"社區", r"management"
            ],
            "maintenance": [
                r"維修", r"修理", r"修繕", r"repair",
                r"冷氣", r"熱水器", r"水管", r"門鎖"
            ],
            "internet": [
                r"網路", r"網費", r"寬頻", r"internet", r"wifi"
            ],
            "cleaning": [
                r"清潔", r"打掃", r"cleaning", r"消毒"
            ]
        }
        
        # 從歷史修正中學習新模式（動態更新）
        self._update_patterns_from_feedback()
        
        logger.info(f"✅ 載入 {len(self.keyword_patterns)} 個分類模式")
    
    def _update_patterns_from_feedback(self):
        """從使用者修正中學習新的關鍵字"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT description, actual_category
                    FROM classification_feedback
                    WHERE confidence < 0.8
                    GROUP BY description, actual_category
                    HAVING COUNT(*) >= 2
                """)
                
                learned_count = 0
                for row in cursor.fetchall():
                    desc, category = row
                    
                    # 提取可能的關鍵字（簡單版：取前 3 個中文詞）
                    words = re.findall(r'[\u4e00-\u9fff]+', desc)
                    if words and category in self.keyword_patterns:
                        for word in words[:3]:
                            pattern = re.escape(word)
                            if pattern not in self.keyword_patterns[category]:
                                self.keyword_patterns[category].append(pattern)
                                learned_count += 1
                                logger.debug(f"✅ 學習新關鍵字: {word} → {category}")
                
                if learned_count > 0:
                    logger.info(f"✅ 從歷史中學習 {learned_count} 個新關鍵字")
        
        except Exception as e:
            logger.error(f"❌ 學習失敗: {str(e)}")
    
    # ==================== 核心分類邏輯 ====================
    
    def classify(
        self,
        description: str,
        amount: float,
        date: Optional[datetime] = None,
        tenant_id: Optional[str] = None
    ) -> TransactionClassification:
        """
        分類單筆交易
        
        邏輯：
        1. 規則匹配（關鍵字）→ 高信心度
        2. 金額特徵（租金通常固定、押金是租金的3倍）→ 中信心度
        3. 時間特徵（月初通常是租金）→ 低信心度
        4. 歷史學習（類似描述的歷史分類）→ 調整信心度
        
        Args:
            description: 交易描述
            amount: 金額
            date: 交易日期（可選）
            tenant_id: 租客 ID（可選）
        
        Returns:
            TransactionClassification: 分類結果
        """
        date = date or datetime.now()
        
        # ✅ 輸入驗證
        if not description or not description.strip():
            logger.warning("⚠️ 交易描述為空")
            return TransactionClassification(
                category="other",
                confidence=0.0,
                reasoning="交易描述為空",
                suggested_action="請提供交易描述",
                category_display=self.CATEGORIES["other"]
            )
        
        # Step 1: 關鍵字規則匹配
        rule_result = self._classify_by_rules(description)
        
        if rule_result[1] >= 0.9:
            # 高信心度，直接返回
            logger.info(f"🎯 高信心度分類: {description[:20]} → {rule_result[0]} ({rule_result[1]:.2f})")
            return TransactionClassification(
                category=rule_result[0],
                confidence=rule_result[1],
                reasoning=f"關鍵字匹配: {rule_result[2]}",
                category_display=self.CATEGORIES.get(rule_result[0], rule_result[0])
            )
        
        # Step 2: 金額特徵
        amount_result = self._classify_by_amount(
            amount, 
            tenant_id, 
            rule_result[0]
        )
        
        # Step 3: 時間特徵
        time_boost = self._get_time_feature_boost(date, rule_result[0])
        
        # Step 4: 歷史學習
        history_result = self._classify_by_history(description)
        
        # 綜合判斷（加權平均）
        final_category, final_confidence = self._merge_results(
            rule_result, 
            amount_result, 
            time_boost,
            history_result
        )
        
        # 信心度低於 0.7 時，建議人工確認
        suggested_action = None
        if final_confidence < 0.7:
            suggested_action = "建議人工確認分類"
            logger.warning(f"⚠️ 低信心度分類: {description[:20]} → {final_category} ({final_confidence:.2f})")
        else:
            logger.info(f"✅ 分類完成: {description[:20]} → {final_category} ({final_confidence:.2f})")
        
        return TransactionClassification(
            category=final_category,
            confidence=final_confidence,
            reasoning=self._build_reasoning(
                rule_result, amount_result, time_boost, history_result
            ),
            suggested_action=suggested_action,
            category_display=self.CATEGORIES.get(final_category, final_category)
        )
    
    def _classify_by_rules(self, description: str) -> Tuple[str, float, str]:
        """
        基於關鍵字規則分類
        
        Args:
            description: 交易描述
        
        Returns:
            (category, confidence, matched_pattern)
        """
        description_lower = description.lower()
        
        best_match = ("other", 0.0, "")
        
        for category, patterns in self.keyword_patterns.items():
            for pattern in patterns:
                try:
                    if re.search(pattern, description_lower, re.IGNORECASE):
                        # 計算匹配強度
                        matches = re.findall(pattern, description_lower, re.IGNORECASE)
                        match_len = len(matches)
                        confidence = min(0.95, 0.8 + match_len * 0.1)
                        
                        if confidence > best_match[1]:
                            best_match = (category, confidence, pattern)
                
                except re.error as e:
                    logger.warning(f"⚠️ 正則表達式錯誤: {pattern} - {e}")
                    continue
        
        return best_match
    
    def _classify_by_amount(
        self,
        amount: float,
        tenant_id: Optional[str] = None,
        hint_category: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        基於金額特徵分類
        
        邏輯：
        - 如果金額 = 租客月租 → 可能是租金
        - 如果金額 = 月租 × 3 → 可能是押金
        - 如果金額 < 2000 → 可能是水電/管理費
        - 如果金額 > 5000 且非整數千 → 可能是維修費
        
        Args:
            amount: 金額
            tenant_id: 租客 ID（可選）
            hint_category: 提示類別（可選）
        
        Returns:
            (category, confidence)
        """
        if tenant_id:
            try:
                # 取得租客的月租
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT base_rent FROM tenants WHERE id = %s
                    """, (tenant_id,))
                    
                    row = cursor.fetchone()
                    
                    if row:
                        monthly_rent = float(row[0])
                        
                        # 判斷
                        if abs(amount - monthly_rent) < 100:
                            logger.debug(f"💰 金額匹配月租: {amount} ≈ {monthly_rent}")
                            return ("rent", 0.85)
                        elif abs(amount - monthly_rent * 3) < 500:
                            logger.debug(f"💰 金額匹配押金: {amount} ≈ {monthly_rent * 3}")
                            return ("deposit", 0.9)
            
            except Exception as e:
                logger.error(f"❌ 查詢月租失敗: {str(e)}")
        
        # 通用金額特徵
        if amount < 2000:
            # 小額通常是水電或管理費
            if hint_category in ["water", "electricity", "management"]:
                return (hint_category, 0.65)
            return ("water", 0.5)
        
        elif amount > 5000 and amount % 1000 != 0:
            # 大額非整數通常是維修費
            return ("maintenance", 0.6)
        
        return (hint_category or "other", 0.3)
    
    def _get_time_feature_boost(
        self, 
        date: datetime, 
        hint_category: str
    ) -> float:
        """
        時間特徵加成
        
        邏輯：
        - 每月 1-5 號的交易，如果分類是 rent → +0.1 信心度
        - 月中的交易，如果是 maintenance → +0.05
        
        Args:
            date: 交易日期
            hint_category: 提示類別
        
        Returns:
            信心度加成
        """
        day = date.day
        
        if hint_category == "rent" and 1 <= day <= 5:
            logger.debug(f"📅 時間加成: 月初租金 +0.1")
            return 0.1
        elif hint_category == "maintenance" and 10 <= day <= 20:
            logger.debug(f"📅 時間加成: 月中維修 +0.05")
            return 0.05
        
        return 0.0
    
    def _classify_by_history(self, description: str) -> Tuple[str, float]:
        """
        基於歷史類似交易分類
        
        使用簡單的文本相似度匹配
        
        Args:
            description: 交易描述
        
        Returns:
            (category, confidence)
        """
        try:
            # 查詢歷史中相似的描述
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 使用前 10 個字元進行模糊匹配
                search_pattern = f"%{description[:10]}%"
                
                cursor.execute("""
                    SELECT actual_category, COUNT(*) as cnt
                    FROM classification_feedback
                    WHERE description LIKE %s
                    GROUP BY actual_category
                    ORDER BY cnt DESC
                    LIMIT 1
                """, (search_pattern,))
                
                row = cursor.fetchone()
                if row and row[1] >= 2:
                    # 歷史中有 2 次以上類似記錄
                    logger.debug(f"📚 歷史匹配: {row[0]} (出現 {row[1]} 次)")
                    return (row[0], 0.75)
        
        except Exception as e:
            logger.error(f"❌ 歷史查詢失敗: {str(e)}")
        
        return ("other", 0.0)
    
    def _merge_results(
        self,
        rule_result: Tuple,
        amount_result: Tuple,
        time_boost: float,
        history_result: Tuple
    ) -> Tuple[str, float]:
        """
        合併所有特徵的結果
        
        權重分配：
        - 規則匹配：50%
        - 金額特徵：30%
        - 歷史學習：20%
        - 時間加成：bonus
        
        Args:
            rule_result: 規則匹配結果
            amount_result: 金額特徵結果
            time_boost: 時間加成
            history_result: 歷史學習結果
        
        Returns:
            (category, confidence)
        """
        weights = {"rule": 0.5, "amount": 0.3, "history": 0.2}
        
        # 計算加權分數
        scores = {}
        
        # Rule
        scores[rule_result[0]] = scores.get(rule_result[0], 0) + \
            rule_result[1] * weights["rule"]
        
        # Amount
        scores[amount_result[0]] = scores.get(amount_result[0], 0) + \
            amount_result[1] * weights["amount"]
        
        # History
        scores[history_result[0]] = scores.get(history_result[0], 0) + \
            history_result[1] * weights["history"]
        
        # 找出最高分
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        
        # 加上時間加成
        if best_category == rule_result[0]:
            best_score = min(1.0, best_score + time_boost)
        
        return (best_category, best_score)
    
    def _build_reasoning(
        self,
        rule_result: Tuple,
        amount_result: Tuple,
        time_boost: float,
        history_result: Tuple
    ) -> str:
        """建立分類理由說明"""
        reasons = []
        
        if rule_result[1] > 0.7:
            reasons.append(f"關鍵字 '{rule_result[2]}' 強烈匹配")
        
        if amount_result[1] > 0.6:
            category_name = self.CATEGORIES.get(amount_result[0], amount_result[0])
            reasons.append(f"金額特徵符合 {category_name}")
        
        if time_boost > 0:
            reasons.append("時間特徵加成")
        
        if history_result[1] > 0.6:
            reasons.append("歷史類似交易")
        
        return " | ".join(reasons) if reasons else "低信心度分類"
    
    # ==================== 反饋學習 ====================
    
    def record_correction(
        self,
        description: str,
        amount: float,
        predicted: str,
        actual: str,
        confidence: float
    ) -> bool:
        """
        記錄使用者修正
        用於持續學習
        
        Args:
            description: 交易描述
            amount: 金額
            predicted: 預測分類
            actual: 實際分類
            confidence: 預測信心度
        
        Returns:
            bool: 成功/失敗
        """
        try:
            # ✅ 驗證類別是否有效
            if actual not in self.CATEGORIES:
                logger.warning(f"⚠️ 無效的分類類別: {actual}")
                return False
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO classification_feedback
                    (description, amount, predicted_category, actual_category, confidence)
                    VALUES (%s, %s, %s, %s, %s)
                """, (description, amount, predicted, actual, confidence))
                
                log_db_operation("INSERT", "classification_feedback", True, 1)
                logger.info(f"✅ 記錄反饋: {predicted} → {actual} (信心度: {confidence:.2f})")
                
                # 如果預測錯誤，立即重新學習
                if predicted != actual:
                    logger.info(f"🔄 觸發重新學習...")
                    self._update_patterns_from_feedback()
                
                return True
        
        except Exception as e:
            log_db_operation("INSERT", "classification_feedback", False, error=str(e))
            logger.error(f"❌ 記錄失敗: {str(e)}")
            return False
    
    def batch_classify(
        self,
        transactions: List[Dict]
    ) -> List[TransactionClassification]:
        """
        批次分類多筆交易
        
        Args:
            transactions: 交易列表，每個包含 description, amount, date, tenant_id
        
        Returns:
            分類結果列表
        """
        results = []
        
        for trans in transactions:
            try:
                result = self.classify(
                    description=trans.get('description', ''),
                    amount=float(trans.get('amount', 0)),
                    date=trans.get('date'),
                    tenant_id=trans.get('tenant_id')
                )
                results.append(result)
            
            except Exception as e:
                logger.error(f"❌ 批次分類失敗: {e}")
                results.append(TransactionClassification(
                    category="other",
                    confidence=0.0,
                    reasoning=f"分類失敗: {str(e)[:50]}",
                    suggested_action="請人工檢查"
                ))
        
        logger.info(f"✅ 批次分類完成: {len(results)} 筆")
        return results
    
    def get_classification_stats(self) -> Dict:
        """
        取得分類統計數據（用於監控模型表現）
        
        Returns:
            統計數據字典
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN predicted_category = actual_category THEN 1 ELSE 0 END) as correct,
                        AVG(confidence) as avg_confidence
                    FROM classification_feedback
                    WHERE corrected_at >= CURRENT_DATE - INTERVAL '30 days'
                """)
                
                row = cursor.fetchone()
                
                if row and row[0] > 0:
                    total = int(row[0])
                    correct = int(row[1])
                    accuracy = correct / total
                    
                    stats = {
                        "total_corrections": total,
                        "correct_predictions": correct,
                        "accuracy": round(accuracy, 3),
                        "avg_confidence": round(float(row[2]), 3)
                    }
                    
                    log_db_operation("SELECT", "classification_feedback (stats)", True, 1)
                    logger.info(f"📊 模型準確率: {accuracy * 100:.1f}% ({correct}/{total})")
                    
                    return stats
                
                return {
                    "total_corrections": 0, 
                    "correct_predictions": 0,
                    "accuracy": 0.0, 
                    "avg_confidence": 0.0
                }
        
        except Exception as e:
            log_db_operation("SELECT", "classification_feedback (stats)", False, error=str(e))
            logger.error(f"❌ 統計失敗: {str(e)}")
            return {}
    
    def get_category_distribution(self) -> Dict[str, int]:
        """
        取得各分類的分佈統計
        
        Returns:
            {category: count} 字典
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT actual_category, COUNT(*) as cnt
                    FROM classification_feedback
                    WHERE corrected_at >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY actual_category
                    ORDER BY cnt DESC
                """)
                
                distribution = {}
                for row in cursor.fetchall():
                    category = row[0]
                    count = int(row[1])
                    distribution[category] = count
                
                logger.info(f"📊 分類分佈: {len(distribution)} 個類別")
                return distribution
        
        except Exception as e:
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return {}
