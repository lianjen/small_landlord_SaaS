"""
Repair Router
處理維修申請相關 API
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.supabase import get_supabase
from routers.tenant import get_current_user

router = APIRouter(prefix="/api/repair", tags=["repair"])

class RepairRequest(BaseModel):
    id: str
    title: str
    description: str
    category: str
    status: str
    created_at: str
    image_urls: Optional[List[str]]

@router.post("/create")
async def create_repair_request(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    images: Optional[List[UploadFile]] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """
    房客提交維修申請
    可上傳多張現場照片
    """
    try:
        supabase = get_supabase()
        
        # 處理多張圖片上傳
        image_urls = []
        if images:
            for idx, image in enumerate(images):
                contents = await image.read()
                file_name = f"repairs/{current_user.get('id')}/{datetime.now().timestamp()}_{idx}_{image.filename}"
                
                storage_response = supabase.storage.from_("repair-images").upload(
                    file_name,
                    contents,
                    {"content-type": image.content_type}
                )
                
                url = supabase.storage.from_("repair-images").get_public_url(file_name)
                image_urls.append(url)
        
        # 插入維修申請
        repair_data = {
            "tenant_id": current_user.get("id"),
            "title": title,
            "description": description,
            "category": category,  # plumbing, electrical, furniture, other
            "status": "pending",  # pending, in_progress, completed, rejected
            "image_urls": image_urls,
            "created_at": datetime.now().isoformat()
        }
        
        response = supabase.table("repair_requests").insert(repair_data).execute()
        
        return {
            "success": True,
            "message": "維修申請已提交",
            "request_id": response.data[0]["id"] if response.data else None
        }
    
    except Exception as e:
        print(f"維修申請失敗: {e}")
        raise HTTPException(status_code=500, detail=f"維修申請失敗: {str(e)}")

@router.get("/my-requests")
async def get_my_repair_requests(current_user: dict = Depends(get_current_user)):
    """
    取得我的維修申請記錄
    """
    try:
        supabase = get_supabase()
        
        response = supabase.table("repair_requests")\
            .select("*")\
            .eq("tenant_id", current_user.get("id"))\
            .order("created_at", desc=True)\
            .execute()
        
        return {"requests": response.data if response.data else []}
    
    except Exception as e:
        return {"requests": []}
