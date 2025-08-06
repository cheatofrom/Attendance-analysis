# 休息日配置 (格式: "DD")
HOLIDAYS = [
    "05",
    "06",
    "13",
    "19",
    "20",
    "27"
]
MONTH='07'
YEAR=2025  # 修改为整数类型
def get_working_days():
    """计算应出勤天数（总天数减去休息日）"""
    import calendar
    
    # 获取当前月份的总天数
    year = YEAR  # 可以根据实际需求修改
    month = int(MONTH)
    total_days = calendar.monthrange(year, month)[1]
    
    # 计算应出勤天数
    working_days = total_days - len(HOLIDAYS)
    return working_days
    