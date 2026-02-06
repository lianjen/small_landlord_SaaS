"""
租客聯絡方式服務 - v2.0
處理 LINE User ID 綁定、通知偏好設定、綁定驗證狀態

✅ 自動建立 / 升級 tenant_contacts 表
    - 兼容舊 DB（原本只有 tenant_id, line_user_id, notify_*）
    - 新增欄位：
        room_number, is_verified, verified_at,
        pending_room, verification_code, verification_expires_at
✅ 綁定/解綁 LINE User ID（後台以 tenant_id 綁定，視為已驗證）
✅ 更新通知偏好
✅ 查詢綁定狀態
✅ 對齊 tenants 新欄位 (room_number, tenant_name, is_active, base_rent)
"""

from typing import Tuple, Optional, Dict, List

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation


class TenantContactService(BaseDBService):
    """房客聯絡方式管理服務"""

    def __init__(self) -> None:
        super().__init__()
        self._init_tables()

    # ==================== 初始化 / Schema 升級 ====================

    def _init_tables(self) -> None:
        """
        初始化 / 升級 tenant_contacts 表。

        注意：
        - 舊安裝可能沒有 id 欄位或新增欄位，本方法會用 CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN IF NOT EXISTS
        - 不移除任何既有欄位，確保向後相容
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 1) 若不存在則建立完整新表結構
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tenant_contacts (
                        id SERIAL PRIMARY KEY,
                        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                        line_user_id TEXT,
                        room_number VARCHAR(10),
                        is_verified BOOLEAN DEFAULT false,
                        verified_at TIMESTAMP,
                        pending_room VARCHAR(10),
                        verification_code VARCHAR(20),
                        verification_expires_at TIMESTAMP,
                        notify_rent BOOLEAN DEFAULT true,
                        notify_electricity BOOLEAN DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(tenant_id)
                    )
                    """
                )

                # 2) Schema 升級：為舊表補上新欄位（IF NOT EXISTS 保證安全）
                cursor.execute(
                    """
                    ALTER TABLE tenant_contacts
                        ADD COLUMN IF NOT EXISTS room_number VARCHAR(10),
                        ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT false,
                        ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP,
                        ADD COLUMN IF NOT EXISTS pending_room VARCHAR(10),
                        ADD COLUMN IF NOT EXISTS verification_code VARCHAR(20),
                        ADD COLUMN IF NOT EXISTS verification_expires_at TIMESTAMP,
                        ADD COLUMN IF NOT EXISTS notify_rent BOOLEAN DEFAULT true,
                        ADD COLUMN IF NOT EXISTS notify_electricity BOOLEAN DEFAULT true,
                        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """
                )

                # 3) 索引
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_tenant_contacts_tenant_id
                    ON tenant_contacts(tenant_id)
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_tenant_contacts_line_user_id
                    ON tenant_contacts(line_user_id)
                    WHERE line_user_id IS NOT NULL
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_tenant_contacts_room_number
                    ON tenant_contacts(room_number)
                    WHERE room_number IS NOT NULL
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_tenant_contacts_verified
                    ON tenant_contacts(is_verified)
                    """
                )

                logger.info("✅ tenant_contacts 表初始化 / 升級完成")

        except Exception as e:
            logger.error(f"❌ 初始化 tenant_contacts 表失敗: {str(e)}", exc_info=True)

    # ==================== LINE 綁定管理（後台：以 tenant_id 為主） ====================

    def bind_line_user(
        self,
        tenant_id: int,
        line_user_id: str,
        notify_rent: bool = True,
        notify_electricity: bool = True,
    ) -> Tuple[bool, str]:
        """
        綁定 LINE User ID 到房客（後台操作）

        行為：
        - 確認 tenants 表中存在且 is_active = true
        - 若同一 LINE 已綁定其他 tenant_id → 報錯
        - UPSERT tenant_contacts：
            - line_user_id
            - room_number（同步當下 tenants.room_number）
            - is_verified = true（後台綁定視為已驗證）
            - verified_at = NOW()
            - notify_*
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 1. 檢查房客是否存在且活躍
                cursor.execute(
                    """
                    SELECT id, tenant_name, room_number
                    FROM tenants
                    WHERE id = %s AND is_active = true
                    """,
                    (tenant_id,),
                )
                tenant = cursor.fetchone()

                if not tenant:
                    logger.warning(f"綁定失敗：找不到房客 ID {tenant_id}")
                    return False, f"❌ 找不到 ID 為 {tenant_id} 的房客或已停用"

                tenant_name = tenant[1]
                room_number = tenant[2]

                # 2. 檢查 LINE User ID 是否已被其他房客綁定
                cursor.execute(
                    """
                    SELECT tenant_id
                    FROM tenant_contacts
                    WHERE line_user_id = %s
                    """,
                    (line_user_id,),
                )
                existing = cursor.fetchone()

                if existing and existing[0] != tenant_id:
                    logger.warning(
                        f"綁定失敗：LINE ID {line_user_id} 已綁定到房客 ID {existing[0]}"
                    )
                    return False, f"❌ 此 LINE 帳號已綁定到其他房客（ID: {existing[0]}）"

                # 3. 插入或更新綁定（使用 UPSERT）
                cursor.execute(
                    """
                    INSERT INTO tenant_contacts (
                        tenant_id,
                        line_user_id,
                        room_number,
                        is_verified,
                        verified_at,
                        notify_rent,
                        notify_electricity,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, true, NOW(), %s, %s, NOW(), NOW())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        line_user_id = EXCLUDED.line_user_id,
                        room_number = EXCLUDED.room_number,
                        is_verified = true,
                        verified_at = NOW(),
                        notify_rent = EXCLUDED.notify_rent,
                        notify_electricity = EXCLUDED.notify_electricity,
                        updated_at = NOW()
                    """,
                    (tenant_id, line_user_id, room_number, notify_rent, notify_electricity),
                )

                log_db_operation("UPSERT", "tenant_contacts", True, 1)
                logger.info(
                    f"✅ LINE 綁定成功: {tenant_name} ({room_number}) -> {line_user_id}"
                )

                return True, f"✅ 成功綁定 {tenant_name}（{room_number}）"

        except Exception as e:
            log_db_operation("UPSERT", "tenant_contacts", False, error=str(e))
            logger.error(f"❌ LINE 綁定失敗: {str(e)}", exc_info=True)
            return False, f"❌ 綁定失敗: {str(e)[:100]}"

    def unbind_line_user(self, tenant_id: int) -> Tuple[bool, str]:
        """
        解除 LINE 綁定

        行為：
        - 清除 line_user_id
        - 將 is_verified 設為 false
        - 清除 room_number（保留 tenants 那邊才是權威）
        - 清除 pending_* / verification_* 欄位，避免殘留驗證流程狀態
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT line_user_id
                    FROM tenant_contacts
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                existing = cursor.fetchone()

                if not existing or not existing[0]:
                    return False, "❌ 此房客尚未綁定 LINE"

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

                if cursor.rowcount == 0:
                    return False, "❌ 解除綁定失敗"

                log_db_operation("UPDATE", "tenant_contacts", True, 1)
                logger.info(f"✅ 解除 LINE 綁定: tenant_id={tenant_id}")

                return True, "✅ 解除綁定成功"

        except Exception as e:
            log_db_operation("UPDATE", "tenant_contacts", False, error=str(e))
            logger.error(f"❌ 解除綁定失敗: {str(e)}", exc_info=True)
            return False, f"❌ 解除失敗: {str(e)[:100]}"

    # ==================== 查詢功能 ====================

    def get_tenant_contact(self, tenant_id: int) -> Optional[Dict]:
        """
        取得房客聯絡資訊（兼容舊表，並補上驗證相關欄位）

        回傳欄位：
        - tenant_id, line_user_id, notify_rent, notify_electricity
        - created_at, updated_at
        - tenant_name, room_number（COALESCE(tc.room_number, t.room_number)）
        - is_verified, verified_at
        - pending_room, verification_code, verification_expires_at
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        tc.tenant_id,
                        tc.line_user_id,
                        tc.notify_rent,
                        tc.notify_electricity,
                        tc.created_at,
                        tc.updated_at,
                        t.tenant_name,
                        COALESCE(tc.room_number, t.room_number) AS room_number,
                        COALESCE(tc.is_verified, false) AS is_verified,
                        tc.verified_at,
                        tc.pending_room,
                        tc.verification_code,
                        tc.verification_expires_at
                    FROM tenant_contacts tc
                    LEFT JOIN tenants t ON tc.tenant_id = t.id
                    WHERE tc.tenant_id = %s
                    """,
                    (tenant_id,),
                )

                row = cursor.fetchone()

                if not row:
                    # 如果沒有記錄，檢查房客是否存在
                    cursor.execute(
                        """
                        SELECT tenant_name, room_number
                        FROM tenants
                        WHERE id = %s
                        """,
                        (tenant_id,),
                    )
                    tenant = cursor.fetchone()

                    if tenant:
                        return {
                            "tenant_id": tenant_id,
                            "line_user_id": None,
                            "notify_rent": True,
                            "notify_electricity": True,
                            "created_at": None,
                            "updated_at": None,
                            "tenant_name": tenant[0],
                            "room_number": tenant[1],
                            "is_verified": False,
                            "verified_at": None,
                            "pending_room": None,
                            "verification_code": None,
                            "verification_expires_at": None,
                        }

                    return None

                return {
                    "tenant_id": row[0],
                    "line_user_id": row[1],
                    "notify_rent": row[2],
                    "notify_electricity": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                    "tenant_name": row[6],
                    "room_number": row[7],
                    "is_verified": row[8],
                    "verified_at": row[9],
                    "pending_room": row[10],
                    "verification_code": row[11],
                    "verification_expires_at": row[12],
                }

        except Exception as e:
            logger.error(f"❌ 取得聯絡資訊失敗: {str(e)}", exc_info=True)
            return None

    def get_tenant_by_line_id(self, line_user_id: str) -> Optional[Dict]:
        """
        根據 LINE User ID 查詢房客（只回傳已驗證的綁定）

        用途：
        - 之後在發送通知 / LINE Bot 指令時，用 LINE User ID 找到對應的 tenant
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        t.id,
                        COALESCE(tc.room_number, t.room_number) AS room_number,
                        t.tenant_name,
                        t.phone,
                        tc.notify_rent,
                        tc.notify_electricity,
                        t.base_rent,
                        t.deposit,
                        COALESCE(tc.is_verified, false) AS is_verified
                    FROM tenants t
                    INNER JOIN tenant_contacts tc ON t.id = tc.tenant_id
                    WHERE
                        tc.line_user_id = %s
                        AND t.is_active = true
                        AND COALESCE(tc.is_verified, false) = true
                    """,
                    (line_user_id,),
                )

                row = cursor.fetchone()

                if not row:
                    return None

                return {
                    "tenant_id": row[0],
                    "room_number": row[1],
                    "tenant_name": row[2],
                    "phone": row[3],
                    "notify_rent": row[4],
                    "notify_electricity": row[5],
                    "base_rent": row[6],
                    "deposit": row[7],
                    "is_verified": row[8],
                }

        except Exception as e:
            logger.error(f"❌ 根據 LINE ID 查詢房客失敗: {str(e)}", exc_info=True)
            return None

    def get_all_line_bindings(self) -> List[Dict]:
        """
        取得所有 LINE 綁定記錄（不依賴 tc.id）

        注意：
        - 這裡會同時回傳 is_verified，前端可以自行決定是否只顯示已驗證綁定
        - 僅包含 t.is_active = true 且 tc.line_user_id 不為空的紀錄
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        tc.tenant_id,
                        tc.line_user_id,
                        tc.notify_rent,
                        tc.notify_electricity,
                        COALESCE(tc.room_number, t.room_number) AS room_number,
                        t.tenant_name,
                        t.phone,
                        COALESCE(tc.is_verified, false) AS is_verified,
                        tc.verified_at
                    FROM tenant_contacts tc
                    INNER JOIN tenants t ON tc.tenant_id = t.id
                    WHERE
                        t.is_active = true
                        AND tc.line_user_id IS NOT NULL
                    ORDER BY room_number
                    """
                )

                results: List[Dict] = []
                for row in cursor.fetchall():
                    results.append(
                        {
                            "tenant_id": row[0],
                            "line_user_id": row[1],
                            "notify_rent": row[2],
                            "notify_electricity": row[3],
                            "room_number": row[4],
                            "tenant_name": row[5],
                            "phone": row[6],
                            "is_verified": row[7],
                            "verified_at": row[8],
                        }
                    )

                logger.info(f"查詢到 {len(results)} 筆 LINE 綁定記錄")
                return results

        except Exception as e:
            logger.error(f"❌ 查詢 LINE 綁定記錄失敗: {str(e)}", exc_info=True)
            return []

    # ==================== 通知設定管理 ====================

    def update_notification_settings(
        self,
        tenant_id: int,
        notify_rent: Optional[bool] = None,
        notify_electricity: Optional[bool] = None,
    ) -> Tuple[bool, str]:
        """
        更新通知偏好設定

        行為：
        - 若 tenant_contacts 尚無紀錄，會自動建立一筆（以預設 notify_* 為主）
        - 不影響 is_verified / room_number / 驗證流程欄位
        """
        try:
            updates: List[str] = []
            params: List[object] = []

            if notify_rent is not None:
                updates.append("notify_rent = %s")
                params.append(notify_rent)

            if notify_electricity is not None:
                updates.append("notify_electricity = %s")
                params.append(notify_electricity)

            if not updates:
                return False, "❌ 沒有要更新的設定"

            updates.append("updated_at = NOW()")
            params.append(tenant_id)

            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT tenant_id FROM tenant_contacts WHERE tenant_id = %s",
                    (tenant_id,),
                )

                if not cursor.fetchone():
                    cursor.execute(
                        """
                        INSERT INTO tenant_contacts (
                            tenant_id,
                            notify_rent,
                            notify_electricity,
                            created_at,
                            updated_at
                        )
                        VALUES (%s, %s, %s, NOW(), NOW())
                        """,
                        (
                            tenant_id,
                            notify_rent if notify_rent is not None else True,
                            notify_electricity
                            if notify_electricity is not None
                            else True,
                        ),
                    )
                    log_db_operation("INSERT", "tenant_contacts", True, 1)
                    logger.info(f"✅ 建立並更新通知設定: tenant_id={tenant_id}")
                    return True, "✅ 更新成功"

                cursor.execute(
                    f"UPDATE tenant_contacts SET {', '.join(updates)} WHERE tenant_id = %s",
                    tuple(params),
                )

                if cursor.rowcount == 0:
                    return False, "❌ 更新失敗"

                log_db_operation("UPDATE", "tenant_contacts", True, 1)
                logger.info(f"✅ 更新通知設定: tenant_id={tenant_id}")

                return True, "✅ 更新成功"

        except Exception as e:
            log_db_operation("UPDATE", "tenant_contacts", False, error=str(e))
            logger.error(f"❌ 更新通知設定失敗: {str(e)}", exc_info=True)
            return False, f"❌ 更新失敗: {str(e)[:100]}"

    # ==================== 統計功能 ====================

    def get_binding_statistics(self) -> Dict:
        """
        取得 LINE 綁定統計資料

        定義：
        - total_tenants: tenants.is_active = true 的總數
        - bound_count: 已驗證綁定（is_verified = true 且 line_user_id 不為空）
        - unbound_count: total_tenants - bound_count
        - rent_notify_enabled / elec_notify_enabled:
            已驗證綁定且 notify_* = true 的人數
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) FROM tenants WHERE is_active = true"
                )
                total_tenants = cursor.fetchone()[0] or 0

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM tenant_contacts tc
                    INNER JOIN tenants t ON tc.tenant_id = t.id
                    WHERE
                        t.is_active = true
                        AND tc.line_user_id IS NOT NULL
                        AND COALESCE(tc.is_verified, false) = true
                    """
                )
                bound_count = cursor.fetchone()[0] or 0

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM tenant_contacts tc
                    INNER JOIN tenants t ON tc.tenant_id = t.id
                    WHERE
                        t.is_active = true
                        AND tc.line_user_id IS NOT NULL
                        AND COALESCE(tc.is_verified, false) = true
                        AND tc.notify_rent = true
                    """
                )
                rent_notify_count = cursor.fetchone()[0] or 0

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM tenant_contacts tc
                    INNER JOIN tenants t ON tc.tenant_id = t.id
                    WHERE
                        t.is_active = true
                        AND tc.line_user_id IS NOT NULL
                        AND COALESCE(tc.is_verified, false) = true
                        AND tc.notify_electricity = true
                    """
                )
                elec_notify_count = cursor.fetchone()[0] or 0

                binding_rate = (
                    (bound_count / total_tenants * 100) if total_tenants > 0 else 0
                )

                return {
                    "total_tenants": total_tenants,
                    "bound_count": bound_count,
                    "unbound_count": total_tenants - bound_count,
                    "binding_rate": round(binding_rate, 1),
                    "rent_notify_enabled": rent_notify_count,
                    "elec_notify_enabled": elec_notify_count,
                }

        except Exception as e:
            logger.error(f"❌ 取得綁定統計失敗: {str(e)}", exc_info=True)
            return {
                "total_tenants": 0,
                "bound_count": 0,
                "unbound_count": 0,
                "binding_rate": 0,
                "rent_notify_enabled": 0,
                "elec_notify_enabled": 0,
            }


if __name__ == "__main__":
    print("=" * 60)
    print("TenantContactService 測試程式")
    print("=" * 60)

    service = TenantContactService()

    print("\n【測試 1】取得綁定統計")
    stats = service.get_binding_statistics()
    print(f"總房客數: {stats['total_tenants']}")
    print(f"已驗證綁定: {stats['bound_count']}")
    print(f"未綁定: {stats['unbound_count']}")
    print(f"綁定率: {stats['binding_rate']}%")

    print("\n【測試 2】取得所有 LINE 綁定記錄（前 5 筆）")
    bindings = service.get_all_line_bindings()
    for binding in bindings[:5]:
        print(
            f"  - {binding['room_number']} {binding['tenant_name']}: "
            f"{binding['line_user_id']} (verified={binding['is_verified']})"
        )

    print("\n" + "=" * 60)
    print("測試完成！")
