import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2 import sql
from holidays import MONTH
from logger_utils import create_logger

# 创建日志记录器
logger = create_logger("出差数据合并处理")

def process_feishu_data():
    # 处理飞书数据
    file_path = '../data/original/business01.xlsx'
    logger.log_file_operation("开始读取飞书出差数据", file_path)
    
    df = pd.read_excel(file_path, skiprows=1)
    logger.log_info(f"飞书数据读取完成", f"原始数据: {df.shape[0]}行 × {df.shape[1]}列")
    
    columns = ['发起人姓名',  '开始时间', '结束时间', '出差总时长（天）','出差事由','申请状态', '同行人', '同行人.1']
    result_df = df[columns].copy()
    logger.log_info(f"飞书数据字段提取完成", f"提取{len(columns)}个关键字段")
    
    # 合并两个同行人列
    logger.log_info("开始处理飞书同行人数据合并")
    result_df['合并同行人'] = result_df['同行人'].fillna('') + ',' + result_df['同行人.1'].fillna('')
    # 清理合并后的同行人列（去除开头和结尾的逗号）
    result_df['合并同行人'] = result_df['合并同行人'].str.strip(',').str.strip()
    # 如果合并后为空字符串，则设为NaN
    result_df['合并同行人'] = result_df['合并同行人'].replace('', pd.NA)
    
    result_df.columns = ['姓名', '开始时间', '结束时间', '时长', '出差事由','申请状态', '同行人原始', '同行人.1原始', '同行人']
    
    # 筛选已同意的申请
    original_count = len(result_df)
    result_df = result_df[result_df['申请状态'] == '已同意']
    approved_count = len(result_df)
    logger.log_info(f"飞书数据状态筛选完成", f"原始记录: {original_count}条, 已同意: {approved_count}条")
    
    # 添加数据来源标识
    result_df['数据来源'] = '飞书'
    return result_df

def process_dingding_data():
    # 处理钉钉数据
    file_path = '../data/original/business02.xlsx'
    logger.log_file_operation("开始读取钉钉出差数据", file_path)
    
    df = pd.read_excel(file_path, skiprows=1)
    logger.log_info(f"钉钉数据读取完成", f"原始数据: {df.shape[0]}行 × {df.shape[1]}列")
    
    columns = ['创建人', '开始时间', '结束时间', '时长', '出差事由','审批结果', '同行人']
    result_df = df[columns].copy()
    logger.log_info(f"钉钉数据字段提取完成", f"提取{len(columns)}个关键字段")
    
    result_df.columns = ['姓名','开始时间', '结束时间', '时长', '出差事由','申请状态', '同行人']
    
    # 筛选审批通过的申请
    original_count = len(result_df)
    result_df = result_df[result_df['申请状态'] == '审批通过']
    approved_count = len(result_df)
    logger.log_info(f"钉钉数据状态筛选完成", f"原始记录: {original_count}条, 审批通过: {approved_count}条")
    
    # 添加数据来源标识
    result_df['数据来源'] = '钉钉'
    return result_df

def save_to_database(df):
    """
    将数据保存到PostgreSQL数据库
    """
    total_rows = len(df)
    logger.log_database_operation("开始连接数据库", "business")
    
    # 连接PostgreSQL数据库
    conn = psycopg2.connect(
        host="192.168.1.66",
        port="7432",
        database="dingding",
        user="root",
        password="123456"
    )
    cur = conn.cursor()
    logger.log_database_operation("数据库连接成功", "business")
    
    try:
        # 获取列名并清理
        logger.log_info("开始清理字段名", f"原始字段数: {len(df.columns)}")
        field_names = df.columns.tolist()
        cleaned_field_names = []
        for idx, name in enumerate(field_names, 1):
            cleaned_name = str(name).strip()
            cleaned_name = cleaned_name.replace(' ', '_')
            cleaned_name = cleaned_name.replace('(', '')
            cleaned_name = cleaned_name.replace(')', '')
            cleaned_name = cleaned_name.replace('/', '_')
            cleaned_name = cleaned_name.replace('（', '')
            cleaned_name = cleaned_name.replace('）', '')
            cleaned_field_names.append(cleaned_name)
            
            # 每10个字段记录一次进度
            if idx % 10 == 0 or idx == len(field_names):
                logger.log_progress("清理字段名", f"处理第{idx}个字段", idx, len(field_names), "个字段")
        
        # 更新DataFrame的列名
        df.columns = cleaned_field_names
        logger.log_info(f"字段名清理完成", f"清理后字段数: {len(cleaned_field_names)}")
        
        # 先删除已存在的表
        logger.log_database_operation("删除已存在的表", "business")
        cur.execute("DROP TABLE IF EXISTS business")
        conn.commit()
        
        # 创建新表
        logger.log_database_operation("创建新表", "business")
        logger.log_info(f"表结构设计", f"字段数量: {len(cleaned_field_names)}, 字段类型: TEXT")
        create_table_query = sql.SQL("CREATE TABLE business ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col))
                for col in cleaned_field_names
            )
        )
        cur.execute(create_table_query)
        logger.log_database_operation("表创建成功", "business")
        
        # 构建INSERT语句
        logger.log_database_operation("开始批量插入数据", "business", total_rows)
        insert_query = sql.SQL("INSERT INTO business ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cleaned_field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(cleaned_field_names))
        )
        
        # 插入数据
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            values = [str(val) if pd.notna(val) else None for val in row]
            cur.execute(insert_query, values)
            
            # 每20行记录一次进度
            if idx % 20 == 0 or idx == total_rows:
                employee_name = row.get('姓名', 'N/A')
                logger.log_data_processing("插入出差数据", idx, total_rows, f"当前员工: {employee_name}")
        
        conn.commit()
        logger.log_database_operation("数据插入完成", "business", total_rows)
        
    except Exception as e:
        logger.log_error(f"数据库操作失败", e, f"总行数: {total_rows}, 字段数: {len(df.columns)}")
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()
        logger.log_info("数据库连接已关闭")

def clean_datetime(date_str):
    """
    统一处理日期时间格式
    支持格式：
    - 2025-05-13 08:30
    - 2025-05-07 上午
    返回日期部分的字符串
    """
    if pd.isna(date_str):
        return date_str
    
    parts = date_str.split()
    if len(parts) >= 1:
        date_part = parts[0]  # 获取日期部分 (2025-05-13)
        return date_part
    return date_str

def main():
    # 开始脚本执行，设置总步骤数
    logger.start_script(total_steps=6)
    
    try:
        # 步骤1: 处理飞书数据
        logger.start_step("处理飞书出差数据", 1)
        feishu_df = process_feishu_data()
        logger.complete_step("飞书数据处理")
        
        # 步骤2: 处理钉钉数据
        logger.start_step("处理钉钉出差数据", 2)
        dingding_df = process_dingding_data()
        logger.complete_step("钉钉数据处理")
        
        # 步骤3: 合并数据框
        logger.start_step("合并两个数据源", 3)
        combined_df = pd.concat([feishu_df, dingding_df], ignore_index=True)
        logger.log_info(f"数据合并完成", f"飞书: {len(feishu_df)}条, 钉钉: {len(dingding_df)}条, 合并后: {len(combined_df)}条")
        logger.complete_step("数据合并")
        
        # 步骤4: 统一日期格式
        logger.start_step("统一日期格式", 4)
        combined_df['开始时间'] = combined_df['开始时间'].str.replace('年', '-').str.replace('月', '-').str.replace('日', '')
        combined_df['结束时间'] = combined_df['结束时间'].str.replace('年', '-').str.replace('月', '-').str.replace('日', '')
        logger.log_info("日期格式统一完成")
        logger.complete_step("日期格式处理")
        
        # 步骤5: 筛选指定月份数据
        logger.start_step(f"筛选{MONTH}月份数据", 5)
        # 提取日期部分用于筛选
        combined_df['处理日期'] = combined_df['开始时间'].apply(clean_datetime)
        combined_df['处理日期'] = pd.to_datetime(combined_df['处理日期'])
        
        # 筛选指定月份的数据
        before_filter = len(combined_df)
        combined_df = combined_df[combined_df['处理日期'].dt.strftime('%m') == MONTH]
        after_filter = len(combined_df)
        
        # 删除临时列
        combined_df = combined_df.drop('处理日期', axis=1)
        
        logger.log_info(f"{MONTH}月份数据筛选完成", f"筛选前: {before_filter}条, 筛选后: {after_filter}条")
        logger.complete_step("月份数据筛选")
        
        # 步骤6: 排序并保存到数据库
        logger.start_step("数据排序并保存到数据库", 6)
        # 按姓名和开始时间排序
        combined_df = combined_df.sort_values(by=['姓名', '开始时间'])
        logger.log_info("数据排序完成", "按姓名和开始时间排序")
        
        # 保存到数据库
        save_to_database(combined_df)
        logger.complete_step("数据保存")
        
        # 脚本执行成功完成
        summary = f"成功处理{len(combined_df)}条{MONTH}月份出差记录"
        logger.finish_script(summary=summary)
        
    except Exception as e:
        logger.log_error(f"出差数据合并处理失败", e)
        logger.finish_script(summary="脚本执行过程中发生错误")

if __name__ == "__main__":
    main()