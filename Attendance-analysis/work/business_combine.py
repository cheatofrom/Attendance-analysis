import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2 import sql
from holidays import MONTH

def process_feishu_data():
    # 处理飞书数据
    file_path = '../data/original/business01.xlsx'
    df = pd.read_excel(file_path, skiprows=1)
    
    columns = ['发起人姓名',  '开始时间', '结束时间', '出差总时长（天）', '出差事由','申请状态', '同行人', '同行人.1']
    result_df = df[columns].copy()
    
    # 合并两个同行人列
    result_df['合并同行人'] = result_df['同行人'].fillna('') + ',' + result_df['同行人.1'].fillna('')
    # 清理合并后的同行人列（去除开头和结尾的逗号）
    result_df['合并同行人'] = result_df['合并同行人'].str.strip(',').str.strip()
    # 如果合并后为空字符串，则设为NaN
    result_df['合并同行人'] = result_df['合并同行人'].replace('', pd.NA)
    
    result_df.columns = ['姓名', '开始时间', '结束时间', '时长', '出差事由','申请状态', '同行人原始', '同行人.1原始', '同行人']
    result_df = result_df[result_df['申请状态'] == '已同意']
    
    # 添加数据来源标识
    result_df['数据来源'] = '飞书'
    return result_df

def process_dingding_data():
    # 处理钉钉数据
    file_path = '../data/original/business02.xlsx'
    df = pd.read_excel(file_path, skiprows=1)
    
    columns = ['创建人', '开始时间', '结束时间', '时长', '出差事由','审批结果', '同行人']
    result_df = df[columns].copy()
    
    result_df.columns = ['姓名','开始时间', '结束时间', '时长', '出差事由','申请状态', '同行人']
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
        host="192.168.1.66",
        port="7432",
        database="dingding",
        user="root",
        password="123456"
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
        cur.execute("DROP TABLE IF EXISTS business")
        conn.commit()
        
        # 创建新表
        create_table_query = sql.SQL("CREATE TABLE business ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col))
                for col in cleaned_field_names
            )
        )
        cur.execute(create_table_query)
        
        # 构建INSERT语句
        insert_query = sql.SQL("INSERT INTO business ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cleaned_field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(cleaned_field_names))
        )
        
        # 插入数据
        for _, row in df.iterrows():
            values = [str(val) if pd.notna(val) else None for val in row]
            cur.execute(insert_query, values)
        
        conn.commit()
        print("数据已成功导入PostgreSQL数据库的business表")
        
    except Exception as e:
        print(f"数据库操作出错: {e}")
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()

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
    # 处理两个数据源
    feishu_df = process_feishu_data()
    dingding_df = process_dingding_data()
    
    # 合并数据框
    combined_df = pd.concat([feishu_df, dingding_df], ignore_index=True)
    
    # 统一日期格式
    combined_df['开始时间'] = combined_df['开始时间'].str.replace('年', '-').str.replace('月', '-').str.replace('日', '')
    combined_df['结束时间'] = combined_df['结束时间'].str.replace('年', '-').str.replace('月', '-').str.replace('日', '')
    
    # 提取日期部分用于筛选
    combined_df['处理日期'] = combined_df['开始时间'].apply(clean_datetime)
    combined_df['处理日期'] = pd.to_datetime(combined_df['处理日期'])
    
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