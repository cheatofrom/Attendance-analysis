from fastapi import FastAPI
from pydantic import BaseModel
import re
import os

app = FastAPI()

class ConfigUpdate(BaseModel):
    holidays: list[str]  # 休息日列表，如 ["01", "05"]
    month: int           # 月份，如 6 (注意现在是整数类型)
    year: int            # 年份，如 2025

@app.post("/update_config")
def update_config(request: ConfigUpdate):
    file_path = "holidays.py"
    
    # 读取原文件
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 更新HOLIDAYS部分（保留原格式）
    new_holidays = 'HOLIDAYS = [\n' + \
                   ',\n'.join(f'    "{day}"' for day in request.holidays) + \
                   '\n]'
    content = re.sub(r'HOLIDAYS\s*=\s*\[[\s\S]*?\]', new_holidays, content)
    
    # 更新MONTH（匹配字符串格式，如 '05'）
    content = re.sub(r"MONTH\s*=\s*'?\d+'?", f"MONTH='{request.month:02d}'", content)
    
    # 更新YEAR
    content = re.sub(r'YEAR\s*=\s*\d+', f'YEAR={request.year}', content)
    
    # 写入新内容
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return {
        "status": "success",
        "updated_values": {
            "holidays": request.holidays,
            "month": request.month,
            "year": request.year
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8911)