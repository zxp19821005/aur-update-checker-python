# -*- coding: utf-8 -*-
"""
提供基础协议（Protocol）类，用于明确定义混入类所依赖的接口
"""
from typing import Protocol, Any, Optional, Dict, List


class LoggerProvider(Protocol):
    """提供日志功能的协议"""

    def debug(self, message: str) -> None:
        """记录调试日志"""
        ...

    def info(self, message: str) -> None:
        """记录信息日志"""
        ...

    def warning(self, message: str) -> None:
        """记录警告日志"""
        ...

    def error(self, message: str) -> None:
        """记录错误日志"""
        ...


class DatabaseProvider(Protocol):
    """提供数据库操作功能的协议"""

    def get_package_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取包信息"""
        ...

    def get_all_packages(self) -> List[Dict[str, Any]]:
        """获取所有包信息"""
        ...

    def update_package(self, package_data: Dict[str, Any]) -> bool:
        """更新包信息"""
        ...


class ConfigProvider(Protocol):
    """提供配置功能的协议"""

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        ...

    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        ...


class MainWindowInterface(LoggerProvider, DatabaseProvider, ConfigProvider):
    """主窗口接口，组合了多个协议接口"""

    logger: Any
    db: Any
    config: Any
