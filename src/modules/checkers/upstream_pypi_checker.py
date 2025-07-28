# -*- coding: utf-8 -*-
import re
import requests
from datetime import datetime
from .base_checker import BaseChecker

class UpstreamPypiChecker(BaseChecker):
    """PyPI上游版本检查器"""

    def __init__(self, logger, config=None):
        """初始化PyPI检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例（可选）
        """
        super().__init__(logger)
        self.logger.debug("PyPI上游检查器初始化")
        self.config = config

        # PyPI API配置
        self.api_url = "https://pypi.org/pypi"

        # 如果提供了配置，从配置中读取
        if config:
            self.api_url = config.get("pypi.api_url", self.api_url)

    async def check_version(self, package_name, pypi_package, version_extract_key=None):
        """检查PyPI包的最新版本

        Args:
            package_name: 软件包名称
            pypi_package: PyPI包名称
            version_extract_key: 版本提取键（可选）

        Returns:
            dict: 包含版本信息的字典
        """
        self.logger.info(f"正在检查PyPI上游版本: {pypi_package}")

        try:
            # 构建API URL
            api_url = f"{self.api_url}/{pypi_package}/json"

            # 发送请求
            response = requests.get(api_url, timeout=30)

            if response.status_code != 200:
                raise Exception(f"PyPI API请求失败: {response.status_code}")

            data = response.json()

            if not data:
                self.logger.warning(f"PyPI包 {pypi_package} 没有版本信息")
                return {
                    "name": package_name,
                    "success": False,
                    "message": "没有版本信息"
                }

            # 提取版本号
            version = data.get("info", {}).get("version")
            release_date = None

            # 尝试获取发布日期
            releases = data.get("releases", {})
            if version in releases and releases[version]:
                release_info = releases[version][0]
                upload_time = release_info.get("upload_time")
                if upload_time:
                    release_date = upload_time

            # 如果有版本提取键，使用正则表达式提取
            if version_extract_key and version:
                try:
                    pattern = re.compile(version_extract_key)
                    match = pattern.search(version)
                    if match:
                        version = match.group(1) if match.groups() else match.group(0)
                except Exception as e:
                    self.logger.error(f"使用版本提取键解析失败: {str(e)}")

            if not version:
                self.logger.warning(f"无法从PyPI包 {pypi_package} 提取版本号")
                return {
                    "name": package_name,
                    "success": False,
                    "message": "无法提取版本号"
                }

            self.logger.info(f"PyPI上游版本检查成功: {version}")

            return {
                "name": package_name,
                "success": True,
                "version": version,
                "date": release_date,
                "url": f"https://pypi.org/project/{pypi_package}/"
            }

        except Exception as error:
            self.logger.error(f"检查PyPI上游版本失败: {str(error)}")
            return {
                "name": package_name,
                "success": False,
                "message": str(error)
            }
