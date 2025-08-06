import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2 import sql
from config import DB_CONFIG  # 导入数据库配置

def process_feishu_data():
    # 处理飞书数据
    file_path = '../data/original/overwork01.xlsx'
    df = pd.read_excel(file_path, skiprows=1)
    
    columns = ['发起人姓名', '开始时间', '结束时间', '时长', '详细说明（加班内容）','申请状态']
    result_df = df[columns].copy()
    
    result_df.columns = ['姓名', '开始时间', '结束时间', '加班时长(小时)', '加班说明','申请状态']
    result_df = result_df[result_df['申请状态'] == '已同意']
    
    # 转换日期格式
    def convert_feishu_date(date_str):
        if pd.isna(date_str):
            return date_str
        # 处理"2025年05月15日 xx:xx"格式
        parts = date_str.split()
        date_part = parts[0]  # 获取日期部分
        
        # 将中文日期格式转换为标准格式
        date_part = date_part.replace('年', '-').replace('月', '-').replace('日', '')
        return date_part if len(parts) == 1 else f"{date_part} {parts[1]}"

    result_df['开始时间'] = result_df['开始时间'].apply(convert_feishu_date)
    result_df['结束时间'] = result_df['结束时间'].apply(convert_feishu_date)
    
    # 添加数据来源标识
    result_df['数据来源'] = '飞书'
    return result_df

def process_dingding_data():
    # 处理钉钉数据
    file_path = '../data/original/overwork02.xlsx'
    df = pd.read_excel(file_path)
    
    columns = ['创建人', '开始时间', '结束时间', '时长（小时）', '详细说明（加班内容）','审批结果']
    result_df = df[columns].copy()
    
    result_df.columns = ['姓名', '开始时间', '结束时间', '加班时长(小时)', '加班说明','申请状态']
    result_df = result_df[result_df['申请状态'] == '审批通过']
    
    # 添加数据来源标识
    result_df['数据来源'] = '钉钉'
    return result_df

def save_to_database(df):
    """
    将数据保存到PostgreSQL数据库
    """
    # 连接PostgreSQL数据库
    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )
    cur = conn.cursor()
    
    try:
        # 获取列名并清理
        field_names = df.columns.tolist()
        cleaned_field_names = []
        for name in field_names:
            cleaned_name = str(name).strip()
            cleaned_name = cleaned_name.replace(' ', '_')
            cleaned_name = cleaned_name.replace('(', '')
            cleaned_name = cleaned_name.replace(')', '')
            cleaned_name = cleaned_name.replace('/', '_')
            cleaned_name = cleaned_name.replace('（', '')
            cleaned_name = cleaned_name.replace('）', '')
            cleaned_field_names.append(cleaned_name)
        
        # 更新DataFrame的列名
        df.columns = cleaned_field_names
        
        # 先删除已存在的表
        cur.execute("DROP TABLE IF EXISTS overwork")
        conn.commit()
        
        # 创建新表
        create_table_query = sql.SQL("CREATE TABLE overwork ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col))
                for col in cleaned_field_names
            )
        )
        cur.execute(create_table_query)
        
        # 构建INSERT语句
        insert_query = sql.SQL("INSERT INTO overwork ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cleaned_field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(cleaned_field_names))
        )
        
        # 插入数据
        for _, row in df.iterrows():
            values = [str(val) if pd.notna(val) else None for val in row]
            cur.execute(insert_query, values)
        
        conn.commit()
        print("数据已成功导入PostgreSQL数据库的overwork表")
        
    except Exception as e:
        print(f"数据库操作出错: {e}")
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()

def main():
    # 导入月份配置
    from holidays import MONTH
    
    # 处理两个数据源
    feishu_df = process_feishu_data()
    dingding_df = process_dingding_data()
    
    # 合并数据框
    combined_df = pd.concat([feishu_df, dingding_df], ignore_index=True)
    
    # 将日期时间字符串转换为datetime对象进行筛选
    combined_df['处理日期'] = pd.to_datetime(combined_df['开始时间'])
    
    # 筛选指定月份的数据
    combined_df = combined_df[combined_df['处理日期'].dt.strftime('%m') == MONTH]
    
    # 删除临时列
    combined_df = combined_df.drop('处理日期', axis=1)
    
    # 按姓名和开始时间排序
    combined_df = combined_df.sort_values(by=['姓名', '开始时间'])
    
    print(f"飞书数据记录数: {len(feishu_df)}")
    print(f"钉钉数据记录数: {len(dingding_df)}")
    print(f"合并后筛选{MONTH}月份总记录数: {len(combined_df)}")
    # 保存到数据库
    save_to_database(combined_df)

if __name__ == "__main__":
    main()