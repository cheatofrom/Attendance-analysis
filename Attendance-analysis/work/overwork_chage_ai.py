import psycopg2
from datetime import datetime, timedelta, date
import pandas as pd
import sys
import os
import time

# 添加work目录到系统路径，以便导入config和holidays模块
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work'))
from config import DB_CONFIG
import holidays
from logger_utils import create_logger

# 初始化日志记录器
logger = create_logger('overwork_change_ai')

# 强制刷新输出缓冲区
def flush_print(*args, **kwargs):
    """带缓冲刷新的print函数"""
    print(*args, **kwargs)
    sys.stdout.flush()

def get_db_connection():
    """创建数据库连接"""
    logger.log_database_operation("正在建立数据库连接", "database")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.log_info("数据库连接建立成功")
        return conn
    except Exception as e:
        logger.log_error(f"数据库连接失败: {e}")
        raise

def get_llm_records(conn):
    """获取LLM处理后的加班记录"""
    logger.log_database_operation("查询LLM处理后的加班记录", "llm_results")
    cursor = conn.cursor()
    try:
        query = """
            SELECT 姓名, 
                   日期, 
                   时间, 
                   时长, 
                   加班说明, 
                   来源
            FROM llm_results
            ORDER BY 姓名, 日期
        """
        # 不输出执行SQL的日志
        cursor.execute(query)
        records = cursor.fetchall()
        
        # 只保留查询结果数量的日志，不输出详细信息
        logger.log_info(f"成功查询到 {len(records)} 条LLM处理后的加班记录")
        
        return records
    except Exception as e:
        logger.log_error(f"查询LLM记录失败: {e}")
        raise
    finally:
        cursor.close()

def update_attendance_for_overtime(cursor, name, date, overtime_hours, source, reason=""):
    """更新考勤记录中的加班信息"""
    
    try:
        # 获取该员工在该日期的考勤记录
        cursor.execute("SELECT * FROM attendance_result WHERE 姓名 = %s", (name,))
        employee_record = cursor.fetchone()
        
        if not employee_record:
            # 不输出未找到员工的日志
            return False
        
        # 不输出找到员工的日志
        
        # 获取列名
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'attendance_result' ORDER BY ordinal_position")
        columns = [col[0] for col in cursor.fetchall()]
        
        # 创建列名到索引的映射
        col_index_map = {col: i for i, col in enumerate(columns)}
        # 不输出字段数量的日志
        
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
        # 不输出更新字段的日志
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
            return True
        else:
            logger.log_error(f"未找到对应的日期字段 {day_column}")
            return False
            
    except Exception as e:
        logger.log_error(f"更新考勤记录时出错: {e}")
        return False

def process_llm_records():
    """处理LLM生成的加班记录，更新考勤结果"""
    logger.start_step("处理LLM加班记录")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 获取所有LLM处理后的加班记录
        llm_records = get_llm_records(conn)
        
        logger.log_info(f"开始处理 {len(llm_records)} 条LLM加班记录")
        
        # 统计变量
        processed_count = 0
        skipped_count = 0
        success_count = 0
        error_count = 0
        not_found_count = 0
        
        # 存储失败的记录
        failed_records = []
        # 存储未找到员工的记录
        not_found_records = []
        
        # 处理每条加班记录
        for i, record in enumerate(llm_records):
            try:
                current_progress = ((i + 1) / len(llm_records)) * 100
                # 只在每50条记录或最后一条记录时输出进度，减少日志输出
                if (i+1) % 50 == 0 or i+1 == len(llm_records):
                    logger.log_progress("LLM记录处理", f"[{i+1}/{len(llm_records)}] ({current_progress:.1f}%) 处理记录")
                
                name, date_str, time_range, duration, reason, source = record
                # 不输出每条记录的处理详情
                
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
                    # 不输出每条跳过记录的日志
                    skipped_count += 1
                    continue
                
                # 更新考勤记录
                result = update_attendance_for_overtime(cursor, name, date_obj, duration, source, reason)
                if result:
                    success_count += 1
                    processed_count += 1
                    # 不输出每条成功记录的日志
                else:
                    not_found_count += 1
                    not_found_records.append({
                        "record": record,
                        "name": name,
                        "date": date_str
                    })
                    # 不输出每条未找到员工的日志
                
            except Exception as e:
                error_count += 1
                logger.log_error(f"处理LLM加班记录时出错: {e}")
                logger.log_data_processing(f"错误记录: {record}")
                # 添加到失败记录列表
                failed_records.append({
                    "record": record,
                    "error": str(e)
                })
        
        # 提交事务
        logger.log_database_operation("提交数据库事务", "attendance_result")
        conn.commit()
        
        # 收集所有需要在最后输出的信息
        summary_info = []
        summary_info.append(f"LLM记录处理完成统计:")
        summary_info.append(f"  - 总记录数: {len(llm_records)}")
        summary_info.append(f"  - 成功处理: {success_count}")
        summary_info.append(f"  - 跳过记录: {skipped_count}")
        summary_info.append(f"  - 未找到员工: {not_found_count}")
        summary_info.append(f"  - 错误记录: {error_count}")
        
        # 收集未找到员工的详细信息
        if not_found_records:
            summary_info.append("\n未找到员工的记录详细信息:")
            for i, not_found in enumerate(not_found_records, 1):
                name = not_found["name"]
                date = not_found["date"]
                record = not_found["record"]
                summary_info.append(f"  {i}. 员工: {name}, 日期: {date}")
                summary_info.append(f"     记录: {record}")
        
        # 收集失败记录的详细信息
        if failed_records:
            summary_info.append("\n失败记录详细信息:")
            for i, failed in enumerate(failed_records, 1):
                record = failed["record"]
                error = failed["error"]
                name = record[0] if len(record) > 0 else "未知"
                date = record[1] if len(record) > 1 else "未知"
                summary_info.append(f"  {i}. 员工: {name}, 日期: {date}")
                summary_info.append(f"     错误: {error}")
                summary_info.append(f"     记录: {record}")
        
        success_rate = (success_count / len(llm_records)) * 100 if llm_records else 0
        summary_info.append(f"\n处理结果: 成功 {success_count}, 未找到员工 {not_found_count}, 跳过 {skipped_count}, 错误 {error_count}")
        
        # 在日志结束前一起输出所有信息
        print("\n正在输出处理结果汇总，请稍候...")
        sys.stdout.flush()
        time.sleep(1)  # 添加延时
        
        logger.log_info("\n" + "="*50)
        logger.log_info("处理结果汇总")
        logger.log_info("="*50)
        sys.stdout.flush()
        
        # 分批输出汇总信息，每批之间添加短暂延时
        batch_size = 5
        for i in range(0, len(summary_info), batch_size):
            batch = summary_info[i:i+batch_size]
            for line in batch:
                logger.log_info(line)
                sys.stdout.flush()
            # 每批之后添加短暂延时
            time.sleep(0.2)
            
        logger.log_info("="*50 + "\n")
        
        # 确保所有日志都被输出
        print("\n处理结果汇总输出完成，正在完成最终步骤...")
        sys.stdout.flush()
        time.sleep(1)  # 增加延时
        
        logger.complete_step("处理LLM加班记录", f"✓ 处理完成 (成功率: {success_rate:.1f}%)")
        # 再次确保输出被刷新
        sys.stdout.flush()
        time.sleep(0.5)  # 添加延时

        
    except Exception as e:
        logger.log_error(f"程序执行出错: {e}")
        logger.log_database_operation("回滚数据库事务", "attendance_result")
        conn.rollback()
        logger.complete_step("处理LLM加班记录", f"✗ 处理失败: {e}")
    finally:
        cursor.close()
        conn.close()
        logger.log_database_operation("数据库连接已关闭", "database")
        # 确保数据库关闭日志被输出
        sys.stdout.flush()
        time.sleep(0.5)

def main():
    logger.start_script("考勤加班记录更新器")
    
    try:
        process_llm_records()
        # 添加更长的延迟，确保所有日志都被输出
        print("\n正在确保所有日志输出完成...")
        sys.stdout.flush()
        time.sleep(3)  # 增加到3秒
        logger.finish_script("考勤加班记录更新器", "✓ 脚本执行完成")
        # 再次确保所有输出都被刷新
        sys.stdout.flush()
        print("\n程序即将结束，请确认所有日志已输出完毕...")
        sys.stdout.flush()
        time.sleep(2)  # 增加到2秒
    except Exception as e:
        logger.log_error(f"脚本执行失败: {e}")
        logger.finish_script("考勤加班记录更新器", f"✗ 脚本执行失败: {e}")
        # 确保错误日志也被刷新
        sys.stdout.flush()
        time.sleep(2)  # 增加到2秒

if __name__ == "__main__":
    try:
        main()
        # 脚本结束前的最终延时，确保所有日志都被输出
        print("\n脚本执行完毕，正在确保所有日志输出完成...")
        sys.stdout.flush()
        time.sleep(3)
        print("程序结束。")
        sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.stdout.flush()