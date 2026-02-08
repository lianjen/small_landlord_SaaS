"""
Supabase Auth 整合服務 - v1.0
✅ 登入/登出功能
✅ Token 驗證與刷新
✅ Session 管理
✅ 完整錯誤處理
✅ 自動 Token 刷新
"""
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

import streamlit as st
from supabase import create_client, Client
from gotrue.errors import AuthApiError

logger = logging.getLogger(__name__)


class AuthService:
    """Supabase 認證服務"""
    
    # Token 過期前自動刷新的時間（秒）
    REFRESH_BUFFER_SECONDS = 300  # 5 分鐘前刷新
    
    def __init__(self):
        """初始化 Supabase Client"""
        try:
            # ✅ 優先從 st.secrets 讀取
            if hasattr(st, 'secrets') and 'supabase' in st.secrets:
                supabase_url = st.secrets["supabase"]["url"]
                supabase_key = st.secrets["supabase"]["key"]
            else:
                # 備用：從環境變數讀取
                import os
                from dotenv import load_dotenv
                load_dotenv()
                
                supabase_url = os.getenv("SUPABASE_URL")
                supabase_key = os.getenv("SUPABASE_ANON_KEY")
                
                if not supabase_url or not supabase_key:
                    raise ValueError("未設定 Supabase 憑證")
            
            self.client: Client = create_client(supabase_url, supabase_key)
            logger.info("✅ Supabase Client 初始化成功")
            
        except Exception as e:
            logger.error(f"❌ Supabase Client 初始化失敗: {e}", exc_info=True)
            raise
    
    # ==================== 登入/登出 ====================
    
    def login(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        用戶登入
        
        Args:
            email: 電子郵件
            password: 密碼
        
        Returns:
            (成功與否, 訊息, 用戶資料)
        """
        try:
            # 驗證輸入
            if not email or not password:
                return False, "請輸入 Email 和密碼", None
            
            # 呼叫 Supabase Auth API
            response = self.client.auth.sign_in_with_password({
                "email": email.strip().lower(),
                "password": password
            })
            
            if not response.user or not response.session:
                return False, "登入失敗：無法取得用戶資料", None
            
            logger.info(f"✅ 登入成功: {email}")
            
            # ✅ 解析用戶資料
            user_data = self._parse_user_data(response)
            
            return True, "登入成功", user_data
                
        except AuthApiError as e:
            logger.warning(f"❌ 登入失敗 ({email}): {e.message}")
            
            # ✅ 友善的錯誤訊息
            error_msg = self._parse_auth_error(e)
            return False, error_msg, None
                
        except Exception as e:
            logger.error(f"❌ 登入異常: {e}", exc_info=True)
            return False, f"系統錯誤: {str(e)}", None
    
    def logout(self) -> Tuple[bool, str]:
        """
        登出用戶
        
        Returns:
            (成功與否, 訊息)
        """
        try:
            self.client.auth.sign_out()
            logger.info("✅ 用戶已登出")
            return True, "登出成功"
            
        except Exception as e:
            logger.error(f"❌ 登出失敗: {e}", exc_info=True)
            return False, f"登出失敗: {str(e)}"
    
    # ==================== Token 驗證與刷新 ====================
    
    def verify_token(self, access_token: str) -> Optional[Dict]:
        """
        驗證 Access Token 是否有效
        
        Args:
            access_token: JWT Access Token
        
        Returns:
            用戶資料 or None
        """
        try:
            if not access_token:
                return None
            
            response = self.client.auth.get_user(access_token)
            
            if not response or not response.user:
                return None
            
            # 返回簡化的用戶資料
            return {
                "id": response.user.id,
                "email": response.user.email,
                "role": response.user.user_metadata.get("role", "landlord"),
                "name": response.user.user_metadata.get("name", "用戶")
            }
            
        except Exception as e:
            logger.warning(f"Token 驗證失敗: {e}")
            return None
    
    def refresh_session(self, refresh_token: str) -> Optional[Dict]:
        """
        刷新過期的 Session
        
        Args:
            refresh_token: Refresh Token
        
        Returns:
            新的 Session 資料 or None
        """
        try:
            if not refresh_token:
                return None
            
            response = self.client.auth.refresh_session(refresh_token)
            
            if not response or not response.session:
                return None
            
            logger.info("✅ Session 已刷新")
            
            # 返回新的 Token 資料
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": response.user.user_metadata.get("role", "landlord"),
                    "name": response.user.user_metadata.get("name", "用戶")
                }
            }
            
        except Exception as e:
            logger.error(f"Session 刷新失敗: {e}", exc_info=True)
            return None
    
    def check_and_refresh_token(self, user_data: Dict) -> Optional[Dict]:
        """
        檢查 Token 是否即將過期，自動刷新
        
        Args:
            user_data: 包含 expires_at 和 refresh_token 的用戶資料
        
        Returns:
            更新後的用戶資料 or None
        """
        try:
            expires_at = user_data.get("expires_at")
            refresh_token = user_data.get("refresh_token")
            
            if not expires_at or not refresh_token:
                return None
            
            # 計算過期時間
            expires_time = datetime.fromtimestamp(expires_at)
            now = datetime.now()
            time_until_expiry = (expires_time - now).total_seconds()
            
            # 如果即將過期（小於 5 分鐘），自動刷新
            if time_until_expiry < self.REFRESH_BUFFER_SECONDS:
                logger.info(f"⏰ Token 即將過期（剩餘 {time_until_expiry:.0f} 秒），自動刷新")
                
                new_session = self.refresh_session(refresh_token)
                
                if new_session:
                    # 合併新舊資料
                    updated_data = user_data.copy()
                    updated_data.update(new_session)
                    return updated_data
            
            return user_data
            
        except Exception as e:
            logger.error(f"Token 刷新檢查失敗: {e}", exc_info=True)
            return None
    
    # ==================== 註冊功能 ====================
    
    def register(
        self, 
        email: str, 
        password: str, 
        name: str,
        role: str = "landlord"
    ) -> Tuple[bool, str]:
        """
        新用戶註冊
        
        Args:
            email: 電子郵件
            password: 密碼（至少 6 字元）
            name: 用戶姓名
            role: 角色（landlord/tenant）
        
        Returns:
            (成功與否, 訊息)
        """
        try:
            # 驗證輸入
            if not email or not password or not name:
                return False, "請填寫完整資訊"
            
            if len(password) < 6:
                return False, "密碼至少需要 6 個字元"
            
            # 呼叫 Supabase Auth API
            response = self.client.auth.sign_up({
                "email": email.strip().lower(),
                "password": password,
                "options": {
                    "data": {
                        "name": name,
                        "role": role
                    }
                }
            })
            
            if response.user:
                logger.info(f"✅ 註冊成功: {email}")
                
                # 檢查是否需要 Email 驗證
                if response.user.email_confirmed_at:
                    return True, "註冊成功！"
                else:
                    return True, "註冊成功！請檢查 Email 完成驗證"
            
            return False, "註冊失敗：無法建立用戶"
            
        except AuthApiError as e:
            logger.warning(f"❌ 註冊失敗 ({email}): {e.message}")
            
            # 友善的錯誤訊息
            if "User already registered" in str(e):
                return False, "此 Email 已被註冊"
            elif "Password should be at least" in str(e):
                return False, "密碼強度不足"
            else:
                return False, f"註冊失敗: {e.message}"
                
        except Exception as e:
            logger.error(f"❌ 註冊異常: {e}", exc_info=True)
            return False, f"系統錯誤: {str(e)}"
    
    # ==================== 密碼管理 ====================
    
    def reset_password_request(self, email: str) -> Tuple[bool, str]:
        """
        請求重設密碼（發送 Email）
        
        Args:
            email: 電子郵件
        
        Returns:
            (成功與否, 訊息)
        """
        try:
            self.client.auth.reset_password_email(email.strip().lower())
            logger.info(f"✅ 密碼重設請求已發送: {email}")
            return True, "密碼重設信已發送至您的 Email"
            
        except Exception as e:
            logger.error(f"❌ 密碼重設請求失敗: {e}", exc_info=True)
            return False, "發送失敗，請稍後再試"
    
    def update_password(self, new_password: str) -> Tuple[bool, str]:
        """
        更新密碼（需要已登入）
        
        Args:
            new_password: 新密碼
        
        Returns:
            (成功與否, 訊息)
        """
        try:
            if len(new_password) < 6:
                return False, "密碼至少需要 6 個字元"
            
            self.client.auth.update_user({"password": new_password})
            logger.info("✅ 密碼已更新")
            return True, "密碼更新成功"
            
        except Exception as e:
            logger.error(f"❌ 密碼更新失敗: {e}", exc_info=True)
            return False, f"更新失敗: {str(e)}"
    
    # ==================== 輔助方法 ====================
    
    def _parse_user_data(self, response) -> Dict[str, Any]:
        """
        解析 Supabase Auth 響應，提取用戶資料
        
        Args:
            response: Supabase Auth Response
        
        Returns:
            標準化的用戶資料字典
        """
        return {
            "id": response.user.id,
            "email": response.user.email,
            "role": response.user.user_metadata.get("role", "landlord"),
            "name": response.user.user_metadata.get("name", "用戶"),
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_at": response.session.expires_at,
            "email_confirmed": response.user.email_confirmed_at is not None,
            "created_at": response.user.created_at,
            "last_sign_in": response.user.last_sign_in_at
        }
    
    def _parse_auth_error(self, error: AuthApiError) -> str:
        """
        解析 Auth 錯誤，返回友善的中文訊息
        
        Args:
            error: AuthApiError
        
        Returns:
            友善的錯誤訊息
        """
        error_str = str(error).lower()
        
        if "invalid login credentials" in error_str:
            return "帳號或密碼錯誤"
        elif "email not confirmed" in error_str:
            return "請先驗證您的 Email"
        elif "invalid email" in error_str:
            return "Email 格式不正確"
        elif "password" in error_str and "weak" in error_str:
            return "密碼強度不足"
        elif "rate limit" in error_str:
            return "操作過於頻繁，請稍後再試"
        elif "network" in error_str or "connection" in error_str:
            return "網路連線異常，請檢查網路"
        else:
            return f"登入失敗: {error.message}"
    
    def get_current_user(self) -> Optional[Dict]:
        """
        取得當前登入的用戶（從 Supabase Session）
        
        Returns:
            用戶資料 or None
        """
        try:
            response = self.client.auth.get_user()
            
            if response and response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": response.user.user_metadata.get("role", "landlord"),
                    "name": response.user.user_metadata.get("name", "用戶")
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"取得當前用戶失敗: {e}")
            return None


# ============================================
# 測試程式碼
# ============================================
if __name__ == "__main__":
    # 簡單測試
    try:
        auth = AuthService()
        print("✅ AuthService 初始化成功")
        
        # 測試登入（使用測試帳號）
        # success, msg, user = auth.login("test@example.com", "test123")
        # print(f"登入測試: {msg}")
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
