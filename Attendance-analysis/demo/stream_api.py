#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式响应API示例
使用FastAPI构建，提供HTTP流式响应功能
"""

import asyncio
import random
import time
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI(
    title="流式响应API示例",
    description="提供HTTP流式响应功能演示",
    version="1.0.0"
)


@app.get("/stream")
async def stream_response():
    """
    返回流式响应，每秒发送一条数据
    """
    async def generate_data() -> AsyncGenerator[str, None]:
        for i in range(100):  # 发送100条数据
            # 生成随机数据
            data = {
                "timestamp": datetime.now().isoformat(),
                "value": random.random(),
                "index": i
            }
            # 转换为字符串并发送
            yield f"data: {data}\n\n"
            await asyncio.sleep(1)  # 每秒发送一条
    
    return StreamingResponse(
        generate_data(),
        media_type="text/event-stream"
    )


@app.get("/stream-json")
async def stream_json():
    """
    返回JSON格式的流式响应，每秒发送一条数据
    """
    async def generate_json() -> AsyncGenerator[str, None]:
        for i in range(100):  # 发送100条数据
            # 生成随机数据
            data = f'{{"timestamp": "{datetime.now().isoformat()}", "value": {random.random()}, "index": {i}}}\n'
            yield data
            await asyncio.sleep(1)  # 每秒发送一条
    
    return StreamingResponse(
        generate_json(),
        media_type="application/json"
    )


@app.get("/stream-text")
async def stream_text():
    """
    返回纯文本格式的流式响应，每秒发送一行
    """
    async def generate_text() -> AsyncGenerator[str, None]:
        for i in range(100):  # 发送100行文本
            yield f"行 {i}: 当前时间 {datetime.now().isoformat()} - 随机值 {random.random()}\n"
            await asyncio.sleep(1)  # 每秒发送一行
    
    return StreamingResponse(
        generate_text(),
        media_type="text/plain"
    )


@app.get("/")
async def root():
    """
    根路径，返回API信息
    """
    return {
        "message": "流式响应API示例",
        "version": "1.0.0",
        "endpoints": {
            "GET /stream": "返回Server-Sent Events格式的流式响应",
            "GET /stream-json": "返回JSON格式的流式响应",
            "GET /stream-text": "返回纯文本格式的流式响应"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "stream_api:app",
        host="0.0.0.0",
        port=6538,  # 将端口从8901改为6538
        reload=False
    )