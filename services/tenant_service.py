"""
租客管理服務 - v4.0 (Pydantic + Supabase)
✅ 整合 Pydantic 驗證層
✅ 租客 CRUD 操作
✅ 房間佔用檢查
✅ 常量驗證
✅ 完整統計功能
✅ 與其他模組兼容
✅ SQL 注入防護
✅ DataFrame 安全處理
✅ 與 tenant_contacts 整合
✅ 完全適配 Supabase
"""

import pandas as pd
from datetime import date, datetime
from typing import Tuple, Optional, Dict, List, Union
from pydantic import ValidationError

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation

# ✅ 導入 Pydantic Schemas
from schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListItem
)

# 導入常量配置
try:
    from config.constants import ROOMS, PAYMENT
    CONSTANTS_LOADED = True
except ImportError:
    logger.warning("⚠️ 無法載入 config.constants，使用備用常量")
    CONSTANTS_LOADED = False

    class BackupConstants:
        class ROOMS:
            ALL_ROOMS = [
                "1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D",
                "4A", "4B", "4C", "4D",
            ]

        class PAYMENT:
            METHODS = ["现金", "转账", "其他"]

    ROOMS = BackupConstants.ROOMS
    PAYMENT = BackupConstants.PAYMENT


class TenantService(BaseDBService):
    """租客管理服務 (繼承 BaseDBService，整合 Pydantic)"""

    def __init__(self):
        super().__init__()
        self.all_rooms = ROOMS.ALL_ROOMS
        self.payment_methods = PAYMENT.METHODS

    # ==================== 查詢操作 ====================

    def get_tenants(self, active_only: bool = True) -> pd.DataFrame:
        """
        獲取租客列表（返回 DataFrame）

        Args:
            active_only: 是否只查詢活躍租客

        Returns:
            租客 DataFrame
        """

        def query():
            with self.get_connection() as conn:
                cursor = conn.cursor()

                condition = "WHERE status = 'active'" if active_only else ""
                
                cursor.execute(
                    f"""
                    SELECT 
                        id, room_number, name, phone, email, id_number,
                        deposit_amount, rent_amount, rent_due_day,
                        move_in_date, move_out_date, status, notes,
                        created_at, updated_at
                    FROM tenants
                    {condition}
                    ORDER BY room_number
                """
                )

                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()

                if not data:
                    logger.info("📭 無租客記錄")
                    return pd.DataFrame(columns=columns)

                log_db_operation("SELECT", "tenants", True, len(data))
                logger.info(f"✅ 查詢到 {len(data)} 位租客")
                return pd.DataFrame(data, columns=columns)

        return self.retry_on_failure(query)

    def get_all_tenants(self, include_inactive: bool = True) -> List[Dict]:
        """
        取得所有房客（返回列表格式）

        Args:
            include_inactive: 是否包含已停用的房客

        Returns:
            房客列表
        """
        try:
            df = self.get_tenants(active_only=not include_inactive)

            if not isinstance(df, pd.DataFrame):
                logger.error(f"❌ 回傳類型錯誤: 期望 DataFrame，實際 {type(df)}")
                return []

            if df.empty:
                logger.info("📭 無房客記錄")
                return []

            result = df.to_dict("records")
            logger.info(f"✅ 取得 {len(result)} 筆房客資料")
            return result

        except AttributeError as e:
            logger.error(f"❌ DataFrame 操作錯誤: {str(e)}", exc_info=True)
            return []

        except Exception as e:
            logger.error(f"❌ 取得所有房客失敗: {str(e)}", exc_info=True)
            return []

    def get_active_tenants(self) -> List[Dict]:
        """
        取得所有有效房客

        Returns:
            有效房客列表
        """
        try:
            df = self.get_tenants(active_only=True)

            if not isinstance(df, pd.DataFrame):
                logger.error(f"❌ 回傳類型錯誤: 期望 DataFrame，實際 {type(df)}")
                return []

            if df.empty:
                logger.info("📭 無有效房客")
                return []

            result = df.to_dict("records")
            logger.info(f"✅ 取得 {len(result)} 筆有效房客")
            return result

        except Exception as e:
            logger.error(f"❌ 取得有效房客失敗: {str(e)}", exc_info=True)
            return []

    def get_tenant_by_id(self, tenant_id: str) -> Optional[Dict]:
        """
        根據 ID 查詢租客

        Args:
            tenant_id: 租客 ID (TEXT)

        Returns:
            租客資訊字典，如果不存在返回 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT 
                        id, room_number, name, phone, email, id_number,
                        deposit_amount, rent_amount, rent_due_day,
                        move_in_date, move_out_date, status, notes,
                        created_at, updated_at
                    FROM tenants
                    WHERE id = %s
                """,
                    (tenant_id,),
                )

                row = cursor.fetchone()

                if not row:
                    logger.warning(f"⚠️ 找不到租客 ID: {tenant_id}")
                    return None

                columns = [desc[0] for desc in cursor.description]
                log_db_operation("SELECT", "tenants", True, 1)
                return dict(zip(columns, row))

        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}", exc_info=True)
            return None

    def get_tenant_by_room(self, room_number: str) -> Optional[Dict]:
        """
        根據房號查詢租客

        Args:
            room_number: 房號

        Returns:
            租客資訊字典，如果不存在返回 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT 
                        id, room_number, name, phone, email, id_number,
                        deposit_amount, rent_amount, rent_due_day,
                        move_in_date, move_out_date, status, notes,
                        created_at, updated_at
                    FROM tenants
                    WHERE room_number = %s AND status = 'active'
                """,
                    (room_number,),
                )

                row = cursor.fetchone()

                if not row:
                    logger.info(f"📭 房間 {room_number} 目前無租客")
                    return None

                columns = [desc[0] for desc in cursor.description]
                log_db_operation("SELECT", "tenants", True, 1)
                return dict(zip(columns, row))

        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}", exc_info=True)
            return None

    # ==================== 新增操作（整合 Pydantic）====================

    def add_tenant(
        self,
        tenant_data: Union[TenantCreate, Dict, None] = None,
        # ✅ 保留舊參數以向後兼容
        room: str = None,
        name: str = None,
        phone: str = None,
        deposit: float = None,
        base_rent: float = None,
        start: date = None,
        end: date = None,
        payment_method: str = None,
        has_water_fee: bool = False,
        annual_discount_months: int = 0,
        discount_notes: str = "",
        # ✅ 新增 Pydantic 支援的欄位
        email: str = None,
        id_number: str = None,
        rent_due_day: int = 5,
        notes: str = None,
    ) -> Tuple[bool, str]:
        """
        新增租客（支援 Pydantic 驗證）

        使用方式 1（推薦）：
            tenant = TenantCreate(
                name="王小明",
                room_number="4C",
                ...
            )
            success, msg = service.add_tenant(tenant_data=tenant)

        使用方式 2（向後兼容）：
            success, msg = service.add_tenant(
                room="4C",
                name="王小明",
                ...
            )

        Args:
            tenant_data: TenantCreate 物件或資料字典
            其他參數: 向後兼容的舊參數

        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            # ==================== Pydantic 驗證 ====================
            
            # 方式 1：使用 TenantCreate 物件
            if isinstance(tenant_data, TenantCreate):
                validated_data = tenant_data.model_dump()
                logger.info("✅ 使用 Pydantic 驗證（TenantCreate 物件）")
            
            # 方式 2：使用字典（自動驗證）
            elif isinstance(tenant_data, dict):
                try:
                    tenant_create = TenantCreate(**tenant_data)
                    validated_data = tenant_create.model_dump()
                    logger.info("✅ 使用 Pydantic 驗證（字典轉換）")
                except ValidationError as e:
                    error_msg = self._format_validation_error(e)
                    logger.error(f"❌ Pydantic 驗證失敗: {error_msg}")
                    return False, f"資料驗證失敗: {error_msg}"
            
            # 方式 3：傳統參數（組裝後驗證）
            else:
                # 組裝資料字典
                data_dict = {
                    "name": name,
                    "room_number": room,
                    "phone": phone or "",
                    "email": email,
                    "id_number": id_number,
                    "rent_amount": base_rent or deposit or 0,  # ✅ 兼容舊參數名
                    "rent_due_day": rent_due_day,
                    "deposit_amount": deposit or 0,
                    "move_in_date": start,
                    "move_out_date": end,
                    "notes": notes or discount_notes or "",
                }
                
                try:
                    tenant_create = TenantCreate(**data_dict)
                    validated_data = tenant_create.model_dump()
                    logger.info("✅ 使用 Pydantic 驗證（傳統參數）")
                except ValidationError as e:
                    error_msg = self._format_validation_error(e)
                    logger.error(f"❌ Pydantic 驗證失敗: {error_msg}")
                    return False, f"資料驗證失敗: {error_msg}"

            # ==================== 額外業務驗證 ====================
            
            # 驗證房號
            if validated_data['room_number'] not in self.all_rooms:
                logger.warning(f"❌ 房號無效: {validated_data['room_number']}")
                return False, f"無效房號: {validated_data['room_number']}"

            # 檢查房間是否已被佔用
            if not self.check_room_availability(validated_data['room_number']):
                logger.warning(f"❌ 房間已被佔用: {validated_data['room_number']}")
                return False, f"房間 {validated_data['room_number']} 已有租客"

            # ==================== 資料庫操作 ====================
            
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO tenants 
                    (room_number, name, phone, email, id_number,
                     rent_amount, rent_due_day, deposit_amount,
                     move_in_date, move_out_date, status, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        validated_data['room_number'],
                        validated_data['name'],
                        validated_data.get('phone', ''),
                        validated_data.get('email'),
                        validated_data.get('id_number'),
                        validated_data['rent_amount'],
                        validated_data.get('rent_due_day', 5),
                        validated_data['deposit_amount'],
                        validated_data['move_in_date'],
                        validated_data.get('move_out_date'),
                        validated_data.get('status', 'active'),
                        validated_data.get('notes', ''),
                    ),
                )

                tenant_id = cursor.fetchone()[0]
                conn.commit()
                
                log_db_operation("INSERT", "tenants", True, 1)
                logger.info(
                    f"✅ 新增租客: {validated_data['name']} "
                    f"({validated_data['room_number']}) - ID: {tenant_id}"
                )
                
                return True, f"成功新增租客 {validated_data['name']}"

        except ValidationError as e:
            # Pydantic 驗證錯誤
            error_msg = self._format_validation_error(e)
            log_db_operation("INSERT", "tenants", False, error=error_msg)
            logger.error(f"❌ 資料驗證失敗: {error_msg}")
            return False, f"資料驗證失敗: {error_msg}"

        except Exception as e:
            # 其他錯誤
            log_db_operation("INSERT", "tenants", False, error=str(e))
            logger.error(f"❌ 新增失敗: {str(e)}", exc_info=True)
            return False, f"新增失敗: {str(e)[:100]}"

    def create_tenant(self, tenant_data: Union[TenantCreate, Dict]) -> Optional[str]:
        """
        新增房客（別名方法，返回 ID）

        Args:
            tenant_data: TenantCreate 物件或資料字典

        Returns:
            新增房客的 ID，失敗返回 None
        """
        try:
            success, msg = self.add_tenant(tenant_data=tenant_data)

            if success:
                # 取得剛新增的租客 ID
                if isinstance(tenant_data, TenantCreate):
                    room_number = tenant_data.room_number
                else:
                    room_number = tenant_data.get("room_number")
                
                tenant = self.get_tenant_by_room(room_number)
                return tenant["id"] if tenant else None

            return None

        except Exception as e:
            logger.error(f"❌ 新增房客失敗: {str(e)}", exc_info=True)
            return None

    # ==================== 更新操作（整合 Pydantic）====================

    def update_tenant(
        self,
        tenant_id: str,
        tenant_data: Union[TenantUpdate, Dict, None] = None,
        # ✅ 保留舊參數以向後兼容
        room: str = None,
        name: str = None,
        phone: str = None,
        deposit: float = None,
        base_rent: float = None,
        start: date = None,
        end: date = None,
        payment_method: str = None,
        has_water_fee: bool = None,
        annual_discount_months: int = None,
        discount_notes: str = None,
        # ✅ 新增 Pydantic 支援的欄位
        email: str = None,
        id_number: str = None,
        rent_due_day: int = None,
        notes: str = None,
        status: str = None,
    ) -> Tuple[bool, str]:
        """
        更新租客資訊（支援 Pydantic 驗證）

        使用方式 1（推薦）：
            update_data = TenantUpdate(
                phone="0912-345-678",
                rent_amount=6500.0
            )
            success, msg = service.update_tenant(tenant_id, tenant_data=update_data)

        使用方式 2（向後兼容）：
            success, msg = service.update_tenant(
                tenant_id,
                phone="0912-345-678",
                base_rent=6500.0
            )

        Args:
            tenant_id: 租客 ID
            tenant_data: TenantUpdate 物件或資料字典
            其他參數: 向後兼容的舊參數

        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            # ==================== Pydantic 驗證 ====================
            
            # 方式 1：使用 TenantUpdate 物件
            if isinstance(tenant_data, TenantUpdate):
                validated_data = tenant_data.model_dump(exclude_unset=True)
                logger.info("✅ 使用 Pydantic 驗證（TenantUpdate 物件）")
            
            # 方式 2：使用字典（自動驗證）
            elif isinstance(tenant_data, dict):
                try:
                    tenant_update = TenantUpdate(**tenant_data)
                    validated_data = tenant_update.model_dump(exclude_unset=True)
                    logger.info("✅ 使用 Pydantic 驗證（字典轉換）")
                except ValidationError as e:
                    error_msg = self._format_validation_error(e)
                    logger.error(f"❌ Pydantic 驗證失敗: {error_msg}")
                    return False, f"資料驗證失敗: {error_msg}"
            
            # 方式 3：傳統參數（組裝後驗證）
            else:
                # 組裝資料字典（只包含有值的欄位）
                data_dict = {}
                
                if name is not None:
                    data_dict["name"] = name
                if room is not None:
                    data_dict["room_number"] = room
                if phone is not None:
                    data_dict["phone"] = phone
                if email is not None:
                    data_dict["email"] = email
                if id_number is not None:
                    data_dict["id_number"] = id_number
                if base_rent is not None:
                    data_dict["rent_amount"] = base_rent
                if rent_due_day is not None:
                    data_dict["rent_due_day"] = rent_due_day
                if deposit is not None:
                    data_dict["deposit_amount"] = deposit
                if start is not None:
                    data_dict["move_in_date"] = start
                if end is not None:
                    data_dict["move_out_date"] = end
                if status is not None:
                    data_dict["status"] = status
                if notes is not None or discount_notes is not None:
                    data_dict["notes"] = notes or discount_notes
                
                if not data_dict:
                    return False, "沒有要更新的欄位"
                
                try:
                    tenant_update = TenantUpdate(**data_dict)
                    validated_data = tenant_update.model_dump(exclude_unset=True)
                    logger.info("✅ 使用 Pydantic 驗證（傳統參數）")
                except ValidationError as e:
                    error_msg = self._format_validation_error(e)
                    logger.error(f"❌ Pydantic 驗證失敗: {error_msg}")
                    return False, f"資料驗證失敗: {error_msg}"

            # ==================== 額外業務驗證 ====================
            
            # 檢查租客是否存在
            existing_tenant = self.get_tenant_by_id(tenant_id)
            if not existing_tenant:
                return False, f"租客 ID {tenant_id} 不存在"

            # 驗證房號（如果有變更）
            if 'room_number' in validated_data:
                if validated_data['room_number'] not in self.all_rooms:
                    return False, f"無效房號: {validated_data['room_number']}"
                
                # 檢查新房間是否已被佔用（排除自己）
                existing_room_tenant = self.get_tenant_by_room(validated_data['room_number'])
                if existing_room_tenant and existing_room_tenant['id'] != tenant_id:
                    return False, f"房間 {validated_data['room_number']} 已有租客"

            # ==================== 資料庫操作 ====================
            
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 動態組裝 UPDATE SQL
                set_clauses = []
                values = []
                
                for field, value in validated_data.items():
                    set_clauses.append(f"{field} = %s")
                    values.append(value)
                
                set_clauses.append("updated_at = NOW()")
                values.append(tenant_id)
                
                sql = f"""
                    UPDATE tenants
                    SET {', '.join(set_clauses)}
                    WHERE id = %s
                """
                
                cursor.execute(sql, values)
                conn.commit()
                
                log_db_operation("UPDATE", "tenants", True, 1)
                logger.info(f"✅ 更新租客 ID: {tenant_id}")

                # 若房號有變更，同步更新 tenant_contacts.room_number
                if 'room_number' in validated_data:
                    old_room = existing_tenant['room_number']
                    new_room = validated_data['room_number']
                    
                    if old_room != new_room:
                        try:
                            cursor.execute(
                                """
                                UPDATE tenant_contacts
                                SET room_number = %s,
                                    updated_at = NOW()
                                WHERE tenant_id = %s
                                """,
                                (new_room, tenant_id),
                            )
                            if cursor.rowcount > 0:
                                logger.info(
                                    f"🔄 已同步更新 tenant_contacts.room_number: "
                                    f"{old_room} -> {new_room}"
                                )
                        except Exception:
                            # tenant_contacts 表可能不存在，忽略錯誤
                            pass

                return True, f"成功更新租客資料"

        except ValidationError as e:
            # Pydantic 驗證錯誤
            error_msg = self._format_validation_error(e)
            log_db_operation("UPDATE", "tenants", False, error=error_msg)
            logger.error(f"❌ 資料驗證失敗: {error_msg}")
            return False, f"資料驗證失敗: {error_msg}"

        except Exception as e:
            # 其他錯誤
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}", exc_info=True)
            return False, f"更新失敗: {str(e)[:100]}"

    # ==================== 刪除操作 ====================

    def delete_tenant(self, tenant_id: str) -> Tuple[bool, str]:
        """
        刪除租客（軟刪除）

        行為：
        - tenants.status = 'inactive'
        - 同步清理 tenant_contacts 中的綁定資訊

        Args:
            tenant_id: 租客 ID

        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 檢查租客是否存在
                cursor.execute(
                    "SELECT name FROM tenants WHERE id = %s",
                    (tenant_id,),
                )
                row = cursor.fetchone()

                if not row:
                    return False, f"租客 ID {tenant_id} 不存在"

                tenant_name = row[0]

                # 軟刪除
                cursor.execute(
                    """
                    UPDATE tenants
                    SET status = 'inactive',
                        move_out_date = CURRENT_DATE,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (tenant_id,),
                )

                conn.commit()
                log_db_operation("UPDATE", "tenants (soft delete)", True, 1)
                logger.info(f"✅ 刪除租客 ID: {tenant_id} ({tenant_name})")

                # 同步清理 tenant_contacts 綁定狀態（如果表存在）
                try:
                    cursor.execute(
                        """
                        UPDATE tenant_contacts
                        SET
                            line_user_id = NULL,
                            is_verified = false,
                            room_number = NULL,
                            pending_room = NULL,
                            verification_code = NULL,
                            verification_expires_at = NULL,
                            updated_at = NOW()
                        WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                    if cursor.rowcount > 0:
                        logger.info(
                            f"🔄 已清理 tenant_contacts 綁定狀態 (tenant_id={tenant_id})"
                        )
                except Exception:
                    # tenant_contacts 表可能不存在，忽略錯誤
                    pass

                return True, f"成功刪除租客 {tenant_name}"

        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 刪除失敗: {str(e)}", exc_info=True)
            return False, f"刪除失敗: {str(e)[:100]}"

    # ==================== 輔助方法 ====================

    def _format_validation_error(self, error: ValidationError) -> str:
        """
        格式化 Pydantic 驗證錯誤訊息
        
        Args:
            error: ValidationError 物件
        
        Returns:
            格式化的錯誤訊息
        """
        errors = []
        for err in error.errors():
            field = " -> ".join(str(loc) for loc in err['loc'])
            message = err['msg']
            errors.append(f"{field}: {message}")
        
        return "; ".join(errors)

    def check_room_availability(self, room_number: str) -> bool:
        """
        檢查房間是否可用

        Args:
            room_number: 房號

        Returns:
            bool: True=可用, False=已佔用
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM tenants WHERE room_number = %s AND status = 'active'",
                    (room_number,),
                )

                count = cursor.fetchone()[0]
                is_available = count == 0

                logger.info(
                    f"🔍 房間 {room_number}: {'可用' if is_available else '已佔用'}"
                )
                return is_available

        except Exception as e:
            logger.error(f"❌ 檢查失敗: {str(e)}", exc_info=True)
            return False

    def get_available_rooms(self) -> List[str]:
        """
        取得所有可用房間

        Returns:
            可用房間列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT room_number 
                    FROM tenants 
                    WHERE status = 'active'
                """
                )

                occupied_rooms = [row[0] for row in cursor.fetchall()]
                available_rooms = [
                    room for room in self.all_rooms if room not in occupied_rooms
                ]

                log_db_operation(
                    "SELECT", "tenants (available rooms)", True, len(available_rooms)
                )
                logger.info(f"✅ 可用房間: {len(available_rooms)} 間")
                return available_rooms

        except Exception as e:
            log_db_operation(
                "SELECT", "tenants (available rooms)", False, error=str(e)
            )
            logger.error(f"❌ 查詢失敗: {str(e)}", exc_info=True)
            return []

    def get_vacant_rooms(self, all_rooms: Optional[List[str]] = None) -> List[str]:
        """
        取得空房列表（別名方法）

        Args:
            all_rooms: 所有房間號碼列表（如果不提供，使用預設房間列表）

        Returns:
            空房號碼列表
        """
        return self.get_available_rooms()

    def get_tenant_statistics(self) -> Dict:
        """
        取得租客統計數據

        Returns:
            統計數據字典
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT 
                        COUNT(*) as total_tenants,
                        SUM(rent_amount) as total_rent,
                        AVG(rent_amount) as avg_rent,
                        SUM(deposit_amount) as total_deposit
                    FROM tenants
                    WHERE status = 'active'
                """
                )

                row = cursor.fetchone()

                total_tenants = int(row[0] or 0)
                total_rooms = len(self.all_rooms)
                available_rooms = total_rooms - total_tenants
                occupancy_rate = (
                    total_tenants / total_rooms * 100 if total_rooms > 0 else 0
                )

                stats = {
                    "total_tenants": total_tenants,
                    "total_rent": float(row[1] or 0),
                    "avg_rent": float(row[2] or 0),
                    "total_deposit": float(row[3] or 0),
                    "occupied_rooms": total_tenants,
                    "available_rooms": available_rooms,
                    "total_rooms": total_rooms,
                    "occupancy_rate": round(occupancy_rate, 2),
                }

                log_db_operation("SELECT", "tenants (statistics)", True, 1)
                logger.info(f"✅ 統計完成: 出租率 {occupancy_rate:.1f}%")

                return stats

        except Exception as e:
            log_db_operation("SELECT", "tenants (statistics)", False, error=str(e))
            logger.error(f"❌ 統計失敗: {str(e)}", exc_info=True)
            return {
                "total_tenants": 0,
                "total_rent": 0.0,
                "avg_rent": 0.0,
                "total_deposit": 0.0,
                "occupied_rooms": 0,
                "available_rooms": len(self.all_rooms),
                "total_rooms": len(self.all_rooms),
                "occupancy_rate": 0.0,
            }

    def get_occupancy_rate(self, total_rooms: Optional[int] = None) -> float:
        """
        計算出租率（別名方法）

        Args:
            total_rooms: 總房間數（如果不提供，使用預設房間總數）

        Returns:
            出租率（百分比）
        """
        try:
            stats = self.get_tenant_statistics()
            return stats["occupancy_rate"]

        except Exception as e:
            logger.error(f"❌ 計算出租率失敗: {str(e)}", exc_info=True)
            return 0.0

    def get_expiring_leases(self, days: int = 30) -> List[Dict]:
        """
        取得即將到期的租約

        Args:
            days: 提前天數（預設 30 天）

        Returns:
            即將到期的租客列表
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT 
                        id, 
                        room_number, 
                        name, 
                        phone, 
                        move_out_date,
                        (move_out_date - CURRENT_DATE) as days_remaining
                    FROM tenants
                    WHERE status = 'active' 
                    AND move_out_date <= CURRENT_DATE + make_interval(days => %s)
                    AND move_out_date >= CURRENT_DATE
                    ORDER BY move_out_date
                """,
                    (days,),
                )

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                log_db_operation(
                    "SELECT", "tenants (expiring leases)", True, len(rows)
                )
                logger.info(f"⏰ 找到 {len(rows)} 筆即將到期的租約")

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            log_db_operation(
                "SELECT", "tenants (expiring leases)", False, error=str(e)
            )
            logger.error(f"❌ 查詢失敗: {str(e)}", exc_info=True)
            return []

    def check_lease_expiry(self, days_ahead: int = 45) -> List[Dict]:
        """
        檢查即將到期的租約（別名方法）

        Args:
            days_ahead: 提前幾天檢查

        Returns:
            即將到期的房客列表
        """
        return self.get_expiring_leases(days=days_ahead)


# ============================================
# 本機測試
# ============================================
if __name__ == "__main__":
    from schemas.tenant import TenantCreate, TenantUpdate
    from datetime import date, timedelta
    
    service = TenantService()

    print("=== 測試房客服務 (Pydantic + Supabase) ===\n")

    # 測試 1：Pydantic 驗證（應該成功）
    print("1. 測試 Pydantic 驗證（正確資料）:")
    try:
        tenant_data = TenantCreate(
            name="測試房客",
            room_number="4D",
            phone="0912-345-678",
            email="test@example.com",
            rent_amount=6000.0,
            deposit_amount=12000.0,
            move_in_date=date.today(),
            move_out_date=date.today() + timedelta(days=365)
        )
        print(f"   ✅ 驗證成功: {tenant_data.name} ({tenant_data.room_number})\n")
    except ValidationError as e:
        print(f"   ❌ 驗證失敗: {e}\n")

    # 測試 2：Pydantic 驗證（應該失敗）
    print("2. 測試 Pydantic 驗證（錯誤資料）:")
    try:
        tenant_data = TenantCreate(
            name="王",  # ❌ 太短
            room_number="4D",
            rent_amount=-100,  # ❌ 負數
            move_in_date=date.today()
        )
        print(f"   ❌ 未攔截錯誤資料\n")
    except ValidationError as e:
        print(f"   ✅ 成功攔截錯誤: {e.error_count()} 個錯誤\n")

    # 測試 3：取得所有房客
    print("3. 所有房客 (DataFrame):")
    df = service.get_tenants()
    print(f"   共 {len(df)} 筆房客資料\n")

    # 測試 4：統計
    print("4. 租客統計:")
    stats = service.get_tenant_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # 測試 5：空房
    print("\n5. 可用房間:")
    vacant = service.get_vacant_rooms()
    if vacant:
        print(f"   {', '.join(vacant[:5])}... (共 {len(vacant)} 間)")
    else:
        print("   無空房")

    print("\n✅ 測試完成")
