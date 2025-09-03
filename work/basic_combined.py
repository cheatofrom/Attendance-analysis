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
from logger_utils import create_logger

# 创建日志记录器
logger = create_logger("基础数据合并处理")

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
        logger.log_file_operation("开始读取Excel文件", file_path)
        
        # 读取Excel文件，跳过前3行
        df = pd.read_excel(file_path, sheet_name=0, skiprows=3)
        
        # 计算文件大小
        import os
        file_size = f"{os.path.getsize(file_path) / 1024 / 1024:.2f}MB"
        logger.log_file_operation("Excel文件读取完成", file_path, file_size)
        logger.log_info(f"原始数据形状: {df.shape[0]}行 × {df.shape[1]}列")
        
        # 设置前6列的列名
        column_names = ['姓名', '考勤组', '部门', '工号', '职位', 'UserId']
        # 从第7列开始，列名设置为01,02,03...
        remaining_columns = [f"{i:02d}" for i in range(1, len(df.columns)-5)]
        df.columns = column_names + remaining_columns
        logger.log_info(f"列名设置完成，共{len(df.columns)}列", f"基础字段: {len(column_names)}列, 日期字段: {len(remaining_columns)}列")
        
        # 删除完全空白的行（更严格的清理）
        original_rows = len(df)
        logger.log_info("开始清理空白行数据")
        
        df_cleaned = df.dropna(how='all')
        # 删除所有列都为NaN或空字符串的行
        df_cleaned = df_cleaned.loc[~df_cleaned.apply(lambda x: x.isna().all() or (x == '').all(), axis=1)]
        
        removed_rows = original_rows - len(df_cleaned)
        logger.log_info(f"空白行清理完成", f"删除了{removed_rows}行空白数据，剩余{len(df_cleaned)}行")
        
        # 处理列数
        current_columns = len(df_cleaned.columns)
        logger.log_info(f"开始处理列数标准化", f"当前列数: {current_columns}, 期望列数: {expected_columns}")
        
        if current_columns < expected_columns:
            # 如果列数不足，添加空列
            for i in range(current_columns, expected_columns):
                df_cleaned[f'空白列_{i+1}'] = None
            logger.log_info(f"列数补齐完成", f"添加了{expected_columns - current_columns}个空白列")
        elif current_columns > expected_columns:
            # 如果列数过多，截断到指定列数
            df_cleaned = df_cleaned.iloc[:, :expected_columns]
            logger.log_info(f"列数截断完成", f"截断了{current_columns - expected_columns}列")
        
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
        
        logger.log_info(f"Excel文件处理完成", f"最终数据形状: {df_cleaned.shape[0]}行 × {df_cleaned.shape[1]}列")
        return df_cleaned
    except Exception as e:
        logger.log_error(f"处理Excel文件失败", e, f"文件路径: {file_path}")
        return None

def create_basic_table(conn, field_names):
    """创建基础数据表"""
    cursor = conn.cursor()
    
    try:
        logger.log_database_operation("删除已存在的表", "basic")
        # 先删除已存在的表
        cursor.execute("DROP TABLE IF EXISTS basic")
        conn.commit()
        
        logger.log_database_operation("创建新表", "basic")
        logger.log_info(f"表结构设计", f"字段数量: {len(field_names)}, 字段类型: TEXT")
        
        # 创建表，使用处理后的字段名
        create_table_query = sql.SQL("CREATE TABLE basic ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col))  # 使用TEXT类型而不是VARCHAR
                for col in field_names
            )
        )
        cursor.execute(create_table_query)
        conn.commit()
        logger.log_database_operation("表创建成功", "basic")
    except Exception as e:
        logger.log_error(f"创建基础数据表失败", e, f"字段数量: {len(field_names)}")
        conn.rollback()
    finally:
        cursor.close()

def save_basic_data_to_db(conn, processed_data, field_names):
    """将基础数据保存到数据库"""
    cursor = conn.cursor()
    
    try:
        total_rows = len(processed_data)
        logger.log_database_operation("开始批量插入数据", "basic", total_rows)
        
        # 构建INSERT语句
        insert_query = sql.SQL("INSERT INTO basic ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(field_names))
        )
        
        # 插入数据
        for idx, (_, row) in enumerate(processed_data.iterrows(), 1):
            values = [str(val) if pd.notna(val) else None for val in row]  # 使用None代替空字符串
            cursor.execute(insert_query, values)
            
            # 每100行记录一次进度
            if idx % 100 == 0 or idx == total_rows:
                logger.log_data_processing("插入基础数据", idx, total_rows, f"当前行: {row.get('姓名', 'N/A')}")
        
        conn.commit()
        logger.log_database_operation("数据插入完成", "basic", total_rows)
    except Exception as e:
        logger.log_error(f"保存基础数据失败", e, f"总行数: {len(processed_data)}, 字段数: {len(field_names)}")
        conn.rollback()
    finally:
        cursor.close()

def create_result_table(conn):
    """创建考勤结果表"""
    cursor = conn.cursor()
    
    # 基础字段
    basic_fields = ['姓名', '考勤组', '部门', '工号', '职位', 'UserId']
    # 每日考勤字段
    day_fields = [f'第{i}天' for i in range(1, total_days + 1)]

    
    # 所有字段(移除统计字段)
    all_fields = basic_fields + day_fields
    
    logger.log_database_operation("删除已存在的考勤结果表", "attendance_result")
    logger.log_info(f"考勤结果表结构设计", f"基础字段: {len(basic_fields)}个, 日期字段: {len(day_fields)}个, 总字段: {len(all_fields)}个")
    
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
        logger.log_database_operation("考勤结果表创建成功", "attendance_result")
    except Exception as e:
        logger.log_error(f"创建考勤结果表失败", e, f"字段数量: {len(all_fields)}")
        conn.rollback()
    finally:
        cursor.close()

def save_results_to_db(conn, data):
    """将考勤分析结果保存到数据库"""
    cursor = conn.cursor()
    
    total_rows = len(data)
    logger.log_database_operation("开始保存考勤分析结果", "attendance_result", total_rows)
    
    # 准备INSERT语句
    fields = list(data[0].keys())
    insert_sql = sql.SQL("INSERT INTO attendance_result ({}) VALUES ({})").format(
        sql.SQL(', ').join(map(sql.Identifier, fields)),
        sql.SQL(', ').join(sql.Placeholder() * len(fields))
    )
    
    try:
        # 批量插入数据
        for idx, row in enumerate(data, 1):
            # 处理nan值
            values = [
                (str(val) if val not in (None, 'nan', 'None', '') else '')
                for val in row.values()
            ]
            cursor.execute(insert_sql, values)
            
            # 每50行记录一次进度
            if idx % 50 == 0 or idx == total_rows:
                logger.log_data_processing("保存考勤结果", idx, total_rows, f"当前员工: {row.get('姓名', 'N/A')}")
        
        conn.commit()
        logger.log_database_operation("考勤分析结果保存完成", "attendance_result", total_rows)
    except Exception as e:
        logger.log_error(f"保存考勤结果失败", e, f"总行数: {total_rows}, 字段数: {len(fields)}")
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
    if not times:
        # 没有打卡记录，算作2次缺卡
        if cell and cell not in (None, 'nan', 'None'):
            return f"缺卡(2次) {str(cell)}"
        return "缺卡(2次)"
    elif len(times) == 1:
        # 只有1次打卡记录，算作1次缺卡
        if cell and cell not in (None, 'nan', 'None'):
            return f"缺卡(1次) {str(cell)}"
        return "缺卡(1次)"
    
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
    total_rows = len(rows)
    logger.log_info(f"开始分析考勤数据", f"总员工数: {total_rows}人, 分析天数: {len(day_columns)}天")
    
    for idx, row in enumerate(rows, 1):
        record = dict(zip(all_columns, row)) if isinstance(row, tuple) else row
        result_row = {key: record[key] for key in basic_fields}
        
        # 分析每一天的考勤情况
        for i, col in enumerate(day_columns, start=1):
            result = analyze_day(record[col], i)
            result_row[f"第{i}天"] = result if result else ""
            
        data.append(result_row)
        
        # 每20个员工记录一次进度
        if idx % 20 == 0 or idx == total_rows:
            employee_name = record.get('姓名', 'N/A')
            logger.log_data_processing("分析员工考勤", idx, total_rows, f"当前员工: {employee_name}")
    
    logger.log_info(f"考勤数据分析完成", f"共分析{total_rows}名员工的考勤数据")
    return data

def main():
    # 开始脚本执行，设置总步骤数
    logger.start_script(total_steps=6)
    
    try:
        # 步骤1: 连接数据库
        logger.start_step("连接数据库", 1)
        conn = get_db_connection()
        logger.complete_step("数据库连接")
        
        # 步骤2: 处理原始Excel文件
        logger.start_step("处理原始Excel文件", 2)
        input_file = "../data/original/basic.xlsx"
        processed_data = process_excel_file(input_file)
        
        if processed_data is None:
            raise Exception("Excel处理失败")
        logger.complete_step("Excel文件处理")
        
        # 步骤3: 处理字段名
        logger.start_step("处理和清理字段名", 3)
        field_names = processed_data.columns.tolist()
        
        # 将字段名中的特殊字符替换为下划线，确保字段名有效
        cleaned_field_names = []
        for idx, name in enumerate(field_names, 1):
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
            
            # 每10个字段记录一次进度
            if idx % 10 == 0 or idx == len(field_names):
                logger.log_progress("清理字段名", f"处理第{idx}个字段", idx, len(field_names), "个字段")
        
        logger.log_info(f"字段名处理完成", f"原始字段: {len(field_names)}个, 清理后字段: {len(cleaned_field_names)}个")
        logger.complete_step("字段名处理")
        
        # 步骤4: 创建基础数据表并保存数据
        logger.start_step("创建基础数据表并保存数据", 4)
        create_basic_table(conn, cleaned_field_names)
        save_basic_data_to_db(conn, processed_data, cleaned_field_names)
        logger.complete_step("基础数据表创建和数据保存")
        
        # 步骤5: 创建考勤结果表
        logger.start_step("创建考勤结果表", 5)
        create_result_table(conn)
        logger.complete_step("考勤结果表创建")
        
        # 步骤6: 分析考勤数据并保存结果
        logger.start_step("分析考勤数据并保存结果", 6)
        data = analyze_results(processed_data.to_dict('records'))
        save_results_to_db(conn, data)
        logger.complete_step("考勤数据分析和结果保存")
        
        # 脚本执行成功完成
        summary = f"成功处理{len(processed_data)}名员工的{len(day_columns)}天考勤数据"
        logger.finish_script(summary=summary)
        
    except Exception as e:
        logger.log_error(f"基础数据合并处理失败", e)
        logger.finish_script(summary="脚本执行过程中发生错误")
    finally:
        if 'conn' in locals():
            conn.close()
            logger.log_info("数据库连接已关闭")

if __name__ == "__main__":
    main()