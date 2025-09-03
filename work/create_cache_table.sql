-- 创建跨月记录缓存表
CREATE TABLE IF NOT EXISTS cross_month_cache (
    id SERIAL PRIMARY KEY,
    record_type TEXT NOT NULL, -- 'freework', 'business', 'overwork'
    name TEXT NOT NULL,        -- 员工姓名
    start_time TEXT NOT NULL,   -- 开始时间
    end_time TEXT NOT NULL,     -- 结束时间
    duration TEXT,             -- 时长
    reason TEXT,               -- 请假说明/出差事由/加班说明
    status TEXT,               -- 申请状态
    type TEXT,                 -- 请假类型（仅请假记录有）
    colleagues TEXT,           -- 同行人（仅出差记录有）
    source TEXT NOT NULL,      -- 数据来源
    processed BOOLEAN DEFAULT FALSE, -- 是否已处理
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_cross_month_cache_name ON cross_month_cache(name);
CREATE INDEX IF NOT EXISTS idx_cross_month_cache_record_type ON cross_month_cache(record_type);
CREATE INDEX IF NOT EXISTS idx_cross_month_cache_processed ON cross_month_cache(processed);