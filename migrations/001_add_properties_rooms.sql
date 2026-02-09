-- ==================================================
-- MicroRent Schema Migration v1.0
-- 新增物件 (Properties) 與房間 (Rooms) 層級
-- ==================================================

-- 1. 建立物件表 (Properties)
-- 用於管理多棟建築物或社區
CREATE TABLE IF NOT EXISTS properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL,  -- 將在後續設定 FK
    
    -- 基本資訊
    name TEXT NOT NULL,
    type TEXT DEFAULT 'apartment',  -- apartment/house/building/mixed
    
    -- 地址資訊
    address TEXT,
    city TEXT,
    district TEXT,
    lat DECIMAL(10,8),
    lng DECIMAL(11,8),
    
    -- 房東備註
    notes TEXT,
    
    -- 統計字段（查詢優化）
    total_rooms INT DEFAULT 0,
    occupied_rooms INT DEFAULT 0,
    vacant_rooms INT DEFAULT 0,
    
    -- 稽核
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 索引
    CONSTRAINT unique_owner_property_name UNIQUE(owner_id, name)
);

-- 建立索引
CREATE INDEX IF NOT EXISTS idx_properties_owner_id ON properties(owner_id);
CREATE INDEX IF NOT EXISTS idx_properties_city_district ON properties(city, district);

-- ==================================================

-- 2. 建立房間表 (Rooms)
-- 支援靈活的房號編號系統
CREATE TABLE IF NOT EXISTS rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL,  -- 方便 RLS 查詢
    
    -- 房號（彈性設計）
    room_number TEXT NOT NULL,  -- "101"、"A1-客房"、"套房-201"
    floor INT,
    
    -- 房間詳情
    area_sqm DECIMAL(10,2),  -- 坪數/平方米
    bedrooms INT DEFAULT 1,
    bathrooms INT DEFAULT 1,
    
    -- 設施 (JSONB 儲存靈活資料)
    amenities JSONB DEFAULT '{}',
    -- 例: {"air_conditioner": true, "balcony": false, "parking": "B3"}
    
    -- 租金配置
    base_rent DECIMAL(10,2) NOT NULL,
    deposit DECIMAL(10,2),
    utilities_included JSONB DEFAULT '{}',
    -- 例: {"water": true, "electricity": false, "gas": false}
    
    -- 房間狀態
    status TEXT DEFAULT 'vacant',  -- vacant/occupied/maintenance/reserved
    
    -- 照片
    photos JSONB DEFAULT '[]',
    
    -- 房東備註
    notes TEXT,
    
    -- 稽核
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_property_room_number UNIQUE(property_id, room_number)
);

-- 建立索引
CREATE INDEX IF NOT EXISTS idx_rooms_property_id ON rooms(property_id);
CREATE INDEX IF NOT EXISTS idx_rooms_owner_id ON rooms(owner_id);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);

-- ==================================================

-- 3. 修改 tenants 表（如果已存在）
-- 新增 room_id 欄位關聯房間
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'tenants' AND column_name = 'room_id'
    ) THEN
        ALTER TABLE tenants ADD COLUMN room_id UUID REFERENCES rooms(id) ON DELETE SET NULL;
        CREATE INDEX idx_tenants_room_id ON tenants(room_id);
    END IF;
END $$;

-- ==================================================

-- 4. RLS 安全策略
-- 啟用 Row Level Security
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;

-- 房東只能看自己的物件
DROP POLICY IF EXISTS "properties_owner_isolation" ON properties;
CREATE POLICY "properties_owner_isolation" ON properties
    FOR SELECT USING (
        owner_id = (SELECT id FROM auth.users WHERE auth.uid() = id)
    );

-- 房東只能看自己的房間
DROP POLICY IF EXISTS "rooms_owner_isolation" ON rooms;
CREATE POLICY "rooms_owner_isolation" ON rooms
    FOR SELECT USING (
        owner_id = (SELECT id FROM auth.users WHERE auth.uid() = id)
    );

-- ==================================================
-- Migration 完成
-- ==================================================
