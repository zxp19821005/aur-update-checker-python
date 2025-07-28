# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

class BaseChecker(ABC):
    """上游检查器基类，所有具体的上游检查器都应该继承这个类"""

    def __init__(self, logger, package_config=None):
        """初始化基类

        Args:
            logger: 日志模块实例
            package_config: 软件包配置字典（可选）
        """
        self.logger = logger
        self.package_config = package_config

    @abstractmethod
    async def check_version(self, package_name, url, version_extract_key=None):
        """检查上游版本的抽象方法，所有子类必须实现这个方法

        Args:
            package_name: 软件包名称
            url: 上游URL
            version_extract_key: 版本提取键（可选）

        Returns:
            dict: 包含版本信息的字典
        """
        pass
