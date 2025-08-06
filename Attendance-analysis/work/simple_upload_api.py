#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的文件上传API - 7个参数对应7个文件
"""

import os
from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn

app = FastAPI(title="简单文件上传API", version="1.0.0")

# 目标目录
UPLOAD_DIR = "/home/dell/mnt/ai-work/Attendance-analysis/data/original"

@app.post("/upload")
async def upload_files(
    basic: UploadFile = File(...),
    business01: UploadFile = File(...),
    business02: UploadFile = File(...),
    freework01: UploadFile = File(...),
    freework02: UploadFile = File(...),
    overwork01: UploadFile = File(...),
    overwork02: UploadFile = File(...)
):
    """上传7个文件，每个参数对应一个文件"""
    
    # 确保上传目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # 文件映射
    files = {
        "basic.xlsx": basic,
        "business01.xlsx": business01,
        "business02.xlsx": business02,
        "freework01.xlsx": freework01,
        "freework02.xlsx": freework02,
        "overwork01.xlsx": overwork01,
        "overwork02.xlsx": overwork02
    }
    
    uploaded = []
    errors = []
    
    for filename, file in files.items():
        try:
            # 检查文件扩展名
            if not file.filename.lower().endswith('.xlsx'):
                errors.append(f"{filename}: 不是Excel文件")
                continue
            
            # 保存文件
            file_path = os.path.join(UPLOAD_DIR, filename)
            content = await file.read()
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            uploaded.append({
                "filename": filename,
                "size_mb": round(len(content) / (1024 * 1024), 2)
            })
            
        except Exception as e:
            errors.append(f"{filename}: {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "uploaded": uploaded,
        "errors": errors,
        "total_uploaded": len(uploaded),
        "total_errors": len(errors)
    }

@app.get("/")
async def root():
    """根路径"""
    return {"message": "简单文件上传API", "endpoint": "/upload"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8901) 