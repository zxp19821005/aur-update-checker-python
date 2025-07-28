# -*- coding: utf-8 -*-
import re
import requests
from datetime import datetime
from .base_checker import BaseChecker

class UpstreamGitlabChecker(BaseChecker):
    """GitLab上游版本检查器"""

    def __init__(self, logger, config=None, main_checker=None):
        """初始化GitLab检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例（可选）
            main_checker: 主检查器实例（可选），用于版本比较
        """
        super().__init__(logger)
        self.logger.debug("GitLab上游检查器初始化")
        self.config = config
        self.main_checker = main_checker  # 存储主检查器实例引用

        # GitLab API配置
        self.api_url = "https://gitlab.com/api/v4"
        self.per_page = 100
        self.token = ""

        # 如果提供了配置，从配置中读取
        if config:
            self.api_url = config.get("gitlab.api_url", self.api_url)
            self.per_page = config.get("gitlab.per_page", self.per_page)
            self.token = config.get("gitlab.token", self.token)

    def is_gitlab_url(self, url):
        """判断URL是否为GitLab仓库URL

        Args:
            url: 要检查的URL

        Returns:
            bool: 如果是GitLab URL则返回True
        """
        gitlab_domains = ["gitlab.com", "gitlab.", "gl."]
        return any(domain in url.lower() for domain in gitlab_domains)

    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """检查GitLab仓库的最新版本

        Args:
            package_name: 软件包名称
            url: GitLab仓库URL
            version_pattern_regex: 版本匹配正则表达式（可选）
            **kwargs: 额外参数，可包含：
                - version_extract_key: 版本提取键（可选）
                - aur_version: AUR版本号（可选），用于格式验证
                - version_pattern: 版本模式（可选），如"x.y.z"

        Returns:
            dict: 包含版本信息的字典
        """
        # 从kwargs中获取可选参数
        version_extract_key = kwargs.get('version_extract_key')
        aur_version = kwargs.get('aur_version')
        version_pattern = kwargs.get('version_pattern')

        self.logger.info(f"正在检查GitLab上游版本: {url}")
        self.logger.debug(f"传入的版本提取关键字: {version_extract_key}")
        self.logger.debug(f"传入的AUR版本: {aur_version}")
        self.logger.debug(f"传入的版本模式: {version_pattern}")

        try:
            # 解析GitLab仓库信息
            repo_info = self._parse_gitlab_url(url)
            if not repo_info:
                raise ValueError(f"无效的GitLab URL: {url}")

            # 获取仓库的最新发布版本
            headers = {}
            if self.token:
                headers["PRIVATE-TOKEN"] = self.token

            # 尝试获取发布版本
            api_url = f"{self.api_url}/projects/{repo_info['project_id']}/releases"
            response = requests.get(
                api_url,
                headers=headers,
                params={"per_page": self.per_page},
                timeout=30
            )

            if response.status_code != 200 or not response.json():
                # 如果无法获取releases，尝试获取tags
                api_url = f"{self.api_url}/projects/{repo_info['project_id']}/repository/tags"
                response = requests.get(
                    api_url,
                    headers=headers,
                    params={"per_page": self.per_page},
                    timeout=30
                )

            if response.status_code != 200:
                raise Exception(f"GitLab API请求失败: {response.status_code}")

            data = response.json()

            if not data:
                self.logger.warning(f"GitLab仓库 {url} 没有发布版本或标签")
                return {
                    "name": package_name,
                    "success": False,
                    "message": "仓库没有发布版本或标签"
                }

            # 提取版本号
            version = None
            date = None

            # 首先尝试从releases获取版本
            if "tag_name" in data[0]:
                # 处理releases数据
                version = self._clean_version(data[0]["tag_name"])
                date = data[0].get("released_at") or data[0].get("created_at")
            else:
                # 处理tags数据
                version = self._clean_version(data[0]["name"])
                # Tags API不直接提供日期，可以考虑额外请求commit信息
                date = data[0].get("commit", {}).get("created_at")

            # 如果有版本提取键，使用正则表达式提取
            if version_extract_key and version:
                try:
                    pattern = re.compile(version_extract_key)
                    match = pattern.search(version)
                    if match:
                        version = match.group(1) if match.groups() else match.group(0)
                except Exception as e:
                    self.logger.error(f"使用版本提取键解析失败: {str(e)}")

            # 如果提供了AUR版本和版本模式，验证提取的版本格式是否符合要求
            if version and aur_version and version_pattern and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                if self.main_checker._is_version_similar(version, version_pattern):
                    self.logger.info(f"提取的版本 {version} 与版本模式 {version_pattern} 匹配")
                else:
                    self.logger.debug(f"提取的版本 {version} 与版本模式 {version_pattern} 不匹配，但仍然使用")

            if not version:
                self.logger.warning(f"无法从GitLab仓库 {url} 提取版本号")
                return {
                    "name": package_name,
                    "success": False,
                    "message": "无法提取版本号"
                }

            self.logger.info(f"GitLab上游版本检查成功: {version}")

            return {
                "name": package_name,
                "success": True,
                "version": version,
                "date": date,
                "url": url
            }

        except Exception as error:
            self.logger.error(f"检查GitLab上游版本失败: {str(error)}")
            return {
                "name": package_name,
                "success": False,
                "message": str(error)
            }

    def _parse_gitlab_url(self, url):
        """解析GitLab URL获取项目ID或仓库信息

        Args:
            url: GitLab仓库URL

        Returns:
            dict: 包含项目ID的字典，如果解析失败则返回None
        """
        # 如果URL中包含项目ID，直接提取
        project_id_match = re.search(r"gitlab\.com/api/v4/projects/(\d+)", url)
        if project_id_match:
            return {"project_id": project_id_match.group(1)}

        # 否则，从路径中提取项目名称
        path_match = re.search(r"gitlab\.com/([^/]+/[^/]+)", url)
        if path_match:
            project_path = path_match.group(1)
            # URL编码项目路径
            encoded_path = requests.utils.quote(project_path, safe='')
            return {"project_id": encoded_path}

        return None

    def _clean_version(self, version):
        """清理版本字符串，移除常见前缀

        Args:
            version: 原始版本字符串

        Returns:
            str: 清理后的版本字符串
        """
        if not version:
            return ""

        # 移除常见的版本前缀
        prefixes = ["v", "V", "release-", "version-", "rel-", "ver-"]
        for prefix in prefixes:
            if version.startswith(prefix):
                version = version[len(prefix):]
                break

        return version

module = {
    "UpstreamGitlabChecker": UpstreamGitlabChecker
}
