import psycopg2
from datetime import datetime, timedelta
import pandas as pd
from config import DB_CONFIG
import sys
import holidays

# 强制刷新输出缓冲区
def flush_print(*args, **kwargs):
    """带缓冲刷新的print函数"""
    print(*args, **kwargs)
    sys.stdout.flush()

def get_db_connection():
    """创建数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def get_overwork_records(conn):
    """获取加班记录"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 姓名, 
                   split_part(开始时间, ' ', 1) as 加班日期,
                   开始时间, 
                   结束时间, 
                   加班时长小时, 
                   加班说明, 
                   申请状态, 
                   数据来源
            FROM overwork
            WHERE 申请状态 IN ('已同意', '审批通过')
            ORDER BY 姓名, 开始时间
        """)
        records = cursor.fetchall()
        return records
    finally:
        cursor.close()

def update_attendance_for_overtime(cursor, name, date, overtime_hours, source):
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
        
        # 构建更新语句
        day_column = f"第{date.day}天"
        if day_column in col_index_map:
            # 获取当前值
            current_value = employee_record[col_index_map[day_column]]
            
            # 构建新的值
            if current_value and str(current_value) != 'nan':
                new_value = f"{current_value} + {source}加班({overtime_hours}h)"
            else:
                new_value = f"{source}加班({overtime_hours}h)"
            
            # 更新记录
            update_query = f"UPDATE attendance_result SET \"{day_column}\" = %s WHERE 姓名 = %s"
            cursor.execute(update_query, (new_value, name))
            flush_print(f"✅ 已更新 {name} 在 {date.date()} 的考勤记录：{new_value}")
        else:
            flush_print(f"❌ 未找到 {name} 在 {date.date()} 的考勤记录")
            
    except Exception as e:
        flush_print(f"❌ 更新考勤记录时出错: {e}")

def process_cached_records(cursor):
    """处理缓存的跨月加班记录"""
    failed_records = []
    try:
        from cross_month_cache import get_cached_records, mark_record_as_processed
        conn = cursor.connection
        cached_records = get_cached_records(conn, 'overwork')
        flush_print(f"✅ 获取到 {len(cached_records)} 条缓存的跨月加班记录")
        for record in cached_records:
            try:
                record_id = record[0]  # id 在第1列
                name = record[2]       # name 在第3列
                start_time = record[3] # start_time 在第4列
                end_time = record[4]   # end_time 在第5列
                duration = record[5]   # duration 在第6列
                source = record[10]    # source 在第11列
                flush_print(f"正在处理缓存的 {name} 的加班记录: {start_time} -> {end_time}")
                start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
                from holidays import MONTH
                current_month = int(MONTH)
                if start_date.month == current_month and start_date.day == 1:
                    process_date = start_date
                else:
                    flush_print(f"⚠️ 缓存的加班记录开始日期不是当前月第一天: {name} {start_time}，跳过处理")
                    continue
                overtime_hours = float(duration.replace('小时', '').replace('h', ''))
                update_attendance_for_overtime(cursor, name, process_date, overtime_hours, source)
                mark_record_as_processed(conn, record_id)
            except Exception as e:
                flush_print(f"❌ 处理缓存加班记录时出错: {e}")
                failed_records.append({
                    '姓名': record[2] if len(record) > 2 else '',
                    '开始时间': record[3] if len(record) > 3 else '',
                    '结束时间': record[4] if len(record) > 4 else '',
                    '加班时长': record[5] if len(record) > 5 else '',
                    '数据来源': record[10] if len(record) > 10 else '',
                    '错误信息': str(e)
                })
        flush_print("✅ 所有缓存的跨月加班记录处理完成")
    except ImportError:
        flush_print("⚠️ 未找到缓存模块，跳过处理缓存记录")
    except Exception as e:
        flush_print(f"❌ 处理缓存记录时出错: {e}")
        failed_records.append({'错误信息': str(e)})
    return failed_records

def main():
    process_overtime_records()

if __name__ == "__main__":
    main()