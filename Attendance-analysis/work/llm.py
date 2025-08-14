import requests
import json
import argparse
import time
import asyncio
import aiohttp
from logger_utils import create_logger

# 初始化日志记录器
logger = create_logger('llm_processor')

async def get_llm_response_async(prompt, timeout=1200):
    """
    异步向Ollama API发送请求并获取响应，增加超时处理
    参数:
    prompt (str): 用户提示/问题
    timeout (int): 请求超时时间（秒），默认120秒
    返回:
    str: 模型的响应文本，失败时返回None
    """
    url = "http://192.168.1.66:11434/api/generate"
    
    # 准备请求数据 - 使用固定的模型名称和参数
    system_prompt = (
    "公司的加班要求是好几个人一起加班的话只会发一条审批记录，"
    "我需要你把每个人的相关的加班信息整理一下，加班时长你应该要计算一下，"
    "整理成：名字，日期，时间，加班时长。"
    "例如格式必须为:袁俊祥,2025-07-31,18:00-20:00,2.0\n"
    "example：\n"
    "input：\"杨春森 2025-07-25 17:30 2025-07-25 19:00 1.5 "
    "为了满足订单需要，EA5000气缸装配，测试，C1900N卧龙电机动力总成装配，"
    "测试发货等需要，今日连班人员6人，朱强，赵宁宁，岳飞扬，马崇坤，马建发，缪招胜， 钉钉\"\n"
    "answer：\"杨春森,2025-07-25,17:30-19:00,1.5\n"
    "朱强,2025-07-25,17:30-19:00,1.5\n"
    "赵宁宁,2025-07-25,17:30-19:00,1.5\n"
    "岳飞扬,2025-07-25,17:30-19:00,1.5\n"
    "马崇坤,2025-07-25,17:30-19:00,1.5\n"
    "马建发,2025-07-25,17:30-19:00,1.5\n"
    "缪招胜,2025-07-25,17:30-19:00,1.5\""
)

    payload = {
        "model": "gpt-oss:20b",
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "temperature": 0
    }
    
    start_time = time.time()
    
    try:
        # 设置超时和重试策略
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        
        # 异步发送POST请求到Ollama API，带超时设置
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            try:
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()  # 如果请求失败则抛出异常
                    
                    # 解析JSON响应
                    result = await response.json()
                    response_text = result.get("response")
                    
                    if not response_text or response_text.strip() == "":
                        logger.log_error("API返回空响应")
                        return None
                    
                    elapsed = time.time() - start_time
                    return response_text
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                logger.log_error(f"API请求超时 (>{timeout}秒)，已耗时: {elapsed:.2f}秒")
                return None
            except aiohttp.ClientResponseError as e:
                elapsed = time.time() - start_time
                logger.log_error(f"API响应错误: {e.status} - {e.message}，已耗时: {elapsed:.2f}秒")
                return None
    except aiohttp.ClientError as e:
        elapsed = time.time() - start_time
        logger.log_error(f"异步API请求失败: {e}，已耗时: {elapsed:.2f}秒")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        elapsed = time.time() - start_time
        logger.log_error(f"解析异步API响应失败: {e}，已耗时: {elapsed:.2f}秒")
        return None
    except asyncio.CancelledError:
        elapsed = time.time() - start_time
        logger.log_error(f"API请求被取消，已耗时: {elapsed:.2f}秒")
        # 不再重新抛出异常，而是返回None，让调用者能够继续处理其他任务
        return None
    except Exception as e:
        logger.log_error(f"未预期的异常: {e}")
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