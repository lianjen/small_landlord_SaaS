"""
Authentication Router
處理用戶登入、註冊與 Token 驗證
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
import sys
import os

# 添加 backend 到 Python Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.supabase import get_supabase

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    房客/房東登入
    回傳 JWT Token 與用戶資訊
    """
    try:
        supabase = get_supabase()
        
        # 使用 Supabase Auth 驗證
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if not response.user:
            raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
        
        return LoginResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "role": response.user.user_metadata.get("role", "tenant")
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"登入失敗: {str(e)}")

@router.post("/logout")
async def logout():
    """登出"""
    try:
        supabase = get_supabase()
        supabase.auth.sign_out()
        return {"message": "登出成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登出失敗: {str(e)}")
