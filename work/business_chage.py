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
    
    # 获取当前月份
    from holidays import MONTH
    current_month = int(MONTH)
    
    # 检查是否跨月
    is_cross_month = start_date.month != end_date.month
    
    # 获取需要更新的列名（第X天）
    if is_cross_month:
        # 如果开始日期是当前月的第一天，说明这是从缓存中取出的记录
        # 直接处理从开始日到结束日的部分
        if start_date.month == current_month and start_date.day == 1:
            start_day = 1
            end_day = int(end_date.strftime('%d'))
        # 如果开始日期的月份是当前月，处理从开始日到月底
        elif start_date.month == current_month:
            start_day = int(start_date.strftime('%d'))
            # 获取当月最后一天
            if current_month in [1, 3, 5, 7, 8, 10, 12]:
                end_day = 31
            elif current_month in [4, 6, 9, 11]:
                end_day = 30
            else:  # 2月
                end_day = 29 if start_date.year % 4 == 0 and (start_date.year % 100 != 0 or start_date.year % 400 == 0) else 28
        # 如果结束日期的月份是当前月，但开始日期不是当前月，不处理
        # 这种情况会在下个月处理（通过缓存）
        else:
            return
    else:
        # 不跨月，正常处理
        start_day = int(start_date.strftime('%d'))
        end_day = int(end_date.strftime('%d'))
    
    # 构建出差信息，包含同行人
    business_info = f"出差({business_reason})"
    if colleagues and not pd.isna(colleagues):
        business_info = f"出差({business_reason})[同行人:{colleagues}]"
    
    # 构建更新语句并追加更新
    for day in range(start_day, end_day + 1):
        column_name = f'第{day}天'
        
        # 查询当前记录
        check_query = sql.SQL("""
            SELECT {} FROM attendance_result 
            WHERE 姓名 = %s
        """).format(sql.Identifier(column_name))
        
        cursor.execute(check_query, (name,))
        result = cursor.fetchone()
        
        if not result:
            print(f"警告: 未找到员工 {name} 的记录")
            continue
            
        current_value = result[0]
        
        # 如果当前值为空，直接设置；否则追加
        new_value = business_info
        if current_value and not pd.isna(current_value):
            new_value = f"{current_value}\n{business_info}"
        
        # 更新记录
        update_query = sql.SQL("""
            UPDATE attendance_result 
            SET {} = %s
            WHERE 姓名 = %s
        """).format(sql.Identifier(column_name))
        
        cursor.execute(update_query, (new_value, name))

def update_colleague_attendance(cursor, name, start_date, end_date, business_reason, initiator):
    """更新同行人的考勤记录"""
    # 将日期字符串转换为datetime对象
    start_date = datetime.strptime(start_date.split()[0], '%Y-%m-%d')
    end_date = datetime.strptime(end_date.split()[0], '%Y-%m-%d')
    
    # 获取当前月份
    from holidays import MONTH
    current_month = int(MONTH)
    
    # 检查是否跨月
    is_cross_month = start_date.month != end_date.month
    
    # 获取需要更新的列名（第X天）
    if is_cross_month:
        # 如果开始日期是当前月的第一天，说明这是从缓存中取出的记录
        # 直接处理从开始日到结束日的部分
        if start_date.month == current_month and start_date.day == 1:
            start_day = 1
            end_day = int(end_date.strftime('%d'))
        # 如果开始日期的月份是当前月，处理从开始日到月底
        elif start_date.month == current_month:
            start_day = int(start_date.strftime('%d'))
            # 获取当月最后一天
            if current_month in [1, 3, 5, 7, 8, 10, 12]:
                end_day = 31
            elif current_month in [4, 6, 9, 11]:
                end_day = 30
            else:  # 2月
                end_day = 29 if start_date.year % 4 == 0 and (start_date.year % 100 != 0 or start_date.year % 400 == 0) else 28
        # 如果结束日期的月份是当前月，但开始日期不是当前月，不处理
        # 这种情况会在下个月处理（通过缓存）
        else:
            return
    else:
        # 不跨月，正常处理
        start_day = int(start_date.strftime('%d'))
        end_day = int(end_date.strftime('%d'))
    
    # 构建出差信息，包含发起人
    business_info = f"出差(同行)[发起人:{initiator}]"
    
    # 构建更新语句并追加更新
    for day in range(start_day, end_day + 1):
        column_name = f'第{day}天'
        
        # 检查当前同行人在该日期是否已有记录
        check_query = sql.SQL("""
            SELECT {} FROM attendance_result 
            WHERE 姓名 = %s
        """).format(sql.Identifier(column_name))
        
        cursor.execute(check_query, (name,))
        current_status = cursor.fetchone()
        
        if not current_status:
            print(f"警告: 未找到员工 {name} 的记录")
            continue
            
        current_value = current_status[0]
        
        # 如果当前值为空，直接设置；否则追加
        # 但只有当当前记录不包含出差信息时才更新
        if current_value is None or pd.isna(current_value):
            new_value = business_info
            update_query = sql.SQL("""
                UPDATE attendance_result 
                SET {} = %s
                WHERE 姓名 = %s
            """).format(sql.Identifier(column_name))
            
            cursor.execute(update_query, (new_value, name))
        elif '出差' not in str(current_value):
            new_value = f"{current_value}\n{business_info}"
            update_query = sql.SQL("""
                UPDATE attendance_result 
                SET {} = %s
                WHERE 姓名 = %s
            """).format(sql.Identifier(column_name))
            
            cursor.execute(update_query, (new_value, name))

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
            
            # 验证开始日期是否为当前月的第一天
            try:
                start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
                from holidays import MONTH
                current_month = int(MONTH)
                
                if start_date.month == current_month and start_date.day == 1:
                    # 更新发起人的考勤记录
                    update_attendance_record(cursor, name, start_time, end_time, reason, colleagues)
                    
                    # 处理同行人的考勤记录
                    process_colleagues(cursor, name, start_time, end_time, reason, colleagues)
                    
                    # 标记为已处理
                    mark_record_as_processed(conn, record_id)
                else:
                    print(f"⚠️ 缓存的出差记录开始日期不是当前月第一天: {name} {start_time}，跳过处理")
                    continue
            except Exception as e:
                print(f"❌ 处理缓存出差记录失败: {e}")
                continue
        
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
                    # 导入缓存模块并保存跨月记录
                    try:
                        from cross_month_cache import save_business_to_cache
                        # 构建完整的记录
                        duration = f"{(end_date - start_date).days + 1}天"
                        status = "已通过"
                        colleagues_raw1 = colleagues if colleagues else ""
                        colleagues_raw2 = ""
                        source = "钉钉"
                        
                        # 保存到缓存表
                        full_record = (name, start_time, end_time, duration, reason, status, colleagues_raw1, colleagues_raw2, colleagues, source)
                        save_business_to_cache(conn, full_record)
                        print(f"✅ 已将跨月出差记录缓存: {name} {start_time} -> {end_time}")
                    except ImportError:
                        print("⚠️ 未找到缓存模块，无法缓存跨月记录")
                    except Exception as e:
                        print(f"❌ 缓存跨月出差记录时出错: {e}")
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