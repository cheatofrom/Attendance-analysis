import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2 import sql

def process_feishu_data():
    # 处理飞书数据
    file_path = '../data/original/freework01.xlsx'
    df = pd.read_excel(file_path, skiprows=1)
    
    # 打印列名，用于调试
    
    columns = ['发起人姓名', '开始时间', '结束时间', '时长', '请假事由','申请状态','假期类型']
    result_df = df[columns].copy()
    
    result_df.columns = ['姓名', '开始时间', '结束时间', '时长', '请假说明','申请状态','请假类型']
    result_df = result_df[result_df['申请状态'] == '已同意']
    
    # 将时长转为字符串并添加"天"单位
    result_df['时长'] = result_df['时长'].astype(str) + '天'
    
    # 转换日期格式
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

    result_df['开始时间'] = result_df['开始时间'].apply(convert_feishu_date)
    result_df['结束时间'] = result_df['结束时间'].apply(convert_feishu_date)
    
    # 添加数据来源标识
    result_df['数据来源'] = '飞书'
    return result_df

def process_dingding_data():
    # 处理钉钉数据
    file_path = '../data/original/freework02.xlsx'
    df = pd.read_excel(file_path)
    
    
    # 修改为实际的列名
    columns = ['创建人', '开始时间', '结束时间', '时长', '请假事由', '审批结果','请假类型']
    result_df = df[columns].copy()
    
    # 重命名列以匹配目标格式
    result_df.columns = ['姓名', '开始时间', '结束时间', '时长', '请假说明', '申请状态','请假类型']
    result_df = result_df[result_df['申请状态'] == '审批通过']
    
    # 保持时长字段为字符串格式
    result_df['时长'] = result_df['时长'].astype(str)
    
    # 转换日期格式
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

    result_df['开始时间'] = result_df['开始时间'].apply(convert_dingding_date)
    result_df['结束时间'] = result_df['结束时间'].apply(convert_dingding_date)
    
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
        cur.execute("DROP TABLE IF EXISTS freework")
        conn.commit()
        
        # 创建新表
        create_table_query = sql.SQL("CREATE TABLE freework ({})").format(
            sql.SQL(', ').join(
                sql.SQL("{} TEXT").format(sql.Identifier(col))
                for col in cleaned_field_names
            )
        )
        cur.execute(create_table_query)
        
        # 构建INSERT语句
        insert_query = sql.SQL("INSERT INTO freework ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cleaned_field_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(cleaned_field_names))
        )
        
        # 插入数据
        for _, row in df.iterrows():
            values = [str(val) if pd.notna(val) else None for val in row]
            cur.execute(insert_query, values)
        
        conn.commit()
        print("数据已成功导入PostgreSQL数据库的freework表")
        
    except Exception as e:
        print(f"数据库操作出错: {e}")
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()

def main():
    print("🔄 开始执行自由工作数据合并处理...")
    
    # 导入月份配置
    from holidays import MONTH
    
    print("📁 正在处理飞书数据...")
    # 处理两个数据源
    feishu_df = process_feishu_data()
    
    print("📁 正在处理钉钉数据...")
    dingding_df = process_dingding_data()
    
    print("🔗 正在合并数据...")
    # 合并数据框
    combined_df = pd.concat([feishu_df, dingding_df], ignore_index=True)
    
    print("📅 正在处理日期格式...")
    # 将日期时间字符串转换为datetime对象进行筛选
    combined_df['处理日期'] = combined_df['开始时间'].apply(lambda x: pd.to_datetime(x.split()[0] if pd.notna(x) else None))
    
    print(f"📊 正在筛选{MONTH}月份数据...")
    # 筛选指定月份的数据
    combined_df = combined_df[combined_df['处理日期'].dt.strftime('%m') == MONTH]
    
    # 删除临时列
    combined_df = combined_df.drop('处理日期', axis=1)
    
    print("📋 正在排序数据...")
    # 按姓名和开始时间排序
    combined_df = combined_df.sort_values(by=['姓名', '开始时间'])
    
    print("💾 正在保存到数据库...")
    # 保存到数据库
    save_to_database(combined_df)
    
    print("✅ 自由工作数据合并处理完成！")

if __name__ == "__main__":
    main()