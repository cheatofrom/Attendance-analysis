import os
import pandas as pd
import psycopg2
import psycopg2.extras
from datetime import datetime

# 数据库配置
DB_CONFIG = {
    "host": "192.168.1.66",
    "port": "7432",
    "database": "dingding",
    "user": "root",
    "password": "123456"
}

def get_db_connection():
    """创建数据库连接"""
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def export_llm_results_to_excel():
    """导出llm_results表数据为Excel文件"""
    try:
        # 连接数据库
        conn = get_db_connection()
        if not conn:
            return None
            
        # 查询llm_results表数据
        query = """
            SELECT 
                id,
                姓名,
                日期,
                时间,
                时长,
                加班说明,
                来源,
                创建时间
            FROM llm_results
            ORDER BY 创建时间 DESC
        """
        
        # 使用pandas读取数据
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("llm_results表中没有数据")
            conn.close()
            return None
            
        print(f"从llm_results表中读取到 {len(df)} 条记录")
        
        # 创建output目录（如果不存在）
        # 获取项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # 从work目录向上一级到项目根目录
        output_dir = os.path.join(project_root, 'work', 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f'AI处理结果（只供核对）_{timestamp}.xlsx')
        
        # 导出为Excel文件
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # 主数据表
            df.to_excel(writer, index=False, sheet_name='AI处理结果')
            
            # 按来源统计表
            if '来源' in df.columns:
                source_stats = df.groupby('来源').agg({
                    '姓名': 'count',
                    '时长': 'sum'
                }).rename(columns={'姓名': '记录数', '时长': '总时长'})
                source_stats.to_excel(writer, sheet_name='按来源统计')
            
            # 按姓名统计表
            if '姓名' in df.columns:
                name_stats = df.groupby('姓名').agg({
                    '时长': ['count', 'sum', 'mean']
                })
                name_stats.columns = ['记录数', '总时长', '平均时长']
                name_stats.to_excel(writer, sheet_name='按姓名统计')
        
        print(f"✅ AI处理结果已成功导出到: {output_file}")
        
        # 关闭数据库连接
        conn.close()
        
        return output_file
        
    except Exception as e:
        print(f"导出Excel文件时出错: {e}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def main():
    """主函数"""
    print("开始导出llm_results表数据...")
    result_file = export_llm_results_to_excel()
    
    if result_file:
        print(f"导出完成: {result_file}")
    else:
        print("导出失败")

if __name__ == "__main__":
    main()