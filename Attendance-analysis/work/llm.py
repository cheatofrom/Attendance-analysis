import requests
import json
import argparse
import time
import asyncio
import aiohttp
from logger_utils import create_logger

# 初始化日志记录器
logger = create_logger('llm_processor')

def get_llm_response(prompt):
    """
    向Ollama API发送请求并获取响应
    
    参数:
    prompt (str): 用户提示/问题
    
    返回:
    str: 模型的响应文本
    """
    url = "http://192.168.1.66:11434/api/generate"
    
    # 记录API请求开始
    logger.log_info(f"开始向LLM API发送请求，提示长度: {len(prompt)} 字符")
    logger.log_progress("API请求", "准备请求数据")
    
    # 准备请求数据 - 使用固定的模型名称和参数
    system_prompt = "公司的加班要求是好几个人一起加班的话应该只会发一条审批记录，我需要你把每个人的相关的加班信息整理一下，加班时长你应该要计算一下，整理成：名字，日期，时间，加班时长.例如格式必须为:袁俊祥,2025-07-31,18:00-20:00,2.0"
    
    payload = {
        "model": "gpt-oss:20b",
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "temperature": 0.7
    }
    
    start_time = time.time()
    
    try:
        # logger.log_progress("API请求", f"发送POST请求到 {url}")
        
        # 发送POST请求到Ollama API
        response = requests.post(url, json=payload)
        response.raise_for_status()  # 如果请求失败则抛出异常
        
        response_time = time.time() - start_time
        # logger.log_info(f"API请求成功，响应时间: {response_time:.2f}秒")
        # logger.log_progress("API请求", "解析JSON响应")
        
        # 解析JSON响应
        result = response.json()
        response_text = result["response"]
        
        # logger.log_info(f"LLM响应长度: {len(response_text)} 字符")
        # logger.log_progress("API请求", "✓ 请求完成")
        
        return response_text
    
    except requests.exceptions.RequestException as e:
        error_time = time.time() - start_time
        logger.log_error(f"API请求失败 (耗时 {error_time:.2f}秒): {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        error_time = time.time() - start_time
        logger.log_error(f"解析API响应失败 (耗时 {error_time:.2f}秒): {e}")
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
    
    # 记录异步API请求开始
    # logger.log_info(f"开始异步向LLM API发送请求，提示长度: {len(prompt)} 字符")
    # logger.log_progress("异步API请求", "准备请求数据")
    
    # 准备请求数据 - 使用固定的模型名称和参数
    system_prompt = "公司的加班要求是好几个人一起加班的话应该只会发一条审批记录，我需要你把每个人的相关的加班信息整理一下，加班时长你应该要计算一下，整理成：名字，日期，时间，加班时长.例如格式必须为:袁俊祥,2025-07-31,18:00-20:00,2.0"
    
    payload = {
        "model": "gpt-oss:20b",
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "temperature": 0.7
    }
    
    start_time = time.time()
    
    try:
        # logger.log_progress("异步API请求", f"发送异步POST请求到 {url}")
        
        # 异步发送POST请求到Ollama API
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()  # 如果请求失败则抛出异常
                
                response_time = time.time() - start_time
                # logger.log_info(f"异步API请求成功，响应时间: {response_time:.2f}秒")
                # logger.log_progress("异步API请求", "解析JSON响应")
                
                # 解析JSON响应
                result = await response.json()
                response_text = result["response"]
                
                # logger.log_info(f"异步LLM响应长度: {len(response_text)} 字符")
                # logger.log_progress("异步API请求", "✓ 异步请求完成")
                
                return response_text
    
    except aiohttp.ClientError as e:
        error_time = time.time() - start_time
        logger.log_error(f"异步API请求失败 (耗时 {error_time:.2f}秒): {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        error_time = time.time() - start_time
        logger.log_error(f"解析异步API响应失败 (耗时 {error_time:.2f}秒): {e}")
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
    logger.start_step("处理加班数据")
    logger.log_data_processing(f"开始处理加班数据: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    
    # 查询模型
    response = get_llm_response(prompt)
    
    if response:
        logger.log_info(f"LLM处理成功，响应长度: {len(response)} 字符")
        logger.log_data_processing(f"处理结果预览: {response[:100]}{'...' if len(response) > 100 else ''}")
        logger.complete_step("处理加班数据", "✓ 数据处理完成")
        return response
    else:
        logger.log_error("LLM处理失败，请检查Ollama服务是否运行")
        logger.complete_step("处理加班数据", "✗ 数据处理失败")
        return None

def process_multiple_data(data_list):
    """
    处理多条加班数据
    
    参数:
    data_list (list): 加班数据列表
    
    返回:
    list: 处理结果列表
    """
    logger.start_step("批量处理加班数据")
    logger.log_info(f"开始批量处理 {len(data_list)} 条加班数据")
    
    results = []
    success_count = 0
    failed_count = 0
    
    for i, data in enumerate(data_list):
        current_progress = ((i + 1) / len(data_list)) * 100
        logger.log_progress("批量处理进度", f"[{i+1}/{len(data_list)}] ({current_progress:.1f}%) 处理第 {i+1} 条数据")
        
        start_time = time.time()
        result = process_overtime_data(data)
        process_time = time.time() - start_time
        
        if result:
            results.append(result)
            success_count += 1
            logger.log_info(f"第 {i+1} 条数据处理成功 (耗时 {process_time:.2f}秒)")
        else:
            failed_count += 1
            logger.log_error(f"第 {i+1} 条数据处理失败 (耗时 {process_time:.2f}秒)")
        
        # 添加延迟，避免请求过于频繁
        if i < len(data_list) - 1:
            logger.log_progress("批量处理进度", "等待1秒避免请求过于频繁...")
            time.sleep(1)
    
    logger.log_info(f"批量处理完成: 成功 {success_count} 条，失败 {failed_count} 条，总计 {len(data_list)} 条")
    logger.complete_step("批量处理加班数据", f"✓ 批量处理完成 ({success_count}/{len(data_list)} 成功)")
    
    return results

def main():
    logger.start_script("LLM加班数据处理器")
    
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="处理加班数据")
    parser.add_argument("--file", type=str, help="包含加班数据的文件路径，每行一条数据")
    parser.add_argument("--data", type=str, help="单条加班数据")
    args = parser.parse_args()
    
    try:
        if args.file:
            # 从文件读取多条数据
            logger.start_step("文件数据处理")
            logger.log_file_operation(f"读取文件: {args.file}")
            
            try:
                with open(args.file, 'r', encoding='utf-8') as f:
                    data_list = [line.strip() for line in f if line.strip()]
                
                if data_list:
                    logger.log_info(f"从文件 {args.file} 中成功读取了 {len(data_list)} 条有效数据")
                    results = process_multiple_data(data_list)
                    
                    success_rate = (len(results) / len(data_list)) * 100 if data_list else 0
                    logger.log_info(f"文件处理完成: 成功处理 {len(results)}/{len(data_list)} 条数据 (成功率: {success_rate:.1f}%)")
                    logger.complete_step("文件数据处理", f"✓ 文件处理完成 ({len(results)}/{len(data_list)} 成功)")
                else:
                    logger.log_error(f"文件 {args.file} 中没有有效数据")
                    logger.complete_step("文件数据处理", "✗ 文件中无有效数据")
            except Exception as e:
                logger.log_error(f"读取文件时出错: {e}")
                logger.complete_step("文件数据处理", f"✗ 文件读取失败: {e}")
        
        elif args.data:
            # 处理单条数据
            logger.start_step("单条数据处理")
            logger.log_info(f"处理单条数据: {args.data[:50]}{'...' if len(args.data) > 50 else ''}")
            result = process_overtime_data(args.data)
            
            if result:
                logger.complete_step("单条数据处理", "✓ 单条数据处理成功")
            else:
                logger.complete_step("单条数据处理", "✗ 单条数据处理失败")
        
        else:
            # 使用示例数据
            logger.start_step("示例数据处理")
            example_data = "杨春森 2025-07-31 18:00 2025-07-31 20:00 2 支援仓库搬仓库，加班人员4人，张海鹏，马建发，殷顺威，杨孔祥"
            logger.log_info("未提供数据，使用示例数据进行处理")
            result = process_overtime_data(example_data)
            
            if result:
                logger.complete_step("示例数据处理", "✓ 示例数据处理成功")
            else:
                logger.complete_step("示例数据处理", "✗ 示例数据处理失败")
        
        logger.finish_script("LLM加班数据处理器", "✓ 脚本执行完成")
        
    except Exception as e:
        logger.log_error(f"脚本执行过程中发生未预期错误: {e}")
        logger.finish_script("LLM加班数据处理器", f"✗ 脚本执行失败: {e}")

if __name__ == "__main__":
    main()
else:
    # 当作为模块导入时，导出query_llm函数
    __all__ = ['query_llm', 'query_llm_async']