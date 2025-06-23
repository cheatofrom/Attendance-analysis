import psycopg2
import re
from datetime import datetime, timedelta
import pandas as pd
from holidays import HOLIDAYS
from psycopg2 import sql
from config import DB_CONFIG
import sys
import calendar
from holidays import MONTH, YEAR

# 强制刷新输出缓冲区
def flush_print(*args, **kwargs):
    """带缓冲刷新的print函数"""
    print(*args, **kwargs)
    sys.stdout.flush()

# 修改pandas显示设置
pd.set_option('display.max_columns', None)  # 显示所有列
pd.set_option('display.width', None)        # 设置显示宽度为无限制
pd.set_option('display.max_colwidth', None) # 设置列宽度为无限制
pd.set_option('display.max_rows', 50)       # 显示50行数据
pd.set_option('display.min_rows', 50)       # 最少显示50行

# 基础字段定义
basic_fields = ['姓名', '考勤组', '部门', '工号', '职位', 'UserId']
# 动态获取当月天数
total_days = calendar.monthrange(YEAR, int(MONTH))[1]
# 修改 day_columns 的定义，使用数字格式
day_columns = [f"{i:02d}" for i in range(1, total_days + 1)]
all_columns = basic_fields + day_columns

# 打卡时间规则常量
MORNING_LIMIT = datetime.strptime("08:33", "%H:%M")
EVENING_LIMIT = datetime.strptime("18:00", "%H:%M")
HALF_DAY_ABSENT = timedelta(minutes=30)   # 迟到30分钟起算旷工0.5天
FULL_DAY_ABSENT = timedelta(hours=3)      # 迟到3小时及以上算旷工1天
EARLY_LEAVE_THRESHOLD = timedelta(minutes=30)  # 早退30分钟判定标准

def get_db_connection():
    """创建数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def process_excel_file(file_path, expected_columns=37):
    """
    处理Excel文件：只读取第一个sheet，从第4行开始读取，删除空白行，确保指定列数
    
    参数:
        file_path (str): Excel文件路径
        expected_columns (int): 期望的列数(默认为37)
    
    返回:
        pd.DataFrame: 处理后的DataFrame
    """
    try:
        # 读取Excel文件，跳过前3行
        df = pd.read_excel(file_path, sheet_name=0, skiprows=3)
        flush_print(f"✅ 原始数据形状: {df.shape} (行×列)")
        
        # 设置前6列的列名
        column_names = ['姓名', '考勤组', '部门', '工号', '职位', 'UserId']
        # 从第7列开始，列名设置为01,02,03...
        remaining_columns = [f"{i:02d}" for i in range(1, len(df.columns)-5)]
        df.columns = column_names + remaining_columns
        
        # 删除完全空白的行（更严格的清理）
        df_cleaned = df.dropna(how='all')
        # 删除所有列都为NaN或空字符串的行
        df_cleaned = df_cleaned.loc[~df_cleaned.apply(lambda x: x.isna().all() or (x == '').all(), axis=1)]
        
        # 处理列数
        current_columns = len(df_cleaned.columns)
        
        if current_columns < expected_columns:
            # 如果列数不足，添加空列
            for i in range(current_columns, expected_columns):
                df_cleaned[f'空白列_{i+1}'] = None
            flush_print(f"✅ 已添加 {expected_columns - current_columns} 个空白列")
        elif current_columns > expected_columns:
            # 如果列数过多，截断到指定列数
            df_cleaned = df_cleaned.iloc[:, :expected_columns]
            flush_print(f"✅ 已截断 {current_columns - expected_columns} 列")
        
        # 最终清理
        # 1. 删除所有完全为空的行
        df_cleaned = df_cleaned.dropna(how='all')
        # 2. 重置索引
        df_cleaned = df_cleaned.reset_index(drop=True)
        # 3. 删除末尾的空行
        last_valid_index = df_cleaned.apply(lambda x: x.notna().any() or (x != '').any(), axis=1).values.argmin()
        if last_valid_index > 0:
            df_cleaned = df_cleaned.iloc[:last_valid_index]
        
        # 找到最后一个非空行的索引
        last_valid_row = None
        for idx in range(len(df_cleaned)-1, -1, -1):
            row = df_cleaned.iloc[idx]
            if not row.isna().all() and not (row == '').all():
                last_valid_row = idx
                break
        
        # 只保留到最后一个非空行
        if last_valid_row is not None:
            df_cleaned = df_cleaned.iloc[:last_valid_row + 1]
        
        flush_print(f"✅ 最终数据形状: {df_cleaned.shape} (确保为 {expected_columns} 列)")
        return df_cleaned
    except Exception as e:
        flush_print(f"❌ 处理文件时出错: {e}")
        return None

def create_basic_table(conn, field_names):
    """创建基础数据表"""
    cursor = conn.cursor()
    
    try:
        # 先删除已存在的表
        cursor.execute("DROP TABLE IF EXISTS basic")
        conn.commit()
        
        # 创建表，使用处理后的字段名
        create_table_query = sql.SQL("CREATE TABLE basic ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col))  # 使用TEXT类型而不是VARCHAR
                for col in field_names
            )
        )
        cursor.execute(create_table_query)
        conn.commit()
        flush_print("✅ 基础数据表创建成功")
    except Exception as e:
        flush_print(f"❌ 创建基础表失败: {e}")
        conn.rollback()
    finally:
        cursor.close()

def save_basic_data_to_db(conn, processed_data, field_names):
    """将基础数据保存到数据库"""
    cursor = conn.cursor()
    
    try:
        # 构建INSERT语句
        insert_query = sql.SQL("INSERT INTO basic ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(field_names))
        )
        
        # 插入数据
        for _, row in processed_data.iterrows():
            values = [str(val) if pd.notna(val) else None for val in row]  # 使用None代替空字符串
            cursor.execute(insert_query, values)
        
        conn.commit()
        flush_print("✅ 基础数据已成功导入PostgreSQL数据库")
    except Exception as e:
        flush_print(f"❌ 保存基础数据失败: {e}")
        conn.rollback()
    finally:
        cursor.close()

def create_result_table(conn):
    """创建考勤结果表"""
    cursor = conn.cursor()
    
    # 基础字段
    basic_fields = ['姓名', '考勤组', '部门', '工号', '职位', 'UserId']
    # 每日考勤字段
    day_fields = [f'第{i}天' for i in range(1, 32)]
    
    # 所有字段(移除统计字段)
    all_fields = basic_fields + day_fields
    
    # 创建表SQL
    create_table_sql = sql.SQL("CREATE TABLE IF NOT EXISTS attendance_result ({})").format(
        sql.SQL(', ').join(
            sql.SQL("{} TEXT").format(sql.Identifier(field))
            for field in all_fields
        )
    )
    
    try:
        cursor.execute("DROP TABLE IF EXISTS attendance_result")
        cursor.execute(create_table_sql)
        conn.commit()
        flush_print("✅ 考勤结果表创建成功")
    except Exception as e:
        flush_print(f"❌ 创建考勤结果表失败: {e}")
        conn.rollback()
    finally:
        cursor.close()

def save_results_to_db(conn, data):
    """将考勤分析结果保存到数据库"""
    cursor = conn.cursor()
    
    # 准备INSERT语句
    fields = list(data[0].keys())
    insert_sql = sql.SQL("INSERT INTO attendance_result ({}) VALUES ({})").format(
        sql.SQL(', ').join(map(sql.Identifier, fields)),
        sql.SQL(', ').join(sql.Placeholder() * len(fields))
    )
    
    try:
        # 批量插入数据
        for row in data:
            # 处理nan值
            values = [
                (str(val) if val not in (None, 'nan', 'None', '') else '')
                for val in row.values()
            ]
            cursor.execute(insert_sql, values)
        
        conn.commit()
        flush_print("✅ 考勤分析结果已保存到数据库")
    except Exception as e:
        flush_print(f"❌ 保存考勤结果失败: {e}")
        conn.rollback()
    finally:
        cursor.close()

def extract_times(cell):
    """提取 HH:MM 格式的时间"""
    if not cell:
        return []
    times = re.findall(r"\d{2}:\d{2}", str(cell))
    return [datetime.strptime(t.strip(), "%H:%M") for t in times]

def analyze_day(cell, day):
    """分析单日考勤情况"""
    times = extract_times(cell)
    
    # 如果是休息日
    if f"{day:02d}" in HOLIDAYS:
        if not times:
            return ""
        else:
            return str(cell) if cell not in (None, 'nan', 'None') else ""
    
    # 工作日逻辑
    if not times or len(times) < 2:
        if cell and cell not in (None, 'nan', 'None'):
            return f"缺卡(1天) {str(cell)}"
        return "缺卡(1天)"
    
    morning = min(times)
    evening = max(times)
    
    # 初始化违规时长
    morning_late = timedelta()
    evening_early = timedelta()
    
    # 计算迟到时长
    if morning > MORNING_LIMIT:
        morning_late = datetime.combine(datetime.today(), morning.time()) - \
                      datetime.combine(datetime.today(), MORNING_LIMIT.time())
    
    # 计算早退时长（只在下午判断）
    if evening.hour >= 12 and evening < EVENING_LIMIT:
        evening_early = datetime.combine(datetime.today(), EVENING_LIMIT.time()) - \
                       datetime.combine(datetime.today(), evening.time())
    
    times_str = f"({morning.strftime('%H:%M')}, {evening.strftime('%H:%M')})"
    
    # 判断考勤状态
    # 1. 优先判断旷工
    if morning_late >= FULL_DAY_ABSENT:
        return f"旷工1天{times_str}"
    elif HALF_DAY_ABSENT <= morning_late < FULL_DAY_ABSENT:
        return f"旷工0.5天{times_str}"
    
    # 2. 判断迟到和早退
    reasons = []
    if morning_late > timedelta():  # 有迟到就记录
        reasons.append("迟到")
    if evening.hour >= 12 and evening_early >= EARLY_LEAVE_THRESHOLD:  # 早退必须满足两个条件：在下午且提前30分钟以上
        reasons.append("早退")
    
    # 3. 返回最终结果
    if not reasons:
        return f"正常{times_str}"
    else:
        return f"{'+'.join(reasons)}{times_str}"

def analyze_results(rows):
    """分析考勤结果"""
    data = []
    for row in rows:
        record = dict(zip(all_columns, row)) if isinstance(row, tuple) else row
        result_row = {key: record[key] for key in basic_fields}
        
        for i, col in enumerate(day_columns, start=1):
            result = analyze_day(record[col], i)
            result_row[f"第{i}天"] = result if result else ""
            
        data.append(result_row)
    return data

def main():
    flush_print("🔄 开始执行基础数据合并处理...")
    flush_print("📊 正在连接数据库...")
    
    # 连接数据库
    conn = get_db_connection()
    
    try:
        flush_print("📁 正在处理原始Excel文件...")
        # 1. 处理原始Excel文件
        input_file = "../data/original/basic.xlsx"
        processed_data = process_excel_file(input_file)
        
        if processed_data is None:
            raise Exception("Excel处理失败")
        
        flush_print("🔧 正在处理字段名...")
        # 2. 处理字段名
        field_names = processed_data.columns.tolist()
        
        # 将字段名中的特殊字符替换为下划线，确保字段名有效
        cleaned_field_names = []
        for name in field_names:
            # 清理字段名
            cleaned_name = str(name).strip()
            cleaned_name = cleaned_name.replace(' ', '_')
            cleaned_name = cleaned_name.replace('/', '_')
            cleaned_name = cleaned_name.replace('(', '')
            cleaned_name = cleaned_name.replace(')', '')
            cleaned_name = cleaned_name.replace('.', '_')
            cleaned_name = cleaned_name.replace('\n', '_')
            # 确保字段名以字母开头
            if cleaned_name[0].isdigit():
                cleaned_name = 'column_' + cleaned_name  # 修改前缀为 column_
            cleaned_field_names.append(cleaned_name)
        
        flush_print("🗄️ 正在创建基础数据表...")
        # 3. 创建基础数据表并保存数据
        create_basic_table(conn, cleaned_field_names)
        save_basic_data_to_db(conn, processed_data, cleaned_field_names)
        
        flush_print("📋 正在创建考勤结果表...")
        # 4. 创建考勤结果表
        create_result_table(conn)
        
        flush_print("🔍 正在分析考勤数据...")
        # 5. 分析考勤数据
        data = analyze_results(processed_data.to_dict('records'))
        
        flush_print("💾 正在保存考勤分析结果...")
        # 6. 保存考勤分析结果到数据库
        save_results_to_db(conn, data)
        
        flush_print("✅ 基础数据合并处理完成！")
        
    except Exception as e:
        flush_print(f"❌ 程序执行出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()