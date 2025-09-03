import os
import time
import asyncio
import psycopg2
import psycopg2.extras
import aiopg
import re
from datetime import datetime
from llm import query_llm_async  # 导入异步查询函数

# 数据库配置
DB_CONFIG = {
    "host": "192.168.1.66",
    "port": "7432",
    "database": "dingding",
    "user": "root",
    "password": "123456"
}

async def get_db_pool():
    """创建数据库连接池"""
    dsn = f"dbname={DB_CONFIG['database']} user={DB_CONFIG['user']} password={DB_CONFIG['password']} host={DB_CONFIG['host']} port={DB_CONFIG['port']}"
    return await aiopg.create_pool(dsn)

async def create_results_table():
    """创建结果表，如果不存在的话"""
    async with await get_db_pool() as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS llm_results (
                        id SERIAL PRIMARY KEY,
                        姓名 VARCHAR(100),
                        日期 DATE,
                        时间 VARCHAR(20),
                        时长 NUMERIC(10, 2),
                        加班说明 TEXT,
                        来源 VARCHAR(100),
                        创建时间 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
async def clear_results_table():
    """清空结果表并确保表结构正确"""
    async with await get_db_pool() as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 删除表并重新创建，确保表结构正确
                await cursor.execute("DROP TABLE IF EXISTS llm_results")
                await create_results_table()
                print("已清空结果表并更新表结构")

async def save_result_to_db(name, date, time_range, duration, reason, data_source):
    """保存处理结果到数据库"""
    async with await get_db_pool() as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO llm_results (姓名, 日期, 时间, 时长, 加班说明, 来源)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, date, time_range, duration, reason, data_source))
                return True

async def get_overwork_records():
    """异步获取加班记录"""
    async with await get_db_pool() as pool:
        async with pool.acquire() as conn:
            async with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 姓名, 
                           开始时间, 
                           结束时间, 
                           加班时长小时, 
                           加班说明, 
                           申请状态, 
                           数据来源
                    FROM overwork
                    WHERE 申请状态 IN ('已同意', '审批通过')
                    ORDER BY 姓名, 开始时间
                """)
                records = await cursor.fetchall()
                return records

async def process_record_async(record, i, total_records):
    """异步处理单条加班记录，但不立即保存到数据库，而是返回处理结果
    
    参数:
    record: 加班记录
    i: 记录索引
    total_records: 总记录数
    
    返回:
    dict: 处理结果，包含解析后的数据
    """
    # 构建提示词
    name = record['姓名']
    start_time = record['开始时间']
    end_time = record['结束时间']
    duration = record['加班时长小时']
    reason = record['加班说明']
    data_source = record['数据来源']
    
    # 解析日期和时间
    start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
    start_time_only = start_time.split()[1][:5]  # 提取时间部分 HH:MM
    
    end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
    end_time_only = end_time.split()[1][:5]  # 提取时间部分 HH:MM
    
    # 构建提示词
    prompt = f"{name} {start_date.strftime('%Y-%m-%d')} {start_time_only} {end_date.strftime('%Y-%m-%d')} {end_time_only} {duration} {reason} {data_source}"
    
    print(f"\n开始处理第 {i+1}/{total_records} 条记录")
    print(f"Prompt: {prompt}")
    print(f"数据来源: {data_source}")
    
    # 调用LLM处理
    response = await query_llm_async(prompt)
    
    if not response:
        print(f"第 {i+1} 条记录获取响应失败")
        return None
        
    print(f"第 {i+1} 条记录处理完成，回答：", response)
    
    # 解析LLM响应
    # 预期格式: "姓名,日期,时间范围,时长"
    # 例如: "丁国涛,2025-07-09,18:32-19:44,1.2"
    try:
        # 处理可能包含多行数据的响应
        lines = response.strip().split('\n')
        parsed_results = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 使用正则表达式解析每行响应
            pattern = r'([^,]+),([^,]+),([^,]+),([^,]+)'
            match = re.match(pattern, line)
            
            if not match:
                print(f"无法解析行: {line}")
                continue
                
            parsed_name = match.group(1).strip()
            parsed_date = match.group(2).strip()
            parsed_time = match.group(3).strip()
            parsed_duration = match.group(4).strip()
            
            # 清理时长字段，确保只包含数字和小数点
            cleaned_duration = re.sub(r'[^0-9.]', '', parsed_duration)
            
            try:
                duration_float = float(cleaned_duration)
                
                # 将解析结果添加到列表中，而不是立即保存到数据库
                parsed_results.append({
                    'name': parsed_name,
                    'date': parsed_date,
                    'time_range': parsed_time,
                    'duration': duration_float,
                    'reason': prompt,  # 使用完整的prompt作为加班说明
                    'data_source': data_source
                })
                
                print(f"已解析: {parsed_name}, {parsed_date}, {parsed_time}, {cleaned_duration}, 加班说明: {prompt}, {data_source}")
            except ValueError as e:
                print(f"时长转换错误: {e}, 原始值: '{parsed_duration}'")
        
        if parsed_results:
            return {
                'success': True,  # 添加成功标志
                'success_count': len(parsed_results),
                'source': data_source,
                'raw_response': response,
                'parsed_results': parsed_results
            }
        else:
            print(f"未能成功解析任何记录")
            return None
            
    except Exception as e:
        print(f"处理LLM响应时出错: {e}")
        return None

async def process_db_data_async(max_concurrent=10):
    """异步处理数据库中的加班记录并保存到结果表
    先处理所有记录，然后一次性批量保存到数据库
    
    参数:
    max_concurrent: 最大并发请求数
    
    返回:
    list: 处理结果列表
    """
    try:
        # 创建并清空结果表
        await create_results_table()
        await clear_results_table()
        
        # 获取加班记录
        records = await get_overwork_records()
        
        if not records:
            print("数据库中没有符合条件的加班记录")
            return []
            
        # 统计数据来源
        data_sources = {}
        for record in records:
            source = record['数据来源']
            if source in data_sources:
                data_sources[source] += 1
            else:
                data_sources[source] = 1
        
        total_records = len(records)
        print(f"读取 {total_records} 条加班记录")
        print(f"设置最大并发数: {max_concurrent}")
        
        # 创建任务列表
        tasks = []
        semaphore = asyncio.Semaphore(max_concurrent)  # 限制并发数
        
        async def bounded_process(record, i):
            async with semaphore:
                return await process_record_async(record, i, total_records)
        
        for i, record in enumerate(records):
            task = asyncio.create_task(bounded_process(record, i))
            tasks.append(task)
        
        # 等待所有任务完成
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # 过滤掉None结果
        valid_results = [r for r in results if r is not None]
        
        # 收集所有解析结果
        all_parsed_results = []
        for result in valid_results:
            if 'parsed_results' in result:
                all_parsed_results.extend(result['parsed_results'])
        
        # 统计成功处理的记录数
        total_success_count = len(all_parsed_results)
        
        # 一次性批量保存到数据库
        print(f"\n开始批量保存 {total_success_count} 条记录到数据库...")
        saved_count = 0
        
        # 使用事务批量保存数据
        async with await get_db_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 开始事务
                    await cursor.execute("BEGIN")
                    
                    try:
                        # 批量插入数据
                        for parsed_result in all_parsed_results:
                            await cursor.execute("""
                                INSERT INTO llm_results (姓名, 日期, 时间, 时长, 加班说明, 来源)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                parsed_result['name'],
                                parsed_result['date'],
                                parsed_result['time_range'],
                                parsed_result['duration'],
                                parsed_result['reason'],
                                parsed_result['data_source']
                            ))
                            saved_count += 1
                        
                        # 提交事务
                        await cursor.execute("COMMIT")
                        print(f"✅ 成功批量保存 {saved_count} 条记录到数据库")
                    except Exception as e:
                        # 回滚事务
                        await cursor.execute("ROLLBACK")
                        print(f"❌ 批量保存失败: {e}")
        
        processing_time = end_time - start_time
        print(f"\n处理完成，共解析 {total_success_count} 条记录，保存 {saved_count}/{total_records} 条回答到数据库")
        print(f"处理耗时: {processing_time:.2f} 秒，平均每条记录 {processing_time/total_records:.4f} 秒")
        
        # 打印数据来源统计
        print("\n数据来源统计:")
        for source, count in data_sources.items():
            print(f"  - {source}: {count} 条记录")
            
        # 打印结果表中的数据统计
        print("\n结果表数据统计:")
        async with await get_db_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT 来源, COUNT(*) 
                        FROM llm_results 
                        GROUP BY 来源
                    """)
                    source_stats = await cursor.fetchall()
                    for source, count in source_stats:
                        print(f"  - {source}: {count} 条记录")
        
        return valid_results
    
    except Exception as e:
        print(f"处理出错: {e}")
        return []

async def query_results():
    """查询结果表中的数据"""
    try:
        async with await get_db_pool() as pool:
            async with pool.acquire() as conn:
                async with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    await cursor.execute("""
                        SELECT 姓名, 日期, 时间, 时长, 加班说明, 来源, 创建时间
                        FROM llm_results
                        ORDER BY 创建时间 DESC
                    """)
                    results = await cursor.fetchall()
                    
                    if not results:
                        print("结果表中没有数据")
                        return
                    
                    print(f"\n查询到 {len(results)} 条结果:")
                    print("-" * 120)
                    print(f"{'姓名':<10} {'日期':<12} {'时间':<15} {'时长':<8} {'加班说明':<30} {'来源':<10}")
                    print("-" * 120)
                    
                    for row in results:
                        # 截断过长的加班说明
                        reason = row['加班说明']
                        if reason and len(reason) > 27:
                            reason = reason[:27] + '...'
                        print(f"{row['姓名']:<10} {row['日期']:<12} {row['时间']:<15} {row['时长']:<8} {reason:<30} {row['来源']:<10}")
                    
                    print("-" * 120)
    except Exception as e:
        print(f"查询结果出错: {e}")

async def main_async():
    max_concurrent = 10  # 可以根据需要调整并发数
    await process_db_data_async(max_concurrent)
    
    # 查询处理结果
    await query_results()

def main():
    """同步入口函数，调用异步主函数"""
    asyncio.run(main_async())

if __name__ == "__main__":
    main()