# -*- coding: utf-8 -*-
"""
API 上游检查器抽象类，用于处理基于 API 的版本检查
"""
import asyncio
import json
from abc import abstractmethod
from datetime import datetime
from .base_checker import BaseChecker
from ..version_processor import VersionProcessor
from ..http_client import HttpClient

class ApiChecker(BaseChecker):
    """API上游检查器抽象类，为所有基于API的检查器提供共同功能"""

    def __init__(self, logger, config=None, main_checker=None):
        """初始化API检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例（可选）
            main_checker: 主检查器实例（可选）
        """
        super().__init__(logger, config)
        self.config = config
        self.main_checker = main_checker
        self.version_processor = VersionProcessor(logger, self.package_config)

        # API 通用配置
        self.api_url = ""
        self.timeout = 30
        self.headers = {}

        # 初始化认证信息（子类可以覆盖）
        self.init_auth()

    def init_auth(self):
        """初始化API认证信息，子类可以覆盖此方法提供特定的认证"""
        pass

    def _get_http_client(self):
        """获取HTTP客户端实例

        Returns:
            HttpClient: HTTP客户端实例
        """
        # 获取单例实例并配置
        http_client = HttpClient.get_instance(self.logger)

        # 如果有自定义头信息，应用它们
        if self.headers:
            http_client.configure(headers=self.headers, timeout=self.timeout)

        return http_client

    async def _get_session(self):
        """获取HTTP客户端实例，保持与旧代码的兼容性

        Returns:
            HttpClient: HTTP客户端实例
        """
        return self._get_http_client()

    async def _make_api_request(self, endpoint, params=None, method="GET"):
        """发送API请求

        Args:
            endpoint: API端点
            params: 查询参数（可选）
            method: HTTP方法，默认为GET

        Returns:
            dict: API响应的JSON数据

        Raises:
            Exception: 请求失败时抛出
        """
        url = f"{self.api_url}/{endpoint}"
        self.logger.debug(f"发送API请求: {url}")

        http_client = self._get_http_client()

        try:
            if method.upper() == "GET":
                result = await http_client.get(url, params=params, timeout=self.timeout)

                if not result["success"]:
                    raise Exception(f"API请求失败: {result.get('status')}, {result.get('error')}")

                return result["data"]
            else:
                # 处理其他HTTP方法
                raise NotImplementedError(f"不支持的HTTP方法: {method}")

        except asyncio.TimeoutError:
            raise Exception(f"API请求超时: {url}")

        except Exception as e:
            self.logger.error(f"API请求错误: {str(e)}")
            raise

    @abstractmethod
    async def parse_api_response(self, data):
        """解析API响应，子类必须实现此方法

        Args:
            data: API响应数据

        Returns:
            dict: 包含版本信息的字典
        """
        pass

    @abstractmethod
    async def check_version(self, package_name, url, **kwargs):
        """检查上游版本，子类必须实现此方法

        Args:
            package_name: 软件包名称
            url: 上游URL
            **kwargs: 其他参数

        Returns:
            dict: 包含版本信息的字典
        """
        pass
