"""
Payment Router
處理繳費回報相關 API
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import sys
import os
import base64

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.supabase import get_supabase
from routers.tenant import get_current_user

router = APIRouter(prefix="/api/payment", tags=["payment"])

class PaymentSubmission(BaseModel):
    amount: int
    payment_date: str
    payment_method: str
    note: Optional[str] = None

@router.post("/submit")
async def submit_payment(
    amount: int = Form(...),
    payment_date: str = Form(...),
    payment_method: str = Form(...),
    note: Optional[str] = Form(None),
    receipt_image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """
    房客提交繳費紀錄
    可上傳轉帳截圖作為憑證
    """
    try:
        supabase = get_supabase()
        
        # 處理圖片上傳
        image_url = None
        if receipt_image:
            # 讀取圖片內容
            contents = await receipt_image.read()
            file_name = f"receipts/{current_user.get('id')}/{datetime.now().timestamp()}_{receipt_image.filename}"
            
            # 上傳到 Supabase Storage
            storage_response = supabase.storage.from_("payment-receipts").upload(
                file_name,
                contents,
                {"content-type": receipt_image.content_type}
            )
            
            # 取得公開 URL
            image_url = supabase.storage.from_("payment-receipts").get_public_url(file_name)
        
        # 插入繳費記錄（狀態為 pending，需房東確認）
        payment_data = {
            "tenant_id": current_user.get("id"),
            "amount": amount,
            "payment_date": payment_date,
            "payment_method": payment_method,
            "note": note,
            "receipt_url": image_url,
            "status": "pending",  # pending, confirmed, rejected
            "created_at": datetime.now().isoformat()
        }
        
        response = supabase.table("payment_submissions").insert(payment_data).execute()
        
        return {
            "success": True,
            "message": "繳費記錄已提交，等待房東確認",
            "submission_id": response.data[0]["id"] if response.data else None
        }
    
    except Exception as e:
        print(f"繳費提交失敗: {e}")
        raise HTTPException(status_code=500, detail=f"繳費提交失敗: {str(e)}")

@router.get("/submissions")
async def get_my_submissions(current_user: dict = Depends(get_current_user)):
    """
    取得我的繳費提交記錄
    """
    try:
        supabase = get_supabase()
        
        response = supabase.table("payment_submissions")\
            .select("*")\
            .eq("tenant_id", current_user.get("id"))\
            .order("created_at", desc=True)\
            .limit(20)\
            .execute()
        
        return {"submissions": response.data}
    
    except Exception as e:
        return {"submissions": []}
