# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import shutil
from datetime import datetime
from loguru import logger
import threading
from pathlib import Path

class LoggerModule:
    """
    日志模块，负责处理应用日志记录功能。
    支持统一的日志格式和动态调整日志级别。
    """

    # 单例实例
    _instance = None

    @staticmethod
    def get_instance():
        """获取 LoggerModule 的单例实例"""
        if LoggerModule._instance is None:
            LoggerModule._instance = LoggerModule()
        return LoggerModule._instance

    def __init__(self, module_name="general"):
        """初始化日志模块

        Args:
            module_name: 模块名称，默认为 'general'
        """
        # 模块名称
        self.module_name = module_name

        # 日志级别定义
        self.LOG_LEVELS = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50
        }

        # 默认日志级别
        self.current_log_level = self.LOG_LEVELS["DEBUG"]

        # 存储最近的日志
        self.recent_logs = []
        self.max_logs_to_store = 1000

        # 配置日志格式
        log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

        # 清除默认处理器
        logger.remove()

        # 添加控制台处理器
        logger.add(sys.stderr, format=log_format, level="DEBUG", enqueue=True)

        # 尝试从配置系统获取日志路径
        try:
            from .config import ConfigManager
            config = ConfigManager.get_instance()
            # 获取配置中的日志路径，如果不存在则使用默认值
            log_path = config.get("logging.path")
            if log_path and os.path.exists(os.path.dirname(log_path)):
                logs_dir = log_path
            else:
                # 使用默认路径
                config_dir = os.path.join(os.path.expanduser("~"), ".config", "aur-update-checker-python")
                if not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)
                logs_dir = os.path.join(config_dir, "logs")
        except (ImportError, Exception) as e:
            # 配置系统不可用，使用默认路径
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "aur-update-checker-python")
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            logs_dir = os.path.join(config_dir, "logs")

        # 确保日志目录存在
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)

        # 主日志文件 - 使用高级轮转配置
        # 尝试从配置系统获取日志文件名
        try:
            log_file_name = "aur-checker.log"  # 默认文件名
            if 'config' in locals():  # 确保config已定义
                custom_log_file = config.get("logging.file")
                if custom_log_file:
                    log_file_name = custom_log_file
        except Exception:
            log_file_name = "aur-checker.log"  # 出错时使用默认文件名

        main_log_file = os.path.join(logs_dir, log_file_name)
        logger.add(
            main_log_file, 
            format=log_format, 
            level="DEBUG", 
            rotation="5 MB",  # 当文件达到5MB时轮转
            retention="1 week",  # 保留1周的日志
            compression="zip", 
            enqueue=True,
            backtrace=True,  # 错误日志包含回溯信息
            diagnose=True    # 增强诊断信息
        )

        # 错误日志单独存储
        error_log_file = os.path.join(logs_dir, "errors.log")
        logger.add(
            error_log_file,
            format=log_format,
            level="ERROR",  # 只记录错误和严重错误
            rotation="1 day",  # 每天轮转
            retention="30 days",  # 保留30天
            compression="zip",
            enqueue=True,
            backtrace=True
        )

        # 限制日志文件总大小
        self.max_total_log_size = 500 * 1024 * 1024  # 500MB

        # 设置当前模块日志上下文
        self.logger = logger.bind(name=module_name)

        # 添加结构化JSON日志
        structured_log_file = os.path.join(logs_dir, "structured.jsonl")
        json_format = '{{"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", "level": "{level}", "module": "{name}", "function": "{function}", "line": {line}, "message": {message}, "extra": {extra}}}'
        logger.add(
            structured_log_file,
            format=json_format,
            level="INFO",
            rotation="1 day",
            retention="1 week",
            compression="zip",
            serialize=True  # 确保日志被序列化为JSON
        )

        # 启动日志清理线程
        self._start_log_maintenance_thread(logs_dir)

        self.logger.info(f"{module_name} 日志模块初始化完成")

    def _start_log_maintenance_thread(self, logs_dir):
        """启动日志维护线程，定期检查和清理日志文件

        Args:
            logs_dir: 日志目录路径
        """
        def maintenance_task():
            while True:
                try:
                    # 每天运行一次维护任务
                    time.sleep(86400)  # 24小时
                    self.logger.debug("执行日志维护任务...")
                    self._clean_old_logs(logs_dir)
                    self._check_total_logs_size(logs_dir)
                except Exception as e:
                    self.logger.error(f"日志维护任务失败: {str(e)}")

        # 启动后台线程
        thread = threading.Thread(target=maintenance_task, daemon=True)
        thread.start()
        self.logger.debug("日志维护线程已启动")

    def _clean_old_logs(self, logs_dir):
        """清理过旧的日志文件

        Args:
            logs_dir: 日志目录路径
        """
        now = time.time()
        max_age = 30 * 86400  # 30天

        try:
            for path in Path(logs_dir).glob("**/*"):
                if path.is_file() and path.suffix in ['.zip', '.gz', '.log']:
                    file_age = now - path.stat().st_mtime
                    if file_age > max_age:
                        path.unlink()
                        self.logger.debug(f"已删除过旧的日志文件: {path}")

            self.logger.info("日志清理完成")
        except Exception as e:
            self.logger.error(f"清理旧日志失败: {str(e)}")

    def _check_total_logs_size(self, logs_dir):
        """检查日志总大小并在必要时清理

        Args:
            logs_dir: 日志目录路径
        """
        try:
            total_size = sum(f.stat().st_size for f in Path(logs_dir).glob("**/*") if f.is_file())
            self.logger.debug(f"当前日志总大小: {total_size / (1024 * 1024):.2f} MB")

            # 如果超出最大大小限制
            if total_size > self.max_total_log_size:
                self.logger.warning(f"日志总大小超出限制 ({total_size / (1024 * 1024):.2f} MB > {self.max_total_log_size / (1024 * 1024)} MB)")

                # 获取所有压缩日志文件，按修改时间排序
                files = sorted(
                    [f for f in Path(logs_dir).glob("**/*.zip") if f.is_file()], 
                    key=lambda f: f.stat().st_mtime
                )

                # 删除最旧的日志文件，直到总大小低于85%的限制
                target_size = 0.85 * self.max_total_log_size
                while files and total_size > target_size:
                    oldest_file = files.pop(0)  # 获取最旧的文件
                    file_size = oldest_file.stat().st_size
                    oldest_file.unlink()
                    total_size -= file_size
                    self.logger.info(f"已删除旧日志文件以释放空间: {oldest_file}")

                self.logger.info(f"清理后日志总大小: {total_size / (1024 * 1024):.2f} MB")
        except Exception as e:
            self.logger.error(f"检查日志大小失败: {str(e)}")

    def log_structured(self, level, message, **extra):
        """记录结构化日志

        Args:
            level: 日志级别
            message: 日志消息
            **extra: 额外的结构化数据
        """
        # 使用标准日志级别函数，并附加额外数据
        log_func = getattr(self.logger, level.lower(), None)
        if log_func and callable(log_func):
            # 使用loguru的bind方法添加额外字段
            log_func(message, **extra)

            # 添加到内存日志
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level.lower(),
                "message": message,
                "module": self.module_name,
                "extra": extra
            }
            self.recent_logs.insert(0, log_entry)

            # 限制日志数量
            if len(self.recent_logs) > self.max_logs_to_store:
                self.recent_logs.pop()

    def set_log_level(self, level):
        """设置日志级别

        Args:
            level: 日志级别名称，例如 'DEBUG', 'INFO' 等
        """
        if level.upper() in self.LOG_LEVELS:
            self.current_log_level = self.LOG_LEVELS[level.upper()]
            self.info(f"日志级别已设置为: {level}")
        else:
            self.warning(f"无效的日志级别: {level}，使用默认级别 DEBUG")

    def get_log_levels(self):
        """获取日志级别名称列表

        Returns:
            list: 日志级别名称列表
        """
        return list(self.LOG_LEVELS.keys())

    def get_current_log_level(self):
        """获取当前日志级别

        Returns:
            str: 当前日志级别名称
        """
        for name, level in self.LOG_LEVELS.items():
            if level == self.current_log_level:
                return name
        return "UNKNOWN"

    def add_to_recent_logs(self, level, message, extra=None):
        """添加日志到最近的日志列表，支持结构化数据

        Args:
            level: 日志级别
            message: 日志消息
            extra: 额外的结构化数据（可选）
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.lower(),
            "message": message if isinstance(message, str) else str(message),
            "module": self.module_name
        }

        # 如果有额外数据，添加到日志条目中
        if extra:
            log_entry["extra"] = extra

        # 添加上下文信息
        log_entry["context"] = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pid": os.getpid(),
            "thread_name": threading.current_thread().name
        }

        self.recent_logs.insert(0, log_entry)

        # 限制日志数量
        if len(self.recent_logs) > self.max_logs_to_store:
            self.recent_logs.pop()

    def get_recent_logs(self, count=100, min_level=None):
        """获取最近的日志

        Args:
            count: 要获取的日志数量，默认为100
            min_level: 最低日志级别，默认为None (不过滤)

        Returns:
            list: 最近的日志列表
        """
        # 如果没有指定最低级别，使用当前设置的日志级别
        if min_level is None:
            min_level = self.current_log_level
        else:
            # 如果提供的是级别名称，转换为对应的数值
            if isinstance(min_level, str) and min_level.upper() in self.LOG_LEVELS:
                min_level = self.LOG_LEVELS[min_level.upper()]

        # 过滤低于指定级别的日志
        filtered_logs = [log for log in self.recent_logs if 
                        self.LOG_LEVELS.get(log.get("level", "").upper(), 0) >= min_level]

        # 返回指定数量的日志
        return filtered_logs[:count]

    def debug(self, message, **extra):
        """记录调试级别日志，支持额外结构化数据

        Args:
            message: 日志消息
            **extra: 额外的结构化数据，将作为JSON字段记录
        """
        if self.LOG_LEVELS["DEBUG"] >= self.current_log_level:
            if extra:
                # 带有额外结构化数据的日志
                self.logger.bind(**extra).debug(message)
                self.add_to_recent_logs("DEBUG", message, extra)
            else:
                # 普通日志
                self.logger.debug(message)
                self.add_to_recent_logs("DEBUG", message)

    def info(self, message, **extra):
        """记录信息级别日志，支持额外结构化数据

        Args:
            message: 日志消息
            **extra: 额外的结构化数据，将作为JSON字段记录
        """
        if self.LOG_LEVELS["INFO"] >= self.current_log_level:
            if extra:
                # 带有额外结构化数据的日志
                self.logger.bind(**extra).info(message)
                self.add_to_recent_logs("INFO", message, extra)
            else:
                # 普通日志
                self.logger.info(message)
                self.add_to_recent_logs("INFO", message)

    def warning(self, message, **extra):
        """记录警告级别日志，支持额外结构化数据

        Args:
            message: 日志消息
            **extra: 额外的结构化数据，将作为JSON字段记录
        """
        if self.LOG_LEVELS["WARNING"] >= self.current_log_level:
            if extra:
                # 带有额外结构化数据的日志
                self.logger.bind(**extra).warning(message)
                self.add_to_recent_logs("WARNING", message, extra)
            else:
                # 普通日志
                self.logger.warning(message)
                self.add_to_recent_logs("WARNING", message)

    def error(self, message, **extra):
        """记录错误级别日志，支持额外结构化数据

        Args:
            message: 日志消息
            **extra: 额外的结构化数据，将作为JSON字段记录
        """
        if self.LOG_LEVELS["ERROR"] >= self.current_log_level:
            if extra:
                # 带有额外结构化数据的日志
                self.logger.bind(**extra).error(message)
                self.add_to_recent_logs("ERROR", message, extra)
            else:
                # 普通日志
                self.logger.error(message)
                self.add_to_recent_logs("ERROR", message)

    def critical(self, message, **extra):
        """记录严重错误级别日志，支持额外结构化数据

        Args:
            message: 日志消息
            **extra: 额外的结构化数据，将作为JSON字段记录
        """
        if self.LOG_LEVELS["CRITICAL"] >= self.current_log_level:
            if extra:
                # 带有额外结构化数据的日志
                self.logger.bind(**extra).critical(message)
                self.add_to_recent_logs("CRITICAL", message, extra)
            else:
                # 普通日志
                self.logger.critical(message)
                self.add_to_recent_logs("CRITICAL", message)
