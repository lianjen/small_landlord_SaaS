"""
Supabase Auth 整合服務
處理登入、登出、會話驗證
"""
import logging
from typing import Optional, Tuple, Dict
from datetime import datetime, timedelta

import streamlit as st
from supabase import create_client, Client
from gotrue.errors import AuthApiError

logger = logging.getLogger(__name__)


class AuthService:
    """Supabase 認證服務"""
    
    def __init__(self):
        """初始化 Supabase Client"""
        try:
            supabase_url = st.secrets["supabase"]["url"]
            supabase_key = st.secrets["supabase"]["key"]
            self.client: Client = create_client(supabase_url, supabase_key)
            logger.info("✅ Supabase Client 初始化成功")
        except Exception as e:
            logger.error(f"❌ Supabase Client 初始化失敗: {e}")
            raise
    
    def login(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        用戶登入
        
        Returns:
            (成功與否, 訊息, 用戶資料)
        """
        try:
            # 呼叫 Supabase Auth API
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                logger.info(f"✅ 登入成功: {email}")
                
                # 解析用戶資料
                user_data = {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": response.user.user_metadata.get("role", "landlord"),
                    "name": response.user.user_metadata.get("name", "用戶"),
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at
                }
                
                return True, "登入成功", user_data
            else:
                return False, "登入失敗：無法取得用戶資料", None
                
        except AuthApiError as e:
            logger.warning(f"❌ 登入失敗 ({email}): {e.message}")
            
            # 友善的錯誤訊息
            if "Invalid login credentials" in str(e):
                return False, "帳號或密碼錯誤", None
            elif "Email not confirmed" in str(e):
                return False, "請先驗證您的 Email", None
            else:
                return False, f"登入失敗: {e.message}", None
                
        except Exception as e:
            logger.error(f"❌ 登入異常: {e}", exc_info=True)
            return False, f"系統錯誤: {str(e)}", None
    
    def logout(self) -> bool:
        """登出用戶"""
        try:
            self.client.auth.sign_out()
            logger.info("✅ 用戶已登出")
            return True
        except Exception as e:
            logger.error(f"❌ 登出失敗: {e}")
            return False
    
    def verify_token(self, access_token: str) -> Optional[Dict]:
        """
        驗證 Access Token 是否有效
        
        Returns:
            用戶資料 or None
        """
        try:
            response = self.client.auth.get_user(access_token)
            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": response.user.user_metadata.get("role", "landlord")
                }
            return None
        except Exception as e:
            logger.warning(f"Token 驗證失敗: {e}")
            return None
    
    def refresh_session(self, refresh_token: str) -> Optional[Dict]:
        """
        刷新過期的 Session
        
        Returns:
            新的用戶資料 or None
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)
            if response.session:
                return {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at
                }
            return None
        except Exception as e:
            logger.error(f"Session 刷新失敗: {e}")
            return None
    
    def register(self, email: str, password: str, name: str) -> Tuple[bool, str]:
        """
        新用戶註冊（未來功能）
        """
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "name": name,
                        "role": "landlord"
                    }
                }
            })
            
            if response.user:
                return True, "註冊成功！請檢查 Email 完成驗證"
            return False, "註冊失敗"
            
        except Exception as e:
            return False, f"註冊失敗: {str(e)}"
