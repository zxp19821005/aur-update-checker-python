# -*- coding: utf-8 -*-
"""
Web 上游检查器抽象类，用于处理基于网页的版本检查
"""
import re
import asyncio
from abc import abstractmethod
from datetime import datetime
from bs4 import BeautifulSoup
from .base_checker import BaseChecker
from ..version_processor import VersionProcessor
from ..http_client import HttpClient

class WebChecker(BaseChecker):
    """Web上游检查器抽象类，为所有基于网页内容的检查器提供共同功能"""

    def __init__(self, logger, config=None, main_checker=None):
        """初始化Web检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例（可选）
            main_checker: 主检查器实例（可选）
        """
        super().__init__(logger, config)
        self.config = config
        self.main_checker = main_checker
        self.version_processor = VersionProcessor(logger, self.package_config)

        # Web请求通用配置
        self.timeout = 30
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        self.headers = {
            "User-Agent": self.user_agent
        }

        # 如果提供了配置，从配置中读取
        if config:
            self.user_agent = config.get("upstream.user_agent", self.user_agent)
            self.timeout = config.get("upstream.timeout", self.timeout)
            self.headers["User-Agent"] = self.user_agent

    def _get_http_client(self):
        """获取HTTP客户端实例

        Returns:
            HttpClient: HTTP客户端实例
        """
        # 获取单例实例并配置
        http_client = HttpClient.get_instance(self.logger)

        # 配置客户端，应用自定义头信息和超时
        http_client.configure(headers=self.headers, timeout=self.timeout)

        return http_client

    async def _get_session(self):
        """获取HTTP客户端实例，保持与旧代码的兼容性

        Returns:
            HttpClient: HTTP客户端实例
        """
        return self._get_http_client()

    async def _fetch_page(self, url):
        """获取网页内容

        Args:
            url: 要获取的URL

        Returns:
            str: 网页内容

        Raises:
            Exception: 请求失败时抛出
        """
        self.logger.debug(f"获取网页内容: {url}")

        http_client = self._get_http_client()

        try:
            result = await http_client.get_text(url)

            if result is None:
                raise Exception(f"获取网页失败: {url}")

            return result

        except asyncio.TimeoutError:
            raise Exception(f"网页请求超时: {url}")

        except Exception as e:
            self.logger.error(f"网页请求错误: {str(e)}")
            raise

    async def _parse_html(self, html_content, parser="html.parser"):
        """解析HTML内容为BeautifulSoup对象

        Args:
            html_content: HTML内容
            parser: 解析器，默认为html.parser

        Returns:
            BeautifulSoup: 解析后的对象
        """
        return BeautifulSoup(html_content, parser)

    async def extract_version_from_text(self, text, version_pattern=None, version_extract_key=None):
        """从文本中提取版本信息

        Args:
            text: 文本内容
            version_pattern: 版本模式（可选）
            version_extract_key: 版本提取键（可选）

        Returns:
            str: 提取的版本号，如果未找到则返回None
        """
        if version_pattern:
            # 将version_pattern转换为正则表达式
            pattern = version_pattern.replace('.', r'\.').replace('x', r'\d+')
            match = re.search(pattern, text)
            if match:
                return match.group()

        # 使用version_processor提取版本
        version = self.version_processor.extract_version_from_text(text)
        if version:
            return version

        # 如果提供了version_extract_key，尝试使用它提取版本
        if version_extract_key and version_extract_key in text:
            pattern = f"{re.escape(version_extract_key)}(\d+(?:\.\d+)*)"
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return None

    @abstractmethod
    async def parse_page_content(self, content, **kwargs):
        """解析网页内容，子类必须实现此方法

        Args:
            content: 网页内容
            **kwargs: 其他参数

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
