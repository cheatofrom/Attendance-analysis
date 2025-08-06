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
    try:
        # 导入缓存模块
        from cross_month_cache import get_cached_records, mark_record_as_processed
        
        # 获取当前连接
        conn = cursor.connection
        
        # 获取与当前月份相关的缓存加班记录
        cached_records = get_cached_records(conn, 'overwork')
        flush_print(f"✅ 获取到 {len(cached_records)} 条缓存的跨月加班记录")
        
        # 处理每条缓存记录
        for record in cached_records:
            try:
                record_id = record[0]  # id 在第1列
                name = record[2]       # name 在第3列
                start_time = record[3] # start_time 在第4列
                end_time = record[4]   # end_time 在第5列
                duration = record[5]   # duration 在第6列
                source = record[10]    # source 在第11列
                
                flush_print(f"正在处理缓存的 {name} 的加班记录: {start_time} -> {end_time}")
                
                # 解析时间
                start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
                end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
                
                # 获取当前月份
                from holidays import MONTH
                current_month = int(MONTH)
                
                # 确定要处理的日期
                if start_date.month == current_month:
                    process_date = start_date
                elif end_date.month == current_month:
                    process_date = end_date
                else:
                    # 当前月既不是开始月也不是结束月，不处理
                    continue
                
                # 解析时长
                overtime_hours = float(duration.replace('小时', '').replace('h', ''))
                
                # 更新考勤记录
                update_attendance_for_overtime(cursor, name, process_date, overtime_hours, source)
                
                # 标记为已处理
                mark_record_as_processed(conn, record_id)
                
            except Exception as e:
                flush_print(f"❌ 处理缓存加班记录时出错: {e}")
        
        flush_print("✅ 所有缓存的跨月加班记录处理完成")
        
    except ImportError:
        flush_print("⚠️ 未找到缓存模块，跳过处理缓存记录")
    except Exception as e:
        flush_print(f"❌ 处理缓存记录时出错: {e}")

def process_overtime_records():
    """处理加班记录，更新考勤结果"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # 先处理缓存的跨月记录
        process_cached_records(cursor)
        
        # 获取所有加班记录
        cursor.execute("SELECT 姓名, 开始时间, 结束时间, 加班时长小时, 数据来源, 加班说明, 申请状态 FROM overwork")
        overwork_records = cursor.fetchall()
        
        flush_print(f"✅ 获取到 {len(overwork_records)} 条加班记录")
        
        # 处理每条加班记录
        for record in overwork_records:
            try:
                name, start_time, end_time, duration, source, reason, status = record
                
                # 解析时间
                start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
                end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
                
                # 检查是否跨月
                is_cross_month = start_date.month != end_date.month
                
                # 如果跨月，只处理当前月份的部分
                from holidays import MONTH
                current_month = int(MONTH)
                
                # 确定要处理的日期
                if is_cross_month:
                    if start_date.month == current_month:
                        # 当前月是开始月，处理开始日期
                        process_date = start_date
                    elif end_date.month == current_month:
                        # 当前月是结束月，处理结束日期
                        process_date = end_date
                    else:
                        # 当前月既不是开始月也不是结束月，不处理
                        flush_print(f"⚠️ 检测到跨月加班记录: {name} {start_time} -> {end_time}，将在缓存阶段处理")
                        continue
                else:
                    # 不跨月，处理开始日期
                    process_date = start_date
                
                # 解析时长
                overtime_hours = float(duration.replace('小时', '').replace('h', ''))
                
                # 更新考勤记录
                update_attendance_for_overtime(cursor, name, process_date, overtime_hours, source)
                
            except Exception as e:
                flush_print(f"❌ 处理加班记录时出错: {e}")
        
        conn.commit()
        flush_print("✅ 考勤记录更新完成")
        
    except Exception as e:
        flush_print(f"❌ 程序执行出错: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def main():
    process_overtime_records()

if __name__ == "__main__":
    main()