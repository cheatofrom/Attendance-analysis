import psycopg2
from datetime import datetime
from psycopg2 import sql
from config import DB_CONFIG
import holidays


def get_db_connection():
    """创建数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def get_freework_records(cursor):
    """获取所有请假记录，并处理特殊姓名标识"""
    query = """
    SELECT 
        CASE 
            WHEN 姓名 LIKE '%CDTL' THEN LEFT(姓名, LENGTH(姓名)-4)
            ELSE 姓名
        END as 姓名,
        开始时间, 
        结束时间, 
        请假说明, 
        时长,
        数据来源,
        请假类型
    FROM freework
    """
    cursor.execute(query)
    return cursor.fetchall()

def update_attendance_record(cursor, name, start_date, end_date, leave_reason, duration, source, leave_type):
    """更新指定日期范围内的考勤记录，将请假信息追加到现有记录后"""
    try:
        # 提取上午/下午信息
        start_time_parts = start_date.split()
        end_time_parts = end_date.split()
        
        # 获取上午/下午信息
        start_period = start_time_parts[1] if len(start_time_parts) > 1 else ""
        end_period = end_time_parts[1] if len(end_time_parts) > 1 else ""
        
        # 将日期字符串转换为datetime对象
        start_date = datetime.strptime(start_time_parts[0], '%Y-%m-%d')
        end_date = datetime.strptime(end_time_parts[0], '%Y-%m-%d')
        
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
        
        # 构建更新语句并追加更新
        for day in range(start_day, end_day + 1):
            column_name = f'第{day}天'
            
            # 修改查询语句，使用 LIKE 进行模糊匹配
            check_query = sql.SQL("""
                SELECT {} FROM attendance_result 
                WHERE 姓名 LIKE %s || '%%'
            """).format(sql.Identifier(column_name))
            
            cursor.execute(check_query, (name,))
            result = cursor.fetchone()
            
            if not result:
                print(f"警告: 未找到员工 {name} 的记录")
                continue
                
            current_value = result[0]
            
            # 生成请假信息，添加上午/下午信息（如果是0.5天请假）
            time_period = ""
            if "0.5" in str(duration) and start_period:
                time_period = f"[{start_period}]"
            elif "0.5" in str(duration) and end_period:
                time_period = f"[{end_period}]"
                
            leave_info = f"\n{source}请假({duration}){time_period}[{leave_type}]({leave_reason})"
            
            new_value = leave_info.lstrip('\n')
            
            # 更新记录时也使用模糊匹配
            update_query = sql.SQL("""
                UPDATE attendance_result 
                SET {} = %s
                WHERE 姓名 LIKE %s || '%%'
            """).format(sql.Identifier(column_name))
            
            cursor.execute(update_query, (new_value, name))
            
    except Exception as e:
        print(f"处理 {name} 的请假记录时出错: {e}")
        raise e

def process_cached_records(cursor):
    """处理缓存的跨月请假记录"""
    try:
        # 导入缓存模块
        from cross_month_cache import get_cached_records, mark_record_as_processed
        
        # 获取当前连接
        conn = cursor.connection
        
        # 获取与当前月份相关的缓存请假记录
        cached_records = get_cached_records(conn, 'freework')
        print(f"✅ 获取到 {len(cached_records)} 条缓存的跨月请假记录")
        
        # 处理每条缓存记录
        for record in cached_records:
            record_id = record[0]  # id 在第1列
            name = record[2]       # name 在第3列
            start_time = record[3] # start_time 在第4列
            end_time = record[4]   # end_time 在第5列
            reason = record[5]     # reason 在第6列
            duration = record[6]   # duration 在第7列
            source = record[7]     # source 在第8列
            leave_type = record[8] # leave_type 在第9列
            
            print(f"正在处理缓存的 {name} 的请假记录: {start_time} -> {end_time}")
            
            # 更新考勤记录
            try:
                update_attendance_record(cursor, name, start_time, end_time, reason, duration, source, leave_type)
                # 标记为已处理
                mark_record_as_processed(conn, record_id)
            except Exception as e:
                print(f"❌ 处理缓存记录失败: {e}")
                continue
        
        print("✅ 所有缓存的跨月请假记录处理完成")
        
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
        
        # 获取所有请假记录
        freework_records = get_freework_records(cursor)
        print(f"✅ 获取到 {len(freework_records)} 条请假记录")
        
        # 处理每条请假记录
        for record in freework_records:
            name, start_time, end_time, reason, duration, source, leave_type = record
            print(f"正在处理 {name} 的请假记录: {start_time} -> {end_time}")
            
            try:
                update_attendance_record(cursor, name, start_time, end_time, reason, duration, source, leave_type)
                
                # 检查是否需要缓存跨月记录
                try:
                    start_date = datetime.strptime(start_time.split()[0], '%Y-%m-%d')
                    end_date = datetime.strptime(end_time.split()[0], '%Y-%m-%d')
                    
                    if start_date.month != end_date.month:
                        print(f"⚠️ 检测到跨月请假记录: {name} {start_time} -> {end_time}，将在下月处理")
                except Exception as e:
                    print(f"❌ 检查跨月记录时出错: {e}")
            except Exception as e:
                print(f"❌ 处理失败: {e}")
                continue
        
        # 提交事务
        conn.commit()
        print("✅ 所有请假记录处理完成")
        
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()