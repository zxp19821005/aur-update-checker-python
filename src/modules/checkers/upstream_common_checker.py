# -*- coding: utf-8 -*-
import re
import requests
from datetime import datetime
from .base_checker import BaseChecker

class UpstreamCommonChecker(BaseChecker):
    """通用上游版本检查器，尝试从网页内容中提取版本信息"""

    def __init__(self, logger, config=None, main_checker=None):
        """初始化通用检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例（可选）
            main_checker: 主检查器实例，用于版本比较（可选）
        """
        super().__init__(logger)
        self.logger.debug("通用上游检查器初始化")
        self.config = config
        self.main_checker = main_checker
        self.package_config = None

        # 用户代理
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

        # 如果提供了配置，从配置中读取
        if config:
            self.user_agent = config.get("upstream.user_agent", self.user_agent)

    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """检查通用URL的最新版本

        Args:
            package_name: 软件包名称
            url: 上游URL
            version_pattern_regex: 版本提取正则表达式
            **kwargs: 其他参数，如version_extract_key, aur_version, version_pattern等

        Returns:
            dict: 包含版本信息的字典
        """
        self.logger.info(f"正在检查通用上游版本: {url}")

        # 从kwargs获取参数
        version_extract_key = kwargs.get("version_extract_key")
        aur_version = kwargs.get("aur_version")
        version_pattern = kwargs.get("version_pattern")

        # 默认版本提取模式
        default_patterns = [
            r"[vV]ersion\s*[:]?\s*([\d\.]+)",  # Version: 1.2.3
            r"[vV]er\s*[:]?\s*([\d\.]+)",      # Ver: 1.2.3
            r"latest.*?([\d\.]+)",         # latest release 1.2.3
            r"最新.*?([\d\.]+)",           # 最新版本 1.2.3
            r"版本.*?([\d\.]+)",           # 版本号 1.2.3
            r"release.*?([\d\.]+)",        # release 1.2.3
            r"下载.*?([\d\.]+)",           # 下载 1.2.3
            r"([\d\.]+)\s*\(最新\)",     # 1.2.3 (最新)
            r"([\d\.]+)\s*\(latest\)"    # 1.2.3 (latest)
        ]

        if not version_extract_key:
            self.logger.info(f"未提供版本提取键，将使用默认模式")

        try:
            # 发送请求
            headers = {"User-Agent": self.user_agent}
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                raise Exception(f"请求失败: {response.status_code}")

            # 获取页面内容
            content = response.text

            # 使用正则表达式提取版本
            try:
                version = None
                # 确保version_extract_key是字符串类型
                if version_extract_key and not isinstance(version_extract_key, str):
                    version_extract_key = str(version_extract_key)

                # 优先使用传入的version_pattern_regex
                if version_pattern_regex:
                    try:
                        pattern = re.compile(version_pattern_regex)
                        match = pattern.search(content)
                        if match:
                            version = match.group(1) if match.groups() else match.group(0)
                            self.logger.info(f"使用传入的版本模式提取到版本号: {version}")

                            # 尝试验证版本合理性
                            if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                                if self.main_checker._is_version_similar(version, version_pattern):
                                    self.logger.info(f"提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                                else:
                                    self.logger.debug(f"提取的版本 {version} 与AUR版本格式不匹配，但仍然返回")

                            return {
                                "name": package_name,
                                "success": True,
                                "version": version,
                                "date": datetime.now().isoformat(),
                                "url": url
                            }
                    except Exception as pattern_error:
                        self.logger.debug(f"使用传入的版本模式提取失败: {str(pattern_error)}")

                # 使用默认模式提取
                patterns = [version_extract_key] if version_extract_key else default_patterns

                # 尝试所有模式
                for pattern_str in patterns:
                    if not pattern_str or not isinstance(pattern_str, str):
                        continue

                    try:
                        pattern = re.compile(pattern_str)
                        match = pattern.search(content)
                        if match:
                            version = match.group(1) if match.groups() else match.group(0)
                            self.logger.info(f"使用模式 {pattern_str} 从内容中提取到版本: {version}")

                            # 尝试验证版本合理性
                            if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                                if self.main_checker._is_version_similar(version, version_pattern):
                                    self.logger.info(f"提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                                else:
                                    self.logger.debug(f"提取的版本 {version} 与AUR版本格式不匹配，但仍然返回")

                            break
                    except Exception as pattern_error:
                        self.logger.debug(f"模式 {pattern_str} 无效: {str(pattern_error)}")
                        continue

                if not version:
                    self.logger.warning(f"在内容中未找到匹配的版本号")
                    return {
                        "name": package_name,
                        "success": False,
                        "message": "未找到匹配的版本号"
                    }

                self.logger.info(f"通用上游版本检查成功: {version}")

                return {
                    "name": package_name,
                    "success": True,
                    "version": version,
                    "date": datetime.now().isoformat(),
                    "url": url
                }

            except Exception as e:
                self.logger.error(f"版本提取失败: {str(e)}")
                return {
                    "name": package_name,
                    "success": False,
                    "message": f"版本提取失败: {str(e)}"
                }

        except Exception as error:
            self.logger.error(f"检查通用上游版本失败: {str(error)}")
            return {
                "name": package_name,
                "success": False,
                "message": str(error)
            }