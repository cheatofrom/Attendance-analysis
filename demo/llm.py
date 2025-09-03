import requests
import json
import argparse
import time
import asyncio
import aiohttp

def get_llm_response(prompt):
    """
    向Ollama API发送请求并获取响应
    
    参数:
    prompt (str): 用户提示/问题
    
    返回:
    str: 模型的响应文本
    """
    url = "http://192.168.1.66:11434/api/generate"
    
    # 准备请求数据 - 使用固定的模型名称和参数
    system_prompt = "公司的加班要求是好几个人一起加班的话应该只会发一条审批记录，我需要你把每个人的相关的加班信息整理一下，加班时长你应该要计算一下，整理成：名字，日期，时间，加班时长.例如格式必须为:袁俊祥,2025-07-31,18:00-20:00,2.0"
    
    payload = {
        "model": "gpt-oss:20b",
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "temperature": 0.7
    }
    
    try:
        # 发送POST请求到Ollama API
        response = requests.post(url, json=payload)
        response.raise_for_status()  # 如果请求失败则抛出异常
        
        # 解析JSON响应
        result = response.json()
        return result["response"]
    
    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"解析响应错误: {e}")
        return None

async def get_llm_response_async(prompt):
    """
    异步向Ollama API发送请求并获取响应
    
    参数:
    prompt (str): 用户提示/问题
    
    返回:
    str: 模型的响应文本
    """
    url = "http://192.168.1.66:11434/api/generate"
    
    # 准备请求数据 - 使用固定的模型名称和参数
    system_prompt = "公司的加班要求是好几个人一起加班的话应该只会发一条审批记录，我需要你把每个人的相关的加班信息整理一下，加班时长你应该要计算一下，整理成：名字，日期，时间，加班时长.例如格式必须为:袁俊祥,2025-07-31,18:00-20:00,2.0"
    
    payload = {
        "model": "gpt-oss:20b",
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "temperature": 0.7
    }
    
    try:
        # 异步发送POST请求到Ollama API
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()  # 如果请求失败则抛出异常
                
                # 解析JSON响应
                result = await response.json()
                return result["response"]
    
    except aiohttp.ClientError as e:
        print(f"请求错误: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"解析响应错误: {e}")
        return None

def query_llm(prompt):
    """
    封装的LLM查询函数，只接收prompt参数并返回模型回答
    
    参数:
    prompt (str): 用户提示/问题
    
    返回:
    str: 模型的响应文本
    """
    return get_llm_response(prompt)

async def query_llm_async(prompt):
    """
    异步封装的LLM查询函数，只接收prompt参数并返回模型回答
    
    参数:
    prompt (str): 用户提示/问题
    
    返回:
    str: 模型的响应文本
    """
    return await get_llm_response_async(prompt)

def process_overtime_data(prompt):
    """
    处理单条加班数据
    
    参数:
    prompt (str): 加班数据描述
    
    返回:
    str: 处理结果
    """
    print(f"处理问题: {prompt}")
    print("-" * 50)
    
    # 查询模型
    response = get_llm_response(prompt)
    
    if response:
        print("\n回答:")
        print(response)
        print("-" * 50)
        return response
    else:
        print("获取响应失败，请检查Ollama服务是否运行。")
        return None

def process_multiple_data(data_list):
    """
    处理多条加班数据
    
    参数:
    data_list (list): 加班数据列表
    
    返回:
    list: 处理结果列表
    """
    results = []
    for i, data in enumerate(data_list):
        print(f"\n处理第 {i+1}/{len(data_list)} 条数据")
        result = process_overtime_data(data)
        if result:
            results.append(result)
        # 添加延迟，避免请求过于频繁
        if i < len(data_list) - 1:
            time.sleep(1)
    return results

def main():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="处理加班数据")
    parser.add_argument("--file", type=str, help="包含加班数据的文件路径，每行一条数据")
    parser.add_argument("--data", type=str, help="单条加班数据")
    args = parser.parse_args()
    
    if args.file:
        # 从文件读取多条数据
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                data_list = [line.strip() for line in f if line.strip()]
            
            if data_list:
                print(f"从文件 {args.file} 中读取了 {len(data_list)} 条数据")
                results = process_multiple_data(data_list)
                print(f"\n成功处理 {len(results)}/{len(data_list)} 条数据")
            else:
                print(f"文件 {args.file} 中没有有效数据")
        except Exception as e:
            print(f"读取文件时出错: {e}")
    
    elif args.data:
        # 处理单条数据
        process_overtime_data(args.data)
    
    else:
        # 使用示例数据
        example_data = "杨春森 2025-07-31 18:00 2025-07-31 20:00 2 支援仓库搬仓库，加班人员4人，张海鹏，马建发，殷顺威，杨孔祥"
        print("未提供数据，使用示例数据:")
        process_overtime_data(example_data)

if __name__ == "__main__":
    main()
else:
    # 当作为模块导入时，导出query_llm函数
    __all__ = ['query_llm', 'query_llm_async']