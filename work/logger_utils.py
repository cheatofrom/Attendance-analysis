import sys
import time
from datetime import datetime
from typing import Optional, Any
import traceback

class ProgressLogger:
    """统一的进度日志监控类"""
    
    def __init__(self, script_name: str):
        self.script_name = script_name
        self.start_time = None
        self.current_step = ""
        self.total_steps = 0
        self.completed_steps = 0
        
    def start_script(self, script_description: str = None, total_steps: int = 0):
        """开始脚本执行"""
        self.start_time = time.time()
        self.total_steps = total_steps
        self.completed_steps = 0
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if script_description:
            self.log(f"🚀 [{self.script_name}] {script_description} - {timestamp}")
        else:
            self.log(f"🚀 [{self.script_name}] 脚本开始执行 - {timestamp}")
            
        if total_steps > 0:
            self.log(f"📋 总共需要执行 {total_steps} 个主要步骤")
    
    def start_step(self, step_name: str, step_number: int = None):
        """开始执行某个步骤"""
        self.current_step = step_name
        if step_number:
            self.completed_steps = step_number - 1
            progress = f"[{step_number}/{self.total_steps}]" if self.total_steps > 0 else f"[{step_number}]"
            self.log(f"🔄 {progress} {step_name}...")
        else:
            self.log(f"🔄 {step_name}...")
    
    def complete_step(self, step_name: str = None, status_message: str = None):
        """完成某个步骤"""
        step_name = step_name or self.current_step
        self.completed_steps += 1
        
        if status_message:
            if "✓" in status_message:
                icon = "✅"
                status = status_message
            elif "✗" in status_message:
                icon = "❌"
                status = status_message
            else:
                icon = "✅"
                status = status_message
        else:
            icon = "✅"
            status = "完成"
            
        elapsed = self._get_elapsed_time()
        progress = f"[{self.completed_steps}/{self.total_steps}]" if self.total_steps > 0 else f"[{self.completed_steps}]"
        self.log(f"{icon} {progress} {step_name} {status} - 耗时: {elapsed}")
    
    def log_progress(self, category: str, message: str, current: int = None, total: int = None, item_name: str = "项"):
        """记录处理进度"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if current is not None and total is not None:
            # 数值进度模式
            percentage = (current / total * 100) if total > 0 else 0
            progress_bar = self._create_progress_bar(current, total)
            elapsed = self._get_elapsed_time()
            
            # 估算剩余时间
            if current > 0 and self.start_time:
                elapsed_seconds = time.time() - self.start_time
                avg_time_per_item = elapsed_seconds / current
                remaining_items = total - current
                eta_seconds = avg_time_per_item * remaining_items
                eta = self._format_time(eta_seconds)
                eta_info = f" | 预计剩余: {eta}"
            else:
                eta_info = ""
                
            self.log(f"📊 [{timestamp}] {category}: {message} {progress_bar} {current}/{total} {item_name} ({percentage:.1f}%) - 已用时: {elapsed}{eta_info}")
        else:
            # 文本进度模式
            self.log(f"📊 [{timestamp}] {category}: {message}")
    
    def log_data_processing(self, operation: str, current_row: int = None, total_rows: int = None, data_info: str = ""):
        """记录数据处理进度"""
        if current_row is not None and total_rows is not None:
             if current_row % 100 == 0 or current_row == total_rows:  # 每100条记录或最后一条记录时输出
                 extra_info = f" | {data_info}" if data_info else ""
                 self.log_progress("数据处理", f"{operation}", current_row, total_rows, "条数据")
                 if extra_info:
                     self.log(f"   └─ {data_info}")
        else:
            # 文本模式
            timestamp = datetime.now().strftime("%H:%M:%S")
            info_text = f" | {data_info}" if data_info else ""
            self.log(f"🔄 [{timestamp}] {operation}{info_text}")
    
    def log_database_operation(self, operation: str, table_name: str, affected_rows: int = None):
        """记录数据库操作"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if affected_rows is not None:
            self.log(f"🗄️  [{timestamp}] 数据库操作: {operation} 表 '{table_name}' - 影响 {affected_rows} 行")
        else:
            self.log(f"🗄️  [{timestamp}] 数据库操作: {operation} 表 '{table_name}'")
    
    def log_file_operation(self, operation: str, file_path: str, file_size: str = None):
        """记录文件操作"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        size_info = f" | 大小: {file_size}" if file_size else ""
        self.log(f"📁 [{timestamp}] 文件操作: {operation} '{file_path}'{size_info}")
    
    def log_error(self, error_msg: str, exception: Exception = None, context: str = None):
        """记录错误信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log(f"❌ [{timestamp}] 错误: {error_msg}")
        
        if context:
            self.log(f"   └─ 上下文: {context}")
            
        if exception:
            self.log(f"   └─ 异常类型: {type(exception).__name__}")
            self.log(f"   └─ 异常详情: {str(exception)}")
            
            # 记录堆栈跟踪（仅前几行，避免过长）
            tb_lines = traceback.format_exc().split('\n')
            relevant_lines = [line for line in tb_lines if 'work/' in line or 'File' in line][:5]
            if relevant_lines:
                self.log("   └─ 堆栈跟踪:")
                for line in relevant_lines:
                    if line.strip():
                        self.log(f"      {line.strip()}")
    
    def log_warning(self, warning_msg: str, context: str = None):
        """记录警告信息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log(f"⚠️  [{timestamp}] 警告: {warning_msg}")
        if context:
            self.log(f"   └─ 上下文: {context}")
    
    def log_info(self, info_msg: str, details: str = None):
        """记录信息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log(f"ℹ️  [{timestamp}] {info_msg}")
        if details:
            self.log(f"   └─ {details}")
    
    def finish_script(self, script_description: str = None, summary: str = None):
        """结束脚本执行"""
        total_elapsed = self._get_total_elapsed_time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if script_description and "✓" in summary if summary else False:
            self.log(f"🎉 [{self.script_name}] {script_description} 执行成功完成 - {timestamp}")
        elif script_description and "✗" in summary if summary else False:
            self.log(f"💥 [{self.script_name}] {script_description} 执行失败 - {timestamp}")
        elif script_description:
            self.log(f"🎉 [{self.script_name}] {script_description} 执行完成 - {timestamp}")
        else:
            self.log(f"🎉 [{self.script_name}] 脚本执行完成 - {timestamp}")
            
        self.log(f"⏱️  总执行时间: {total_elapsed}")
        
        if self.total_steps > 0:
            self.log(f"📈 完成步骤: {self.completed_steps}/{self.total_steps}")
            
        if summary:
            self.log(f"📝 执行摘要: {summary}")
    
    def log(self, message: str):
        """输出日志消息"""
        print(message)
        sys.stdout.flush()
    
    def _create_progress_bar(self, current: int, total: int, width: int = 20) -> str:
        """创建进度条"""
        if total == 0:
            return "[" + "─" * width + "]"
            
        filled = int(width * current / total)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def _get_elapsed_time(self) -> str:
        """获取从开始到现在的耗时"""
        if not self.start_time:
            return "未知"
        elapsed_seconds = time.time() - self.start_time
        return self._format_time(elapsed_seconds)
    
    def _get_total_elapsed_time(self) -> str:
        """获取总耗时"""
        if not self.start_time:
            return "未知"
        elapsed_seconds = time.time() - self.start_time
        return self._format_time(elapsed_seconds)
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}分{secs:.1f}秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours}小时{minutes}分{secs:.1f}秒"

# 便捷函数
def create_logger(script_name: str) -> ProgressLogger:
    """创建日志记录器"""
    return ProgressLogger(script_name)

# 装饰器用于自动记录函数执行时间
def log_execution_time(logger: ProgressLogger, operation_name: str):
    """装饰器：自动记录函数执行时间"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.log(f"🔄 开始执行: {operation_name}")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.log(f"✅ 完成执行: {operation_name} - 耗时: {logger._format_time(elapsed)}")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.log_error(f"执行失败: {operation_name} - 耗时: {logger._format_time(elapsed)}", e)
                raise
        return wrapper
    return decorator