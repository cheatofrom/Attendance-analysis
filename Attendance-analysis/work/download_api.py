#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
考勤分析系统 API 接口
使用 FastAPI 构建，提供调用 run_all_scripts.sh 脚本的功能
"""

import os
import subprocess
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
import glob

app = FastAPI(
    title="考勤分析系统 API",
    description="提供考勤分析脚本调用功能",
    version="1.0.0"
)

# 全局变量存储脚本执行状态
script_status = {
    'is_running': False,
    'start_time': None,
    'end_time': None,
    'exit_code': None,
    'output': '',
    'error': ''
}

def run_script():
    """执行脚本并返回结果"""
    global script_status
    
    script_status['is_running'] = True
    script_status['start_time'] = datetime.now().isoformat()
    script_status['output'] = ''
    script_status['error'] = ''
    
    try:
        # 获取脚本的绝对路径
        script_path = os.path.join(os.path.dirname(__file__), 'run_all_scripts.sh')
        
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        
        # 执行脚本
        process = subprocess.Popen(
            ['bash', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(__file__)
        )
        
        # 获取输出
        stdout, stderr = process.communicate()
        
        script_status['output'] = stdout
        if stderr:
            script_status['error'] = stderr
        
        # 获取退出代码
        exit_code = process.returncode
        script_status['exit_code'] = exit_code
        script_status['end_time'] = datetime.now().isoformat()
        script_status['is_running'] = False
        
        if exit_code == 0:
            return True, "脚本执行成功"
        else:
            return False, f"脚本执行失败，退出代码: {exit_code}"
            
    except Exception as e:
        script_status['error'] = str(e)
        script_status['end_time'] = datetime.now().isoformat()
        script_status['is_running'] = False
        script_status['exit_code'] = -1
        return False, f"执行脚本时发生异常: {e}"

@app.post("/api/run-script")
async def run_basic_combined() -> Dict[str, Any]:
    """启动 run_all_scripts.sh 脚本并等待执行完成"""
    global script_status
    
    if script_status['is_running']:
        raise HTTPException(
            status_code=409,
            detail="脚本正在运行中，请稍后再试"
        )
    
    # 同步执行脚本并等待完成
    success, message = run_script()
    
    if success:
        return {
            "success": True,
            "message": message,
            "status": script_status
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=message
        )

@app.post("/api/run-script-async")
async def run_script_async() -> Dict[str, Any]:
    """在后台异步启动 run_all_scripts.sh 脚本"""
    global script_status
    
    if script_status['is_running']:
        raise HTTPException(
            status_code=409,
            detail="脚本正在运行中，请稍后再试"
        )
    
    # 启动后台线程执行脚本
    import threading
    thread = threading.Thread(target=run_script)
    thread.daemon = True
    thread.start()
    
    return {
        "success": True,
        "message": "脚本已启动，正在后台执行",
        "status": script_status
    }

@app.get("/api/script-status")
async def get_script_status() -> Dict[str, Any]:
    """获取脚本执行状态"""
    return {
        "success": True,
        "status": script_status
    }

@app.get("/api/files")
async def get_output_files() -> Dict[str, Any]:
    """获取输出目录中的所有文件"""
    try:
        output_dir = os.path.join(os.path.dirname(__file__), 'output')
        
        if not os.path.exists(output_dir):
            return {
                "success": True,
                "files": [],
                "message": "输出目录不存在"
            }
        
        # 获取所有文件
        files = []
        for file_path in glob.glob(os.path.join(output_dir, '*')):
            if os.path.isfile(file_path):
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                
                files.append({
                    "name": file_name,
                    "size": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "modified_time": file_time,
                    "download_url": f"/api/download/{file_name}"
                })
        
        # 按修改时间排序，最新的在前
        files.sort(key=lambda x: x['modified_time'], reverse=True)
        
        return {
            "success": True,
            "files": files,
            "total_count": len(files)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取文件列表失败: {str(e)}"
        )

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """下载指定的输出文件"""
    try:
        output_dir = os.path.join(os.path.dirname(__file__), 'output')
        file_path = os.path.join(output_dir, filename)
        
        # 安全检查：确保文件在输出目录内
        if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
            raise HTTPException(
                status_code=400,
                detail="无效的文件路径"
            )
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"文件 {filename} 不存在"
            )
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"下载文件失败: {str(e)}"
        )

@app.get("/api/latest-file")
async def get_latest_file() -> Dict[str, Any]:
    """获取最新的输出文件"""
    try:
        output_dir = os.path.join(os.path.dirname(__file__), 'output')
        
        if not os.path.exists(output_dir):
            return {
                "success": False,
                "message": "输出目录不存在"
            }
        
        # 获取所有文件
        files = []
        for file_path in glob.glob(os.path.join(output_dir, '*')):
            if os.path.isfile(file_path):
                file_name = os.path.basename(file_path)
                file_time = os.path.getmtime(file_path)
                files.append((file_name, file_time))
        
        if not files:
            return {
                "success": False,
                "message": "没有找到输出文件"
            }
        
        # 获取最新的文件
        latest_file, latest_time = max(files, key=lambda x: x[1])
        
        return {
            "success": True,
            "file": {
                "name": latest_file,
                "modified_time": datetime.fromtimestamp(latest_time).isoformat(),
                "download_url": f"/api/download/{latest_file}"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取最新文件失败: {str(e)}"
        )

@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "message": "考勤分析系统 API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/run-script": "启动考勤分析脚本（同步执行，等待完成）",
            "POST /api/run-script-async": "启动考勤分析脚本（异步执行，后台运行）",
            "GET /api/script-status": "获取脚本执行状态",
            "GET /api/files": "获取所有输出文件列表",
            "GET /api/download/{filename}": "下载指定的输出文件",
            "GET /api/latest-file": "获取最新的输出文件"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "download_api:app",
        host="0.0.0.0",
        port=8900,
        reload=False
    )
