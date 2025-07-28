# -*- coding: utf-8 -*-
"""
错误处理配置模块，提供错误处理系统的全局配置
"""
import os
import json
import logging
from typing import Dict, Any, Optional

# 尝试导入增强错误处理功能
try:
    from .error_handler_integration import (
        ENHANCED_ERROR_HANDLING_AVAILABLE,
        get_error_registry,
        ErrorSeverity,
        ErrorCategory
    )
except ImportError:
    ENHANCED_ERROR_HANDLING_AVAILABLE = False


class ErrorHandlerConfig:
    """错误处理系统配置类"""

    def __init__(self, config=None, logger=None):
        """初始化错误处理配置

        Args:
            config: 应用程序配置对象（可选）
            logger: 日志记录器（可选）
        """
        self.logger = logger or logging.getLogger(__name__)
        self.config = config

        # 默认配置
        self.default_config = {
            "error_handling": {
                "enabled": True,
                "log_to_file": True,
                "error_log_path": "logs/errors.log",
                "max_error_records": 1000,
                "report_errors": True,
                "show_traceback": True,

                # 网络请求错误处理配置
                "network": {
                    "retry_count": 5,
                    "retry_delay": 1.0,
                    "max_retry_delay": 60.0,
                    "timeout": 30.0,
                    "respect_retry_after": True,
                    "retry_status_codes": [429, 500, 502, 503, 504]
                },

                # I/O操作错误处理配置
                "io": {
                    "retry_count": 3,
                    "retry_delay": 0.5,
                    "create_missing_dirs": True
                }
            }
        }

        # 从配置对象加载设置
        self.settings = self._load_from_config()

        # 初始化错误处理系统
        self._initialize()

    def _load_from_config(self) -> Dict[str, Any]:
        """从应用配置加载错误处理设置"""
        settings = dict(self.default_config)

        if self.config:
            # 从应用配置对象加载错误处理设置
            error_config = {}

            # 尝试不同的配置路径，兼容不同配置结构
            for key in ["error_handling", "error", "errors"]:
                if self.config.get(key):
                    error_config = self.config.get(key)
                    break

            if error_config:
                # 更新顶层配置
                for key, value in error_config.items():
                    if key in settings["error_handling"] and not isinstance(value, dict):
                        settings["error_handling"][key] = value

                # 更新网络配置
                network_config = error_config.get("network", {})
                if network_config:
                    for key, value in network_config.items():
                        if key in settings["error_handling"]["network"]:
                            settings["error_handling"]["network"][key] = value

                # 更新I/O配置
                io_config = error_config.get("io", {})
                if io_config:
                    for key, value in io_config.items():
                        if key in settings["error_handling"]["io"]:
                            settings["error_handling"]["io"][key] = value

        return settings

    def _initialize(self):
        """初始化错误处理系统"""
        # 检查是否启用错误处理
        if not self.settings["error_handling"]["enabled"]:
            self.logger.info("错误处理系统已禁用")
            return

        # 检查是否存在增强错误处理模块
        if not ENHANCED_ERROR_HANDLING_AVAILABLE:
            self.logger.warning("增强错误处理模块不可用，使用基本错误处理")
            return

        # 设置全局错误注册表
        registry = get_error_registry()
        if registry:
            registry.max_records = self.settings["error_handling"]["max_error_records"]
            self.logger.debug(f"错误注册表已配置，最大记录数: {registry.max_records}")

        # 配置错误日志文件
        if self.settings["error_handling"]["log_to_file"]:
            log_path = self.settings["error_handling"]["error_log_path"]

            # 确保日志目录存在
            log_dir = os.path.dirname(log_path)
            if log_dir and not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir, exist_ok=True)
                    self.logger.debug(f"创建错误日志目录: {log_dir}")
                except Exception as e:
                    self.logger.warning(f"无法创建错误日志目录: {str(e)}")

        self.logger.info("错误处理系统已初始化")

    def get_network_error_config(self) -> Dict[str, Any]:
        """获取网络错误处理配置"""
        return self.settings["error_handling"]["network"]

    def get_io_error_config(self) -> Dict[str, Any]:
        """获取I/O错误处理配置"""
        return self.settings["error_handling"]["io"]

    def is_enhanced_available(self) -> bool:
        """检查增强错误处理是否可用"""
        return ENHANCED_ERROR_HANDLING_AVAILABLE

    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        if not ENHANCED_ERROR_HANDLING_AVAILABLE:
            return {"error": "增强错误处理模块不可用"}

        registry = get_error_registry()
        if not registry:
            return {"error": "错误注册表不可用"}

        return registry.get_error_statistics()

    def clear_error_records(self, only_resolved: bool = False) -> bool:
        """清除错误记录

        Args:
            only_resolved: 如果为True，只清除已解决的错误记录

        Returns:
            bool: 操作是否成功
        """
        if not ENHANCED_ERROR_HANDLING_AVAILABLE:
            return False

        registry = get_error_registry()
        if not registry:
            return False

        if only_resolved:
            registry.clear_resolved()
        else:
            registry.clear_all()

        return True
