import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2 import sql
from logger_utils import create_logger  # 导入日志工具

# 创建日志记录器
logger = create_logger("freework_combine")

# ----------------------------
# 辅助函数
# ----------------------------
def read_excel_auto(file_path, **kwargs):
    """
    根据文件后缀自动选择 engine 读取 Excel
    """
    if file_path.lower().endswith('.xls'):
        return pd.read_excel(file_path, engine='xlrd', **kwargs)
    else:  # 默认 .xlsx
        return pd.read_excel(file_path, engine='openpyxl', **kwargs)


def convert_feishu_date(date_str):
    """
    将飞书日期格式 "2025年05月16日 上午" 转为 "2025-05-16 上午"
    """
    if pd.isna(date_str):
        return date_str
    try:
        parts = date_str.split()
        date_part = parts[0]
        time_part = parts[1] if len(parts) > 1 else ""
        date_obj = datetime.strptime(date_part, '%Y年%m月%d日')
        formatted_date = date_obj.strftime('%Y-%m-%d')
        return f"{formatted_date} {time_part}".strip()
    except Exception:
        return date_str


def convert_dingding_date(date_str):
    """
    将钉钉日期格式 "2025-05-06 18:00" 转为 "2025-05-06 上午/下午"
    """
    if pd.isna(date_str):
        return date_str
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
        time_period = "上午" if date_obj.hour < 12 else "下午"
        return f"{date_obj.strftime('%Y-%m-%d')} {time_period}"
    except Exception:
        return date_str


# ----------------------------
# 数据处理函数
# ----------------------------
def process_feishu_data():
    file_path = '../data/original/freework01.xlsx'
    logger.log_file_operation("开始读取飞书请假数据", file_path)

    df = read_excel_auto(file_path, skiprows=1)
    logger.log_info("飞书请假数据读取完成", f"原始数据行数: {len(df)}, 列数: {len(df.columns)}")

    columns = ['发起人姓名', '开始时间', '结束时间', '时长', '请假事由','申请状态','假期类型']
    result_df = df[columns].copy()
    logger.log_data_processing("提取指定列", len(columns), len(df.columns), "列")

    result_df.columns = ['姓名', '开始时间', '结束时间', '时长', '请假说明','申请状态','请假类型']
    logger.log_info("列名重命名完成")

    # 筛选已同意申请
    before_filter = len(result_df)
    result_df = result_df[result_df['申请状态'] == '已同意']
    after_filter = len(result_df)
    logger.log_data_processing("筛选已同意申请", after_filter, before_filter, f"过滤掉 {before_filter - after_filter} 条")

    # 处理时长
    result_df['时长'] = result_df['时长'].astype(str) + '天'
    logger.log_info("时长字段处理完成", "添加'天'单位")

    # 转换日期格式
    result_df['开始时间'] = result_df['开始时间'].apply(convert_feishu_date)
    result_df['结束时间'] = result_df['结束时间'].apply(convert_feishu_date)
    logger.log_info("日期格式转换完成")

    # 添加数据来源
    result_df['数据来源'] = '飞书'
    logger.log_info("飞书请假数据处理完成", f"最终记录数: {len(result_df)}")
    return result_df


def process_dingding_data():
    file_path = '../data/original/freework02.xlsx'
    logger.log_file_operation("开始读取钉钉请假数据", file_path)

    df = read_excel_auto(file_path)
    logger.log_info("钉钉请假数据读取完成", f"原始数据行数: {len(df)}, 列数: {len(df.columns)}")

    columns = ['创建人', '开始时间', '结束时间', '时长', '请假事由', '审批结果','请假类型']
    result_df = df[columns].copy()
    logger.log_data_processing("提取指定列", len(columns), len(df.columns), "列")

    result_df.columns = ['姓名', '开始时间', '结束时间', '时长', '请假说明', '申请状态','请假类型']
    logger.log_info("列名重命名完成")

    # 筛选审批通过
    before_filter = len(result_df)
    result_df = result_df[result_df['申请状态'] == '审批通过']
    after_filter = len(result_df)
    logger.log_data_processing("筛选审批通过申请", after_filter, before_filter, f"过滤掉 {before_filter - after_filter} 条")

    # 时长字段转为字符串
    result_df['时长'] = result_df['时长'].astype(str)
    logger.log_info("时长字段处理完成", "转换为字符串格式")

    # 转换日期格式
    result_df['开始时间'] = result_df['开始时间'].apply(convert_dingding_date)
    result_df['结束时间'] = result_df['结束时间'].apply(convert_dingding_date)
    logger.log_info("日期格式转换完成")

    # 添加数据来源
    result_df['数据来源'] = '钉钉'
    logger.log_info("钉钉请假数据处理完成", f"最终记录数: {len(result_df)}")
    return result_df


# ----------------------------
# 数据库保存
# ----------------------------
def save_to_database(df):
    total_rows = len(df)
    logger.log_database_operation("开始连接数据库", "freework")

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
        # 清理字段名
        field_names = df.columns.tolist()
        cleaned_field_names = [str(name).strip().replace(' ', '_')
                               .replace('(', '').replace(')', '')
                               .replace('/', '_').replace('（','').replace('）','')
                               for name in field_names]
        df.columns = cleaned_field_names

        # 删除旧表
        cur.execute("DROP TABLE IF EXISTS freework")
        conn.commit()

        # 创建新表
        create_table_query = sql.SQL("CREATE TABLE freework ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col)) for col in cleaned_field_names
            )
        )
        cur.execute(create_table_query)
        conn.commit()

        # 插入数据
        insert_query = sql.SQL("INSERT INTO freework ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cleaned_field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(cleaned_field_names))
        )
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            values = [str(val) if pd.notna(val) else None for val in row]
            cur.execute(insert_query, values)

            if idx % 10 == 0 or idx == total_rows:
                employee_name = row.get('姓名', 'N/A')
                logger.log_data_processing("插入请假数据", idx, total_rows, f"当前员工: {employee_name}")

        conn.commit()
        logger.log_database_operation("数据插入完成", "freework", total_rows)

    except Exception as e:
        logger.log_error("数据库操作失败", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()
        logger.log_info("数据库连接已关闭")


# ----------------------------
# 主流程
# ----------------------------
def main():
    logger.start_script(total_steps=6)

    try:
        from holidays import MONTH
        logger.log_info(f"开始处理{MONTH}月份请假数据")

        # 1. 飞书
        logger.start_step("处理飞书请假数据", 1)
        feishu_df = process_feishu_data()
        logger.complete_step("飞书数据处理")

        # 2. 钉钉
        logger.start_step("处理钉钉请假数据", 2)
        dingding_df = process_dingding_data()
        logger.complete_step("钉钉数据处理")

        # 3. 合并
        logger.start_step("合并两个数据源", 3)
        combined_df = pd.concat([feishu_df, dingding_df], ignore_index=True)
        logger.log_info("数据合并完成", f"飞书: {len(feishu_df)}条, 钉钉: {len(dingding_df)}条, 合并后: {len(combined_df)}条")
        logger.complete_step("数据合并")

        # 4. 筛选月份
        logger.start_step(f"筛选{MONTH}月份数据", 4)
        combined_df['处理日期'] = combined_df['开始时间'].apply(lambda x: pd.to_datetime(x.split()[0] if pd.notna(x) else None))
        before_filter = len(combined_df)
        combined_df = combined_df[combined_df['处理日期'].dt.strftime('%m') == MONTH]
        after_filter = len(combined_df)
        combined_df = combined_df.drop('处理日期', axis=1)
        logger.log_info(f"{MONTH}月份数据筛选完成", f"筛选前: {before_filter}条, 筛选后: {after_filter}条")
        logger.complete_step("月份数据筛选")

        # 5. 排序
        logger.start_step("数据排序", 5)
        combined_df = combined_df.sort_values(by=['姓名', '开始时间'])
        logger.log_info("数据排序完成", "按姓名和开始时间排序")
        logger.complete_step("数据排序")

        # 6. 保存数据库
        logger.start_step("保存到数据库", 6)
        save_to_database(combined_df)
        logger.complete_step("数据保存")

        logger.finish_script(summary=f"成功处理{len(combined_df)}条{MONTH}月份请假记录")

    except Exception as e:
        logger.log_error("请假数据合并处理失败", e)
        logger.finish_script(summary="脚本执行过程中发生错误")


if __name__ == "__main__":
    main()
