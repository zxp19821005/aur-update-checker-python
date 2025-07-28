# -*- coding: utf-8 -*-
import re
import os
import asyncio
from datetime import datetime
from .api_checker import ApiChecker


class UpstreamGithubChecker(ApiChecker):
    """GitHub上游版本检查器"""

    def __init__(self, logger, config=None, main_checker=None):
        """初始化GitHub检查器

        Args:
            logger: 日志模块实例
            config: 配置模块实例（可选）
            main_checker: 主检查器实例（可选），用于版本比较
        """
        super().__init__(logger, config, main_checker)
        self.logger.debug("GitHub上游检查器初始化")

        # GitHub API配置
        self.api_url = "https://api.github.com"
        self.per_page = 100

        # 如果提供了配置，从配置中读取
        if config:
            self.api_url = config.get("github.api_url", self.api_url)
            self.per_page = config.get("github.per_page", self.per_page)

    def init_auth(self):
        """初始化GitHub API认证信息"""
        # 设置GitHub令牌，如果配置中有的话
        self.token = ""
        if self.config:
            self.token = self.config.get("github.token", "")

        # 如果有令牌，添加到请求头中
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

        # 添加GitHub API需要的头信息
        self.headers["Accept"] = "application/vnd.github.v3+json"

    async def _get_session(self):
        """获取aiohttp会话，使用ApiChecker中的实现"""
        return await super()._get_session()

    def _parse_github_url(self, url):
        """解析GitHub URL，提取用户名和仓库名"""
        if not url:
            return None

        patterns = [
            # 标准GitHub URL格式
            r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$",
            # GitHub页面URL
            r"github\.com/([^/]+)/([^/]+?)(?:/|$)",
            # 带有releases/tag的URL
            r"github\.com/([^/]+)/([^/]+?)/releases/tag/([^/]+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                owner = match.group(1)
                repo = match.group(2)

                # 移除.git后缀
                if repo.endswith(".git"):
                    repo = repo[:-4]

                # 移除URL中的查询参数
                if "?" in repo:
                    repo = repo.split("?")[0]

                return {
                    "owner": owner,
                    "repo": repo,
                    "tag": match.groups()[2] if len(match.groups()) > 2 else None
                }

        return None

    async def parse_api_response(self, data, response_type="release", **kwargs):
        """解析GitHub API响应

        Args:
            data: API响应数据
            response_type: 响应类型，可以是'release'、'tag'或'asset'
            **kwargs: 其他参数，包括：
                version_extract_key: 版本提取键
                version_pattern: 版本模式

        Returns:
            dict: 包含解析后版本信息的字典
        """
        self.logger.debug(f"解析GitHub API {response_type}响应")

        # 获取可选参数
        version_extract_key = kwargs.get("version_extract_key")
        version_pattern = kwargs.get("version_pattern")

        result = {
            "success": False,
            "version": None,
            "date": None,
            "message": "未找到版本信息"
        }

        try:
            if response_type == "release":
                # 处理release响应
                if not data:
                    return result

                # 提取版本号
                tag_name = data.get("tag_name")
                if tag_name:
                    # 清理版本号
                    version = tag_name
                    if version.startswith("v") or version.startswith("V"):
                        version = version[1:]

                    # 提取发布日期
                    published_at = data.get("published_at")
                    if published_at:
                        date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    else:
                        date = datetime.now()

                    return {
                        "success": True,
                        "version": version,
                        "date": date,
                        "message": "成功从release中获取版本信息"
                    }

            elif response_type == "tag":
                # 处理tag响应
                if not data or not isinstance(data, list) or len(data) == 0:
                    return result

                # 提取最新标签的名称
                tag_name = data[0].get("name")
                if tag_name:
                    # 清理版本号
                    version = tag_name
                    if version.startswith("v") or version.startswith("V"):
                        version = version[1:]

                    return {
                        "success": True,
                        "version": version,
                        "date": datetime.now(),  # 标签没有日期信息，使用当前日期
                        "message": "成功从tag中获取版本信息"
                    }

            elif response_type == "asset":
                # 处理assets响应
                if not data or not isinstance(data, list) or len(data) == 0:
                    return result

                # 如果有版本提取关键字，搜索匹配的资产
                if version_extract_key:
                    for asset in data:
                        name = asset.get("name", "")
                        if version_extract_key in name:
                            # 提取版本号
                            version = self.version_processor.extract_version_from_text(name)
                            if version:
                                return {
                                    "success": True,
                                    "version": version,
                                    "date": datetime.now(),
                                    "message": f"从资产文件 {name} 中提取到版本信息"
                                }

        except Exception as e:
            self.logger.error(f"解析GitHub API响应时出错: {str(e)}")
            result["message"] = f"解析出错: {str(e)}"

        return result

    def _format_version(self, version_str):
        """格式化版本字符串（去掉'v'前缀）"""
        if version_str and version_str.startswith('v'):
            return version_str[1:]
        return version_str

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


    async def _github_api_request(self, endpoint, error_message):
        """GitHub API请求基础方法"""
        try:
            # 获取HTTP客户端
            http_client = self._get_http_client()

            # 设置请求头
            headers = {"User-Agent": "Mozilla/5.0 Chrome/91.0.4472.124 Safari/537.36"}
            if self.token:
                headers["Authorization"] = f"token {self.token}"

            # 发送请求
            result = await http_client.get(endpoint, headers=headers, timeout=self.timeout)

            # 检查请求是否成功
            if result.get("success", False):
                return result.get("data")
            else:
                status_code = result.get("status", "未知")
                error_msg = result.get("error", "未知错误")
                self.logger.warning(f"{error_message} 失败: {error_msg}")
                return None
        except Exception as e:
            self.logger.error(f"{error_message} 时出错: {str(e)}")
            return None

    async def _get_latest_release(self, owner, repo):
        """获取最新的release信息"""
        api_url = f"{self.api_url}/repos/{owner}/{repo}/releases/latest"
        result = await self._github_api_request(api_url, f"获取仓库 {owner}/{repo} 的release")
        if result:
            return result
        return None

    async def _get_latest_tag(self, owner, repo):
        """获取最新的tag信息"""
        api_url = f"{self.api_url}/repos/{owner}/{repo}/tags"
        tags = await self._github_api_request(api_url, f"获取仓库 {owner}/{repo} 的tags")
        if tags:
            return tags[0]["name"]
        return None

    async def _get_files_from_release_page(self, owner, repo, release_tag):
        """从发布页面获取下载文件列表"""
        try:
            # 构建release页面URL
            release_url = f"https://github.com/{owner}/{repo}/releases/tag/{release_tag}"
            self.logger.info(f"获取发布页面: {release_url}")

            # 请求页面内容
            headers = {"User-Agent": "Mozilla/5.0 Chrome/91.0.4472.124 Safari/537.36"}

            # 获取HTTP客户端
            http_client = self._get_http_client()

            # 发送请求获取页面内容
            result = await http_client.get(
                release_url,
                headers=headers,
                timeout=self.timeout
            )

            # 检查请求是否成功
            if not result.get("success", False):
                status_code = result.get("status", "未知")
                error_msg = result.get("error", "未知错误")
                self.logger.error(f"获取页面失败，状态码: {status_code}，错误: {error_msg}")
                return None

            # 获取HTML内容
            html_content = result.get("data", "")
            if not html_content:
                self.logger.error("获取的页面内容为空")
                return None

            # 提取下载链接并存入临时列表
            download_links = []

            # 匹配所有下载链接
            # 添加一些调试信息，记录HTML的一小部分
            self.logger.debug(f"HTML内容片段（前500字符）: {html_content[:500]}")

            # 更通用的下载链接匹配模式
            # 1. 匹配任何href中包含releases/download的链接
            download_pattern1 = r'href="([^"]*?releases/download/[^"]*?)"'
            # 2. 匹配任何href中包含archive/refs/tags的链接（源代码下载）
            download_pattern2 = r'href="([^"]*?archive/refs/tags/[^"]*?)"'
            # 3. 直接匹配已知的下载文件名后缀
            extensions = r'\.(zip|tar\.gz|exe|msi|dmg|deb|rpm|AppImage|pacman)'
            download_pattern3 = r'href="([^"]*?' + extensions + r')"'
            # 4. 尝试直接提取a标签中包含下载相关类或文本的链接
            download_pattern4 = r'<a[^>]*?class="[^"]*?release-download[^"]*?"[^>]*?href="([^"]*?)"'

            patterns = [download_pattern1, download_pattern2, download_pattern3, download_pattern4]

            # 记录使用的模式
            self.logger.debug(f"使用 {len(patterns)} 种模式匹配下载链接")

            # 合并所有匹配结果
            for i, pattern in enumerate(patterns):
                matches = list(re.finditer(pattern, html_content, re.IGNORECASE))
                self.logger.debug(f"模式 {i+1} 匹配到 {len(matches)} 个结果")

                for match in matches:
                    link = match.group(1)
                    # 确保是完整URL
                    if not link.startswith("http"):
                        if link.startswith("/"):
                            link = f"https://github.com{link}"
                        else:
                            link = f"https://github.com/{link}"

                    if link not in download_links:  # 避免重复
                        download_links.append(link)
                        self.logger.debug(f"找到下载链接: {link}")

            self.logger.info(f"从页面提取到 {len(download_links)} 个下载文件链接")

            # 如果没有提取到任何文件，返回None
            if not download_links:
                self.logger.warning("未从发布页面提取到任何下载文件")
                return None

            # 从下载链接中提取文件名
            files = []
            for link in download_links:
                filename = link.split("/")[-1]
                files.append({"filename": filename, "url": link})
                self.logger.debug(f"找到文件: {filename}")

            return files
        except Exception as e:
            self.logger.error(f"从发布页面提取文件时出错: {str(e)}")
            return None

    async def _extract_version_from_files(self, files, version_extract_key=None, aur_version=None, version_pattern=None):
        """从文件列表中提取版本号，可选使用版本提取关键字过滤

        Args:
            files: 文件列表
            version_extract_key: 版本提取关键字（可选）
            aur_version: AUR版本号（可选），用于格式验证
            version_pattern: 版本模式（可选），如"x.y.z"

        Returns:
            dict: 包含版本信息的字典，如果提取失败则为None
        """
        if not files:
            return None

        # 如果有版本提取关键字，过滤文件
        filtered_files = files
        if version_extract_key:
            # 移除前导点号，因为我们要检查的是文件名中的子字符串，而不是文件扩展名
            clean_key = version_extract_key
            if clean_key.startswith("."):
                clean_key = clean_key[1:]

            self.logger.info(f"使用版本提取关键字 '{version_extract_key}' 过滤文件")

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
                # 如果提供了AUR版本和版本模式，验证提取的版本格式是否符合要求
                if aur_version and version_pattern and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                    if self.main_checker._is_version_similar(version, version_pattern):
                        self.logger.info(f"提取的版本 {version} 与版本模式 {version_pattern} 匹配")
                    else:
                        self.logger.debug(f"提取的版本 {version} 与版本模式 {version_pattern} 不匹配，但仍然使用")

                version_files.append({
                    "filename": file_info["filename"],
                    "url": file_info["url"],
                    "version": version
                })

        if not version_files:
            self.logger.warning("无法从文件中提取版本号")
            return None

        # 获取最新版本
        versions = [f["version"] for f in version_files]
        best_version = self.version_processor.get_latest_version(versions)
        self.logger.info(f"从文件中提取的最佳版本: {best_version}")

        return {
            "version": best_version,
            "all_versions": versions,
            "files": version_files,
            "date": datetime.now().strftime("%Y-%m-%d")
        }

    async def _get_release_assets(self, owner, repo, release_tag):
        """通过GitHub API获取发布版本的资产文件列表"""
        api_url = f"{self.api_url}/repos/{owner}/{repo}/releases/tags/{release_tag}"
        release_data = await self._github_api_request(api_url, f"获取仓库 {owner}/{repo} 的release资产")

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

    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """检查GitHub仓库的最新版本

        按以下逻辑检查:
        1. 首先查看是否存在不为空的版本提取关键字. 如果存在, 则通过GitHub API提供的接口获取release资产文件,
           然后获取最新版本
        2. 如果没有定义版本提取关键字或者版本提取关键字为空, 则直接通过api请求release获取最新版本
        3. 如果没有定义版本提取关键字或者版本提取关键字为空, 且没有发行版, 则直接通过api请求tags来获取最新的标签

        Args:
            package_name: 软件包名称
            url: GitHub仓库URL
            version_pattern_regex: 版本匹配正则表达式（可选）
            **kwargs: 额外参数，可包含：
                - version_extract_key: 版本提取关键字
                - aur_version: AUR版本号，用于格式验证
                - version_pattern: 版本模式，如"x.y.z"

        Returns:
            dict: 包含版本信息的字典
        """
        # 从kwargs中获取可选参数
        version_extract_key = kwargs.get('version_extract_key')
        aur_version = kwargs.get('aur_version')
        version_pattern = kwargs.get('version_pattern')
        self.logger.info(f"检查 GitHub 仓库: {url}")
        self.logger.debug(f"传入的版本提取关键字: {version_extract_key}")
        self.logger.debug(f"传入的AUR版本: {aur_version}")
        self.logger.debug(f"传入的版本模式: {version_pattern}")

        try:
            # 解析GitHub URL, 提取用户名和仓库名
            repo_info = self._parse_github_url(url)
            if not repo_info:
                self.logger.error(f"无法从URL {url} 解析仓库信息")
                return {
                    "name": package_name,
                    "success": False,
                    "message": f"无法从URL {url} 解析仓库信息"
                }

            owner = repo_info['owner']
            repo = repo_info['repo']
            self.logger.debug(f"解析到仓库: {owner}/{repo}")

            # 获取最新release信息
            release = await self._get_latest_release(owner, repo)
            release_tag = release['tag_name'] if release else None
            self.logger.debug(f"获取到的release标签: {release_tag}")

            # 初始化version_info为None, 避免未定义错误
            version_info = None

            # 步骤1: 如果存在不为空的版本提取关键字且存在release, 则通过API获取资产文件
            if version_extract_key and release_tag:
                self.logger.info(f"使用版本提取关键字: {version_extract_key}")
                self.logger.info(f"找到最新的release标签: {release_tag}")

                # 通过GitHub API获取release资产文件
                files = await self._get_release_assets(owner, repo, release_tag)

                # 如果API获取失败, 尝试从发布页面获取文件
                if not files:
                    self.logger.warning("无法通过API获取资产文件, 尝试从发布页面获取")
                    files = await self._get_files_from_release_page(owner, repo, release_tag)

                if files:
                    self.logger.debug(f"获取到 {len(files)} 个文件")
                    for file in files:
                        self.logger.debug(f"  - {file['filename']}")

                    # 从文件中提取版本
                    version_info = await self._extract_version_from_files(
                        files=files, 
                        version_extract_key=version_extract_key, 
                        aur_version=aur_version, 
                        version_pattern=version_pattern
                    )

                    if version_info:
                        self.logger.info(f"使用版本提取关键字 '{version_extract_key}' 从文件中提取到版本: {version_info['version']}")
                        return self._create_result(
                            package_name=package_name,
                            success=True,
                            version=version_info["version"],
                            date=release.get('published_at', "")[:10] if release else None,
                            url=url,
                            all_versions=version_info["all_versions"]
                        )
                    else:
                        self.logger.warning("无法从文件中提取版本号, 将尝试其他方法")

            # 步骤2: 如果没有定义版本提取关键字或上面的步骤失败, 且存在release, 尝试直接从API获取最新版本
            if release:
                # 直接使用release的tag_name作为版本
                version = self._format_version(release_tag)
                if self._is_valid_version(version):
                    self.logger.info(f"从release API获取到版本: {version}")
                    return self._create_result(
                        package_name=package_name,
                        success=True,
                        version=version,
                        date=release['published_at'][:10],
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
                    return self._create_result(
                        package_name=package_name,
                        success=True,
                        version=version,
                        url=url
                    )
                else:
                    self.logger.warning(f"从tag获取的标签 '{latest_tag}' 不是有效版本")

            # 如果所有方法都失败
            self.logger.warning(f"无法从GitHub仓库 {url} 提取有效版本号")
            return self._create_result(
                package_name=package_name,
                success=False,
                message="无法提取有效版本号, 可能需要手动检查"
            )

        except Exception as e:
            self.logger.error(f"检查 GitHub 版本时出错: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return self._create_result(
                package_name=package_name,
                success=False,
                message=f"检查版本时出错: {str(e)}"
            )
