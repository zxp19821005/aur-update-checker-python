# -*- coding: utf-8 -*-
"""
错误处理使用示例，展示如何在项目中使用增强的错误处理功能
"""
import asyncio
import os
import aiohttp
import time
from typing import Dict, Any, Optional

# 导入错误处理集成模块
from .error_handler_integration import (
    network_request_error_handler,
    async_network_request_error_handler,
    file_io_error_handler,
    get_error_statistics
)

# 导入错误配置模块
from .error_configuration import ErrorHandlerConfig

class ErrorHandlingExamples:
    """错误处理使用示例类"""

    def __init__(self, logger, config=None):
        """初始化错误处理示例

        Args:
            logger: 日志记录器
            config: 配置对象（可选）
        """
        self.logger = logger

        # 初始化错误处理配置
        self.error_config = ErrorHandlerConfig(config, logger)

        # 获取网络和I/O配置
        self.network_config = self.error_config.get_network_error_config()
        self.io_config = self.error_config.get_io_error_config()

    # ===== 网络请求错误处理示例 =====

    @network_request_error_handler(
        retry_count=5,  # 重试5次
        retry_delay=1.0,  # 初始延迟1秒
        max_retry_delay=30.0  # 最大延迟30秒
    )
    def fetch_url_with_retry(self, url: str) -> Dict[str, Any]:
        """带重试的URL获取

        演示如何在同步函数中使用网络请求错误处理装饰器

        Args:
            url: 要获取的URL

        Returns:
            Dict: 包含响应数据的字典
        """
        self.logger.info(f"正在获取URL: {url}")

        # 这里仅作示例，实际应用应该使用异步HTTP客户端
        import requests

        # 发送HTTP请求
        response = requests.get(
            url, 
            timeout=self.network_config.get("timeout", 30.0)
        )

        # 检查响应
        response.raise_for_status()  # 如果状态码不是2xx，将引发异常

        # 尝试解析JSON响应
        try:
            return response.json()
        except ValueError:
            return {"text": response.text}

    @async_network_request_error_handler(
        retry_count=3,
        retry_delay=1.0
    )
    async def fetch_url_async_with_retry(self, url: str) -> Dict[str, Any]:
        """带重试的异步URL获取

        演示如何在异步函数中使用网络请求错误处理装饰器

        Args:
            url: 要获取的URL

        Returns:
            Dict: 包含响应数据的字典
        """
        self.logger.info(f"正在异步获取URL: {url}")

        # 使用aiohttp发送异步HTTP请求
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.network_config.get("timeout", 30.0))
            ) as response:
                # 检查响应
                if response.status >= 400:
                    response.raise_for_status()

                # 尝试解析JSON响应
                try:
                    return await response.json()
                except ValueError:
                    return {"text": await response.text()}

    # ===== 文件I/O错误处理示例 =====

    @file_io_error_handler(
        retry_count=3,
        create_dirs=True  # 如果目录不存在，尝试创建
    )
    def save_data_to_file(self, file_path: str, data: Any) -> bool:
        """安全地将数据保存到文件

        演示如何使用文件I/O错误处理装饰器

        Args:
            file_path: 文件路径
            data: 要保存的数据

        Returns:
            bool: 是否保存成功
        """
        self.logger.info(f"正在保存数据到文件: {file_path}")

        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 根据数据类型选择写入方式
        if isinstance(data, (dict, list)):
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif isinstance(data, bytes):
            with open(file_path, 'wb') as f:
                f.write(data)
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(str(data))

        self.logger.debug(f"数据已成功保存到: {file_path}")
        return True

    # ===== 结合使用示例 =====

    async def download_and_save_file(self, url: str, file_path: str) -> bool:
        """从URL下载文件并保存到指定路径

        演示如何组合使用不同的错误处理装饰器

        Args:
            url: 文件URL
            file_path: 保存路径

        Returns:
            bool: 是否成功
        """
        self.logger.info(f"正在下载文件 {url} 并保存到 {file_path}")

        try:
            # 使用异步错误处理下载文件
            data = await self.download_file_with_retry(url)
            if not data:
                self.logger.error("下载失败")
                return False

            # 使用I/O错误处理保存文件
            return self.save_data_to_file(file_path, data)

        except Exception as e:
            self.logger.error(f"下载并保存文件时出错: {str(e)}")
            return False

    @async_network_request_error_handler(
        retry_count=3,
        retry_delay=2.0
    )
    async def download_file_with_retry(self, url: str) -> bytes:
        """带重试的文件下载

        Args:
            url: 文件URL

        Returns:
            bytes: 文件数据
        """
        self.logger.info(f"正在下载文件: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    response.raise_for_status()

                return await response.read()

    # ===== 错误统计和分析 =====

    def print_error_statistics(self):
        """打印错误统计信息"""
        stats = get_error_statistics()

        self.logger.info("===== 错误统计信息 =====")

        if "error" in stats:
            self.logger.warning(f"无法获取错误统计: {stats['error']}")
            return

        self.logger.info(f"总错误数: {stats.get('total_errors', 0)}")
        self.logger.info(f"已解决错误数: {stats.get('resolved_count', 0)}")

        # 按分类统计
        if 'by_category' in stats:
            self.logger.info("按分类统计:")
            for category, count in stats['by_category'].items():
                self.logger.info(f"  - {category}: {count}")

        # 按严重程度统计
        if 'by_severity' in stats:
            self.logger.info("按严重程度统计:")
            for severity, count in stats['by_severity'].items():
                self.logger.info(f"  - {severity}: {count}")

    def clear_error_records(self):
        """清除错误记录"""
        if self.error_config.clear_error_records():
            self.logger.info("已清除所有错误记录")
        else:
            self.logger.warning("清除错误记录失败")
