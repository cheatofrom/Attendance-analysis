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
    # 记录处理开始时间
    record_start_time = time.time()
    
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
    
    # 调用LLM处理，增加异常处理
    try:
        # 尝试获取LLM响应，增加超时和错误处理
        response = await query_llm_async(prompt)
        
        # 检查响应是否为空
        if not response or response.strip() == "":
            logger.log_error(f"处理记录 {i+1}/{total_records} 获取响应为空")
            return {
                'success': False,
                'index': i,
                'total': total_records,
                'error': '获取响应失败或响应为空',
                'prompt': prompt,
                'raw_response': None,
                'processing_time': time.time() - record_start_time,
                'source': data_source
            }
    except asyncio.CancelledError:
        # 处理取消异常
        elapsed = time.time() - record_start_time
        logger.log_error(f"处理记录 {i+1}/{total_records} 被取消，已耗时: {elapsed:.2f}秒")
        return {
            'success': False,
            'index': i,
            'total': total_records,
            'error': '任务被取消',
            'prompt': prompt,
            'raw_response': None,
            'processing_time': elapsed,
            'source': data_source
        }
    except Exception as e:
        # 处理其他异常
        elapsed = time.time() - record_start_time
        import traceback
        error_details = traceback.format_exc()
        logger.log_error(f"处理记录 {i+1}/{total_records} 异常: {e}，已耗时: {elapsed:.2f}秒")
        logger.log_error(f"错误详情: {error_details}")
        return {
            'success': False,
            'index': i,
            'total': total_records,
            'error': f'处理异常: {str(e)}',
            'prompt': prompt,
            'raw_response': None,
            'processing_time': time.time() - record_start_time,
            'source': data_source
        }
    
    # 不直接打印，而是将原始记录和模型返回结果作为结果的一部分返回
    # 解析LLM响应
    # 预期格式: "姓名,日期,时间范围,时长"
    # 例如: "丁国涛,2025-07-09,18:32-19:44,1.2"
    try:
        # 处理可能包含多行数据的响应
        lines = response.strip().split('\n')
        parsed_results = []
        parse_errors = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 使用正则表达式解析每行响应
            pattern = r'([^,]+),([^,]+),([^,]+),([^,]+)'
            match = re.match(pattern, line)
            
            if not match:
                parse_errors.append(f"无法解析: {line}")
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
            except ValueError as e:
                parse_errors.append(f"时长错误: '{parsed_duration}'")
        
        # 计算处理时间
        record_end_time = time.time()
        record_processing_time = record_end_time - record_start_time
        
        if parsed_results:
            success_count = len(parsed_results)
            return {
                'success': True,  # 添加成功标志
                'success_count': success_count,
                'source': data_source,
                'raw_response': response,
                'parsed_results': parsed_results,
                'processing_time': record_processing_time,
                'index': i,
                'total': total_records,
                'prompt': prompt,
                'parse_errors': parse_errors
            }
        else:
            return {
                'success': False,
                'source': data_source,
                'raw_response': response,
                'processing_time': record_processing_time,
                'index': i,
                'total': total_records,
                'prompt': prompt,
                'parse_errors': parse_errors
            }
            
    except Exception as e:
        error_message = f"处理LLM响应时出错: {e}"
        return {
            'success': False,
            'index': i,
            'total': total_records,
            'error': error_message,
            'prompt': prompt,
            'raw_response': response,
            'processing_time': time.time() - record_start_time
        }

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
        
        # 输出开始分析的日志
        print("\n=== 开始分析加班记录 ===\n")
        
        # 记录大模型开始处理的日志
        print("🤖 大模型开始处理加班数据...")
        
        # 创建任务列表
        tasks = []
        semaphore = asyncio.Semaphore(max_concurrent)  # 限制并发数
        
        async def bounded_process(record, i):
            async with semaphore:
                return await process_record_async(record, i, total_records)
        
        for i, record in enumerate(records):
            task = asyncio.create_task(bounded_process(record, i))
            tasks.append(task)
        
        # 创建一个字典来存储已完成的任务结果，按索引排序
        completed_results = {}
        next_index_to_print = 0
        
        # 等待任务完成并按顺序输出日志
        start_time = time.time()
        
        # 创建一个函数来处理完成的任务
        def process_completed_result(result):
            nonlocal next_index_to_print
            if result is None:
                return
                
            index = result.get('index', 0)
            completed_results[index] = result
            
            # 检查是否可以按顺序输出日志
            while next_index_to_print in completed_results:
                result = completed_results[next_index_to_print]
                i = result.get('index', 0)
                total = result.get('total', total_records)
                
                # 输出日志
                if result.get('success', False):
                    # 输出原始记录和模型返回结果
                    if 'prompt' in result and 'raw_response' in result:
                        print(f"\n📤 原始记录 [{i+1}/{total}]: {result['prompt']}")
                        print(f"📥 模型返回 [{i+1}/{total}]:\n {result['raw_response']}")
                    
                    # 输出解析结果
                    if 'parsed_results' in result:
                        for parsed in result['parsed_results']:
                            print(f"✅ 解析结果 [{i+1}/{total}]: {parsed['name']}, {parsed['date']}, {parsed['time_range']}, {parsed['duration']}小时")
                            
                        # 输出解析错误
                        if 'parse_errors' in result and result['parse_errors']:
                            for error in result['parse_errors']:
                                print(f"⚠️ 解析警告 [{i+1}/{total}]: {error}")
                    
                    # 输出处理完成信息
                    if 'processing_time' in result:
                        print(f"⏱️ 处理完成 [{i+1}/{total}]: {result['processing_time']:.2f}秒")
                        print("------------------------------------------------------------------\n\n")
                else:
                    # 输出错误信息
                    error_msg = result.get('error', '未知错误')
                    print(f"\n📤 原始记录 [{i+1}/{total}]: {result.get('prompt', '无提示词')}")
                    raw_response = result.get('raw_response', None)
                    if raw_response:
                        print(f"📥 模型返回 [{i+1}/{total}]: {raw_response}")
                    else:
                        print(f"📥 模型返回 [{i+1}/{total}]: 无响应")
                    
                    # 输出解析错误
                    if 'parse_errors' in result and result['parse_errors']:
                        for error in result['parse_errors']:
                            print(f"⚠️ 解析警告 [{i+1}/{total}]: {error}")
                    
                    print(f"❌ 处理失败 [{i+1}/{total}]: {error_msg}")
                    if 'processing_time' in result:
                        print(f"⏱️ 处理完成 [{i+1}/{total}]: {result['processing_time']:.2f}秒")
                
                # 移除已处理的结果并更新下一个要打印的索引
                del completed_results[next_index_to_print]
                next_index_to_print += 1
        
        # 为每个任务添加回调函数，使用更健壮的错误处理
        def safe_callback(task):
            try:
                if not task.cancelled():
                    result = task.result()
                    if result:
                        process_completed_result(result)
                else:
                    print(f"警告: 任务 {task} 被取消，跳过结果处理")
            except asyncio.CancelledError:
                print(f"警告: 任务被取消，无法获取结果")
            except Exception as e:
                print(f"回调处理异常: {e}")
        
        for task in tasks:
            task.add_done_callback(lambda t: safe_callback(t))
        
        # 等待所有任务完成，使用更健壮的错误处理
        try:
            # 使用gather的return_exceptions=True参数，避免一个任务失败导致所有任务失败
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            print("警告: 部分任务被取消，但会继续处理已完成的任务")
        except Exception as e:
            print(f"等待任务完成时出错: {e}，但会继续处理已完成的任务")
        end_time = time.time()
        
        # 收集所有解析结果
        all_parsed_results = []
        success_by_source = {}
        
        # 获取所有任务的结果，安全地处理可能的异常
        results = []
        cancelled_count = 0
        error_count = 0
        
        for task in tasks:
            try:
                if task.done():
                    if task.cancelled():
                        cancelled_count += 1
                        continue
                    
                    result = task.result()
                    if result is not None:
                        results.append(result)
                else:
                    print(f"警告: 任务未完成，跳过结果处理")
            except asyncio.CancelledError:
                cancelled_count += 1
                print(f"警告: 任务被取消，跳过结果处理")
            except Exception as e:
                error_count += 1
                print(f"获取任务结果异常: {e}")
        
        if cancelled_count > 0 or error_count > 0:
            print(f"⚠️ 统计: {cancelled_count} 个任务被取消, {error_count} 个任务出错, {len(results)} 个任务成功")
        
        for result in results:
            if result is None:
                continue
                
            if 'parsed_results' in result:
                source = result.get('source', '未知来源')
                count = len(result['parsed_results'])
                
                if source in success_by_source:
                    success_by_source[source] += count
                else:
                    success_by_source[source] = count
                    
                all_parsed_results.extend(result['parsed_results'])
        
        # 统计成功处理的记录数
        total_success_count = len(all_parsed_results)
        
        # 打印按来源统计的成功解析数
        print("\n📊 按数据来源统计解析成功数:")
        for source, count in success_by_source.items():
            print(f"  - {source}: {count} 条记录")
        print(f"  总计: {total_success_count} 条记录解析成功")
        
        # 输出分析结束的日志
        print("\n=== 加班记录分析完成 ===\n")
        
        # 批量保存到数据库，使用分批事务提交
        if total_success_count > 0:
            print(f"📊 总计解析: {total_success_count}/{total_records} 条记录 ({total_success_count/total_records*100:.1f}%)")
            saved_count = 0
            failed_batches = 0
            
            # 使用事务批量保存数据，每50条记录提交一次，避免单个大事务
            batch_size = 50
            batches = [all_parsed_results[i:i+batch_size] for i in range(0, len(all_parsed_results), batch_size)]
            
            try:
                async with await get_db_pool() as pool:
                    async with pool.acquire() as conn:
                        for batch_index, batch in enumerate(batches):
                            if not batch:  # 跳过空批次
                                continue
                                
                            try:
                                async with conn.cursor() as cursor:
                                    # 开始事务
                                    await cursor.execute("BEGIN")
                                    
                                    try:
                                        # 批量插入数据
                                        for parsed_result in batch:
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
                                        print(f"✅ 保存批次 {batch_index+1}/{len(batches)}: {len(batch)}条记录")
                                    except Exception as e:
                                        # 回滚事务
                                        await cursor.execute("ROLLBACK")
                                        failed_batches += 1
                                        print(f"❌ 保存批次 {batch_index+1}/{len(batches)} 失败: {e}")
                            except Exception as e:
                                failed_batches += 1
                                print(f"❌ 批次 {batch_index+1}/{len(batches)} 事务处理失败: {e}")
                        
                        print(f"✅ 总共保存记录: {saved_count}条, 失败批次: {failed_batches}个")
            except Exception as e:
                print(f"❌ 数据库连接失败: {e}")
        else:
            print("⚠️ 没有成功解析的记录，跳过保存步骤")
        
        processing_time = end_time - start_time
        print(f"\n⏱️ 总耗时: {processing_time:.2f}秒, 平均: {processing_time/total_records:.4f}秒/条, 速度: {total_records/processing_time:.2f}条/秒")
        
        # 打印数据来源和处理效率统计
        if total_records > 0:
            parse_success_rate = total_success_count / total_records * 100
            save_success_rate = saved_count / total_records * 100 if total_records > 0 else 0
            print(f"\n📊 解析率: {parse_success_rate:.1f}%, 保存率: {save_success_rate:.1f}%")
        
        # 查询结果表中的数据统计
        try:
            async with await get_db_pool() as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT COUNT(*) 
                            FROM llm_results
                        """)
                        total_count = await cursor.fetchone()
                        print(f"✅ 数据库总记录: {total_count[0]}条")
        except Exception as e:
            print(f"❌ 查询数据库记录失败: {e}")
        
        return all_parsed_results
    
    except asyncio.CancelledError:
        print(f"处理被取消: 可能是用户中断了操作或系统超时")
        # 尝试保存已收集的结果
        if 'all_parsed_results' in locals() and all_parsed_results:
            print(f"尝试保存已收集的 {len(all_parsed_results)} 条结果...")
            # 这里可以调用一个单独的函数来保存结果，避免代码重复
            # 为简化，这里省略实现
        # 返回已收集的结果，而不是空列表
        return all_parsed_results if 'all_parsed_results' in locals() else []
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"处理出错: {e}")
        print(f"错误详情: {error_details}")
        # 返回已收集的结果，而不是空列表
        return all_parsed_results if 'all_parsed_results' in locals() else []

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
                    
                    print(f"\n查询到 {len(results)} 条结果")
                    # 注释掉详细表格输出，避免在日志中显示大量表格数据
                    # print("-" * 120)
                    # print(f"{'姓名':<10} {'日期':<12} {'时间':<15} {'时长':<8} {'加班说明':<30} {'来源':<10}")
                    # print("-" * 120)
                    # 
                    # for row in results:
                    #     # 截断过长的加班说明
                    #     reason = row['加班说明']
                    #     if reason and len(reason) > 27:
                    #         reason = reason[:27] + '...'
                    #     print(f"{row['姓名']:<10} {row['日期']:<12} {row['时间']:<15} {row['时长']:<8} {reason:<30} {row['来源']:<10}")
                    # 
                    # print("-" * 120)
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