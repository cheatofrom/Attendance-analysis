import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2 import sql
from logger_utils import create_logger  # 导入日志工具

# 创建日志记录器
logger = create_logger("freework_combine")

def process_feishu_data():
    # 处理飞书数据
    file_path = '../data/original/freework01.xlsx'
    logger.log_file_operation("开始读取飞书请假数据", file_path)
    
    df = pd.read_excel(file_path, skiprows=1)
    logger.log_info(f"飞书请假数据读取完成", f"原始数据行数: {len(df)}, 列数: {len(df.columns)}")
    
    columns = ['发起人姓名', '开始时间', '结束时间', '时长', '请假事由','申请状态','假期类型']
    result_df = df[columns].copy()
    logger.log_data_processing("提取指定列", len(columns), len(df.columns), "列")
    
    result_df.columns = ['姓名', '开始时间', '结束时间', '时长', '请假说明','申请状态','请假类型']
    logger.log_info("列名重命名完成")
    
    # 筛选已同意的申请
    before_filter = len(result_df)
    result_df = result_df[result_df['申请状态'] == '已同意']
    after_filter = len(result_df)
    logger.log_data_processing("筛选已同意申请", after_filter, before_filter, f"条记录，过滤掉{before_filter - after_filter}条")
    
    # 将时长转为字符串并添加"天"单位
    logger.log_info("开始处理时长字段")
    result_df['时长'] = result_df['时长'].astype(str) + '天'
    logger.log_info("时长字段处理完成", "添加'天'单位")
    
    # 转换日期格式
    logger.log_info("开始转换日期格式")
    def convert_feishu_date(date_str):
        if pd.isna(date_str):
            return date_str
        # 处理"2025年05月16日 上午"格式
        parts = date_str.split()
        date_part = parts[0]  # 获取日期部分
        time_part = parts[1] if len(parts) > 1 else ""  # 获取时间部分（上午/下午）
        
        date_obj = datetime.strptime(date_part, '%Y年%m月%d日')
        formatted_date = date_obj.strftime('%Y-%m-%d')
        return f"{formatted_date} {time_part}".strip()

    # 处理开始时间和结束时间
    for idx, row in result_df.iterrows():
        if (idx + 1) % 8 == 0 or (idx + 1) == len(result_df):
            employee_name = row.get('姓名', 'N/A')
            logger.log_data_processing("转换日期格式", idx + 1, len(result_df), f"当前员工: {employee_name}")
    
    result_df['开始时间'] = result_df['开始时间'].apply(convert_feishu_date)
    result_df['结束时间'] = result_df['结束时间'].apply(convert_feishu_date)
    logger.log_info("日期格式转换完成")
    
    # 添加数据来源标识
    result_df['数据来源'] = '飞书'
    logger.log_info(f"飞书请假数据处理完成", f"最终记录数: {len(result_df)}")
    return result_df

def process_dingding_data():
    # 处理钉钉数据
    file_path = '../data/original/freework02.xlsx'
    logger.log_file_operation("开始读取钉钉请假数据", file_path)
    
    df = pd.read_excel(file_path)
    logger.log_info(f"钉钉请假数据读取完成", f"原始数据行数: {len(df)}, 列数: {len(df.columns)}")
    
    # 修改为实际的列名
    columns = ['创建人', '开始时间', '结束时间', '时长', '请假事由', '审批结果','请假类型']
    result_df = df[columns].copy()
    logger.log_data_processing("提取指定列", len(columns), len(df.columns), "列")
    
    # 重命名列以匹配目标格式
    result_df.columns = ['姓名', '开始时间', '结束时间', '时长', '请假说明', '申请状态','请假类型']
    logger.log_info("列名重命名完成")
    
    # 筛选审批通过的申请
    before_filter = len(result_df)
    result_df = result_df[result_df['申请状态'] == '审批通过']
    after_filter = len(result_df)
    logger.log_data_processing("筛选审批通过申请", after_filter, before_filter, f"条记录，过滤掉{before_filter - after_filter}条")
    
    # 保持时长字段为字符串格式
    logger.log_info("开始处理时长字段")
    result_df['时长'] = result_df['时长'].astype(str)
    logger.log_info("时长字段处理完成", "转换为字符串格式")
    
    # 转换日期格式
    logger.log_info("开始转换日期格式")
    def convert_dingding_date(date_str):
        if pd.isna(date_str):
            return date_str
        # 处理"2025-05-06 18:00"格式
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            # 判断时间是上午还是下午
            hour = date_obj.hour
            time_period = "上午" if hour < 12 else "下午"
            # 返回日期和上午/下午标记
            return f"{date_obj.strftime('%Y-%m-%d')} {time_period}"
        except ValueError:
            # 如果解析失败，返回原始值
            return date_str

    # 处理开始时间和结束时间
    for idx, row in result_df.iterrows():
        if (idx + 1) % 8 == 0 or (idx + 1) == len(result_df):
            employee_name = row.get('姓名', 'N/A')
            logger.log_data_processing("转换日期格式", idx + 1, len(result_df), f"当前员工: {employee_name}")
    
    result_df['开始时间'] = result_df['开始时间'].apply(convert_dingding_date)
    result_df['结束时间'] = result_df['结束时间'].apply(convert_dingding_date)
    logger.log_info("日期格式转换完成")
    
    # 添加数据来源标识
    result_df['数据来源'] = '钉钉'
    logger.log_info(f"钉钉请假数据处理完成", f"最终记录数: {len(result_df)}")
    return result_df

def save_to_database(df):
    """
    将数据保存到PostgreSQL数据库
    """
    total_rows = len(df)
    logger.log_database_operation("开始连接数据库", "freework")
    
    # 连接PostgreSQL数据库
    conn = psycopg2.connect(
        host="192.168.1.66",
        port="7432",
        database="dingding",
        user="root",
        password="123456"
    )
    cur = conn.cursor()
    logger.log_database_operation("数据库连接成功", "freework")
    
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
        logger.log_database_operation("删除已存在的表", "freework")
        cur.execute("DROP TABLE IF EXISTS freework")
        conn.commit()
        
        # 创建新表
        logger.log_database_operation("创建新表", "freework")
        logger.log_info(f"表结构设计", f"字段数量: {len(cleaned_field_names)}, 字段类型: TEXT")
        create_table_query = sql.SQL("CREATE TABLE freework ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col))
                for col in cleaned_field_names
            )
        )
        cur.execute(create_table_query)
        logger.log_database_operation("表创建成功", "freework")
        
        # 构建INSERT语句
        logger.log_database_operation("开始批量插入数据", "freework", total_rows)
        insert_query = sql.SQL("INSERT INTO freework ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cleaned_field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(cleaned_field_names))
        )
        
        # 插入数据
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            values = [str(val) if pd.notna(val) else None for val in row]
            cur.execute(insert_query, values)
            
            # 每10行记录一次进度
            if idx % 10 == 0 or idx == total_rows:
                employee_name = row.get('姓名', 'N/A')
                logger.log_data_processing("插入请假数据", idx, total_rows, f"当前员工: {employee_name}")
        
        conn.commit()
        logger.log_database_operation("数据插入完成", "freework", total_rows)
        
    except Exception as e:
        logger.log_error(f"数据库操作失败", e, f"总行数: {total_rows}, 字段数: {len(df.columns)}")
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()
        logger.log_info("数据库连接已关闭")

def main():
    # 开始脚本执行，设置总步骤数
    logger.start_script(total_steps=6)
    
    try:
        # 导入月份配置
        from holidays import MONTH
        logger.log_info(f"开始处理{MONTH}月份请假数据")
        
        # 步骤1: 处理飞书数据
        logger.start_step("处理飞书请假数据", 1)
        feishu_df = process_feishu_data()
        logger.complete_step("飞书数据处理")
        
        # 步骤2: 处理钉钉数据
        logger.start_step("处理钉钉请假数据", 2)
        dingding_df = process_dingding_data()
        logger.complete_step("钉钉数据处理")
        
        # 步骤3: 合并数据框
        logger.start_step("合并两个数据源", 3)
        combined_df = pd.concat([feishu_df, dingding_df], ignore_index=True)
        logger.log_info(f"数据合并完成", f"飞书: {len(feishu_df)}条, 钉钉: {len(dingding_df)}条, 合并后: {len(combined_df)}条")
        logger.complete_step("数据合并")
        
        # 步骤4: 日期处理和筛选
        logger.start_step(f"筛选{MONTH}月份数据", 4)
        # 将日期时间字符串转换为datetime对象进行筛选
        combined_df['处理日期'] = combined_df['开始时间'].apply(lambda x: pd.to_datetime(x.split()[0] if pd.notna(x) else None))
        logger.log_info("日期转换完成")
        
        # 筛选指定月份的数据
        before_filter = len(combined_df)
        combined_df = combined_df[combined_df['处理日期'].dt.strftime('%m') == MONTH]
        after_filter = len(combined_df)
        
        # 删除临时列
        combined_df = combined_df.drop('处理日期', axis=1)
        
        logger.log_info(f"{MONTH}月份数据筛选完成", f"筛选前: {before_filter}条, 筛选后: {after_filter}条")
        logger.complete_step("月份数据筛选")
        
        # 步骤5: 数据排序
        logger.start_step("数据排序", 5)
        # 按姓名和开始时间排序
        combined_df = combined_df.sort_values(by=['姓名', '开始时间'])
        logger.log_info("数据排序完成", "按姓名和开始时间排序")
        logger.complete_step("数据排序")
        
        # 步骤6: 保存到数据库
        logger.start_step("保存到数据库", 6)
        save_to_database(combined_df)
        logger.complete_step("数据保存")
        
        # 脚本执行成功完成
        summary = f"成功处理{len(combined_df)}条{MONTH}月份请假记录"
        logger.finish_script(summary=summary)
        
    except Exception as e:
        logger.log_error(f"请假数据合并处理失败", e)
        logger.finish_script(summary="脚本执行过程中发生错误")

if __name__ == "__main__":
    main()