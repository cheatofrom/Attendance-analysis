import requests
import json
import argparse
import time
import asyncio
import aiohttp
from logger_utils import create_logger

# 初始化日志记录器
logger = create_logger('llm_processor')

async def get_llm_response_async(prompt):
    """
    异步向Ollama API发送请求并获取响应
    参数:
    prompt (str): 用户提示/问题
    返回:
    str: 模型的响应文本
    """
    url = "http://192.168.1.66:11434/api/generate"
    
    # 简化日志，不记录请求开始信息
    
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
        
        # 异步发送POST请求到Ollama API
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()  # 如果请求失败则抛出异常
                
                # 解析JSON响应，简化日志输出
                result = await response.json()
                response_text = result["response"]
                
                return response_text
    
    except aiohttp.ClientError as e:
        logger.log_error(f"异步API请求失败: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logger.log_error(f"解析异步API响应失败: {e}")
        return None

async def query_llm_async(prompt):
    """
    异步封装的LLM查询函数，只接收prompt参数并返回模型回答
    
    参数:
    prompt (str): 用户提示/问题
    
    返回:
    str: 模型的响应文本
    """
    return await get_llm_response_async(prompt)

if __name__ == "__main__":
    print("此模块提供LLM查询功能，不应直接运行")
else:
    # 当作为模块导入时，导出query_llm函数
    __all__ = ['query_llm', 'query_llm_async', 'clean_llm_response']