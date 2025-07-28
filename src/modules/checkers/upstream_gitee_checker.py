# -*- coding: utf-8 -*-
import re
import aiohttp
import json
from datetime import datetime

from .base_checker import BaseChecker
from ..version_processor import VersionProcessor

class UpstreamGiteeChecker(BaseChecker):
    """Gitee 上游检查器"""

    def __init__(self, logger, config=None, main_checker=None):
        """初始化Gitee检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例（可选）
            main_checker: 主检查器实例，用于版本比较（可选）
        """
        super().__init__(logger, config)
        self.logger.debug("Gitee上游检查器初始化")
        self.config = config
        self.main_checker = main_checker
        self.package_config = None
        self.version_processor = VersionProcessor(logger, self.package_config)

        # Gitee API配置
        self.api_url = "https://gitee.com/api/v5"
        self.timeout = 30

    def _format_version(self, version_str):
        """格式化版本字符串（去掉'v'前缀）"""
        if version_str and version_str.startswith('v'):
            return version_str[1:]
        return version_str

    def _is_valid_version(self, version_str):
        """验证版本号是否为有效格式"""
        if not version_str:
            return False

        # 检查格式，过滤明显无效的版本
        if version_str.lower() in ["latest", "current", "stable", "master", "main", "head", "nightly", "next"]:
            self.logger.debug(f"版本 '{version_str}' 是特殊标签，不是有效版本号")
            return False

        # 标准的三段式版本 (1.2.3)
        if re.match(r"^\d+\.\d+\.\d+$", version_str):
            return True

        # 两段式版本号 (1.2)
        if re.match(r"^\d+\.\d+$", version_str):
            return True

        # 其他可接受的版本格式
        if re.match(r"^\d+(\.\d+){1,2}(-[a-zA-Z0-9]+)?$", version_str):
            return True

        return False

    def _extract_version_from_filename(self, filename):
        """从文件名中提取版本号"""
        self.logger.debug(f"尝试从文件名提取版本号: {filename}")

        # 对于特殊格式的deb包名，尝试直接提取完整版本
        # 例如 spark-dwine-helper_5.8-5.3.14_all.deb 应该提取 5.8-5.3.14
        deb_match = re.search(r"_(\d+\.\d+(?:-\d+\.\d+\.\d+)?)_", filename)
        if deb_match:
            full_version = deb_match.group(1)
            self.logger.info(f"从deb包文件名 {filename} 提取到完整版本号: {full_version}")
            return full_version

        # 尝试匹配带有连字符的完整版本号（如5.7.1-5.3.14）
        full_version_match = re.search(r"(\d+\.\d+(?:\.\d+)?-\d+\.\d+\.\d+)(?:\.|_|$)", filename)
        if full_version_match:
            full_version = full_version_match.group(1)
            self.logger.info(f"从文件名 {filename} 提取到完整版本号: {full_version}")
            return full_version

        # 直接尝试匹配数字版本模式
        match = re.search(r"(\d+\.\d+\.\d+|\d+\.\d+)", filename)
        if match:
            version = match.group(1)
            self.logger.info(f"从文件名 {filename} 提取到版本号: {version}")
            if self._is_valid_version(version):
                return version

        # 如果直接匹配失败，尝试更多模式
        patterns = [
            r"[-_]v?(\d+\.\d+\.\d+)[.-]",  # name-1.2.3.ext 或 name_1.2.3.ext
            r"[-_]v?(\d+\.\d+)[.-]",       # name-1.2.ext 或 name_1.2.ext
            r"[-_]v(\d+\.\d+(?:\.\d+)?)[.-]",  # name-vX.Y.Z.ext 或 name_vX.Y.Z.ext
            r"(\d+\.\d+\.\d+)",            # 直接嵌入的版本号
            r"[^0-9](\d+\.\d+\.\d+)[^0-9]", # 数字前后有非数字字符的版本号
            r"[^0-9](\d+\.\d+)[^0-9]"      # 两段式版本号
        ]

        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                version = match.group(1)
                self.logger.info(f"使用模式从文件名 {filename} 提取到版本号: {version}")
                if self._is_valid_version(version):
                    return version

        self.logger.debug(f"无法从文件名 {filename} 提取版本号")
        return None

    def _create_result(self, package_name, success, version=None, date=None, url=None, all_versions=None, message=None):
        """创建统一格式的返回结果"""
        if success:
            return {
                "name": package_name,
                "success": True,
                "version": version,
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "url": url,
                "all_versions": all_versions or [version]
            }
        else:
            return {
                "name": package_name,
                "success": False,
                "message": message or "未知错误"
            }

    async def _get_latest_release(self, owner, repo):
        """获取最新的release信息"""
        api_url = f"{self.api_url}/repos/{owner}/{repo}/releases/latest"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=self.timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        self.logger.info(f"获取仓库 {owner}/{repo} 的release: {response.status} 不存在")
                        return None
        except Exception as e:
            self.logger.error(f"获取仓库 {owner}/{repo} 的release时出错: {str(e)}")
            return None

    async def _get_latest_tag(self, owner, repo):
        """获取最新的tag信息"""
        api_url = f"{self.api_url}/repos/{owner}/{repo}/tags"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=self.timeout) as response:
                    if response.status == 200:
                        tags = await response.json()
                        if tags and len(tags) > 0:
                            return tags[0]["name"]
                    return None
        except Exception as e:
            self.logger.error(f"获取仓库 {owner}/{repo} 的tags时出错: {str(e)}")
            return None

    async def _get_release_assets(self, owner, repo, release_tag):
        """通过Gitee API获取发布版本的资产文件列表"""
        api_url = f"{self.api_url}/repos/{owner}/{repo}/releases/tags/{release_tag}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=self.timeout) as response:
                    if response.status != 200:
                        self.logger.warning(f"无法获取仓库 {owner}/{repo} 的release资产")
                        return None

                    release_data = await response.json()

                    if not release_data or 'assets' not in release_data:
                        self.logger.warning(f"无法获取仓库 {owner}/{repo} 的release资产或没有资产文件")
                        return None

                    files = []
                    for asset in release_data['assets']:
                        filename = asset.get('name')
                        download_url = asset.get('browser_download_url')
                        if filename and download_url:
                            files.append({"filename": filename, "url": download_url})
                            self.logger.debug(f"找到资产文件: {filename}")

                    self.logger.info(f"从API获取到 {len(files)} 个资产文件")
                    return files if files else None
        except Exception as e:
            self.logger.error(f"获取仓库 {owner}/{repo} 的release资产时出错: {str(e)}")
            return None

    async def _extract_version_from_files(self, files, version_extract_key=None):
        """从文件列表中提取版本号，可选使用版本提取关键字过滤"""
        if not files:
            return None

        # 如果有版本提取关键字，过滤文件
        filtered_files = files
        if version_extract_key:
            # 移除前导点号，因为我们要检查的是文件名中的子字符串，而不是文件扩展名
            clean_key = version_extract_key
            if clean_key.startswith("."):
                clean_key = clean_key[1:]

            self.logger.info(f"使用版本提取关键字 '{clean_key}' 过滤文件")

            # 过滤出包含关键字的文件，不限于结尾
            filtered_files = [
                f for f in files
                if clean_key.lower() in f["filename"].lower()
            ]

            if filtered_files:
                self.logger.info(f"使用关键字 '{version_extract_key}' 过滤后找到 {len(filtered_files)} 个文件:")
                for f in filtered_files:
                    self.logger.info(f"  - {f['filename']}")
            else:
                self.logger.warning(f"未找到符合关键字 '{version_extract_key}' 的文件，将使用所有文件")
                filtered_files = files

        # 从文件名中提取版本
        version_files = []
        for file_info in filtered_files:
            version = self._extract_version_from_filename(file_info["filename"])
            if version:
                version_files.append({
                    "filename": file_info["filename"],
                    "url": file_info["url"],
                    "version": version
                })

        if not version_files:
            self.logger.warning("无法从文件中提取版本号")
            return None

        # 对于复合版本号如 "5.8-5.3.14"，我们需要特殊处理
        # 为每个版本创建一个更适合比较的表示
        comparable_versions = []
        version_map = {}

        for f in version_files:
            version = f["version"]

            # 处理复合版本号，提取主要版本部分（前面的数字部分）
            if "-" in version:
                main_part = version.split("-")[0]
                # 确保我们有一个有效的版本号部分
                if self._is_valid_version(main_part):
                    comparable_version = main_part
                else:
                    comparable_version = version
            else:
                comparable_version = version

            comparable_versions.append(comparable_version)
            # 保存原始版本到对应的可比较版本
            version_map[comparable_version] = version

        # 获取最新版本（使用可比较的版本进行排序）
        best_comparable_version = self.version_processor.get_latest_version(comparable_versions)
        # 然后映射回原始的完整版本
        best_version = version_map.get(best_comparable_version, best_comparable_version)

        self.logger.info(f"从文件中提取的最佳版本: {best_version}")

        return {
            "version": best_version,
            "all_versions": [f["version"] for f in version_files],
            "files": version_files,
            "date": datetime.now().strftime("%Y-%m-%d")
        }

    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """检查 Gitee 仓库的版本

        按以下逻辑检查:
        1. 首先查看是否存在不为空的版本提取关键字. 如果存在, 则通过Gitee API提供的接口获取release资产文件,
           然后获取最新版本
        2. 如果没有定义版本提取关键字或者版本提取关键字为空, 则直接通过api请求release获取最新版本
        3. 如果没有定义版本提取关键字或者版本提取关键字为空, 且没有发行版, 则直接通过api请求tags来获取最新的标签

        支持的URL格式：
        - https://gitee.com/owner/repo
        - https://gitee.com/owner/repo/releases

        Args:
            package_name: 软件包名
            url: Gitee仓库URL
            version_pattern_regex: 版本提取正则表达式
            **kwargs: 其他参数，如version_extract_key, aur_version, version_pattern等

        Returns:
            dict: 包含版本信息的字典
        """
        self.logger.info(f"正在检查Gitee上游版本: {url}")

        # 从kwargs获取参数
        version_extract_key = kwargs.get("version_extract_key")
        aur_version = kwargs.get("aur_version")
        version_pattern = kwargs.get("version_pattern")

        self.logger.debug(f"传入的版本提取关键字: {version_extract_key}")
        self.logger.debug(f"传入的AUR版本: {aur_version}")
        self.logger.debug(f"传入的版本模式: {version_pattern}")

        try:
            # 解析URL获取仓库所有者和名称
            match = re.match(r'https?://gitee\.com/([^/]+)/([^/]+)', url)
            if not match:
                self.logger.warning(f"无效的Gitee URL: {url}")
                return self._create_result(
                    package_name=package_name,
                    success=False,
                    message="无效的Gitee URL"
                )

            owner = match.group(1)
            repo = match.group(2).split('/')[0]  # 移除可能的子路径如/releases
            self.logger.debug(f"解析到仓库: {owner}/{repo}")

            # 获取最新release信息
            release = await self._get_latest_release(owner, repo)
            release_tag = release.get('tag_name') if release else None
            self.logger.debug(f"获取到的release标签: {release_tag}")

            # 初始化version_info为None, 避免未定义错误
            version_info = None

            # 步骤1: 如果存在不为空的版本提取关键字且存在release, 则通过API获取资产文件
            if version_extract_key and release_tag:
                self.logger.info(f"使用版本提取关键字: {version_extract_key}")
                self.logger.info(f"找到最新的release标签: {release_tag}")

                # 通过Gitee API获取release资产文件
                files = await self._get_release_assets(owner, repo, release_tag)

                if files:
                    self.logger.debug(f"获取到 {len(files)} 个文件")
                    for file in files:
                        self.logger.debug(f"  - {file['filename']}")

                    # 从文件中提取版本
                    version_info = await self._extract_version_from_files(files, version_extract_key)

                    if version_info:
                        version = version_info["version"]
                        self.logger.info(f"使用版本提取关键字 '{version_extract_key}' 从文件中提取到版本: {version}")

                        # 尝试验证版本合理性
                        if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                            if self.main_checker._is_version_similar(version, version_pattern):
                                self.logger.info(f"提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                            else:
                                self.logger.debug(f"提取的版本 {version} 与AUR版本格式不匹配，但仍然返回")

                        return self._create_result(
                            package_name=package_name,
                            success=True,
                            version=version,
                            date=release.get('created_at', "")[:10] if release else None,
                            url=url,
                            all_versions=version_info["all_versions"]
                        )
                    else:
                        self.logger.warning("无法从文件中提取版本号, 将尝试其他方法")

            # 步骤2: 如果没有定义版本提取关键字或上面的步骤失败, 且存在release, 尝试直接从API获取最新版本
            if release:
                # 直接使用release的tag_name作为版本
                version = self._format_version(release.get('tag_name'))
                if self._is_valid_version(version):
                    self.logger.info(f"从release API获取到版本: {version}")

                    # 尝试验证版本合理性
                    if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                        if self.main_checker._is_version_similar(version, version_pattern):
                            self.logger.info(f"提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                        else:
                            self.logger.debug(f"提取的版本 {version} 与AUR版本格式不匹配，但仍然返回")

                    return self._create_result(
                        package_name=package_name,
                        success=True,
                        version=version,
                        date=release.get('created_at')[:10] if release.get('created_at') else None,
                        url=url
                    )
                else:
                    self.logger.warning(f"从release获取的标签 '{release_tag}' 不是有效版本, 将尝试从tag获取")

            # 步骤3: 如果上述方法都失败(没有定义版本提取关键字或版本提取关键字为空, 且没有发行版), 使用最新的tag
            latest_tag = await self._get_latest_tag(owner, repo)
            if latest_tag:
                version = self._format_version(latest_tag)
                if self._is_valid_version(version):
                    self.logger.info(f"从tag获取到版本: {version}")

                    # 尝试验证版本合理性
                    if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                        if self.main_checker._is_version_similar(version, version_pattern):
                            self.logger.info(f"提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                        else:
                            self.logger.debug(f"提取的版本 {version} 与AUR版本格式不匹配，但仍然返回")

                    return self._create_result(
                        package_name=package_name,
                        success=True,
                        version=version,
                        url=url
                    )
                else:
                    self.logger.warning(f"从tag获取的标签 '{latest_tag}' 不是有效版本")

            # 如果所有方法都失败
            self.logger.warning(f"无法从Gitee仓库 {url} 提取有效版本号")
            return self._create_result(
                package_name=package_name,
                success=False,
                message="无法提取有效版本号, 可能需要手动检查"
            )

        except Exception as e:
            self.logger.error(f"检查Gitee版本时出错: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return self._create_result(
                package_name=package_name,
                success=False,
                message=f"检查版本时出错: {str(e)}"
            )
