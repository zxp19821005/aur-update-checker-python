# -*- coding: utf-8 -*-
"""
NPM上游检查器模块

专门用于检查NPM包的最新版本
"""
import re
import json
import aiohttp
from urllib.parse import quote
from datetime import datetime

from .base_checker import BaseChecker


class UpstreamNpmChecker(BaseChecker):
    """NPM上游版本检查器"""

    def __init__(self, logger, config=None, main_checker=None):
        """初始化NPM上游检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例
            main_checker: 主检查器实例（可选），用于版本比较
        """
        super().__init__(logger)
        self.config = config
        self.main_checker = main_checker  # 存储主检查器实例引用

        # 支持多个镜像源，优先使用国内镜像
        self.npm_mirrors = [
            "https://registry.npmmirror.com/",  # 淘宝NPM镜像
            "https://registry.npmjs.org/"       # 官方源（备用）
        ]
        self.api_base_url = self.npm_mirrors[0]  # 默认使用第一个镜像
        self.timeout = 10  # API请求超时时间（秒）
        self.user_agent = "AUR-Update-Checker/1.0"

    async def check_version(self, package_name, url=None, version_pattern_regex=None, **kwargs):
        """检查NPM包的最新版本

        Args:
            package_name: NPM包名
            url: 可选，包地址（如果不提供，将基于包名构建API URL）
            version_pattern_regex: 可选，版本匹配正则表达式
            **kwargs: 额外参数，可包含：
                - version_extract_key: 可选，指定版本字段（通常不需要）
                - aur_version: AUR版本号（可选），用于格式验证
                - version_pattern: 版本模式（可选），如"x.y.z"

        Returns:
            dict: 包含版本检查结果的字典
        """
        # 从kwargs中获取可选参数
        version_extract_key = kwargs.get('version_extract_key')
        aur_version = kwargs.get('aur_version')
        version_pattern = kwargs.get('version_pattern')

        try:
            self.logger.info(f"正在检查NPM包版本: {package_name}")
            self.logger.debug(f"传入的版本提取关键字: {version_extract_key}")
            self.logger.debug(f"传入的AUR版本: {aur_version}")
            self.logger.debug(f"传入的版本模式: {version_pattern}")

            # 处理包名，移除@scope/部分用于日志记录，但API调用时保留完整包名
            display_name = package_name

            # 如果提供了URL，检查是否需要替换为API URL
            if url:
                # 如果URL是npmjs.com的网页URL而不是API URL，替换为API URL
                if "www.npmjs.com/package/" in url:
                    package_name_from_url = url.split("/package/")[-1].split("/")[0]
                    encoded_name = quote(package_name_from_url, safe='')
                    url = f"{self.api_base_url}{encoded_name}"
                    self.logger.info(f"已将网页URL转换为API URL: {url}")
            else:
                # 对包名进行URL编码，特别是处理@scoped包
                encoded_name = quote(package_name, safe='')
                url = f"{self.api_base_url}{encoded_name}"

            self.logger.debug(f"请求NPM API: {url}")

            # 配置请求头
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json"
            }

            # 尝试所有可用的镜像，直到成功
            data = None
            last_error = None

            # 确定要尝试的镜像列表
            mirrors_to_try = []
            if "registry.npmmirror.com" in url or "registry.npmjs.org" in url:
                # 如果URL已经包含镜像地址，提取包名部分
                for mirror in self.npm_mirrors:
                    if mirror in url:
                        package_path = url.replace(mirror, "")
                        mirrors_to_try = [(mirror, package_path) for mirror in self.npm_mirrors]
                        break
            else:
                # 使用提供的URL作为唯一选项
                mirrors_to_try = [(None, url)]

            # 依次尝试各个镜像
            for mirror_url, package_path in mirrors_to_try:
                try:
                    current_url = package_path if mirror_url is None else f"{mirror_url}{package_path}"
                    self.logger.debug(f"尝试从镜像获取: {current_url}")

                    async with aiohttp.ClientSession() as session:
                        async with session.get(current_url, headers=headers, timeout=self.timeout) as response:
                            if response.status != 200:
                                self.logger.warning(f"镜像 {current_url} 请求失败: HTTP {response.status}")
                                last_error = f"HTTP {response.status}"
                                continue

                            # 尝试解析JSON
                            try:
                                data = await response.json()
                                # 如果成功解析数据，跳出循环
                                break
                            except Exception as e:
                                self.logger.warning(f"解析 {current_url} 的JSON数据失败: {str(e)}")
                                last_error = str(e)
                                continue

                except Exception as e:
                    self.logger.warning(f"连接镜像 {current_url} 出错: {str(e)}")
                    last_error = str(e)
                    continue

            # 如果所有镜像都失败了
            if data is None:
                self.logger.error(f"所有NPM镜像请求均失败，最后错误: {last_error}")
                return {
                    "name": package_name,
                    "success": False,
                    "message": f"NPM API请求失败: {last_error}"
                }

            # 检查并解析版本信息
            latest_version = None
            update_date = None

            # 首先尝试获取latest标签的版本
            if "dist-tags" in data and "latest" in data["dist-tags"]:
                latest_version = data["dist-tags"]["latest"]

                # 尝试获取发布日期
                if latest_version and "time" in data and latest_version in data["time"]:
                    update_date = data["time"][latest_version]
                    # 转换为标准日期格式
                    try:
                        dt = datetime.fromisoformat(update_date.replace("Z", "+00:00"))
                        update_date = dt.strftime("%Y-%m-%d")
                    except Exception as e:
                        self.logger.warning(f"无法解析日期: {update_date}, 错误: {e}")

            # 如果没有latest标签，尝试从versions中找出最新版本
            if not latest_version and "versions" in data:
                versions = list(data["versions"].keys())
                if versions:
                    # 使用版本处理器获取最新版本
                    if hasattr(self, "version_processor") and self.version_processor:
                        latest_version = self.version_processor.get_latest_version(versions)
                    else:
                        # 简单地取最后一个版本（通常是最新的）
                        latest_version = versions[-1]

            if latest_version:
                # 如果提供了AUR版本和版本模式，验证提取的版本格式是否符合要求
                if aur_version and version_pattern and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                    if self.main_checker._is_version_similar(latest_version, version_pattern):
                        self.logger.info(f"提取的版本 {latest_version} 与版本模式 {version_pattern} 匹配")
                    else:
                        self.logger.debug(f"提取的版本 {latest_version} 与版本模式 {version_pattern} 不匹配，但仍然使用")

                self.logger.info(f"成功从NPM获取包 {display_name} 的最新版本: {latest_version}")
                return {
                    "name": package_name,
                    "version": latest_version,
                    "upstream_version": latest_version,
                    "date": update_date,
                    "success": True,
                    "message": "成功检查NPM版本",
                    "package_url": f"https://www.npmjs.com/package/{package_name}",
                }
            else:
                self.logger.error(f"未能从NPM数据中提取版本信息: {package_name}")
                return {
                    "name": package_name,
                    "success": False,
                    "message": "未能从NPM数据中提取版本信息"
                }

        except Exception as e:
            self.logger.error(f"检查NPM版本时出错: {str(e)}")
            return {
                "name": package_name,
                "success": False,
                "message": f"检查NPM版本时出错: {str(e)}"
            }
