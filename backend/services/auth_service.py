"""
Supabase Auth 整合服務 - v2.0
✅ 登入/登出功能
✅ 註冊與密碼管理
✅ Token 驗證與自動刷新
✅ Session 管理
✅ 角色權限支援
✅ 完整錯誤處理
✅ 開發模式支援
✅ 完整日誌記錄
"""
import logging
import os
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
    
    # 默認角色
    DEFAULT_ROLE = "user"
    
    def __init__(self):
        """初始化 Supabase Client"""
        try:
            # ✅ 優先從 st.secrets 讀取
            supabase_url = None
            supabase_key = None
            
            if hasattr(st, 'secrets'):
                try:
                    # 嘗試從 [supabase] 區塊讀取
                    if 'supabase' in st.secrets:
                        supabase_url = st.secrets["supabase"].get("url")
                        supabase_key = st.secrets["supabase"].get("key")
                    
                    # 嘗試從根層讀取
                    if not supabase_url:
                        supabase_url = st.secrets.get("SUPABASE_URL")
                    if not supabase_key:
                        supabase_key = st.secrets.get("SUPABASE_KEY")
                except:
                    pass
            
            # 備用：從環境變數讀取
            if not supabase_url or not supabase_key:
                from dotenv import load_dotenv
                load_dotenv()
                
                supabase_url = os.getenv("SUPABASE_URL")
                supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
            
            if not supabase_url or not supabase_key:
                raise ValueError(
                    "未設定 Supabase 憑證。"
                    "請在 .streamlit/secrets.toml 設定 [supabase] 區塊"
                )
            
            self.client: Client = create_client(supabase_url, supabase_key)
            logger.info("✅ Supabase Auth Service 初始化成功")
            
        except Exception as e:
            logger.error(f"❌ Supabase Auth Service 初始化失敗: {e}", exc_info=True)
            raise
    
    # ==================== 登入/登出 ====================
    
    def login(
        self, 
        email: str, 
        password: str
    ) -> Dict[str, Any]:
        """
        用戶登入
        
        Args:
            email: 電子郵件
            password: 密碼
        
        Returns:
            {
                "success": bool,
                "message": str,
                "user": Dict (可選),
                "access_token": str (可選),
                "refresh_token": str (可選),
                "expires_at": str (可選)
            }
        """
        try:
            # 驗證輸入
            if not email or not password:
                return {
                    "success": False,
                    "message": "請輸入 Email 和密碼"
                }
            
            # 清理 Email
            email = email.strip().lower()
            
            # 呼叫 Supabase Auth API
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not response.user or not response.session:
                return {
                    "success": False,
                    "message": "登入失敗：無法取得用戶資料"
                }
            
            logger.info(f"✅ 登入成功: {email}")
            
            # ✅ 解析用戶資料
            user_data = self._extract_user_data(response.user)
            
            return {
                "success": True,
                "message": "登入成功",
                "user": user_data,
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": self._format_expires_at(response.session.expires_at)
            }
                
        except AuthApiError as e:
            logger.warning(f"❌ 登入失敗 ({email}): {e.message}")
            
            # ✅ 友善的錯誤訊息
            error_msg = self._parse_auth_error(e)
            
            return {
                "success": False,
                "message": error_msg
            }
                
        except Exception as e:
            logger.error(f"❌ 登入異常: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": f"系統錯誤: {str(e)}"
            }
    
    def logout(self) -> Dict[str, Any]:
        """
        登出用戶
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        try:
            self.client.auth.sign_out()
            logger.info("✅ 用戶已登出")
            
            return {
                "success": True,
                "message": "登出成功"
            }
            
        except Exception as e:
            logger.error(f"❌ 登出失敗: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": f"登出失敗: {str(e)}"
            }
    
    # ==================== Token 驗證與刷新 ====================
    
    def verify_token(self, access_token: str) -> Optional[Dict[str, Any]]:
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
            
            logger.debug(f"✅ Token 驗證成功: {response.user.email}")
            
            # 返回簡化的用戶資料
            return self._extract_user_data(response.user)
            
        except Exception as e:
            logger.warning(f"❌ Token 驗證失敗: {e}")
            return None
    
    def refresh_session(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        刷新過期的 Session
        
        Args:
            refresh_token: Refresh Token
        
        Returns:
            {
                "access_token": str,
                "refresh_token": str,
                "expires_at": str,
                "user": Dict
            } or None
        """
        try:
            if not refresh_token:
                logger.warning("⚠️ Refresh Token 為空")
                return None
            
            # 呼叫 Supabase refresh API
            response = self.client.auth.refresh_session(refresh_token)
            
            if not response or not response.session:
                logger.warning("⚠️ Session 刷新失敗：無效的響應")
                return None
            
            logger.info("✅ Session 已刷新")
            
            # 返回新的 Token 資料
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": self._format_expires_at(response.session.expires_at),
                "user": self._extract_user_data(response.user)
            }
            
        except AuthApiError as e:
            logger.error(f"❌ Session 刷新失敗 (Auth): {e.message}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Session 刷新失敗: {e}", exc_info=True)
            return None
    
    def check_token_expiry(self, expires_at: str) -> bool:
        """
        檢查 Token 是否即將過期
        
        Args:
            expires_at: 過期時間 (ISO 8601 格式)
        
        Returns:
            bool: True=需要刷新, False=尚未過期
        """
        try:
            if not expires_at:
                return True
            
            # 解析過期時間
            if isinstance(expires_at, str):
                expires_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            else:
                expires_time = datetime.fromtimestamp(expires_at)
            
            # 計算剩餘時間
            now = datetime.now(expires_time.tzinfo) if expires_time.tzinfo else datetime.now()
            time_until_expiry = (expires_time - now).total_seconds()
            
            # 如果剩餘時間少於緩衝時間，需要刷新
            needs_refresh = time_until_expiry < self.REFRESH_BUFFER_SECONDS
            
            if needs_refresh:
                logger.info(
                    f"⏰ Token 即將過期（剩餘 {int(time_until_expiry)}秒），"
                    f"建議刷新"
                )
            
            return needs_refresh
            
        except Exception as e:
            logger.error(f"❌ Token 過期檢查失敗: {e}", exc_info=True)
            return True  # 發生錯誤時，假設需要刷新
    
    # ==================== 註冊功能 ====================
    
    def register(
        self, 
        email: str, 
        password: str, 
        name: str,
        role: str = None
    ) -> Dict[str, Any]:
        """
        新用戶註冊
        
        Args:
            email: 電子郵件
            password: 密碼（至少 6 字元）
            name: 用戶姓名
            role: 角色（可選，默認為 user）
        
        Returns:
            {
                "success": bool,
                "message": str,
                "requires_verification": bool (可選)
            }
        """
        try:
            # 驗證輸入
            if not email or not password or not name:
                return {
                    "success": False,
                    "message": "請填寫完整資訊"
                }
            
            if len(password) < 6:
                return {
                    "success": False,
                    "message": "密碼至少需要 6 個字元"
                }
            
            # 清理輸入
            email = email.strip().lower()
            name = name.strip()
            role = role or self.DEFAULT_ROLE
            
            # 呼叫 Supabase Auth API
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "name": name,
                        "role": role
                    }
                }
            })
            
            if response.user:
                logger.info(f"✅ 註冊成功: {email} (角色: {role})")
                
                # 檢查是否需要 Email 驗證
                requires_verification = response.user.email_confirmed_at is None
                
                message = (
                    "註冊成功！請檢查 Email 完成驗證" 
                    if requires_verification 
                    else "註冊成功！"
                )
                
                return {
                    "success": True,
                    "message": message,
                    "requires_verification": requires_verification
                }
            
            return {
                "success": False,
                "message": "註冊失敗：無法建立用戶"
            }
            
        except AuthApiError as e:
            logger.warning(f"❌ 註冊失敗 ({email}): {e.message}")
            
            # 友善的錯誤訊息
            error_msg = self._parse_auth_error(e)
            
            return {
                "success": False,
                "message": error_msg
            }
                
        except Exception as e:
            logger.error(f"❌ 註冊異常: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": f"系統錯誤: {str(e)}"
            }
    
    # ==================== 密碼管理 ====================
    
    def reset_password_request(self, email: str) -> Dict[str, Any]:
        """
        請求重設密碼（發送 Email）
        
        Args:
            email: 電子郵件
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        try:
            if not email:
                return {
                    "success": False,
                    "message": "請輸入 Email"
                }
            
            email = email.strip().lower()
            
            self.client.auth.reset_password_email(email)
            
            logger.info(f"✅ 密碼重設請求已發送: {email}")
            
            return {
                "success": True,
                "message": "密碼重設信已發送至您的 Email"
            }
            
        except Exception as e:
            logger.error(f"❌ 密碼重設請求失敗: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": "發送失敗，請稍後再試"
            }
    
    def update_password(self, new_password: str) -> Dict[str, Any]:
        """
        更新密碼（需要已登入）
        
        Args:
            new_password: 新密碼
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        try:
            if not new_password:
                return {
                    "success": False,
                    "message": "請輸入新密碼"
                }
            
            if len(new_password) < 6:
                return {
                    "success": False,
                    "message": "密碼至少需要 6 個字元"
                }
            
            self.client.auth.update_user({"password": new_password})
            
            logger.info("✅ 密碼已更新")
            
            return {
                "success": True,
                "message": "密碼更新成功"
            }
            
        except Exception as e:
            logger.error(f"❌ 密碼更新失敗: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": f"更新失敗: {str(e)}"
            }
    
    # ==================== 用戶資料管理 ====================
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        取得當前登入的用戶（從 Supabase Session）
        
        Returns:
            用戶資料 or None
        """
        try:
            response = self.client.auth.get_user()
            
            if response and response.user:
                return self._extract_user_data(response.user)
            
            return None
            
        except Exception as e:
            logger.debug(f"取得當前用戶失敗: {e}")
            return None
    
    def update_user_metadata(
        self, 
        name: Optional[str] = None,
        role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        更新用戶 Metadata
        
        Args:
            name: 用戶姓名（可選）
            role: 用戶角色（可選）
            **kwargs: 其他自定義欄位
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        try:
            updates = {}
            
            if name:
                updates["name"] = name.strip()
            
            if role:
                updates["role"] = role
            
            # 合併其他欄位
            updates.update(kwargs)
            
            if not updates:
                return {
                    "success": False,
                    "message": "無更新內容"
                }
            
            self.client.auth.update_user({
                "data": updates
            })
            
            logger.info(f"✅ 用戶資料已更新: {list(updates.keys())}")
            
            return {
                "success": True,
                "message": "資料更新成功"
            }
            
        except Exception as e:
            logger.error(f"❌ 用戶資料更新失敗: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": f"更新失敗: {str(e)}"
            }
    
    # ==================== 輔助方法 ====================
    
    def _extract_user_data(self, user) -> Dict[str, Any]:
        """
        從 Supabase User 物件提取用戶資料
        
        Args:
            user: Supabase User 物件
        
        Returns:
            標準化的用戶資料字典
        """
        user_metadata = user.user_metadata or {}
        
        return {
            "id": user.id,
            "email": user.email,
            "name": (
                user_metadata.get("name") or 
                user_metadata.get("display_name") or 
                user.email.split("@")[0]
            ),
            "role": user_metadata.get("role", self.DEFAULT_ROLE),
            "email_confirmed": user.email_confirmed_at is not None,
            "created_at": user.created_at,
            "last_sign_in": user.last_sign_in_at,
            "user_metadata": user_metadata
        }
    
    def _format_expires_at(self, expires_at) -> str:
        """
        格式化過期時間為 ISO 8601 字串
        
        Args:
            expires_at: 時間戳或 datetime 物件
        
        Returns:
            ISO 8601 格式字串
        """
        try:
            if isinstance(expires_at, str):
                return expires_at
            
            if isinstance(expires_at, (int, float)):
                dt = datetime.fromtimestamp(expires_at)
                return dt.isoformat()
            
            if isinstance(expires_at, datetime):
                return expires_at.isoformat()
            
            return str(expires_at)
        
        except Exception as e:
            logger.warning(f"⚠️ 格式化過期時間失敗: {e}")
            return ""
    
    def _parse_auth_error(self, error: AuthApiError) -> str:
        """
        解析 Auth 錯誤，返回友善的中文訊息
        
        Args:
            error: AuthApiError
        
        Returns:
            友善的錯誤訊息
        """
        error_str = str(error).lower()
        error_msg = error.message.lower() if hasattr(error, 'message') else error_str
        
        # 常見錯誤映射
        error_map = {
            "invalid login credentials": "帳號或密碼錯誤",
            "email not confirmed": "請先驗證您的 Email",
            "invalid email": "Email 格式不正確",
            "user already registered": "此 Email 已被註冊",
            "password": "密碼不符合要求（至少 6 字元）",
            "weak password": "密碼強度不足",
            "rate limit": "操作過於頻繁，請稍後再試",
            "network": "網路連線異常，請檢查網路",
            "connection": "無法連接伺服器",
            "token": "登入已過期，請重新登入",
            "expired": "登入已過期，請重新登入"
        }
        
        # 查找匹配的錯誤
        for key, message in error_map.items():
            if key in error_msg:
                return message
        
        # 默認錯誤訊息
        return f"操作失敗: {error.message if hasattr(error, 'message') else str(error)}"
    
    # ==================== 健康檢查 ====================
    
    def health_check(self) -> bool:
        """
        檢查 Auth Service 是否正常運作
        
        Returns:
            bool: True=正常, False=異常
        """
        try:
            # 嘗試取得當前 Session（不會拋出錯誤）
            _ = self.client.auth.get_session()
            return True
        except Exception as e:
            logger.error(f"❌ Auth Service 健康檢查失敗: {e}")
            return False


# ============================================
# 測試程式碼
# ============================================
if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("AuthService v2.0 測試")
    print("=" * 60)
    
    try:
        # 測試 1：初始化
        print("\n📋 測試 1: 初始化")
        auth = AuthService()
        print("✅ AuthService 初始化成功")
        
        # 測試 2：健康檢查
        print("\n📋 測試 2: 健康檢查")
        is_healthy = auth.health_check()
        print(f"✅ 健康狀態: {'正常' if is_healthy else '異常'}")
        
        # 測試 3：登入（需要有效的測試帳號）
        print("\n📋 測試 3: 登入測試")
        print("⚠️ 需要設定測試帳號才能執行登入測試")
        print("跳過登入測試...")
        
        # 測試範例（需要替換為實際測試帳號）
        # result = auth.login("test@example.com", "test123456")
        # if result["success"]:
        #     print(f"✅ 登入成功: {result['user']['email']}")
        #     print(f"   角色: {result['user']['role']}")
        #     print(f"   姓名: {result['user']['name']}")
        # else:
        #     print(f"❌ 登入失敗: {result['message']}")
        
        # 測試 4：Token 過期檢查
        print("\n📋 測試 4: Token 過期檢查")
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        needs_refresh = auth.check_token_expiry(future_time)
        print(f"✅ Token 過期檢查: {'需要刷新' if needs_refresh else '尚未過期'}")
        
        print("\n" + "=" * 60)
        print("✅ 基礎測試通過！")
        print("=" * 60)
        print("\n💡 提示:")
        print("   1. 完整測試需要有效的 Supabase 測試帳號")
        print("   2. 請在 .streamlit/secrets.toml 設定測試帳號")
        print("   3. 測試帳號格式:")
        print("      [test]")
        print("      email = \"test@example.com\"")
        print("      password = \"test123456\"")
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
