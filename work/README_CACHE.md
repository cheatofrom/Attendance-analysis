# 跨月记录缓存系统使用说明

## 概述

本系统用于解决跨月请假、出差和加班记录的处理问题。当一条记录的开始日期和结束日期跨越两个月时，系统会将该记录保存到缓存表中，并在下个月自动处理该记录。

## 文件说明

- `create_cache_table.sql`: 创建缓存表的SQL脚本
- `cross_month_cache.py`: 跨月记录缓存处理核心模块
- `init_cache_table.py`: 初始化缓存表并执行缓存操作的脚本
- `freework_chage.py`: 请假记录处理模块（已集成缓存处理）
- `business_chage.py`: 出差记录处理模块（已集成缓存处理）
- `overwork_chage.py`: 加班记录处理模块（已集成缓存处理）

## 缓存表结构

```sql
CREATE TABLE cross_month_cache (
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
```

## 使用流程

### 初始化缓存表

首次使用时，需要初始化缓存表：

```bash
python init_cache_table.py
```

这将创建缓存表并执行首次缓存操作。

### 月度处理流程

1. 每月初，更新 `holidays.py` 中的 `MONTH` 变量为当前月份
2. 运行各个处理脚本：
   ```bash
   python freework_chage.py
   python business_chage.py
   python overwork_chage.py
   ```

3. 这些脚本会自动：
   - 处理上个月缓存的跨月记录（当前月份部分）
   - 处理当前月份的记录
   - 将新的跨月记录保存到缓存表中，供下个月处理

## 工作原理

### 跨月记录检测

系统通过比较记录的开始日期和结束日期的月份来检测跨月记录：

```python
start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')

if start_date.month != end_date.month:
    # 这是一条跨月记录
```

### 跨月记录处理逻辑

1. **当前月处理**：
   - 如果当前月是开始月，处理从开始日期到月底的部分
   - 如果当前月是结束月，处理从月初到结束日期的部分
   - 如果当前月既不是开始月也不是结束月，跳过处理

2. **缓存处理**：
   - 将跨月记录保存到缓存表中
   - 下个月处理时，从缓存表中读取相关记录并处理
   - 处理完成后，将记录标记为已处理

## 注意事项

1. 确保 `holidays.py` 中的 `MONTH` 变量始终设置为当前处理的月份
2. 缓存表中的记录会被标记为已处理，不会重复处理
3. 如需手动清理缓存表，可执行：
   ```sql
   DELETE FROM cross_month_cache WHERE processed = TRUE;
   ```