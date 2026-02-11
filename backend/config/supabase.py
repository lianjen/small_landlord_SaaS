"""
Supabase Client Configuration
統一管理 Supabase 連線
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase 連線資訊
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("請在 .env 檔案中設定 SUPABASE_URL 和 SUPABASE_KEY")

# 建立全域 Supabase 客戶端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase() -> Client:
    """
    取得 Supabase 客戶端實例
    用於 FastAPI Dependency Injection
    """
    return supabase
