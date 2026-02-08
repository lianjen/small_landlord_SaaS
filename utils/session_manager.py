"""
Session 管理工具 - v1.0
✅ Streamlit Session State 封裝
✅ 用戶資料管理
✅ 自動過期檢查
✅ 安全的資料存取
"""
import streamlit as st
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Session 管理器"""
    
    # Session Key 常量
    USER_KEY = "auth_user"
    LOGIN_TIME_KEY = "login_time"
    LAST_ACTIVITY_KEY = "last_activity"
    
    # Session 過期時間（秒）
    SESSION_TIMEOUT = 3600  # 1 小時無活動自動登出
    
    def __init__(self):
        """初始化 Session Manager"""
        self._init_session_state()
    
    def _init_session_state(self):
        """初始化 Session State 結構"""
        if self.USER_KEY not in st.session_state:
            st.session_state[self.USER_KEY] = None
        
        if self.LOGIN_TIME_KEY not in st.session_state:
            st.session_state[self.LOGIN_TIME_KEY] = None
        
        if self.LAST_ACTIVITY_KEY not in st.session_state:
            st.session_state[self.LAST_ACTIVITY_KEY] = None
    
    # ==================== 用戶資料管理 ====================
    
    def set_user(self, user_data: Dict[str, Any]):
        """
        儲存用戶資料到 Session
        
        Args:
            user_data: 用戶資料字典
        """
        try:
            st.session_state[self.USER_KEY] = user_data
            st.session_state[self.LOGIN_TIME_KEY] = datetime.now()
            st.session_state[self.LAST_ACTIVITY_KEY] = datetime.now()
            
            logger.info(f"✅ 用戶 Session 已建立: {user_data.get('email', 'unknown')}")
            
        except Exception as e:
            logger.error(f"❌ 設定用戶 Session 失敗: {e}", exc_info=True)
    
    def get_user(self) -> Optional[Dict[str, Any]]:
        """
        取得當前用戶資料
        
        Returns:
            用戶資料 or None
        """
        try:
            # 檢查 Session 是否過期
            if self._is_session_expired():
                logger.info("⏰ Session 已過期，自動清除")
                self.clear()
                return None
            
            # 更新最後活動時間
            st.session_state[self.LAST_ACTIVITY_KEY] = datetime.now()
            
            return st.session_state.get(self.USER_KEY)
            
        except Exception as e:
            logger.error(f"❌ 取得用戶 Session 失敗: {e}", exc_info=True)
            return None
    
    def update_user(self, updates: Dict[str, Any]):
        """
        更新用戶資料
        
        Args:
            updates: 要更新的欄位字典
        """
        try:
            current_user = self.get_user()
            
            if not current_user:
                logger.warning("⚠️ 無法更新：用戶未登入")
                return
            
            # 合併更新
            current_user.update(updates)
            st.session_state[self.USER_KEY] = current_user
            
            logger.info("✅ 用戶 Session 已更新")
            
        except Exception as e:
            logger.error(f"❌ 更新用戶 Session 失敗: {e}", exc_info=True)
    
    def clear(self):
        """清除所有 Session 資料"""
        try:
            st.session_state[self.USER_KEY] = None
            st.session_state[self.LOGIN_TIME_KEY] = None
            st.session_state[self.LAST_ACTIVITY_KEY] = None
            
            logger.info("✅ Session 已清除")
            
        except Exception as e:
            logger.error(f"❌ 清除 Session 失敗: {e}", exc_info=True)
    
    # ==================== Session 狀態檢查 ====================
    
    def is_logged_in(self) -> bool:
        """
        檢查用戶是否已登入
        
        Returns:
            bool: True=已登入, False=未登入
        """
        user = self.get_user()
        return user is not None
    
    def _is_session_expired(self) -> bool:
        """
        檢查 Session 是否過期
        
        Returns:
            bool: True=已過期, False=未過期
        """
        last_activity = st.session_state.get(self.LAST_ACTIVITY_KEY)
        
        if not last_activity:
            return False
        
        # 計算無活動時間
        inactive_duration = (datetime.now() - last_activity).total_seconds()
        
        return inactive_duration > self.SESSION_TIMEOUT
    
    def get_session_duration(self) -> Optional[int]:
        """
        取得 Session 持續時間（秒）
        
        Returns:
            持續時間（秒）or None
        """
        login_time = st.session_state.get(self.LOGIN_TIME_KEY)
        
        if not login_time:
            return None
        
        return int((datetime.now() - login_time).total_seconds())
    
    def get_remaining_time(self) -> Optional[int]:
        """
        取得 Session 剩餘時間（秒）
        
        Returns:
            剩餘時間（秒）or None
        """
        last_activity = st.session_state.get(self.LAST_ACTIVITY_KEY)
        
        if not last_activity:
            return None
        
        elapsed = (datetime.now() - last_activity).total_seconds()
        remaining = self.SESSION_TIMEOUT - elapsed
        
        return max(0, int(remaining))
    
    # ==================== 輔助方法 ====================
    
    def get_user_id(self) -> Optional[str]:
        """
        取得當前用戶 ID
        
        Returns:
            user_id or None
        """
        user = self.get_user()
        return user.get("id") if user else None
    
    def get_user_email(self) -> Optional[str]:
        """
        取得當前用戶 Email
        
        Returns:
            email or None
        """
        user = self.get_user()
        return user.get("email") if user else None
    
    def get_user_role(self) -> Optional[str]:
        """
        取得當前用戶角色
        
        Returns:
            role or None
        """
        user = self.get_user()
        return user.get("role") if user else None
    
    def get_user_name(self) -> Optional[str]:
        """
        取得當前用戶姓名
        
        Returns:
            name or None
        """
        user = self.get_user()
        return user.get("name") if user else None
    
    # ==================== 自訂資料儲存 ====================
    
    def set_custom_data(self, key: str, value: Any):
        """
        儲存自訂資料到 Session
        
        Args:
            key: 資料鍵
            value: 資料值
        """
        st.session_state[f"custom_{key}"] = value
    
    def get_custom_data(self, key: str, default: Any = None) -> Any:
        """
        取得自訂資料
        
        Args:
            key: 資料鍵
            default: 預設值
        
        Returns:
            資料值 or 預設值
        """
        return st.session_state.get(f"custom_{key}", default)
    
    def clear_custom_data(self, key: str):
        """
        清除自訂資料
        
        Args:
            key: 資料鍵
        """
        custom_key = f"custom_{key}"
        if custom_key in st.session_state:
            del st.session_state[custom_key]
    
    # ==================== Debug 工具 ====================
    
    def debug_session_info(self):
        """顯示 Session 除錯資訊（僅開發環境使用）"""
        user = self.get_user()
        
        if not user:
            st.sidebar.info("📭 未登入")
            return
        
        with st.sidebar.expander("🔍 Session Debug", expanded=False):
            st.write("**用戶資訊：**")
            st.json({
                "id": user.get("id", "N/A")[:8] + "...",  # 只顯示前 8 字元
                "email": user.get("email", "N/A"),
                "name": user.get("name", "N/A"),
                "role": user.get("role", "N/A")
            })
            
            st.write("**Session 狀態：**")
            st.write(f"- 登入時間：{st.session_state.get(self.LOGIN_TIME_KEY)}")
            st.write(f"- 持續時間：{self.get_session_duration()}秒")
            st.write(f"- 剩餘時間：{self.get_remaining_time()}秒")


# ============================================
# 全域 Session Manager 實例
# ============================================
session_manager = SessionManager()


# ============================================
# 測試程式碼
# ============================================
if __name__ == "__main__":
    print("✅ SessionManager 模組載入成功")
    
    # 測試用戶資料
    test_user = {
        "id": "test-123",
        "email": "test@example.com",
        "name": "測試用戶",
        "role": "landlord"
    }
    
    manager = SessionManager()
    
    # 測試設定用戶
    manager.set_user(test_user)
    print("✅ 設定用戶測試通過")
    
    # 測試取得用戶
    user = manager.get_user()
    assert user == test_user
    print("✅ 取得用戶測試通過")
    
    # 測試清除
    manager.clear()
    assert manager.get_user() is None
    print("✅ 清除 Session 測試通過")
    
    print("\n✅ 所有測試通過")
