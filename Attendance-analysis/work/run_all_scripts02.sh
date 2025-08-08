#!/bin/bash

# 考勤分析系统 - 完整运行脚本 2.0版本
# 按照运行顺序2.0执行所有Python脚本
# 作者: AI Assistant
# 日期: $(date +%Y-%m-%d)

# 设置脚本标题
echo "=========================================="
echo "    考勤分析系统 2.0 - 完整数据处理流程"
echo "=========================================="
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 检查Python环境
echo "🔍 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3 命令"
    echo "请确保已安装 Python 3"
    exit 1
fi

python_version=$(python3 --version 2>&1)
echo "✅ Python版本: $python_version"
echo ""

# 检查工作目录
echo "📁 检查工作目录..."
current_dir=$(pwd)
echo "当前目录: $current_dir"

# 检查所有必要文件是否存在
echo "🔍 检查必要文件..."
required_files=(
    "cross_month_cache.py"
    "basic_combined.py"
    "business_combine.py"
    "freework_combine.py"
    "overwork_combine.py"
    "business_chage.py"
    "freework_chage.py"
    "process_db_async.py"
    "overwork_chage_ai.py"
    "attendance_summary.py"
    "config.py"
    "holidays.py"
    "../data/original/basic.xlsx"
    "../data/original/business01.xlsx"
    "../data/original/business02.xlsx"
    "../data/original/freework01.xlsx"
    "../data/original/freework02.xlsx"
    "../data/original/overwork01.xlsx"
    "../data/original/overwork02.xlsx"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file 存在"
    else
        echo "❌ 错误: $file 不存在"
        exit 1
    fi
done
echo ""

# 检查Python依赖
echo "📦 检查Python依赖..."
python3 -c "
import sys
required_modules = ['psycopg2', 'pandas', 'openpyxl', 'numpy', 'datetime', 'aiopg', 'asyncio']
missing_modules = []

for module in required_modules:
    try:
        __import__(module)
        print(f'✅ {module} 已安装')
    except ImportError:
        missing_modules.append(module)
        print(f'❌ {module} 未安装')

if missing_modules:
    print(f'\n❌ 缺少以下模块: {missing_modules}')
    print('请运行: pip3 install ' + ' '.join(missing_modules))
    sys.exit(1)
"
if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# 创建日志目录
log_dir="logs"
mkdir -p "$log_dir"
timestamp=$(date +%Y%m%d_%H%M%S)
log_file="$log_dir/complete_run_v2_${timestamp}.log"

echo "📝 日志文件: $log_file"
echo ""

# 定义脚本执行函数
run_script() {
    local script_name=$1
    local script_file=$2
    local step_number=$3
    local total_steps=$4
    
    echo "=========================================="
    echo "步骤 $step_number/$total_steps: 执行 $script_name"
    echo "开始时间: $(date '+%H:%M:%S')"
    echo "=========================================="
    
    # 创建单独的日志文件
    local script_log="$log_dir/${script_name}_${timestamp}.log"
    
    # 执行脚本并记录日志
    python3 "$script_file" 2>&1 | tee "$script_log"
    
    local exit_code=${PIPESTATUS[0]}
    
    echo ""
    echo "步骤 $step_number/$total_steps 完成时间: $(date '+%H:%M:%S')"
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ $script_name 执行成功!"
    else
        echo "❌ $script_name 执行失败 (退出代码: $exit_code)"
        echo "📋 请查看日志文件: $script_log"
        return $exit_code
    fi
    
    echo ""
    return 0
}

# 定义脚本列表 (按照运行顺序2.0)
declare -a scripts=(
    "cross_month_cache.py:跨月记录缓存"
    "basic_combined.py:基础数据合并"
    "business_combine.py:业务数据合并"
    "freework_combine.py:自由工作数据合并"
    "overwork_combine.py:加班数据合并"
    "business_chage.py:业务数据变更"
    "freework_chage.py:自由工作数据变更"
    "process_db_async.py:加班数据异步处理"
    "overwork_chage_ai.py:AI加班数据变更"
    "attendance_summary.py:考勤汇总"
)

total_steps=${#scripts[@]}
current_step=0
overall_success=true

echo "🚀 开始执行完整数据处理流程..."
echo "总共 $total_steps 个步骤"
echo ""

# 执行所有脚本
for script_info in "${scripts[@]}"; do
    current_step=$((current_step + 1))
    
    # 解析脚本信息
    script_file=$(echo "$script_info" | cut -d':' -f1)
    script_name=$(echo "$script_info" | cut -d':' -f2)
    
    # 执行脚本
    if ! run_script "$script_name" "$script_file" "$current_step" "$total_steps"; then
        overall_success=false
        echo "❌ 在第 $current_step 步失败，停止执行"
        break
    fi
    
    # 在步骤之间添加短暂延迟
    if [ $current_step -lt $total_steps ]; then
        echo "⏳ 等待 2 秒后继续下一个步骤..."
        sleep 2
        echo ""
    fi
done

echo ""
echo "=========================================="
echo "完整流程执行完成时间: $(date '+%Y-%m-%d %H:%M:%S')"

# 检查整体执行结果
if [ "$overall_success" = true ]; then
    echo "🎉 所有脚本执行成功!"
    echo "📊 考勤分析完整流程已完成"
    echo "✅ 数据已成功处理并保存到数据库"
else
    echo "❌ 部分脚本执行失败"
    echo "📋 请检查上述错误信息和日志文件"
fi

echo ""
echo "📋 执行摘要:"
echo "- 总步骤数: $total_steps"
echo "- 成功步骤: $current_step"
echo "- 主日志文件: $log_file"
echo "- 各步骤日志: $log_dir/*_${timestamp}.log"
echo "=========================================="

# 返回适当的退出代码
if [ "$overall_success" = true ]; then
    exit 0
else
    exit 1
fi