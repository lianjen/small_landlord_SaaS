"""
租客管理服務 - v3.0 Final
✅ 租客 CRUD 操作
✅ 房間佔用檢查
✅ 常量驗證
✅ 完整統計功能
✅ 與其他模組兼容
"""

import pandas as pd
from datetime import date
from typing import Tuple, Optional, Dict, List

from services.base_db import BaseDBService
from services.logger import logger, log_db_operation

# 導入常量配置
try:
    from config.constants import ROOMS, PAYMENT
    CONSTANTS_LOADED = True
except ImportError:
    logger.warning("⚠️ 無法載入 config.constants，使用備用常量")
    CONSTANTS_LOADED = False
    
    class BackupConstants:
        class ROOMS:
            ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
        
        class PAYMENT:
            METHODS = ["现金", "转账", "其他"]
    
    ROOMS = BackupConstants.ROOMS
    PAYMENT = BackupConstants.PAYMENT


class TenantService(BaseDBService):
    """租客管理服務 (繼承 BaseDBService)"""
    
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
                
                condition = "WHERE is_active = true" if active_only else ""
                cursor.execute(f"""
                    SELECT id, room_number, tenant_name, phone, deposit, base_rent,
                           lease_start, lease_end, payment_method, has_water_fee,
                           annual_discount_months, discount_notes, last_ac_cleaning_date,
                           is_active, created_at
                    FROM tenants
                    {condition}
                    ORDER BY room_number
                """)
                
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
            
            if df.empty:
                return []
            
            return df.to_dict('records')
        
        except Exception as e:
            logger.error(f"❌ 取得所有房客失敗: {str(e)}", exc_info=True)
            return []
    
    def get_active_tenants(self) -> List[Dict]:
        """
        取得所有有效房客
        
        Returns:
            有效房客列表
        """
        return self.get_all_tenants(include_inactive=False)
    
    def get_tenant_by_id(self, tenant_id: int) -> Optional[Dict]:
        """
        根據 ID 查詢租客
        
        Args:
            tenant_id: 租客 ID
        
        Returns:
            租客資訊字典，如果不存在返回 None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, room_number, tenant_name, phone, deposit, base_rent,
                           lease_start, lease_end, payment_method, has_water_fee,
                           annual_discount_months, discount_notes, is_active
                    FROM tenants
                    WHERE id = %s
                """, (tenant_id,))
                
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(f"⚠️ 找不到租客 ID: {tenant_id}")
                    return None
                
                columns = [desc[0] for desc in cursor.description]
                log_db_operation("SELECT", "tenants", True, 1)
                return dict(zip(columns, row))
        
        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
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
                
                cursor.execute("""
                    SELECT id, room_number, tenant_name, phone, deposit, base_rent,
                           lease_start, lease_end, payment_method, has_water_fee,
                           annual_discount_months, discount_notes, is_active
                    FROM tenants
                    WHERE room_number = %s AND is_active = true
                """, (room_number,))
                
                row = cursor.fetchone()
                
                if not row:
                    logger.info(f"📭 房間 {room_number} 目前無租客")
                    return None
                
                columns = [desc[0] for desc in cursor.description]
                log_db_operation("SELECT", "tenants", True, 1)
                return dict(zip(columns, row))
        
        except Exception as e:
            log_db_operation("SELECT", "tenants", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
            return None
    
    # ==================== 新增操作 ====================
    
    def add_tenant(
        self, 
        room: str, 
        name: str, 
        phone: str, 
        deposit: float, 
        base_rent: float,
        start: date, 
        end: date, 
        payment_method: str, 
        has_water_fee: bool = False,
        annual_discount_months: int = 0, 
        discount_notes: str = ""
    ) -> Tuple[bool, str]:
        """
        新增租客
        
        Args:
            room: 房號
            name: 租客姓名
            phone: 電話
            deposit: 押金
            base_rent: 基礎月租
            start: 租約開始日
            end: 租約結束日
            payment_method: 付款方式
            has_water_fee: 是否包含水費
            annual_discount_months: 年度折扣月數
            discount_notes: 折扣備註
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            # 驗證房號
            if room not in self.all_rooms:
                logger.warning(f"❌ 房號無效: {room}")
                return False, f"無效房號: {room}"
            
            # 驗證付款方式
            if payment_method not in self.payment_methods:
                logger.warning(f"❌ 支付方式無效: {payment_method}")
                return False, f"無效支付方式: {payment_method}"
            
            # 驗證日期邏輯
            if start >= end:
                logger.warning(f"❌ 日期邏輯錯誤: 開始日 {start} >= 結束日 {end}")
                return False, "租約開始日必須早於結束日"
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 檢查房間是否已被佔用
                cursor.execute(
                    "SELECT COUNT(*) FROM tenants WHERE room_number = %s AND is_active = true",
                    (room,)
                )
                
                if cursor.fetchone()[0] > 0:
                    logger.warning(f"❌ 房間已被佔用: {room}")
                    return False, f"房間 {room} 已有租客"
                
                # 插入租客
                cursor.execute("""
                    INSERT INTO tenants 
                    (room_number, tenant_name, phone, deposit, base_rent, lease_start, 
                     lease_end, payment_method, has_water_fee, annual_discount_months, discount_notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (room, name, phone, deposit, base_rent, start, end, 
                      payment_method, has_water_fee, annual_discount_months, discount_notes))
                
                log_db_operation("INSERT", "tenants", True, 1)
                logger.info(f"✅ 新增租客: {name} ({room})")
                return True, f"成功新增租客 {name}"
        
        except Exception as e:
            log_db_operation("INSERT", "tenants", False, error=str(e))
            logger.error(f"❌ 新增失敗: {str(e)}")
            return False, f"新增失敗: {str(e)[:100]}"
    
    def create_tenant(self, tenant_data: Dict) -> Optional[int]:
        """
        新增房客（別名方法，返回 ID）
        
        Args:
            tenant_data: 房客資料字典
        
        Returns:
            新增房客的 ID，失敗返回 None
        """
        try:
            success, msg = self.add_tenant(
                room=tenant_data['room_number'],
                name=tenant_data['tenant_name'],
                phone=tenant_data.get('phone', ''),
                deposit=tenant_data['deposit'],
                base_rent=tenant_data['base_rent'],
                start=tenant_data['lease_start'],
                end=tenant_data['lease_end'],
                payment_method=tenant_data['payment_method'],
                has_water_fee=tenant_data.get('has_water_fee', False),
                annual_discount_months=tenant_data.get('annual_discount_months', 0),
                discount_notes=tenant_data.get('discount_notes', '')
            )
            
            if success:
                # 取得剛新增的租客 ID
                tenant = self.get_tenant_by_room(tenant_data['room_number'])
                return tenant['id'] if tenant else None
            
            return None
        
        except Exception as e:
            logger.error(f"❌ 新增房客失敗: {str(e)}", exc_info=True)
            return None
    
    # ==================== 更新操作 ====================
    
    def update_tenant(
        self, 
        tenant_id: int, 
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
        tenant_data: Dict = None
    ) -> Tuple[bool, str]:
        """
        更新租客資訊（支援兩種調用方式）
        
        方式1：單獨參數
        方式2：使用 tenant_data 字典
        
        Args:
            tenant_id: 租客 ID
            其他參數: 要更新的欄位（可選）
            tenant_data: 包含所有更新欄位的字典（可選）
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            # 如果提供了 tenant_data，從中提取參數
            if tenant_data:
                room = tenant_data.get('room_number', room)
                name = tenant_data.get('tenant_name', name)
                phone = tenant_data.get('phone', phone)
                deposit = tenant_data.get('deposit', deposit)
                base_rent = tenant_data.get('base_rent', base_rent)
                start = tenant_data.get('lease_start', start)
                end = tenant_data.get('lease_end', end)
                payment_method = tenant_data.get('payment_method', payment_method)
                has_water_fee = tenant_data.get('has_water_fee', has_water_fee)
                annual_discount_months = tenant_data.get('annual_discount_months', annual_discount_months)
                discount_notes = tenant_data.get('discount_notes', discount_notes)
            
            # 驗證必要欄位
            if not all([room, name, deposit is not None, base_rent is not None, start, end, payment_method]):
                return False, "缺少必要欄位"
            
            # 驗證房號和付款方式
            if room not in self.all_rooms:
                return False, f"無效房號: {room}"
            if payment_method not in self.payment_methods:
                return False, f"無效支付方式: {payment_method}"
            
            # 驗證日期邏輯
            if start >= end:
                return False, "租約開始日必須早於結束日"
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 檢查租客是否存在
                cursor.execute("SELECT COUNT(*) FROM tenants WHERE id = %s", (tenant_id,))
                if cursor.fetchone()[0] == 0:
                    return False, f"租客 ID {tenant_id} 不存在"
                
                cursor.execute("""
                    UPDATE tenants SET
                        room_number = %s, tenant_name = %s, phone = %s, deposit = %s,
                        base_rent = %s, lease_start = %s, lease_end = %s, payment_method = %s,
                        has_water_fee = %s, annual_discount_months = %s, discount_notes = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (room, name, phone or '', deposit, base_rent, start, end, 
                      payment_method, has_water_fee or False, annual_discount_months or 0, 
                      discount_notes or '', tenant_id))
                
                log_db_operation("UPDATE", "tenants", True, 1)
                logger.info(f"✅ 更新租客 ID: {tenant_id}")
                return True, f"成功更新租客 {name}"
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 更新失敗: {str(e)}")
            return False, f"更新失敗: {str(e)[:100]}"
    
    # ==================== 刪除操作 ====================
    
    def delete_tenant(self, tenant_id: int) -> Tuple[bool, str]:
        """
        刪除租客（軟刪除）
        
        Args:
            tenant_id: 租客 ID
        
        Returns:
            (bool, str): 成功/失敗訊息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 檢查租客是否存在
                cursor.execute("SELECT tenant_name FROM tenants WHERE id = %s", (tenant_id,))
                row = cursor.fetchone()
                
                if not row:
                    return False, f"租客 ID {tenant_id} 不存在"
                
                tenant_name = row[0]
                
                cursor.execute("UPDATE tenants SET is_active = false, updated_at = NOW() WHERE id = %s", (tenant_id,))
                
                log_db_operation("UPDATE", "tenants (soft delete)", True, 1)
                logger.info(f"✅ 刪除租客 ID: {tenant_id} ({tenant_name})")
                return True, f"成功刪除租客 {tenant_name}"
        
        except Exception as e:
            log_db_operation("UPDATE", "tenants", False, error=str(e))
            logger.error(f"❌ 刪除失敗: {str(e)}")
            return False, f"刪除失敗: {str(e)[:100]}"
    
    # ==================== 輔助方法 ====================
    
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
                    "SELECT COUNT(*) FROM tenants WHERE room_number = %s AND is_active = true",
                    (room_number,)
                )
                
                count = cursor.fetchone()[0]
                is_available = count == 0
                
                logger.info(f"🔍 房間 {room_number}: {'可用' if is_available else '已佔用'}")
                return is_available
        
        except Exception as e:
            logger.error(f"❌ 檢查失敗: {str(e)}")
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
                
                cursor.execute("""
                    SELECT room_number 
                    FROM tenants 
                    WHERE is_active = true
                """)
                
                occupied_rooms = [row[0] for row in cursor.fetchall()]
                available_rooms = [room for room in self.all_rooms if room not in occupied_rooms]
                
                log_db_operation("SELECT", "tenants (available rooms)", True, len(available_rooms))
                logger.info(f"✅ 可用房間: {len(available_rooms)} 間")
                return available_rooms
        
        except Exception as e:
            log_db_operation("SELECT", "tenants (available rooms)", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
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
                
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_tenants,
                        SUM(base_rent) as total_rent,
                        AVG(base_rent) as avg_rent,
                        SUM(deposit) as total_deposit
                    FROM tenants
                    WHERE is_active = true
                """)
                
                row = cursor.fetchone()
                
                total_tenants = int(row[0] or 0)
                total_rooms = len(self.all_rooms)
                available_rooms = total_rooms - total_tenants
                occupancy_rate = (total_tenants / total_rooms * 100) if total_rooms > 0 else 0
                
                stats = {
                    'total_tenants': total_tenants,
                    'total_rent': float(row[1] or 0),
                    'avg_rent': float(row[2] or 0),
                    'total_deposit': float(row[3] or 0),
                    'occupied_rooms': total_tenants,
                    'available_rooms': available_rooms,
                    'total_rooms': total_rooms,
                    'occupancy_rate': round(occupancy_rate, 2)
                }
                
                log_db_operation("SELECT", "tenants (statistics)", True, 1)
                logger.info(f"✅ 統計完成: 出租率 {occupancy_rate:.1f}%")
                
                return stats
        
        except Exception as e:
            log_db_operation("SELECT", "tenants (statistics)", False, error=str(e))
            logger.error(f"❌ 統計失敗: {str(e)}")
            return {
                'total_tenants': 0,
                'total_rent': 0.0,
                'avg_rent': 0.0,
                'total_deposit': 0.0,
                'occupied_rooms': 0,
                'available_rooms': len(self.all_rooms),
                'total_rooms': len(self.all_rooms),
                'occupancy_rate': 0.0
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
            return stats['occupancy_rate']
        
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
                
                cursor.execute("""
                    SELECT id, room_number, tenant_name, phone, lease_end,
                           (lease_end - CURRENT_DATE) as days_remaining
                    FROM tenants
                    WHERE is_active = true 
                    AND lease_end <= CURRENT_DATE + INTERVAL '%s days'
                    AND lease_end >= CURRENT_DATE
                    ORDER BY lease_end
                """ % days)
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                log_db_operation("SELECT", "tenants (expiring leases)", True, len(rows))
                logger.info(f"⏰ 找到 {len(rows)} 筆即將到期的租約")
                
                return [dict(zip(columns, row)) for row in rows]
        
        except Exception as e:
            log_db_operation("SELECT", "tenants (expiring leases)", False, error=str(e))
            logger.error(f"❌ 查詢失敗: {str(e)}")
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
    service = TenantService()
    
    print("=== 測試房客服務 ===\n")
    
    # 測試取得所有房客
    print("1. 所有房客 (DataFrame):")
    df = service.get_tenants()
    print(f"   共 {len(df)} 筆房客資料\n")
    
    # 測試取得所有房客 (List)
    print("2. 所有房客 (List):")
    tenants = service.get_all_tenants()
    for tenant in tenants[:3]:
        print(f"   {tenant['room_number']} - {tenant['tenant_name']}")
    print(f"   共 {len(tenants)} 筆\n")
    
    # 測試統計
    print("3. 租客統計:")
    stats = service.get_tenant_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # 測試即將到期
    print("\n4. 即將到期租約:")
    expiring = service.check_lease_expiry(45)
    for lease in expiring:
        print(f"   {lease['room_number']} - {lease['tenant_name']} (剩餘 {lease['days_remaining']} 天)")
    
    # 測試空房
    print("\n5. 可用房間:")
    vacant = service.get_vacant_rooms()
    print(f"   {', '.join(vacant) if vacant else '無空房'}")
