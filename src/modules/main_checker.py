# -*- coding: utf-8 -*-
from .checkers.upstream_github_checker import UpstreamGithubChecker
from .checkers.upstream_gitlab_checker import UpstreamGitlabChecker
from .checkers.upstream_pypi_checker import UpstreamPypiChecker
from .checkers.upstream_common_checker import UpstreamCommonChecker
from .checkers.upstream_gitee_checker import UpstreamGiteeChecker
from .checkers.upstream_json_checker import UpstreamJsonChecker
from .checkers.upstream_redirect_checker import UpstreamRedirectChecker
from .checkers.upstream_curl_checker import UpstreamCurlChecker
from .checkers.upstream_playwright_checker import UpstreamPlaywrightChecker
from .checkers.upstream_npm_checker import UpstreamNpmChecker
from .aur_checker import AurCheckerModule
from .version_processor import VersionProcessor
import re

class MainCheckerModule:
    """上游检查器主模块，负责协调各种上游检查器"""

    def __init__(self, logger, db_module, config=None):
        """初始化上游检查器主模块

        Args:
            logger: 日志模块实例
            db_module: 数据库模块实例
            config: 配置模块实例（可选）
        """
        self.logger = logger
        self.db_module = db_module
        self.config = config
        self.logger.debug("主检查模块初始化")
        
        # 初始化版本处理器
        self.version_processor = VersionProcessor(logger)

        # 初始化各种上游检查器
        self.github_checker = UpstreamGithubChecker(logger, config, self)  # 传递self作为main_checker
        self.gitlab_checker = UpstreamGitlabChecker(logger, config, self)  # 传递self作为main_checker
        self.pypi_checker = UpstreamPypiChecker(logger, config)
        self.common_checker = UpstreamCommonChecker(logger, config)

        # 初始化新增的上游检查器
        self.gitee_checker = UpstreamGiteeChecker(logger)
        self.json_checker = UpstreamJsonChecker(logger, config, self)
        self.redirect_checker = UpstreamRedirectChecker(logger)
        self.curl_checker = UpstreamCurlChecker(logger, config)
        self.playwright_checker = UpstreamPlaywrightChecker(logger, config, self)  # 传递self作为main_checker
        self.npm_checker = UpstreamNpmChecker(logger, config, self)  # 传递self作为main_checker

        # 初始化AUR检查器
        self.aur_checker = AurCheckerModule(logger, db_module)

        # 上游检查器映射表
        self.checkers = {
            'github': self.github_checker,
            'gitlab': self.gitlab_checker,
            'pypi': self.pypi_checker,
            'common': self.common_checker,
            'gitee': self.gitee_checker,
            'json': self.json_checker,
            'redirect': self.redirect_checker,
            'curl': self.curl_checker,
            'playwright': self.playwright_checker,
            'npm': self.npm_checker
        }

    async def check_single_upstream_version(self, package_info):
        """检查单个软件包的上游版本

        Args:
            package_info: 软件包信息字典

        Returns:
            dict: 包含版本信息的字典
        """
        if not package_info:
            self.logger.error("软件包信息为空")
            return {"name": "unknown", "success": False, "message": "软件包信息为空"}

        name = package_info.get("name")
        upstream_url = package_info.get("upstream_url")
        checker_type = package_info.get("checker_type")
        version_pattern_regex = package_info.get("version_pattern_regex")

        self.logger.info(f"开始检查软件包 {name} 的上游版本")

        # 1. 首先检查数据库中是否有AUR版本数据
        db_package_info = self.db_module.get_package_by_name(name)
        if not db_package_info or not db_package_info.get("aur_version"):
            self.logger.warning(f"数据库中未找到软件包 {name} 的AUR版本信息")
            return {
                "name": name,
                "success": False,
                "message": "数据库中未找到AUR版本信息，请先检查AUR版本"
            }

        # 2. 获取AUR版本并分析其构成
        aur_version = db_package_info.get("aur_version")
        self.logger.info(f"从数据库获取AUR版本: {aur_version}")

        # 分析AUR版本格式并设置版本提取正则表达式
        self._analyze_aur_version_pattern(package_info, aur_version)

        if not upstream_url:
            self.logger.warning(f"软件包 {name} 没有上游URL")
            return {
                "name": name,
                "success": False,
                "message": "没有上游URL"
            }

        try:
            # 根据checker_type或URL特征选择合适的检查器
            checker = None

            if checker_type and checker_type in self.checkers and self.checkers[checker_type]:
                # 如果指定了检查器类型且存在，则使用指定的检查器
                checker = self.checkers[checker_type]
                self.logger.debug(f"使用指定的检查器类型: {checker_type}")
            elif "github.com" in upstream_url:
                checker = self.checkers.get("github")
                self.logger.debug("根据URL自动选择GitHub检查器")
            elif self.checkers.get("gitlab") and self._is_gitlab_url(upstream_url):
                checker = self.checkers.get("gitlab")
                self.logger.debug("根据URL自动选择GitLab检查器")
            elif "pypi.org" in upstream_url or "python.org/pypi" in upstream_url:
                checker = self.checkers.get("pypi")
                self.logger.debug("根据URL自动选择PyPI检查器")
            else:
                # 默认使用通用检查器
                checker = self.checkers.get("common")
                self.logger.debug("使用通用检查器")

            if not checker:
                raise ValueError(f"没有适合URL {upstream_url} 的检查器")

            # 使用选定的检查器检查上游版本
            if checker == self.pypi_checker:
                # 对于PyPI检查器，需要提取包名
                pypi_package = self._parse_pypi_package_from_url(upstream_url) or name
                result = await checker.check_version(name, pypi_package, version_pattern_regex)
            else:
                # 其他检查器（包括json_checker）统一处理
                # 对所有检查器都设置包配置
                checker.package_config = package_info  # 设置当前正在检查的包的配置

                # 重新初始化版本处理器，确保它接收到更新的包配置
                if hasattr(checker, 'version_processor'):
                    checker.version_processor.package_config = package_info

                # 获取可能的额外参数
                extra_args = {}
                # 传递version_extract_key参数
                if package_info.get('version_extract_key'):
                    extra_args['version_extract_key'] = package_info.get('version_extract_key')
                    self.logger.debug(f"检查器使用version_extract_key: {extra_args['version_extract_key']}")

                # 传递AUR版本作为参考信息
                if db_package_info and db_package_info.get('aur_version'):
                    extra_args['aur_version'] = db_package_info.get('aur_version')
                    self.logger.debug(f"检查器使用aur_version参考: {extra_args['aur_version']}")

                # 传递版本模式信息
                if package_info.get('version_pattern'):
                    extra_args['version_pattern'] = package_info.get('version_pattern')
                    self.logger.debug(f"检查器使用version_pattern: {extra_args['version_pattern']}")

                # 根据检查器类型和可用参数动态调用
                if extra_args:
                    self.logger.debug(f"调用{checker_type}检查器，传递额外参数: {', '.join(extra_args.keys())}")
                    try:
                        # 尝试使用额外参数调用
                        result = await checker.check_version(name, upstream_url, version_pattern_regex, **extra_args)
                    except TypeError as e:
                        self.logger.warning(f"检查器不支持全部额外参数，回退到基础调用: {str(e)}")
                        # 如果检查器不支持所有额外参数，则使用基本参数 + version_extract_key尝试
                        try:
                            basic_args = {'version_extract_key': extra_args.get('version_extract_key')} if extra_args.get('version_extract_key') else {}
                            if basic_args:
                                result = await checker.check_version(name, upstream_url, version_pattern_regex, **basic_args)
                            else:
                                result = await checker.check_version(name, upstream_url, version_pattern_regex)
                        except Exception as inner_e:
                            self.logger.warning(f"回退调用也失败，使用标准调用: {str(inner_e)}")
                            result = await checker.check_version(name, upstream_url, version_pattern_regex)
                else:
                    # 没有额外参数时使用标准调用
                    result = await checker.check_version(name, upstream_url, version_pattern_regex)

            # 统一标准化处理所有检查器的返回结果
            if not isinstance(result, dict):
                result = {
                    "name": name,
                    "success": False,
                    "message": "无效的检查结果格式",
                    "version": None,
                    "upstream_version": None
                }

            # 确保必要字段存在
            if "success" not in result:
                version = result.get("version") or result.get("upstream_version")
                result["success"] = bool(version)
                result["version"] = version
                result["upstream_version"] = version

            # 记录最终返回结果
            self.logger.debug(f"最终返回结果: {result}")

            # 更新数据库并确保返回结果一致
            if self.db_module and result.get("version"):
                version = result["version"]
                try:
                    self.db_module.update_upstream_version(name, version)
                    self.logger.info(f"数据库更新成功: {name} -> {version}")
                    # 确保返回结果中的版本信息一致
                    result["upstream_version"] = version
                    result["version"] = version
                except Exception as db_error:
                    self.logger.error(f"数据库更新失败: {str(db_error)}")
                    # 即使数据库更新失败，也保留版本信息
                    result["upstream_version"] = version
                    result["version"] = version

            self.logger.info(f"软件包 {name} 上游版本检查完成，版本: {result.get('version', '未知')}")

            # 标准化返回结果
            self.logger.debug(f"原始检查结果: {result}")
            return {
                "name": name,
                "upstream_version": result.get("version") or result.get("upstream_version"),
                "update_date": result.get("date") or result.get("update_date"),
                "success": result.get("success", False),
                "message": result.get("message", "检查完成")
            }
        except Exception as error:
            self.logger.error(f"检查软件包 {name} 上游版本时出错: {str(error)}")
            return {
                "name": name,
                "success": False,
                "message": str(error)
            }

    async def check_multiple_upstream_versions(self, packages_info):
        """批量检查多个软件包的上游版本

        Args:
            packages_info: 软件包信息列表

        Returns:
            list: 包含各个软件包版本信息的列表
        """
        self.logger.info(f"开始批量检查 {len(packages_info)} 个软件包的上游版本")

        import asyncio

        # 优化：批量预加载AUR版本数据
        package_names = [pkg.get("name") for pkg in packages_info if pkg.get("name")]
        if package_names:
            try:
                # 使用批量查询预加载所有需要的包信息
                self.logger.debug(f"预加载 {len(package_names)} 个软件包的数据库信息")
                package_data_map = self.db_module.get_packages_by_names(package_names)
                self.logger.debug(f"成功预加载 {len(package_data_map)} 个软件包信息")

                # 更新packages_info中的数据库信息
                for i, package_info in enumerate(packages_info):
                    name = package_info.get("name")
                    if name and name in package_data_map:
                        # 合并数据库信息到package_info
                        db_info = package_data_map[name]
                        # 只更新未指定的字段
                        for key, value in db_info.items():
                            if key not in package_info or not package_info[key]:
                                package_info[key] = value
            except Exception as e:
                self.logger.error(f"预加载软件包数据失败: {str(e)}")

        # 创建所有检查任务
        tasks = []
        for package_info in packages_info:
            # 直接调用check_single_upstream_version，并添加内联异常处理
            async def safe_check(pkg_info):
                try:
                    return await self.check_single_upstream_version(pkg_info)
                except Exception as error:
                    name = pkg_info.get("name", "unknown")
                    self.logger.error(f"检查软件包 {name} 版本时发生未捕获的异常: {str(error)}")
                    return {
                        "name": name,
                        "success": False,
                        "message": f"检查过程发生异常: {str(error)}"
                    }

            task = asyncio.create_task(safe_check(package_info))
            tasks.append(task)

        # 并发执行所有任务
        results = await asyncio.gather(*tasks)

        self.logger.info(f"批量检查上游完成，共 {len(results)} 个软件包")
        return results



    def _is_gitlab_url(self, url):
        """检查是否为GitLab URL

        Args:
            url: 要检查的URL

        Returns:
            bool: 如果是GitLab URL则返回True
        """
        if not self.gitlab_checker:
            return False

        gitlab_domains = ["gitlab.com", "gitlab.", "gl."]
        return any(domain in url.lower() for domain in gitlab_domains)

    def _parse_pypi_package_from_url(self, url):
        """从PyPI URL中解析包名

        Args:
            url: PyPI URL

        Returns:
            str: 包名，如果无法解析则返回None
        """
        patterns = [
            r"pypi\.org/project/([^/]+)",
            r"pypi\.org/simple/([^/]+)",
            r"python\.org/pypi/([^/]+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    async def check_version_integrated(self, package_name, check_aur=True):
        """集成版本检查方法

        Args:
            package_name: 软件包名称
            check_aur: 是否先检查AUR版本

        Returns:
            dict: 包含版本信息的字典
        """
        self.logger.info(f"开始检查软件包 {package_name} 版本")

        # 创建结果字典
        result = {
            "name": package_name,
            "success": False,
            "aur_version": None,
            "upstream_version": None,
            "message": ""
        }

        try:
            # 步骤1: 获取软件包信息
            package_info = self.db_module.get_package_by_name(package_name)
            if not package_info:
                self.logger.warning(f"数据库中未找到软件包 {package_name} 的信息")
                package_info = {"name": package_name}

            # 步骤2: 检查AUR版本
            if check_aur:
                aur_result = await self.aur_checker.check_aur_version(package_name)
                if aur_result and aur_result.get("success", False):
                    result["aur_version"] = aur_result.get("version")
                    result["aur_success"] = True
                    self.logger.info(f"AUR版本检查成功: {result['aur_version']}")

                    # 分析AUR版本格式, 更新包信息
                    self._analyze_aur_version_pattern(package_info, result["aur_version"])
                else:
                    self.logger.warning(f"未能获取AUR版本: {aur_result.get('message', '未知错误')}")

            # 步骤3: 检查上游版本
            upstream_info = await self.check_single_upstream_version(package_info)
            if upstream_info and upstream_info.get("success", False):
                result["upstream_version"] = upstream_info.get("upstream_version")
                result["upstream_success"] = True
                result["message"] = upstream_info.get("message", "版本检查成功")
                self.logger.info(f"上游版本检查成功: {result['upstream_version']}")
            else:
                result["message"] = upstream_info.get("message", "上游版本检查失败")
                self.logger.warning(f"上游版本检查失败: {result['message']}")

            # 步骤4: 确定最终结果状态
            result["success"] = result.get("aur_success", False) or result.get("upstream_success", False)

            return result

        except Exception as error:
            self.logger.error(f"集成版本检查失败: {str(error)}")
            result["message"] = f"检查出错: {str(error)}"
            return result

    def _is_version_similar(self, version, version_pattern):
        """
        检查版本号是否与version_pattern类似
        现在使用VersionProcessor中的is_version_similar方法
        
        Args:
            version: 待检查的版本号
            version_pattern: 版本模式（如x.y）

        Returns:
            bool: 是否类似
        """
        return self.version_processor.is_version_similar(version, version_pattern)

    def _analyze_aur_version_pattern(self, package_info, aur_version):
        """分析AUR版本的格式并设置相应的版本模式和提取正则表达式

        集成了版本结构分析和版本提取策略调整功能

        Args:
            package_info: 软件包信息字典
            aur_version: AUR版本字符串
        """
        if not aur_version:
            return

        self.logger.debug(f"分析AUR版本格式: {aur_version}")

        # 统一的版本模式定义: (匹配正则表达式, 模式名称, 策略类型, 提取正则表达式)
        version_patterns = [
            # 基础模式 (原_analyze_version_structure中的模式)
            (r'^\d+\.\d+$', "a.b", "standard", r"(\d+\.\d+)"),
            (r'^\d+\.\d+\.\d+$', "a.b.c", "standard", r"(\d+\.\d+\.\d+)"),
            (r'^\d+\.\d+\.\d+\.\d+$', "a.b.c.d", "standard", r"(\d+\.\d+\.\d+\.\d+)"),
            (r'^\d+\.\d+\.\d+\.\d+\.\d+$', "a.b.c.d.e", "standard", r"(\d+\.\d+\.\d+\.\d+\.\d+)"),
            (r'^\d+\.\d+_\d+\.\d+\.\d+$', "a.b_c.d.e", "standard", r"(\d+\.\d+_\d+\.\d+\.\d+)"),
            (r'^[A-Za-z]+\d+\.\d+\.\d+$', "PrefixVerA.B.C", "prefixed", r"([A-Za-z]+\d+\.\d+\.\d+)"),
            (r'^\d+\.\d+\.\d+\.\d+[A-Z]{2}\.[A-Z]\d+$', "A.B.C.DXX.SN", "standard", r"(\d+\.\d+\.\d+\.\d+[A-Z]{2}\.[A-Z]\d+)"),
            (r'^[A-Za-z]+v\d+$', "NumPrefixVer", "prefixed", r"([A-Za-z]+v\d+)"),

            # 扩展版本模式 (原_adjust_version_extract_strategy中的模式)
            (r'v?(\d+\.\d+\.\d+(?:\.\d+)*)', "标准版本 A.B.C", "standard", r"(\d+\.\d+\.\d+(?:\.\d+)*)"),
            (r'v?(\d+\.\d+)$', "简化版本 A.B", "standard", r"(\d+\.\d+)"),
            (r'(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', "日期版本 YYYY.MM.DD", "date", r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"),
            (r'^(\d+)$', "数字版本 A", "standard", r"(\d+)"),
            (r'([a-zA-Z]+\d+(?:\.\d+)*)', "前缀版本 PREFIX-A.B", "prefixed", r"([a-zA-Z]+\d+(?:\.\d+)*)")
        ]

        # 匹配版本模式
        matched = False
        for pattern, pattern_name, strategy_type, extract_regex in version_patterns:
            if re.search(pattern, aur_version):
                package_info["version_pattern"] = pattern_name
                package_info["version_pattern_name"] = pattern_name
                package_info["version_extract_strategy"] = strategy_type
                package_info["version_pattern_regex"] = extract_regex
                self.logger.debug(f"识别到版本模式: {pattern_name}")
                matched = True
                break

        # 默认处理
        if not matched:
            self.logger.debug("未识别到特定版本模式, 将使用通用策略")
            package_info["version_pattern"] = "unknown"
            package_info["version_pattern_name"] = "未知模式"
            package_info["version_extract_strategy"] = "generic"
            package_info["version_pattern_regex"] = r"(\d+\.\d+\.\d+(?:\.\d+)*)"

    def _adjust_version_extract_strategy(self, package_info, aur_version):
        """根据AUR版本格式调整上游版本提取策略

        Args:
            package_info: 软件包信息字典
            aur_version: AUR版本字符串
        """
        # 直接调用优化后的版本分析方法
        self._analyze_aur_version_pattern(package_info, aur_version)
