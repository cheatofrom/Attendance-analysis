#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
考勤分析系统 API 接口
使用 FastAPI 构建，提供调用 run_all_scripts.sh 脚本的功能
"""

import os
import subprocess
import signal
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import glob
import threading

app = FastAPI(
    title="考勤分析系统 API",
    description="提供考勤分析脚本调用功能",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法，包括OPTIONS
    allow_headers=["*"],
)

# 请求模型
class RunScriptRequest(BaseModel):
    ai_agent_enabled: bool = False

# 全局变量存储脚本执行状态和进程信息
script_status = {
    'is_running': False,
    'start_time': None,
    'end_time': None,
    'exit_code': None,
    'output': '',
    'error': '',
    'interrupted': False
}

# 存储当前运行的进程
current_process = None
process_lock = threading.Lock()

def run_script(ai_agent_enabled=False):
    """执行脚本并返回结果"""
    global script_status, current_process
    
    with process_lock:
        script_status['is_running'] = True
        script_status['start_time'] = datetime.now().isoformat()
        script_status['output'] = ''
        script_status['error'] = ''
        script_status['interrupted'] = False
    
    try:
        # 根据AI agent选择决定使用哪个脚本
        script_name = 'run_all_scripts02.sh' if ai_agent_enabled else 'run_all_scripts.sh'
        script_path = os.path.join(os.path.dirname(__file__), script_name)
        
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        
        # 执行脚本
        with process_lock:
            current_process = subprocess.Popen(
                ['bash', script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(__file__),
                preexec_fn=os.setsid,  # 创建新的进程组，便于终止子进程
                bufsize=1,  # 行缓冲
                universal_newlines=True
            )
        
        # 实时读取输出
        output_lines = []
        error_lines = []
        
        # 使用线程来实时读取stdout和stderr
        def read_stdout():
            for line in iter(current_process.stdout.readline, ''):
                if line:
                    with process_lock:
                        output_lines.append(line)
                        script_status['output'] = ''.join(output_lines)
        
        def read_stderr():
            for line in iter(current_process.stderr.readline, ''):
                if line:
                    with process_lock:
                        error_lines.append(line)
                        script_status['error'] = ''.join(error_lines)
        
        # 启动读取线程
        stdout_thread = threading.Thread(target=read_stdout)
        stderr_thread = threading.Thread(target=read_stderr)
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()
        
        # 等待进程完成
        exit_code = current_process.wait()
        
        # 等待读取线程完成
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        
        with process_lock:
            # 获取退出代码
            script_status['exit_code'] = exit_code
            script_status['end_time'] = datetime.now().isoformat()
            script_status['is_running'] = False
            current_process = None
        
        if script_status['interrupted']:
            return False, "脚本执行被用户中断"
        elif exit_code == 0:
            return True, "脚本执行成功"
        else:
            return False, f"脚本执行失败，退出代码: {exit_code}"
            
    except Exception as e:
        with process_lock:
            script_status['error'] = str(e)
            script_status['end_time'] = datetime.now().isoformat()
            script_status['is_running'] = False
            script_status['exit_code'] = -1
            current_process = None
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
async def run_script_async(request: RunScriptRequest = RunScriptRequest()) -> Dict[str, Any]:
    """在后台异步启动脚本"""
    global script_status
    
    if script_status['is_running']:
        raise HTTPException(
            status_code=409,
            detail="脚本正在运行中，请稍后再试"
        )
    
    # 获取AI agent启用状态
    ai_agent_enabled = request.ai_agent_enabled
    
    # 启动后台线程执行脚本
    import threading
    thread = threading.Thread(target=run_script, args=(ai_agent_enabled,))
    thread.daemon = True
    thread.start()
    
    script_type = "AI增强脚本" if ai_agent_enabled else "标准脚本"
    return {
        "success": True,
        "message": f"{script_type}已启动，正在后台执行",
        "status": script_status
    }

@app.get("/api/script-status")
async def get_script_status() -> Dict[str, Any]:
    """获取脚本执行状态"""
    return {
        "success": True,
        "status": script_status
    }

@app.post("/api/stop-script")
async def stop_script() -> Dict[str, Any]:
    """停止正在运行的脚本"""
    global script_status, current_process
    
    with process_lock:
        if not script_status['is_running']:
            raise HTTPException(
                status_code=400,
                detail="没有正在运行的脚本"
            )
        
        if current_process is None:
            raise HTTPException(
                status_code=400,
                detail="无法找到正在运行的进程"
            )
        
        try:
            # 标记为中断状态
            script_status['interrupted'] = True
            
            # 终止进程组（包括所有子进程）
            os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            
            # 等待进程结束，最多等待5秒
            try:
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 如果5秒后还没结束，强制杀死
                os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
                current_process.wait()
            
            # 更新状态
            script_status['is_running'] = False
            script_status['end_time'] = datetime.now().isoformat()
            script_status['exit_code'] = -2  # 特殊退出代码表示被中断
            script_status['error'] = '脚本执行被用户中断'
            current_process = None
            
            return {
                "success": True,
                "message": "脚本已成功停止",
                "status": script_status
            }
            
        except ProcessLookupError:
            # 进程已经不存在
            script_status['is_running'] = False
            script_status['end_time'] = datetime.now().isoformat()
            script_status['exit_code'] = -2
            current_process = None
            
            return {
                "success": True,
                "message": "脚本已停止（进程已结束）",
                "status": script_status
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"停止脚本时发生错误: {str(e)}"
            )

@app.get("/api/files")
async def get_output_files() -> Dict[str, Any]:
    """获取输出目录中的所有文件"""
    try:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'output')
        
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
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'output')
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

@app.delete("/api/delete/{filename}")
async def delete_file(filename: str) -> Dict[str, Any]:
    """删除指定的输出文件"""
    try:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'output')
        file_path = os.path.join(output_dir, filename)
        
        # 安全检查：确保文件在输出目录内
        if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
            raise HTTPException(
                status_code=400,
                detail="无效的文件路径"
            )
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"文件 {filename} 不存在"
            )
        
        # 检查是否为文件（不是目录）
        if not os.path.isfile(file_path):
            raise HTTPException(
                status_code=400,
                detail=f"{filename} 不是一个有效的文件"
            )
        
        # 删除文件
        os.remove(file_path)
        
        return {
            "success": True,
            "message": f"文件 {filename} 已成功删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除文件失败: {str(e)}"
        )

@app.get("/api/latest-file")
async def get_latest_file() -> Dict[str, Any]:
    """获取最新的输出文件"""
    try:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'output')
        
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
            "POST /api/stop-script": "停止正在运行的脚本",
            "GET /api/script-status": "获取脚本执行状态",
            "GET /api/files": "获取所有输出文件列表",
            "GET /api/download/{filename}": "下载指定的输出文件",
            "DELETE /api/delete/{filename}": "删除指定的输出文件",
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
