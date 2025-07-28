from datetime import datetime
import re
import aiohttp
from urllib.parse import urlparse, urljoin

from .base_checker import BaseChecker
from ..version_processor import VersionProcessor

class UpstreamRedirectChecker(BaseChecker):
    """重定向URL上游检查器"""

    def __init__(self, logger, config=None, main_checker=None):
        super().__init__(logger)
        self.config = config
        self.main_checker = main_checker
        self.package_config = None
        self.version_processor = VersionProcessor(logger, self.package_config)

    # 只保留一个check_version方法，采用与基类相同的签名
    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """检查重定向URL的上游版本

        Args:
            package_name: 软件包名称
            url: 上游URL
            version_extract_key: 版本提取键（可选）
            **kwargs: 其他参数如aur_version, version_pattern等

        Returns:
            dict: 包含版本信息的字典
        """
        self.logger.info(f"正在检查重定向URL上游版本: {url}")
        # 从kwargs中获取version_extract_key参数
        version_extract_key = kwargs.get("version_extract_key")

        # 从kwargs中获取其他参数
        aur_version = kwargs.get("aur_version")
        version_pattern = kwargs.get("version_pattern")

        try:
            # 检查URL是否重定向
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)",
                "Accept": "text/html,application/xhtml+xml,application/xml",
                "Accept-Language": "en-US,en;q=0.5"
            }

            async with aiohttp.ClientSession() as session:
                # 禁用自动重定向，以便检查重定向URL
                async with session.get(url, headers=headers, allow_redirects=False) as response:
                    # 检查是否有重定向
                    if response.status in (301, 302, 303, 307, 308):
                        redirect_url = response.headers.get("Location")

                        if not redirect_url:
                            return {"version": None, "success": False, "message": "无Location头"}

                        # 处理相对URL
                        if not urlparse(redirect_url).netloc:
                            base_url = urlparse(url)
                            base = f"{base_url.scheme}://{base_url.netloc}"
                            redirect_url = urljoin(base, redirect_url)

                        self.logger.debug(f"重定向到: {redirect_url}")

                        # 如果存在version_extract_key，尝试提取
                        if version_extract_key and version_extract_key in redirect_url:
                            pattern = f"{re.escape(version_extract_key)}(\\d+(?:\\.\\d+)*)"
                            match = re.search(pattern, redirect_url)
                            if match:
                                version = match.group(1)
                                return {"version": version, "success": True, "message": "成功从URL提取版本"}

                        # 尝试从URL自动提取版本号
                        filename = redirect_url.split('/')[-1]

                        # 优先使用传入的 version_pattern_regex
                        if version_pattern_regex:
                            try:
                                match = re.search(version_pattern_regex, redirect_url)
                                if match:
                                    version = match.group(1)
                                    self.logger.info(f"使用传入的版本模式提取到版本号: {version}")

                                    # 尝试验证版本合理性
                                    if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                                        if self.main_checker._is_version_similar(version, version_pattern):
                                            self.logger.info(f"提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                                            return {"version": version, "success": True, "message": "成功使用传入模式提取版本"}
                                        else:
                                            self.logger.debug(f"提取的版本 {version} 与AUR版本格式不匹配，不返回")
                                            # 继续尝试其他提取方法
                                            pass
                                    else:
                                        # 如果无法验证（缺少必要组件），仍然返回结果，但标记为未验证
                                        self.logger.debug(f"无法验证版本 {version} 的格式，但仍然返回")
                                        return {"version": version, "success": True, "message": "成功使用传入模式提取版本（未验证格式）"}

                                # 先尝试从URL路径中查找，因为文件名可能包含干扰信息
                                try:
                                    # 根据AUR版本猜测版本格式
                                    if aur_version:
                                        parts_count = len(aur_version.split('.'))
                                        if parts_count > 1:
                                            # 尝试匹配类似格式的版本号
                                            pattern = r'(?:^|/)(\d+' + r'\.\d+' * (parts_count - 1) + r')(?:/|$)'
                                            self.logger.debug(f"尝试从URL路径使用动态生成的模式匹配: {pattern}")
                                            match = re.search(pattern, redirect_url)
                                            if match:
                                                version = match.group(1)
                                                self.logger.info(f"使用动态模式从URL路径提取到版本号: {version}")
                                                if self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                                                    if self.main_checker._is_version_similar(version, version_pattern):
                                                        self.logger.info(f"动态提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                                                        return {"version": version, "success": True, "message": "成功使用动态模式提取版本"}
                                                return {"version": version, "success": True, "message": "成功使用动态模式提取版本（未验证格式）"}
                                except Exception as e:
                                    self.logger.debug(f"从URL路径提取版本失败: {str(e)}")

                                # 尝试从文件名中提取
                                match = re.search(version_pattern_regex, filename)
                                if match:
                                    version = match.group(1)
                                    self.logger.info(f"使用传入的版本模式从文件名提取到版本号: {version}")

                                    # 尝试验证版本合理性
                                    if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                                        if self.main_checker._is_version_similar(version, version_pattern):
                                            self.logger.info(f"从文件名提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                                            return {"version": version, "success": True, "message": "成功使用传入模式从文件名提取版本"}
                                        else:
                                            self.logger.debug(f"从文件名提取的版本 {version} 与AUR版本格式不匹配，不返回")
                                            # 继续尝试其他提取方法
                                            pass
                                    else:
                                        # 如果无法验证（缺少必要组件），仍然返回结果，但标记为未验证
                                        self.logger.debug(f"无法验证从文件名提取的版本 {version} 的格式，但仍然返回")
                                        return {"version": version, "success": True, "message": "成功使用传入模式从文件名提取版本（未验证格式）"}
                            except Exception as e:
                                self.logger.debug(f"使用传入的版本模式提取失败: {str(e)}")

                        # 首先检查是否有与AUR版本完全相同的字符串
                        if aur_version:
                            # 直接在URL中查找完全匹配的版本号
                            escaped_version = re.escape(aur_version)  # 转义特殊字符
                            exact_match = re.search(f"(?:^|[^0-9])({escaped_version})(?:[^0-9]|$)", redirect_url)
                            if exact_match:
                                version = exact_match.group(1)
                                self.logger.info(f"在URL中找到与AUR版本完全匹配的版本号: {version}")
                                return {"version": version, "success": True, "message": "成功提取与AUR版本完全匹配的版本号"}

                            # 根据AUR版本猜测版本格式
                            parts_count = len(aur_version.split('.'))
                            if parts_count > 1:
                                # 尝试匹配类似格式的版本号
                                pattern = r'(?:^|/)(\d+' + r'\.\d+' * (parts_count - 1) + r')(?:/|$)'
                                self.logger.debug(f"尝试使用动态生成的模式匹配: {pattern}")
                                match = re.search(pattern, redirect_url)
                                if match:
                                    version = match.group(1)
                                    self.logger.info(f"使用动态模式从URL路径提取到版本号: {version}")
                                    if self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                                        if self.main_checker._is_version_similar(version, version_pattern):
                                            self.logger.info(f"动态提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                                            return {"version": version, "success": True, "message": "成功使用动态模式提取版本"}
                                    # 格式不匹配，但仍然返回结果，标记为未验证
                                    self.logger.debug(f"动态提取的版本 {version} 与AUR版本格式不匹配，但仍然返回")
                                    return {"version": version, "success": True, "message": "成功使用动态模式提取版本（格式不匹配）"}

                        # 备选模式
                        backup_patterns = [
                            r"[-_](\d+\.\d+\.\d+\.\d+\.\d+)[-/\._]",  # 匹配 5部分版本号
                            r"[-_](\d+\.\d+\.\d+\.\d+)[-/\._]",       # 匹配 4部分版本号
                            r"[-_](\d+\.\d+\.\d+)[-/\._]",            # 匹配 3部分版本号
                            r"[-/](\d+\.\d+\.\d+\.\d+\.\d+)(?:[-/]|$)",  # 路径中的5部分版本号
                            r"[-/](\d+\.\d+\.\d+\.\d+)(?:[-/]|$)",       # 路径中的4部分版本号
                            r"[-/](\d+\.\d+\.\d+)(?:[-/]|$)",             # 路径中的3部分版本号
                            r"_(\d+\.\d+\.\d+\.\d+\.\d+)_",           # 下划线包围的5部分版本号
                            r"_(\d+\.\d+\.\d+\.\d+)_",                # 下划线包围的4部分版本号
                            r"(\d+\.\d+\.\d+\.\d+\.\d+)",             # 匹配任何位置的 5部分版本号
                            r"(\d+\.\d+\.\d+\.\d+)",                  # 匹配任何位置的 4部分版本号
                            r"(\d+\.\d+\.\d+)",                       # 匹配任何位置的 3部分版本号
                            r"(\d+v\d+)",                             # 匹配 2719v1 格式
                            r"[A-Za-z]+(\d+v\d+)\.",                  # 匹配 linuxZiipoo2719v1.deb 格式
                            r"[-_]([0-9]+[A-Za-z][0-9]+)"             # 匹配数字+字母+数字格式
                        ]

                        for pattern in backup_patterns:
                            match = re.search(pattern, filename)
                            if match:
                                version = match.group(1)
                                self.logger.info(f"使用备选模式从文件名提取到版本号: {version}，完整文件名: {filename}")

                                # 尝试验证版本合理性
                                if aur_version and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                                    if self.main_checker._is_version_similar(version, version_pattern):
                                        self.logger.info(f"备选模式提取的版本 {version} 与AUR版本 {aur_version} 格式匹配")
                                        return {"version": version, "success": True, "message": "成功使用备选模式提取版本"}
                                    else:
                                        self.logger.debug(f"备选模式提取的版本 {version} 与AUR版本格式不匹配，不返回")
                                        # 尝试下一个备选模式
                                        continue
                                else:
                                    # 如果无法验证（缺少必要组件），仍然返回结果，但标记为未验证
                                    self.logger.debug(f"无法验证备选模式提取的版本 {version} 的格式，但仍然返回")
                                    return {"version": version, "success": True, "message": "成功使用备选模式提取版本（未验证格式）"}

                        # 如果URL没有重定向或者提取失败，返回错误
                        return {"version": None, "success": False, "message": "URL未重定向"}
                    else:
                        return {"version": None, "success": False, "message": f"未重定向: {response.status}"}
        except Exception as e:
            self.logger.error(f"检查时出错: {e}")
            return {"version": None, "success": False, "message": str(e)}
