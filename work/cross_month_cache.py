import psycopg2
import pandas as pd
from datetime import datetime
import holidays
from config import DB_CONFIG
import sys

# 强制刷新输出缓冲区
def flush_print(*args, **kwargs):
    """带缓冲刷新的print函数"""
    print(*args, **kwargs)
    sys.stdout.flush()

def get_db_connection():
    """创建数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def save_freework_to_cache(conn, record):
    """将跨月请假记录保存到缓存表，只缓存下个月的部分（从下个月1号开始）"""
    cursor = conn.cursor()
    try:
        name, start_time, end_time, duration, reason, status, leave_type, source = record
        
        # 检查是否跨月
        start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
        end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
        
        if start_date.month != end_date.month:
            # 修改开始时间为下个月1号
            next_month_first_day = datetime(end_date.year, end_date.month, 1)
            next_month_start_time = f"{next_month_first_day.strftime('%Y-%m-%d')} 上午"
            
            # 检查是否已存在相同的记录，避免重复插入
            check_query = """
                SELECT COUNT(*) FROM cross_month_cache 
                WHERE record_type = 'freework' AND name = %s AND start_time = %s AND end_time = %s
            """
            cursor.execute(check_query, (name, next_month_start_time, end_time))
            record_count = cursor.fetchone()[0]
            
            if record_count > 0:
                flush_print(f"⚠️ 跨月请假记录已存在，跳过缓存: {name} {next_month_start_time} -> {end_time}")
                return False
            
            # 插入到缓存表，使用修改后的开始时间
            cursor.execute("""
                INSERT INTO cross_month_cache 
                (record_type, name, start_time, end_time, duration, reason, status, type, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ('freework', name, next_month_start_time, end_time, duration, reason, status, leave_type, source))
            flush_print(f"✅ 已将 {name} 的跨月请假记录缓存: {next_month_start_time} -> {end_time}")
            return True
        return False
    except Exception as e:
        flush_print(f"❌ 缓存请假记录时出错: {e}")
        return False
    finally:
        cursor.close()

def save_business_to_cache(conn, record):
    """将跨月出差记录保存到缓存表，只缓存下个月的部分（从下个月1号开始）"""
    cursor = conn.cursor()
    try:
        name, start_time, end_time, duration, reason, status, colleagues_raw1, colleagues_raw2, colleagues, source = record
        
        # 检查是否跨月
        start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
        end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
        
        if start_date.month != end_date.month:
            # 修改开始时间为下个月1号
            next_month_first_day = datetime(end_date.year, end_date.month, 1)
            next_month_start_time = f"{next_month_first_day.strftime('%Y-%m-%d')} 上午"
            
            # 检查是否已存在相同的记录，避免重复插入
            check_query = """
                SELECT COUNT(*) FROM cross_month_cache 
                WHERE record_type = 'business' AND name = %s AND start_time = %s AND end_time = %s
            """
            cursor.execute(check_query, (name, next_month_start_time, end_time))
            record_count = cursor.fetchone()[0]
            
            if record_count > 0:
                flush_print(f"⚠️ 跨月出差记录已存在，跳过缓存: {name} {next_month_start_time} -> {end_time}")
                return False
            
            # 插入到缓存表，使用修改后的开始时间
            cursor.execute("""
                INSERT INTO cross_month_cache 
                (record_type, name, start_time, end_time, duration, reason, status, colleagues, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ('business', name, next_month_start_time, end_time, duration, reason, status, colleagues, source))
            flush_print(f"✅ 已将 {name} 的跨月出差记录缓存: {next_month_start_time} -> {end_time}")
            return True
        return False
    except Exception as e:
        flush_print(f"❌ 缓存出差记录时出错: {e}")
        return False
    finally:
        cursor.close()

def save_overwork_to_cache(conn, record):
    """将跨月加班记录保存到缓存表，只缓存下个月的部分（从下个月1号开始）"""
    cursor = conn.cursor()
    try:
        name, start_time, end_time, duration, reason, status, source = record
        
        # 检查是否跨月
        start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
        end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
        
        if start_date.month != end_date.month:
            # 修改开始时间为下个月1号
            next_month_first_day = datetime(end_date.year, end_date.month, 1)
            next_month_start_time = f"{next_month_first_day.strftime('%Y-%m-%d')} 上午"
            
            # 检查是否已存在相同的记录，避免重复插入
            check_query = """
                SELECT COUNT(*) FROM cross_month_cache 
                WHERE record_type = 'overwork' AND name = %s AND start_time = %s AND end_time = %s
            """
            cursor.execute(check_query, (name, next_month_start_time, end_time))
            record_count = cursor.fetchone()[0]
            
            if record_count > 0:
                flush_print(f"⚠️ 跨月加班记录已存在，跳过缓存: {name} {next_month_start_time} -> {end_time}")
                return False
            
            # 插入到缓存表，使用修改后的开始时间
            cursor.execute("""
                INSERT INTO cross_month_cache 
                (record_type, name, start_time, end_time, duration, reason, status, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, ('overwork', name, next_month_start_time, end_time, duration, reason, status, source))
            flush_print(f"✅ 已将 {name} 的跨月加班记录缓存: {next_month_start_time} -> {end_time}")
            return True
        return False
    except Exception as e:
        flush_print(f"❌ 缓存加班记录时出错: {e}")
        return False
    finally:
        cursor.close()

def get_cached_records(conn, record_type=None):
    """获取缓存的跨月记录"""
    cursor = conn.cursor()
    try:
        # 获取当前月份
        current_month = int(holidays.MONTH)
        current_year = holidays.YEAR
        
        query = """
            SELECT * FROM cross_month_cache 
        """
        
        params = []
        
        if record_type:
            query += " WHERE record_type = %s"
            params.append(record_type)
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        # 筛选出与当前月份相关的记录
        filtered_records = []
        for record in records:
            # 解析日期
            start_time = record[3]  # start_time 在第4列
            end_time = record[4]    # end_time 在第5列
            
            start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
            end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
            
            # 检查记录是否与当前月份相关
            # 由于我们现在只缓存下个月的部分，所以只需要检查开始日期是否为当前月份的第一天
            if start_date.month == current_month and start_date.day == 1:
                filtered_records.append(record)
        
        return filtered_records
    except Exception as e:
        flush_print(f"❌ 获取缓存记录时出错: {e}")
        return []
    finally:
        cursor.close()

def mark_record_as_processed(conn, record_id):
    """将缓存记录标记为已处理"""
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE cross_month_cache SET processed = TRUE WHERE id = %s", (record_id,))
        conn.commit()
        return True
    except Exception as e:
        flush_print(f"❌ 标记缓存记录时出错: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def cache_all_cross_month_records():
    """缓存所有跨月记录"""
    conn = get_db_connection()
    try:
        # 缓存请假记录
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM freework")
        freework_records = cursor.fetchall()
        cursor.close()
        
        freework_cached_count = 0
        for record in freework_records:
            if save_freework_to_cache(conn, record):
                freework_cached_count += 1
        
        flush_print(f"✅ 已缓存 {freework_cached_count} 条跨月请假记录")
        
        # 缓存出差记录
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM business")
        business_records = cursor.fetchall()
        cursor.close()
        
        business_cached_count = 0
        for record in business_records:
            if save_business_to_cache(conn, record):
                business_cached_count += 1
        
        flush_print(f"✅ 已缓存 {business_cached_count} 条跨月出差记录")
        
        # 缓存加班记录
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM overwork")
        overwork_records = cursor.fetchall()
        cursor.close()
        
        overwork_cached_count = 0
        for record in overwork_records:
            if save_overwork_to_cache(conn, record):
                overwork_cached_count += 1
        
        flush_print(f"✅ 已缓存 {overwork_cached_count} 条跨月加班记录")
        
        conn.commit()
        flush_print(f"✅ 所有跨月记录缓存完成")
        
    except Exception as e:
        flush_print(f"❌ 缓存跨月记录时出错: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    # 创建缓存表（如果不存在）
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查缓存表是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'cross_month_cache'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            flush_print("⚠️ 缓存表不存在，请先运行 create_cache_table.sql 创建表")
            return
        
        # 缓存所有跨月记录
        cache_all_cross_month_records()
        
    except Exception as e:
        flush_print(f"❌ 程序执行出错: {e}")
        conn.rollback()  # 添加事务回滚，避免事务中止错误
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()