import psycopg2
from datetime import datetime, timedelta, date
import pandas as pd
import sys
import os

# 添加work目录到系统路径，以便导入config和holidays模块
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work'))
from config import DB_CONFIG
import holidays

# 强制刷新输出缓冲区
def flush_print(*args, **kwargs):
    """带缓冲刷新的print函数"""
    print(*args, **kwargs)
    sys.stdout.flush()

def get_db_connection():
    """创建数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def get_llm_records(conn):
    """获取LLM处理后的加班记录"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 姓名, 
                   日期, 
                   时间, 
                   时长, 
                   加班说明, 
                   来源
            FROM llm_results
            ORDER BY 姓名, 日期
        """)
        records = cursor.fetchall()
        return records
    finally:
        cursor.close()

def update_attendance_for_overtime(cursor, name, date, overtime_hours, source, reason=""):
    """更新考勤记录中的加班信息"""
    try:
        # 获取该员工在该日期的考勤记录
        cursor.execute("SELECT * FROM attendance_result WHERE 姓名 = %s", (name,))
        employee_record = cursor.fetchone()
        
        if not employee_record:
            flush_print(f"❌ 未找到员工 {name} 的记录")
            return
        
        # 获取列名
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'attendance_result' ORDER BY ordinal_position")
        columns = [col[0] for col in cursor.fetchall()]
        
        # 创建列名到索引的映射
        col_index_map = {col: i for i, col in enumerate(columns)}
        
        # 将日期字符串转换为datetime对象
        if isinstance(date, str):
            date_obj = datetime.strptime(date, '%Y-%m-%d')
        elif isinstance(date, datetime):
            date_obj = date
        else:
            # 如果是date类型，转换为datetime类型
            date_obj = datetime.combine(date, datetime.min.time())
        
        # 构建更新语句
        day_column = f"第{date_obj.day}天"
        if day_column in col_index_map:
            # 获取当前值
            current_value = employee_record[col_index_map[day_column]]
            
            # 构建新的值，加入加班说明并用花括号包围
            reason_text = f"{{{reason}}}" if reason else ""
            if current_value and str(current_value) != 'nan':
                new_value = f"{current_value} + {source}加班({overtime_hours}h){reason_text}"
            else:
                new_value = f"{source}加班({overtime_hours}h){reason_text}"
            
            # 更新记录
            update_query = f"UPDATE attendance_result SET \"{day_column}\" = %s WHERE 姓名 = %s"
            cursor.execute(update_query, (new_value, name))
            flush_print(f"✅ 已更新 {name} 在 {date_obj.date()} 的考勤记录：{new_value}")
        else:
            flush_print(f"❌ 未找到 {name} 在 {date_obj.date()} 的考勤记录")
            
    except Exception as e:
        flush_print(f"❌ 更新考勤记录时出错: {e}")

def process_llm_records():
    """处理LLM生成的加班记录，更新考勤结果"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 获取所有LLM处理后的加班记录
        llm_records = get_llm_records(conn)
        
        flush_print(f"✅ 获取到 {len(llm_records)} 条LLM处理后的加班记录")
        
        # 处理每条加班记录
        for record in llm_records:
            try:
                name, date_str, time_range, duration, reason, source = record
                
                # 解析日期
                if isinstance(date_str, str):
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                elif isinstance(date_str, datetime):
                    date_obj = date_str
                else:
                    # 如果是date类型，转换为datetime类型
                    date_obj = datetime.combine(date_str, datetime.min.time())
                
                # 获取当前月份
                from holidays import MONTH
                current_month = int(MONTH)
                
                # 只处理当前月份的记录
                if date_obj.month != current_month:
                    flush_print(f"⚠️ 跳过非当前月份的记录: {name} {date_str}")
                    continue
                
                # 更新考勤记录
                update_attendance_for_overtime(cursor, name, date_obj, duration, source, reason)
                
            except Exception as e:
                flush_print(f"❌ 处理LLM加班记录时出错: {e}")
        
        conn.commit()
        flush_print("✅ 考勤记录更新完成")
        
    except Exception as e:
        flush_print(f"❌ 程序执行出错: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def main():
    process_llm_records()

if __name__ == "__main__":
    main()