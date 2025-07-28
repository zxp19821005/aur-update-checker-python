# -*- coding: utf-8 -*-
"""
日志格式化相关功能
"""
from datetime import datetime

def format_colored_log(log):
    """格式化为彩色HTML格式的日志

    Args:
        log: 日志条目

    Returns:
        str: 格式化后的HTML格式日志
    """
    try:
        level = log.get("level", "INFO").upper()
        timestamp = log.get("timestamp", "")
        module = log.get("module", "")
        message = log.get("message", "")

        # 根据日志级别定义颜色（适合黑色背景）
        level_colors = {
            "DEBUG": "#9ca3af",  # 亮灰色
            "INFO": "#60a5fa",   # 亮蓝色
            "WARNING": "#fcd34d", # 亮黄色
            "ERROR": "#f87171",   # 亮红色
            "CRITICAL": "#ef4444" # 鲜红色
        }

        # 获取该级别的颜色，默认为白色
        level_color = level_colors.get(level, "#FFFFFF")

        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        # 使用HTML格式生成彩色日志
        return (f'<span style="color: #aaa;">{timestamp}</span> '
              + f'<span style="color: {level_color}; font-weight: bold;">[{level}]</span> '
              + f'<span style="color: #4cc0cf;">{module}</span>: '
              + f'<span style="color: #ddd;">{message}</span>')
    except Exception:
        return ""

def format_plain_log(log):
    """格式化为纯文本格式的日志

    Args:
        log: 日志条目

    Returns:
        str: 格式化后的纯文本格式日志
    """
    try:
        level = log.get("level", "INFO").upper()
        timestamp = log.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        module = log.get("module", "")
        message = log.get("message", "")
        return f"{timestamp} [{level}] {module}: {message}"
    except Exception:
        return ""

def format_log(log, use_colored_logs=True):
    """根据设置选择合适的格式化方法

    Args:
        log: 日志条目
        use_colored_logs: 是否使用彩色日志

    Returns:
        str: 格式化后的日志
    """
    if use_colored_logs:
        return format_colored_log(log)
    else:
        return format_plain_log(log)
