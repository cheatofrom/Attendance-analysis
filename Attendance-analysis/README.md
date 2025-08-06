# 考勤分析系统

## 项目简介
本项目为考勤分析系统，基于 FastAPI 提供 Web API 接口，支持一键运行考勤数据分析脚本，并可通过接口下载分析结果。

## 数据来源说明
本系统主要处理七个表：
- 一个钉钉考勤表
- 飞书的请假表、加班表、出差表
- 钉钉的请假表、加班表、出差表

## 主要功能
- 一键运行所有考勤分析脚本（支持同步/异步）
- 查询脚本运行状态
- 获取输出文件列表及下载
- 获取最新输出文件

## 依赖环境
- Python 3.8+
- Conda 环境（推荐）
- FastAPI
- Uvicorn
- 其他依赖见 `environment.yml` 或 `requirements.txt`

## 快速开始
1. 克隆项目
   ```bash
   git clone https://github.com/2661517213/Attendance-analysis.git
   cd Attendance-analysis
   ```
2. 创建并激活 conda 环境
   ```bash
   conda env create -f environment.yml
   conda activate dd
   ```
3. 启动 API 服务
   ```bash
   cd work
   python download_api.py
   # 或
   uvicorn download_api:app --host 0.0.0.0 --port 8900
   ```

## API接口说明
- `POST   /api/run-script`         ：同步运行所有分析脚本
- `POST   /api/run-script-async`   ：异步后台运行所有分析脚本
- `GET    /api/script-status`      ：查询脚本运行状态
- `GET    /api/files`              ：获取输出文件列表
- `GET    /api/download/{filename}`：下载指定输出文件
- `GET    /api/latest-file`        ：获取最新输出文件

## 目录结构
```
Attendance-analysis/
  ├── data/                # 原始数据文件夹
  ├── output/              # 输出结果文件夹
  ├── work/                # 主要脚本和API
  │   ├── download_api.py  # FastAPI主接口
  │   ├── run_all_scripts.sh # 一键运行脚本
  │   └── ...              # 其他分析脚本
  └── README.md            # 项目说明
```

## 联系方式
如有问题请在 GitHub issue 区留言。 