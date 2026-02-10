"""
LINE Rich Menu 管理工具 (Web 介面版)
"""
import streamlit as st
import requests
import json
import os
from services.notification_service import NotificationService
from services.session_manager import session_manager

def render():
    st.title("🤖 LINE Bot 設定")
    
    if not session_manager.is_authenticated():
        st.warning("請先登入")
        return

    notification_service = NotificationService()
    token = notification_service.line_token
    
    if not token:
        st.error("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN，請檢查 .env 或 Secrets。")
        return

    st.info(f"目前 Token: {token[:10]}...{token[-5:]}")
    
    tab1, tab2 = st.tabs(["Rich Menu 上傳", "房客綁定管理"])
    
    with tab1:
        st.subheader("建立 Rich Menu")
        st.markdown("上傳圖片並設定選單動作")
        
        uploaded_image = st.file_uploader("選單圖片 (800x540 or 2500x1686)", type=['jpg', 'png'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
             btn1_label = st.text_input("按鈕 A 標籤", "我的租約")
             btn1_url = st.text_input("按鈕 A 連結", "https://your-app.streamlit.app/?role=tenant&page=profile")
        with col2:
             btn2_label = st.text_input("按鈕 B 標籤", "繳費紀錄")
             btn2_url = st.text_input("按鈕 B 連結", "https://your-app.streamlit.app/?role=tenant&page=payments")
        with col3:
             btn3_label = st.text_input("按鈕 C 標籤", "聯絡房東")
             btn3_action = st.text_input("按鈕 C 動作 (tel)", "tel:0912345678")
            
        if st.button("🚀 建立並設為預設選單", type="primary"):
            if not uploaded_image:
                st.error("請上傳圖片")
            else:
                with st.spinner("正在建立 Rich Menu..."):
                    try:
                        # 1. 定義 Menu 結構 (3格版)
                        rich_menu_object = {
                            "size": {"width": 2500, "height": 843},
                            "selected": True,
                            "name": "MicroRent Default Menu",
                            "chatBarText": "開啟選單",
                            "areas": [
                                {
                                  "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                                  "action": {"type": "uri", "label": btn1_label, "uri": btn1_url}
                                },
                                {
                                  "bounds": {"x": 833, "y": 0, "width": 833, "height": 843},
                                  "action": {"type": "uri", "label": btn2_label, "uri": btn2_url}
                                },
                                {
                                  "bounds": {"x": 1666, "y": 0, "width": 834, "height": 843},
                                  "action": {"type": "uri", "label": btn3_label, "uri": btn3_action}
                                }
                            ]
                        }
                        
                        # 2. 建立 Menu ID
                        headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json"
                        }
                        req = requests.post("https://api.line.me/v2/bot/richmenu", headers=headers, data=json.dumps(rich_menu_object))
                        
                        if req.status_code != 200:
                            st.error(f"建立 Menu ID 失敗: {req.text}")
                            return
                            
                        rich_menu_id = req.json()['richMenuId']
                        st.write(f"✅ Menu ID: `{rich_menu_id}`")
                        
                        # 3. 上傳圖片
                        headers_img = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": uploaded_image.type
                        }
                        req_img = requests.post(
                            f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
                            headers=headers_img,
                            data=uploaded_image.getvalue()
                        )
                        
                        if req_img.status_code != 200:
                            st.error(f"上傳圖片失敗: {req_img.text}")
                            return
                        
                        st.write("✅ 圖片上傳成功")
                        
                        # 4. 設為預設
                        req_default = requests.post(
                            f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
                            headers=headers
                        )
                        
                        if req_default.status_code == 200:
                             st.success("🎉 Rich Menu 已成功發布給所有用戶！")
                        else:
                             st.error(f"設為預設失敗: {req_default.text}")
                             
                    except Exception as e:
                        st.error(f"發生錯誤: {e}")

    with tab2:
        st.info("此功能將列出所有已綁定的 LINE 用戶 (開發中)")
