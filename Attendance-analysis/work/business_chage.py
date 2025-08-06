import psycopg2
import pandas as pd
from datetime import datetime
from psycopg2 import sql
import holidays

# 数据库连接配置
DB_CONFIG = {
    "host": "192.168.1.66",
    "port": "7432",
    "database": "dingding",
    "user": "root",
    "password": "123456"
}

def get_db_connection():
    """创建数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def get_business_records(cursor):
    """获取所有出差记录"""
    query = """
    SELECT 姓名, 开始时间, 结束时间, 出差事由, 同行人
    FROM business
    """
    cursor.execute(query)
    return cursor.fetchall()

def update_attendance_record(cursor, name, start_date, end_date, business_reason, colleagues=None):
    """更新指定日期范围内的考勤记录"""
    # 将日期字符串转换为datetime对象
    start_date = datetime.strptime(start_date.split()[0], '%Y-%m-%d')
    end_date = datetime.strptime(end_date.split()[0], '%Y-%m-%d')
    
    # 检查是否跨月
    is_cross_month = start_date.month != end_date.month
    
    # 如果跨月，只处理当前月份的部分
    from holidays import MONTH
    current_month = int(MONTH)
    
    # 获取需要更新的列名（第X天）
    if is_cross_month:
        if start_date.month == current_month:
            # 当前月是开始月，处理从开始日到月底
            start_day = int(start_date.strftime('%d'))
            # 获取当月最后一天
            if current_month in [1, 3, 5, 7, 8, 10, 12]:
                end_day = 31
            elif current_month in [4, 6, 9, 11]:
                end_day = 30
            else:  # 2月
                end_day = 29 if start_date.year % 4 == 0 and (start_date.year % 100 != 0 or start_date.year % 400 == 0) else 28
        elif end_date.month == current_month:
            # 当前月是结束月，处理从月初到结束日
            start_day = 1
            end_day = int(end_date.strftime('%d'))
        else:
            # 当前月既不是开始月也不是结束月，不处理
            return
    else:
        # 不跨月，正常处理
        start_day = int(start_date.strftime('%d'))
        end_day = int(end_date.strftime('%d'))
    
    # 构建出差信息，包含同行人
    business_info = f"出差({business_reason})"
    if colleagues and not pd.isna(colleagues):
        business_info = f"出差({business_reason})[同行人:{colleagues}]"
    
    # 构建更新语句并直接更新
    for day in range(start_day, end_day + 1):
        column_name = f'第{day}天'
        
        # 直接更新考勤状态
        update_query = sql.SQL("""
            UPDATE attendance_result 
            SET {} = %s
            WHERE 姓名 = %s
        """).format(sql.Identifier(column_name))
        
        cursor.execute(update_query, (business_info, name))

def update_colleague_attendance(cursor, name, start_date, end_date, business_reason, initiator):
    """更新同行人的考勤记录"""
    # 将日期字符串转换为datetime对象
    start_date = datetime.strptime(start_date.split()[0], '%Y-%m-%d')
    end_date = datetime.strptime(end_date.split()[0], '%Y-%m-%d')
    
    # 检查是否跨月
    is_cross_month = start_date.month != end_date.month
    
    # 如果跨月，只处理当前月份的部分
    from holidays import MONTH
    current_month = int(MONTH)
    
    # 获取需要更新的列名（第X天）
    if is_cross_month:
        if start_date.month == current_month:
            # 当前月是开始月，处理从开始日到月底
            start_day = int(start_date.strftime('%d'))
            # 获取当月最后一天
            if current_month in [1, 3, 5, 7, 8, 10, 12]:
                end_day = 31
            elif current_month in [4, 6, 9, 11]:
                end_day = 30
            else:  # 2月
                end_day = 29 if start_date.year % 4 == 0 and (start_date.year % 100 != 0 or start_date.year % 400 == 0) else 28
        elif end_date.month == current_month:
            # 当前月是结束月，处理从月初到结束日
            start_day = 1
            end_day = int(end_date.strftime('%d'))
        else:
            # 当前月既不是开始月也不是结束月，不处理
            return
    else:
        # 不跨月，正常处理
        start_day = int(start_date.strftime('%d'))
        end_day = int(end_date.strftime('%d'))
    
    # 构建出差信息，包含发起人
    business_info = f"出差(同行)[发起人:{initiator}]"
    
    # 构建更新语句并直接更新
    for day in range(start_day, end_day + 1):
        column_name = f'第{day}天'
        
        # 检查当前同行人在该日期是否已有出差记录
        check_query = sql.SQL("""
            SELECT {} FROM attendance_result 
            WHERE 姓名 = %s
        """).format(sql.Identifier(column_name))
        
        cursor.execute(check_query, (name,))
        current_status = cursor.fetchone()
        
        # 如果没有记录或者当前记录不包含出差信息，则更新
        if not current_status or current_status[0] is None or '出差' not in str(current_status[0]):
            # 直接更新考勤状态
            update_query = sql.SQL("""
                UPDATE attendance_result 
                SET {} = %s
                WHERE 姓名 = %s
            """).format(sql.Identifier(column_name))
            
            cursor.execute(update_query, (business_info, name))

def process_colleagues(cursor, name, start_time, end_time, reason, colleagues):
    """处理同行人的考勤记录"""
    if not colleagues or pd.isna(colleagues):
        return
    
    # 分割同行人名单
    colleague_list = colleagues.split(',')
    for colleague in colleague_list:
        colleague = colleague.strip()
        if colleague and colleague != name:  # 确保不是发起人自己
            print(f"  - 更新同行人 {colleague} 的考勤记录")
            update_colleague_attendance(cursor, colleague, start_time, end_time, reason, name)

def process_cached_records(cursor):
    """处理缓存的跨月出差记录"""
    try:
        # 导入缓存模块
        from cross_month_cache import get_cached_records, mark_record_as_processed
        
        # 获取当前连接
        conn = cursor.connection
        
        # 获取与当前月份相关的缓存出差记录
        cached_records = get_cached_records(conn, 'business')
        print(f"✅ 获取到 {len(cached_records)} 条缓存的跨月出差记录")
        
        # 处理每条缓存记录
        for record in cached_records:
            record_id = record[0]  # id 在第1列
            name = record[2]       # name 在第3列
            start_time = record[3] # start_time 在第4列
            end_time = record[4]   # end_time 在第5列
            reason = record[6]     # reason 在第7列
            colleagues = record[8] # colleagues 在第9列
            
            print(f"正在处理缓存的 {name} 的出差记录: {start_time} -> {end_time}")
            
            # 更新发起人的考勤记录
            update_attendance_record(cursor, name, start_time, end_time, reason, colleagues)
            
            # 处理同行人的考勤记录
            process_colleagues(cursor, name, start_time, end_time, reason, colleagues)
            
            # 标记为已处理
            mark_record_as_processed(conn, record_id)
        
        print("✅ 所有缓存的跨月出差记录处理完成")
        
    except ImportError:
        print("⚠️ 未找到缓存模块，跳过处理缓存记录")
    except Exception as e:
        print(f"❌ 处理缓存记录时出错: {e}")

def main():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 先处理缓存的跨月记录
        process_cached_records(cursor)
        
        # 获取所有出差记录
        business_records = get_business_records(cursor)
        print(f"✅ 获取到 {len(business_records)} 条出差记录")
        
        # 处理每条出差记录
        for record in business_records:
            name, start_time, end_time, reason, colleagues = record
            print(f"正在处理 {name} 的出差记录: {start_time} -> {end_time}")
            
            # 更新发起人的考勤记录
            update_attendance_record(cursor, name, start_time, end_time, reason, colleagues)
            
            # 处理同行人的考勤记录
            process_colleagues(cursor, name, start_time, end_time, reason, colleagues)
            
            # 检查是否需要缓存跨月记录
            try:
                start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
                end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
                
                if start_date.month != end_date.month:
                    print(f"⚠️ 检测到跨月出差记录: {name} {start_time} -> {end_time}，将在缓存阶段处理")
            except Exception as e:
                print(f"❌ 检查跨月记录时出错: {e}")
        
        # 提交事务
        conn.commit()
        print("✅ 所有出差记录处理完成")
        
    except Exception as e:
        print(f"❌ 处理出错: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()