import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2 import sql
import requests
import json
import argparse
import asyncio
import aiohttp
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from config import DB_CONFIG  # 导入数据库配置

# AI接口配置
AI_API_URL = "http://192.168.1.66/v1/chat-messages"
AI_API_KEY = "Bearer app-G55syWxYqxnoOH2jOsskKMA6"

# 批处理和并发配置
BATCH_SIZE = 20  # 每批处理的记录数，可根据需要调整
MAX_CONCURRENCY = 5  # 最大并发数，可根据服务器性能和API限制调整

def extract_names_from_json_string(json_string):
    """
    从JSON字符串中提取names数组
    
    参数:
    json_string -- JSON字符串
    
    返回:
    提取的伙伴信息，以逗号分隔的字符串形式
    """
    try:
        # 尝试直接解析JSON字符串
        data = json.loads(json_string)
        
        # 检查是否包含names数组
        if 'names' in data and isinstance(data['names'], list):
            return ','.join(data['names'])
        return ""
    except Exception as e:
        print(f"从JSON字符串提取names数组失败: {e}")
        return ""

def parse_ai_response(response_data):
    """
    解析AI接口返回的响应，提取伙伴信息
    
    参数:
    response_data -- AI接口返回的响应数据
    
    返回:
    提取的伙伴信息，以逗号分隔的字符串形式
    """
    try:
        # 输出响应数据的键，帮助调试
        print(f"AI响应数据键: {list(response_data.keys())}")
        
        # 检查响应格式，处理不同的返回结构
        answer_text = None
        
        # 情况1: 直接包含answer字段
        if 'answer' in response_data:
            answer_text = response_data['answer']
            print("从'answer'字段获取响应文本")
        # 情况2: 包含message字段，message中包含answer字段
        elif 'message' in response_data and isinstance(response_data['message'], dict) and 'answer' in response_data['message']:
            answer_text = response_data['message']['answer']
            print("从'message.answer'字段获取响应文本")
        # 情况3: 用户提供的示例格式
        elif 'event' in response_data and response_data['event'] == 'message' and 'answer' in response_data:
            answer_text = response_data['answer']
            print("从事件消息中的'answer'字段获取响应文本")
            
        # 如果没有找到answer文本，返回空字符串
        if not answer_text:
            print("未找到answer文本")
            return ""
            
        # 输出获取到的answer文本，帮助调试
        print(f"获取到的answer文本: {answer_text[:100]}..." if len(answer_text) > 100 else f"获取到的answer文本: {answer_text}")
            
        # 查找JSON部分（可能包含在<think></think>标签之后）
        if '<think>' in answer_text and '</think>' in answer_text:
            json_part = answer_text.split('</think>')[-1].strip()
            print("从<think></think>标签后提取JSON部分")
        else:
            json_part = answer_text
            print("使用完整answer文本作为JSON部分")
        
        # 输出提取的JSON部分，帮助调试
        print(f"提取的JSON部分: {json_part[:100]}..." if len(json_part) > 100 else f"提取的JSON部分: {json_part}")
        
        # 尝试解析JSON字符串
        try:
            answer_json = json.loads(json_part)
            print(f"成功解析JSON，键: {list(answer_json.keys())}")
            
            # 提取names数组并转换为逗号分隔的字符串
            if 'names' in answer_json and isinstance(answer_json['names'], list):
                result = ','.join(answer_json['names'])
                print(f"提取到names数组: {result}")
                return result
            else:
                print(f"JSON中没有names数组或格式不正确")
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}，尝试在文本中查找JSON部分")
            # 如果JSON解析失败，尝试在文本中查找JSON部分
            import re
            
            # 尝试匹配用户提供的示例格式中的JSON部分
            # 例如: {"names":["高群","王松","李飞",...]}"}
            json_match = re.search(r'\{\s*"names"\s*:\s*\[.*?\]\s*\}', json_part)
            if json_match:
                try:
                    matched_json = json_match.group(0)
                    print(f"正则表达式匹配到names JSON: {matched_json[:100]}..." if len(matched_json) > 100 else f"正则表达式匹配到names JSON: {matched_json}")
                    return extract_names_from_json_string(matched_json)
                except Exception as e:
                    print(f"解析匹配的names JSON失败: {e}")
            
            # 尝试匹配任何JSON对象
            json_match = re.search(r'\{.*?\}', json_part, re.DOTALL)
            if json_match:
                try:
                    matched_json = json_match.group(0)
                    print(f"正则表达式匹配到JSON对象: {matched_json[:100]}..." if len(matched_json) > 100 else f"正则表达式匹配到JSON对象: {matched_json}")
                    answer_json = json.loads(matched_json)
                    print(f"成功解析匹配的JSON，键: {list(answer_json.keys())}")
                    if 'names' in answer_json and isinstance(answer_json['names'], list):
                        result = ','.join(answer_json['names'])
                        print(f"从匹配的JSON中提取到names数组: {result}")
                        return result
                    else:
                        print(f"匹配的JSON中没有names数组或格式不正确")
                except Exception as e:
                    print(f"解析匹配的JSON失败: {e}")
        
        print("未能提取到伙伴信息，返回空字符串")
        return ""
    except Exception as e:
        print(f"解析AI返回的JSON出错: {e}")
        return ""

"""使用说明：

本脚本用于处理飞书和钉钉的加班数据，并通过AI接口提取加班内容中的伙伴信息。

命令行参数：
  --batch-size N    设置AI处理的批处理大小，默认为20条记录一批
  --max-concurrency N  设置异步处理的最大并发数，默认为5
  --async           使用异步并发模式处理AI请求，可显著提高处理速度
  --skip-ai         跳过AI处理步骤，不提取伙伴信息
  --test            运行测试函数，测试AI响应解析功能

使用示例：
  # 使用默认批处理大小(20)处理数据
  python overwork_combine.py
  
  # 使用异步并发模式处理数据
  python overwork_combine.py --async
  
  # 使用自定义批处理大小(50)和并发数(10)处理数据
  python overwork_combine.py --async --batch-size 50 --max-concurrency 10
  
  # 跳过AI处理步骤
  python overwork_combine.py --skip-ai
  
  # 测试AI响应解析功能
  python overwork_combine.py --test

注意：
  - 异步并发模式(--async)通常比普通批处理模式快2-5倍
  - 最大并发数(--max-concurrency)建议设置为5-10，过高可能导致API限流
  - 批处理大小越大，处理速度越快，但可能会增加内存使用
  - 系统会为每个AI请求生成唯一的用户ID，以避免API限流并提高处理速度
  - 如果只需要更新数据结构而不需要AI处理，可以使用--skip-ai参数
  - AI响应格式已更新，现在支持从JSON格式中提取伙伴名单，格式为{"names":["姓名1","姓名2",...]}  
"""

def get_partners_from_ai(overwork_content, user_id=None):
    """
    调用AI接口，从加班内容中提取伙伴信息（同步版本）
    
    参数:
    overwork_content -- 加班内容
    user_id -- 用户ID，如果为None则使用默认ID加随机数
    """
    # 请求头
    headers = {
        "Authorization": AI_API_KEY,
        "Content-Type": "application/json"
    }
    
    # 如果没有提供用户ID，则生成一个
    if user_id is None:
        # 使用时间戳和随机数生成唯一用户ID
        import random
        import time
        user_id = f"overwork-system-{int(time.time())}-{random.randint(1000, 9999)}"
    
    # 请求体内容
    payload = {
        "inputs": {},
        "query": overwork_content,
        "user": user_id
    }
    
    try:
        # 发起POST请求
        response = requests.post(AI_API_URL, headers=headers, data=json.dumps(payload))
        
        # 检查响应状态码
        if response.status_code == 200:
            # 解析返回的JSON数据
            result = response.json()
            # 使用辅助函数解析AI返回的响应
            return parse_ai_response(result)
        else:
            print(f"AI接口请求失败，状态码：{response.status_code}，用户ID：{user_id}")
            return ""
            
    except Exception as e:
        print(f"调用AI接口出错: {e}，用户ID：{user_id}")
        return ""

async def get_partners_from_ai_async(session, overwork_content, user_id=None):
    """
    调用AI接口，从加班内容中提取伙伴信息（异步版本）
    
    参数:
    session -- aiohttp会话
    overwork_content -- 加班内容
    user_id -- 用户ID，如果为None则使用默认ID加随机数
    """
    # 请求头
    headers = {
        "Authorization": AI_API_KEY,
        "Content-Type": "application/json"
    }
    
    # 如果没有提供用户ID，则生成一个
    if user_id is None:
        # 使用时间戳和随机数生成唯一用户ID
        import random
        import time
        user_id = f"overwork-system-{int(time.time())}-{random.randint(1000, 9999)}"
    
    # 请求体内容
    payload = {
        "inputs": {},
        "query": overwork_content,
        "user": user_id
    }
    
    try:
        # 发起异步POST请求
        async with session.post(AI_API_URL, headers=headers, json=payload) as response:
            # 检查响应状态码
            if response.status == 200:
                # 解析返回的JSON数据
                result = await response.json()
                # 使用辅助函数解析AI返回的响应
                return parse_ai_response(result)
            else:
                print(f"AI接口请求失败，状态码：{response.status}，用户ID：{user_id}")
                return ""
                
    except Exception as e:
        print(f"异步调用AI接口出错: {e}，用户ID：{user_id}")
        return ""

def batch_process_partners_from_ai(content_list, batch_size=10):
    """
    批量处理加班内容，提取伙伴信息（同步版本）
    
    参数:
    content_list -- 加班内容列表
    batch_size -- 批处理大小，默认为10条记录一批
    
    返回:
    伙伴信息列表
    """
    results = []
    total = len(content_list)
    
    print(f"开始批量处理 {total} 条加班记录...")
    
    # 导入随机模块
    import random
    import time
    
    # 按批次处理
    for i in range(0, total, batch_size):
        batch = content_list[i:min(i+batch_size, total)]
        print(f"处理批次 {i//batch_size + 1}/{(total-1)//batch_size + 1}，共 {len(batch)} 条记录")
        
        batch_results = []
        for idx, content in enumerate(batch):
            if pd.notna(content) and content.strip() != '':
                # 为每个请求生成唯一的用户ID
                user_id = f"overwork-system-batch{i//batch_size + 1}-{idx}-{int(time.time())}-{random.randint(1000, 9999)}"
                partner = get_partners_from_ai(content, user_id)
                batch_results.append(partner)
            else:
                batch_results.append("")
        
        results.extend(batch_results)
    
    print(f"批量处理完成，共处理 {total} 条记录")
    return results

async def batch_process_partners_from_ai_async(content_list, batch_size=10, max_concurrency=5):
    """
    批量处理加班内容，提取伙伴信息（异步并发版本）
    
    参数:
    content_list -- 加班内容列表
    batch_size -- 批处理大小，默认为10条记录一批
    max_concurrency -- 最大并发数，默认为5
    
    返回:
    伙伴信息列表
    """
    results = []
    total = len(content_list)
    
    print(f"开始异步并发处理 {total} 条加班记录...")
    print(f"最大并发数: {max_concurrency}")
    
    # 导入随机模块
    import random
    import time
    
    # 创建异步HTTP会话
    async with aiohttp.ClientSession() as session:
        # 按批次处理
        for i in range(0, total, batch_size):
            batch = content_list[i:min(i+batch_size, total)]
            print(f"处理批次 {i//batch_size + 1}/{(total-1)//batch_size + 1}，共 {len(batch)} 条记录")
            
            # 创建任务列表
            tasks = []
            for idx, content in enumerate(batch):
                if pd.notna(content) and content.strip() != '':
                    # 为每个请求生成唯一的用户ID
                    user_id = f"overwork-system-async-batch{i//batch_size + 1}-{idx}-{int(time.time())}-{random.randint(1000, 9999)}"
                    # 创建异步任务
                    task = asyncio.create_task(get_partners_from_ai_async(session, content, user_id))
                    tasks.append(task)
                else:
                    # 对于空内容，创建一个已完成的任务，返回空字符串
                    task = asyncio.create_task(asyncio.sleep(0, result=""))
                    tasks.append(task)
            
            # 限制并发数量，分组执行任务
            batch_results = []
            for j in range(0, len(tasks), max_concurrency):
                # 获取当前组的任务
                group_tasks = tasks[j:min(j+max_concurrency, len(tasks))]
                # 并发执行当前组的任务
                group_results = await asyncio.gather(*group_tasks)
                batch_results.extend(group_results)
            
            results.extend(batch_results)
    
    print(f"异步并发处理完成，共处理 {total} 条记录")
    return results

def async_batch_process_wrapper(content_list, batch_size=10, max_concurrency=5):
    """
    异步批处理的包装函数，用于在同步代码中调用异步函数
    """
    return asyncio.run(batch_process_partners_from_ai_async(content_list, batch_size, max_concurrency))

def process_feishu_data(use_async=False):
    # 处理飞书数据
    file_path = '../data/original/overwork01.xlsx'
    df = pd.read_excel(file_path, skiprows=1)
    
    columns = ['发起人姓名', '开始时间', '结束时间', '时长', '详细说明（加班内容）','申请状态']
    result_df = df[columns].copy()
    
    result_df.columns = ['姓名', '开始时间', '结束时间', '加班时长(小时)', '加班说明','申请状态']
    result_df = result_df[result_df['申请状态'] == '已同意']
    
    # 添加伙伴字段
    result_df['伙伴'] = ''
    
    # 批量处理加班内容，提取伙伴信息
    print("开始处理飞书加班数据...")
    if not result_df.empty:
        # 提取所有加班说明
        overwork_contents = result_df['加班说明'].tolist()
        
        # 根据模式选择处理方法
        if use_async:
            print("使用异步并发模式处理飞书数据...")
            partner_results = async_batch_process_wrapper(overwork_contents, BATCH_SIZE, MAX_CONCURRENCY)
        else:
            print("使用同步模式处理飞书数据...")
            partner_results = batch_process_partners_from_ai(overwork_contents, BATCH_SIZE)
        
        # 更新伙伴字段
        result_df['伙伴'] = partner_results
    
    # 转换日期格式
    def convert_feishu_date(date_str):
        if pd.isna(date_str):
            return date_str
        # 处理"2025年05月15日 xx:xx"格式
        parts = date_str.split()
        date_part = parts[0]  # 获取日期部分
        
        # 将中文日期格式转换为标准格式
        date_part = date_part.replace('年', '-').replace('月', '-').replace('日', '')
        return date_part if len(parts) == 1 else f"{date_part} {parts[1]}"

    result_df['开始时间'] = result_df['开始时间'].apply(convert_feishu_date)
    result_df['结束时间'] = result_df['结束时间'].apply(convert_feishu_date)
    
    # 添加数据来源标识
    result_df['数据来源'] = '飞书'
    return result_df

def process_dingding_data(use_async=False):
    # 处理钉钉数据
    file_path = '../data/original/overwork02.xlsx'
    df = pd.read_excel(file_path)
    
    columns = ['创建人', '开始时间', '结束时间', '时长（小时）', '详细说明（加班内容）','审批结果']
    result_df = df[columns].copy()
    
    result_df.columns = ['姓名', '开始时间', '结束时间', '加班时长(小时)', '加班说明','申请状态']
    result_df = result_df[result_df['申请状态'] == '审批通过']
    
    # 添加伙伴字段
    result_df['伙伴'] = ''
    
    # 批量处理加班内容，提取伙伴信息
    print("开始处理钉钉加班数据...")
    if not result_df.empty:
        # 提取所有加班说明
        overwork_contents = result_df['加班说明'].tolist()
        
        # 根据模式选择处理方法
        if use_async:
            print("使用异步并发模式处理钉钉数据...")
            partner_results = async_batch_process_wrapper(overwork_contents, BATCH_SIZE, MAX_CONCURRENCY)
        else:
            print("使用同步模式处理钉钉数据...")
            partner_results = batch_process_partners_from_ai(overwork_contents, BATCH_SIZE)
        
        # 更新伙伴字段
        result_df['伙伴'] = partner_results
    
    # 添加数据来源标识
    result_df['数据来源'] = '钉钉'
    return result_df

def save_to_database(df):
    """
    将数据保存到PostgreSQL数据库
    """
    # 连接PostgreSQL数据库
    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )
    cur = conn.cursor()
    
    try:
        # 获取列名并清理
        field_names = df.columns.tolist()
        cleaned_field_names = []
        for name in field_names:
            cleaned_name = str(name).strip()
            cleaned_name = cleaned_name.replace(' ', '_')
            cleaned_name = cleaned_name.replace('(', '')
            cleaned_name = cleaned_name.replace(')', '')
            cleaned_name = cleaned_name.replace('/', '_')
            cleaned_name = cleaned_name.replace('（', '')
            cleaned_name = cleaned_name.replace('）', '')
            cleaned_field_names.append(cleaned_name)
        
        # 更新DataFrame的列名
        df.columns = cleaned_field_names
        
        # 先删除已存在的表
        cur.execute("DROP TABLE IF EXISTS overwork")
        conn.commit()
        
        # 创建新表
        create_table_query = sql.SQL("CREATE TABLE overwork ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col))
                for col in cleaned_field_names
            )
        )
        cur.execute(create_table_query)
        
        # 构建INSERT语句
        insert_query = sql.SQL("INSERT INTO overwork ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cleaned_field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(cleaned_field_names))
        )
        
        # 插入数据
        for _, row in df.iterrows():
            values = [str(val) if pd.notna(val) else None for val in row]
            cur.execute(insert_query, values)
        
        conn.commit()
        print("数据已成功导入PostgreSQL数据库的overwork表")
        
    except Exception as e:
        print(f"数据库操作出错: {e}")
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()

def parse_arguments():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description='处理加班数据并保存到数据库')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                        help=f'AI处理的批处理大小，默认为{BATCH_SIZE}')
    parser.add_argument('--max-concurrency', type=int, default=MAX_CONCURRENCY,
                        help=f'异步处理的最大并发数，默认为{MAX_CONCURRENCY}')
    parser.add_argument('--skip-ai', action='store_true',
                        help='跳过AI处理步骤，直接使用现有数据')
    parser.add_argument('--async', action='store_true', dest='use_async',
                        help='使用异步并发模式处理AI请求')
    parser.add_argument('--test', action='store_true',
                        help='运行测试函数，测试AI响应解析功能')
    
    return parser.parse_args()

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 更新全局批处理大小
    global BATCH_SIZE
    BATCH_SIZE = args.batch_size
    
    # 更新全局最大并发数
    global MAX_CONCURRENCY
    MAX_CONCURRENCY = args.max_concurrency
    
    # 导入月份配置
    from holidays import MONTH
    
    print("开始处理加班数据...")
    print(f"使用批处理大小: {BATCH_SIZE}")
    if args.use_async:
        print(f"使用异步并发模式，最大并发数: {MAX_CONCURRENCY}")
    
    if args.skip_ai:
        print("已设置跳过AI处理，不会提取伙伴信息")
        # 使用不调用AI的处理函数
        print("直接处理飞书数据...")
        feishu_df = process_feishu_data_without_ai()
        print("直接处理钉钉数据...")
        dingding_df = process_dingding_data_without_ai()
    else:
        # 处理两个数据源
        print(f"{'使用异步模式' if args.use_async else '使用同步模式'}处理飞书数据...")
        feishu_df = process_feishu_data(use_async=args.use_async)
        
        print(f"{'使用异步模式' if args.use_async else '使用同步模式'}处理钉钉数据...")
        dingding_df = process_dingding_data(use_async=args.use_async)
    
    # 合并数据框
    combined_df = pd.concat([feishu_df, dingding_df], ignore_index=True)
    
    # 将日期时间字符串转换为datetime对象进行筛选
    combined_df['处理日期'] = pd.to_datetime(combined_df['开始时间'])
    
    # 筛选指定月份的数据
    combined_df = combined_df[combined_df['处理日期'].dt.strftime('%m') == MONTH]
    
    # 删除临时列
    combined_df = combined_df.drop('处理日期', axis=1)
    
    # 按姓名和开始时间排序
    combined_df = combined_df.sort_values(by=['姓名', '开始时间'])
    
    print("合并数据并保存到数据库...")
    # 保存到数据库
    save_to_database(combined_df)
    
    # 输出统计信息
    print("\n数据处理完成，统计信息:")
    print(f"当前处理月份: {MONTH}月")
    print(f"飞书数据记录数: {len(feishu_df)}")
    print(f"钉钉数据记录数: {len(dingding_df)}")
    print(f"合并后筛选{MONTH}月份总记录数: {len(combined_df)}")
    
    print("所有数据处理完成")

# 不使用AI处理的函数版本
def process_feishu_data_without_ai():
    """
    处理飞书数据但不调用AI接口
    """
    feishu_file = os.path.join(DATA_DIR, 'feishu_overwork.xlsx')
    if not os.path.exists(feishu_file):
        print(f"飞书加班数据文件不存在: {feishu_file}")
        return pd.DataFrame()
    
    # 读取Excel文件
    df = pd.read_excel(feishu_file)
    
    # 重命名列
    column_mapping = {
        '姓名': '姓名',
        '部门': '部门',
        '加班日期': '日期',
        '开始时间': '开始时间',
        '结束时间': '结束时间',
        '加班时长（小时）': '加班时长',
        '加班类型': '加班类型',
        '详细说明（加班内容）': '加班说明'
    }
    
    # 应用列映射
    result_df = df.rename(columns=column_mapping)
    
    # 添加伙伴字段，但不填充
    result_df['伙伴'] = ''
    
    # 添加数据来源标识
    result_df['数据来源'] = '飞书'
    return result_df

def process_dingding_data_without_ai():
    """
    处理钉钉数据但不调用AI接口
    """
    dingding_file = os.path.join(DATA_DIR, 'dingding_overwork.xlsx')
    if not os.path.exists(dingding_file):
        print(f"钉钉加班数据文件不存在: {dingding_file}")
        return pd.DataFrame()
    
    # 读取Excel文件
    df = pd.read_excel(dingding_file)
    
    # 重命名列
    column_mapping = {
        '姓名': '姓名',
        '部门': '部门',
        '加班日期': '日期',
        '开始时间': '开始时间',
        '结束时间': '结束时间',
        '加班时长（小时）': '加班时长',
        '加班类型': '加班类型',
        '加班事由': '加班说明'
    }
    
    # 应用列映射
    result_df = df.rename(columns=column_mapping)
    
    # 添加伙伴字段，但不填充
    result_df['伙伴'] = ''
    
    # 添加数据来源标识
    result_df['数据来源'] = '钉钉'
    return result_df

def test_parse_ai_response():
    """
    测试解析AI响应的函数
    """
    # 测试用例1：标准格式的AI响应
    test_response1 = {
        "answer": '{"names":["张三","李四","王五"]}'
    }
    result1 = parse_ai_response(test_response1)
    expected1 = "张三,李四,王五"
    print(f"测试1结果: {result1 == expected1}，解析结果: {result1}")
    
    # 测试用例2：带有<think>标签的AI响应
    test_response2 = {
        "answer": '<think>\n思考过程\n</think>\n{"names":["赵六","钱七","孙八"]}'
    }
    result2 = parse_ai_response(test_response2)
    expected2 = "赵六,钱七,孙八"
    print(f"测试2结果: {result2 == expected2}，解析结果: {result2}")
    
    # 测试用例3：嵌套在message中的AI响应
    test_response3 = {
        "message": {
            "answer": '{"names":["周九","吴十"]}'
        }
    }
    result3 = parse_ai_response(test_response3)
    expected3 = "周九,吴十"
    print(f"测试3结果: {result3 == expected3}，解析结果: {result3}")
    
    # 测试用例4：格式错误的AI响应
    test_response4 = {
        "answer": "这不是一个有效的JSON格式"
    }
    result4 = parse_ai_response(test_response4)
    print(f"测试4结果: {result4 == ''}，解析结果: {result4}")
    
    # 测试用例5：空的AI响应
    test_response5 = {}
    result5 = parse_ai_response(test_response5)
    print(f"测试5结果: {result5 == ''}，解析结果: {result5}")
    
    # 测试用例6：用户提供的示例格式
    test_response6 = { 
        "event": "message", 
        "task_id": "01225cde-b276-478a-a621-cd888000ce03", 
        "id": "d542113f-3b91-4e8f-8ed9-03315818d66b", 
        "message_id": "d542113f-3b91-4e8f-8ed9-03315818d66b", 
        "conversation_id": "6ade1a4e-9265-45b4-9cf8-f19a224437f4", 
        "mode": "advanced-chat", 
        "answer": "<think>\n\n</think>\n\n{\"names\":[\"高群\",\"王松\",\"李飞\",\"王能武\",\"王星\",\"刘杰\",\"沈洋\",\"田磊\",\"刘成香\",\"刘登\",\"李炎炎\",\"陈威\",\"余东明\",\"王洋\",\"孙盼\",\"林超\",\"曹博文\",\"高星\",\"席智成\",\"魏权\",\"刘贤杰\",\"万俊杰\",\"叶成\",\"李明\",\"怀雄\",\"刘卫宜\",\"张磊磊\"]}" 
    }
    result6 = parse_ai_response(test_response6)
    expected6 = "高群,王松,李飞,王能武,王星,刘杰,沈洋,田磊,刘成香,刘登,李炎炎,陈威,余东明,王洋,孙盼,林超,曹博文,高星,席智成,魏权,刘贤杰,万俊杰,叶成,李明,怀雄,刘卫宜,张磊磊"
    print(f"测试6结果: {result6 == expected6}，解析结果: {result6}")
    
    print("所有测试完成")

if __name__ == "__main__":
    # 解析命令行参数
    args = parse_arguments()
    
    # 如果指定了--test参数，运行测试函数
    if args.test:
        test_parse_ai_response()
        sys.exit(0)
    
    # 运行主程序
    main()