# -*- coding: utf-8 -*-
import os
import re
import asyncio
import subprocess
import tempfile
import pathlib
import time
from datetime import datetime
from contextlib import asynccontextmanager
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import lxml  # 添加lxml解析器支持
import hashlib  # 用于缓存功能

from .base_checker import BaseChecker
from ..version_processor import VersionProcessor

# 初始化Playwright环境
def init_playwright_env():
    """
    初始化Playwright环境，设置正确的浏览器路径
    这个函数在模块导入时执行一次，确保整个应用使用正确的浏览器路径
    """
    import os
    import sys
    import glob

    # 检查是否在虚拟环境中运行
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

    # 可能的浏览器路径
    browser_paths = []

    # 1. 虚拟环境路径
    if in_venv:
        venv_cache = os.path.join(sys.prefix, ".cache", "ms-playwright")
        browser_paths.append(venv_cache)

    # 2. 用户主目录
    user_cache = os.path.expanduser("~/.cache/ms-playwright")
    browser_paths.append(user_cache)

    # 3. 当前目录相对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_cache = os.path.join(script_dir, "..", "..", "..", ".cache", "ms-playwright")
    browser_paths.append(os.path.abspath(local_cache))

    # 4. 系统路径
    system_paths = [
        "/usr/local/share/ms-playwright",
        "/usr/share/ms-playwright",
        "/opt/ms-playwright"
    ]
    browser_paths.extend(system_paths)

    # 检查哪些路径存在
    valid_paths = []
    for path in browser_paths:
        if os.path.exists(path):
            # 检查是否包含浏览器目录
            browser_dirs = glob.glob(os.path.join(path, "chromium*")) + glob.glob(os.path.join(path, "chromium_headless_shell*"))
            if browser_dirs:
                valid_paths.append(path)

    # 如果找到有效路径，设置环境变量
    if valid_paths:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = valid_paths[0]
        return True

    return False

# 模块加载时立即初始化Playwright环境
playwright_env_initialized = init_playwright_env()


def get_browser_launch_options():
    """获取统一的浏览器启动选项，并添加诊断信息"""
    import os
    import sys
    import glob
    import logging

    # 创建日志记录器或使用默认日志
    logger = None
    try:
        from ..logger import LoggerModule
        logger = LoggerModule.get_instance()
    except (ImportError, Exception):
        pass

    # 记录当前环境变量
    if logger:
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "未设置")
        logger.info(f"当前PLAYWRIGHT_BROWSERS_PATH: {browsers_path}")

    # 显示已发现的浏览器引擎
    if playwright_env_initialized:
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if browsers_path and os.path.exists(browsers_path):
            # 列出找到的浏览器引擎
            engine_dirs = glob.glob(os.path.join(browsers_path, "chromium*"))
            if logger and engine_dirs:
                logger.info(f"已找到以下浏览器引擎: {engine_dirs}")

    # 基本配置
    options = {
        'headless': True,
        'args': [
            '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas', '--disable-gpu', '--disable-extensions',
            '--disable-web-security', '--ignore-certificate-errors',
            '--single-process', '--disable-background-networking',
            '--disable-notifications', '--metrics-recording-only', '--mute-audio',
            '--no-default-browser-check', '--no-first-run', '--password-store=basic',
        ],
        'ignore_default_args': ['--enable-automation'],
        'handle_sigint': False, 'handle_sigterm': False, 'handle_sighup': False,
        'chromium_sandbox': False,
        'timeout': 30000,  # 增加超时时间到30秒
    }

    return options

from ..version_processor import VersionProcessor


def ensure_browser_installed():
    """
    确保Playwright浏览器已正确安装
    如果未安装或安装不完整，则自动进行安装
    返回安装结果(成功/失败)

    优化特性：
    1. 使用axel加速下载
    2. 从国内镜像下载
    """
    import os
    import sys
    import subprocess
    import glob
    import shutil
    import tempfile
    import time

    # 检查PLAYWRIGHT_BROWSERS_PATH环境变量
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not browsers_path:
        # 如果未设置，使用默认路径
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            # 虚拟环境
            browsers_path = os.path.join(sys.prefix, ".cache", "ms-playwright")
        else:
            # 用户主目录
            browsers_path = os.path.expanduser("~/.cache/ms-playwright")

        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

    # 创建日志记录器或使用默认日志
    logger = None
    try:
        from ..logger import LoggerModule
        logger = LoggerModule.get_instance()
    except (ImportError, Exception):
        pass

    # 检查是否已有浏览器安装
    has_browser = False
    if os.path.exists(browsers_path):
        browser_dirs = glob.glob(os.path.join(browsers_path, "chromium*"))
        has_browser = len(browser_dirs) > 0
        if logger:
            if has_browser:
                logger.info(f"已安装的浏览器引擎: {browser_dirs}")
            else:
                logger.warning(f"未在 {browsers_path} 找到浏览器引擎")

    # 如果没有找到浏览器，尝试安装
    if not has_browser:
        if logger:
            logger.info("未发现浏览器引擎，尝试安装...")

        # 先检查axel是否可用
        has_axel = shutil.which("axel") is not None
        if logger:
            if has_axel:
                logger.info("检测到axel下载加速工具")
            else:
                logger.info("未检测到axel，将使用默认下载方式")

        # 尝试使用国内镜像加速安装
        try:
            # 获取当前Python解释器路径
            python_executable = sys.executable

            # 设置环境变量
            env_vars = os.environ.copy()

            # 添加国内镜像和下载配置
            env_vars["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://npmmirror.com/mirrors/playwright"

            # 如果axel可用，配置为使用axel下载
            if has_axel:
                # 配置Playwright使用axel作为下载工具
                env_vars["PLAYWRIGHT_DOWNLOAD_COMMAND"] = "axel -a -n 10 -o {output} {url}"
                if logger:
                    logger.info("已配置使用axel加速下载，并发数10")

            # 设置安装参数
            install_cmd = [python_executable, "-m", "playwright", "install", "--force", "chromium"]

            if logger:
                logger.info(f"执行安装命令: {' '.join(install_cmd)}")
                logger.info(f"使用国内镜像: {env_vars.get('PLAYWRIGHT_DOWNLOAD_HOST')}")

            # 运行安装命令
            process = subprocess.run(
                install_cmd,
                check=True,
                env=env_vars,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300  # 5分钟超时，考虑到网络问题
            )

            # 输出安装结果
            if logger:
                if process.stdout:
                    logger.info(f"安装输出: {process.stdout}")
                if process.stderr:
                    logger.warning(f"安装警告/错误: {process.stderr}")

            # 验证安装是否成功
            if os.path.exists(browsers_path):
                # 等待2秒确保文件系统同步
                time.sleep(2)
                browser_dirs = glob.glob(os.path.join(browsers_path, "chromium*"))
                has_browser = len(browser_dirs) > 0
                if logger:
                    if has_browser:
                        logger.info(f"浏览器安装成功: {browser_dirs}")
                    else:
                        # 如果第一次安装失败，尝试使用默认方式安装
                        if "PLAYWRIGHT_DOWNLOAD_COMMAND" in env_vars:
                            logger.warning("使用axel安装失败，尝试使用默认方式安装")
                            # 移除axel配置
                            del env_vars["PLAYWRIGHT_DOWNLOAD_COMMAND"]

                            # 再次运行安装命令
                            process = subprocess.run(
                                install_cmd,
                                check=True,
                                env=env_vars,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=300  # 5分钟超时
                            )

                            # 再次验证
                            time.sleep(2)
                            browser_dirs = glob.glob(os.path.join(browsers_path, "chromium*"))
                            has_browser = len(browser_dirs) > 0
                            if has_browser:
                                logger.info(f"使用默认方式安装成功: {browser_dirs}")
                            else:
                                logger.error(f"浏览器安装失败，未找到浏览器引擎")

            return has_browser

        except Exception as e:
            if logger:
                logger.error(f"浏览器安装过程中出错: {str(e)}")
            return False

    return True

# 模块加载时尝试安装浏览器
browser_installed = ensure_browser_installed()


class BrowserManager:
    """浏览器管理器单例类"""
    _instance = None

    def __new__(cls, logger=None, config=None):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, logger=None, config=None):
        if getattr(self, '_initialized', False): return
        self.logger, self.config = logger, config
        self.browser_pool = []
        self.active_browsers = 0
        self._playwright = None
        self._initialized = False  # 确保初始化只执行一次

        # 从配置中加载设置
        config = config or {}
        self.max_concurrent_browsers = config.get("tools.browser_instances", 2)
        self.browser_timeout = config.get("tools.browser_timeout", 3) * 1000

        # 始终使用Playwright内置浏览器
        self.use_playwright_browser = True
        self.browser_path = None
        self.logger and self.logger.info('将使用Playwright自带浏览器')

        self._initialized = True

    @asynccontextmanager
    async def get_browser(self):
        """获取浏览器实例"""
        browser = None
        playwright_created = False

        try:
            # 尝试清理僵尸进程
            self._clean_zombie_processes()

            # 初始化 playwright 实例
            if self._playwright is None:
                self.logger and self.logger.info("初始化 Playwright 实例...")
                self._playwright = await async_playwright().start()
                playwright_created = True
                self.logger and self.logger.info("Playwright 实例初始化完成")

            # 创建新浏览器实例并记录
            self.active_browsers += 1
            self.logger and self.logger.info(f"创建新的浏览器实例 (当前活跃: {self.active_browsers})")

            # 启动浏览器
            browser = await self._launch_browser()
            yield browser

        except Exception as e:
            self.active_browsers = max(0, self.active_browsers - 1)
            self.logger and self.logger.error(f"获取浏览器实例失败: {str(e)}")
            raise

        finally:
            # 释放浏览器资源
            if browser:
                try:
                    self.logger and self.logger.info("正在关闭浏览器实例...")
                    await browser.close()
                    self.logger and self.logger.info("浏览器实例已关闭")
                except Exception as e:
                    self.logger and self.logger.warning(f"关闭浏览器失败: {str(e)}")
                    try:
                        # 尝试强制关闭
                        await browser.close(timeout=1000)
                    except:
                        pass

                self.active_browsers = max(0, self.active_browsers - 1)
                self.logger and self.logger.info(f"释放浏览器实例 (剩余活跃: {self.active_browsers})")

                # 如果所有浏览器实例都已关闭且是我们创建的playwright实例，则关闭playwright
                if self.active_browsers == 0 and playwright_created and self._playwright:
                    try:
                        self.logger and self.logger.info("关闭 Playwright 实例...")
                        await self._playwright.stop()
                        self._playwright = None
                        self.logger and self.logger.info("Playwright 实例已关闭")
                    except Exception as e:
                        self.logger and self.logger.warning(f"关闭 Playwright 实例失败: {str(e)}")

                # 清理可能的僵尸进程
                self._clean_zombie_processes()

    async def _launch_browser(self):
        """启动浏览器"""
        launch_options = get_browser_launch_options()

        # 检查是否在虚拟环境中运行，如果是，设置适当的环境变量
        import sys, os
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

        if in_venv:
            venv_cache = os.path.join(sys.prefix, ".cache", "ms-playwright")
            self.logger and self.logger.info(f"检测到虚拟环境，使用路径: {venv_cache}")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = venv_cache

        # 使用Playwright自带浏览器
        self.logger and self.logger.info("使用Playwright自带浏览器")

        # 检查浏览器是否已安装，如果未安装则自动安装
        try:
            return await self._playwright.chromium.launch(**launch_options)
        except Exception as e:
            error_msg = str(e)
            self.logger and self.logger.warning(f"启动Playwright浏览器失败: {error_msg}")

            if "Executable doesn't exist" in error_msg or "Please run the following command" in error_msg:
                self.logger and self.logger.warning("Playwright浏览器未正确安装，尝试重新安装...")

                # 诊断环境
                import subprocess, sys, os

                # 检查是否在虚拟环境中运行
                in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
                if in_venv:
                    self.logger and self.logger.info(f"检测到虚拟环境: {sys.prefix}")

                # 输出当前环境的PYTHONPATH和可能的Playwright缓存位置
                potential_paths = [
                    os.path.expanduser("~/.cache/ms-playwright"),
                    os.path.join(sys.prefix, ".cache/ms-playwright"),
                    os.path.join(os.path.dirname(os.path.dirname(sys.executable)), ".cache/ms-playwright")
                ]

                for path in potential_paths:
                    if os.path.exists(path):
                        self.logger and self.logger.info(f"发现Playwright缓存目录: {path}")

                try:
                    # 获取当前Python解释器路径
                    python_executable = sys.executable
                    self.logger and self.logger.info(f"使用Python解释器 {python_executable}")

                    # 检测是否需要配置特殊环境变量
                    env_vars = os.environ.copy()

                    # 如果在虚拟环境中，设置PLAYWRIGHT_BROWSERS_PATH环境变量
                    if in_venv:
                        venv_cache = os.path.join(sys.prefix, ".cache", "ms-playwright")
                        self.logger and self.logger.info(f"为虚拟环境设置浏览器缓存路径: {venv_cache}")
                        env_vars["PLAYWRIGHT_BROWSERS_PATH"] = venv_cache

                    # 强制安装最新版本的浏览器
                    self.logger and self.logger.info("开始安装Playwright浏览器...")
                    process = subprocess.run(
                        [python_executable, "-m", "playwright", "install", "--force", "chromium"], 
                        check=True,
                        env=env_vars,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    # 输出安装过程
                    if process.stdout:
                        self.logger and self.logger.info(f"安装输出: {process.stdout}")
                    if process.stderr:
                        self.logger and self.logger.warning(f"安装警告/错误: {process.stderr}")

                    self.logger and self.logger.info("Playwright浏览器安装成功")

                    # 等待一段时间，确保安装完成
                    import time
                    time.sleep(2)

                    # 重新尝试启动浏览器，传递相同的环境变量
                    self.logger and self.logger.info("重新尝试启动浏览器...")
                    # 为Playwright设置浏览器路径
                    if "PLAYWRIGHT_BROWSERS_PATH" in env_vars:
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = env_vars["PLAYWRIGHT_BROWSERS_PATH"]
                    return await self._playwright.chromium.launch(**launch_options)
                except subprocess.SubprocessError as install_error:
                    self.logger and self.logger.error(f"自动安装Playwright浏览器失败: {str(install_error)}")
                    raise
            else:
                raise

    def _clean_zombie_processes(self):
        """清理僵尸进程 - 使用Playwright自带浏览器不需要此操作"""
        # 由于我们只使用Playwright自带浏览器，不需要清理系统浏览器进程
        self.logger and self.logger.info("使用Playwright浏览器，不需要清理系统浏览器进程")


class UpstreamPlaywrightChecker(BaseChecker):
    """使用Playwright的上游版本检查器"""

    def __init__(self, logger, package_config=None, main_checker=None):
        """初始化Playwright上游检查器

        Args:
            logger: 日志模块实例
            package_config: 包配置（可选）
            main_checker: 主检查器实例（可选），用于版本比较
        """
        super().__init__(logger, package_config)
        # 不再使用共享的浏览器管理器，而是每次检查创建新的Playwright实例
        self.logger = logger
        self.package_config = package_config
        self.main_checker = main_checker  # 存储主检查器实例引用
        self.version_processor = VersionProcessor(logger)
        # 用于存储每个检查的配置
        self.config = package_config or {}

        # 添加版本结果缓存
        self.version_cache = {}
        self.cache_ttl = 3600  # 默认缓存1小时（单位：秒）
        self.cache_enabled = True

        # 如果提供了配置，从配置中读取
        if package_config:
            self.cache_ttl = package_config.get("cache.ttl", self.cache_ttl)
            self.cache_enabled = package_config.get("cache.enabled", self.cache_enabled)

        self.logger and self.logger.debug(f"初始化版本缓存: TTL={self.cache_ttl}秒, 启用状态={self.cache_enabled}")

        # 预定义版本匹配模式，避免重复定义
        # 1. 常用版本提取正则
        self.VERSION_PATTERNS = [
            r'[Vv]ersion:?\s*([0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*)',
            r'版本号?:?\s*([0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*)',
            r'v([0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*)',
            r'([0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*)'
        ]

        # 2. 本地版本格式定义
        self.LOCAL_VERSION_PATTERNS = [
            (r'([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)*)', "标准版本格式"),  # 匹配 x.y.z 或更多段的版本
            (r'([0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?)', "简化版本格式"),    # 匹配 x.y 或带后缀的版本
            (r'([vV]?[0-9]+\.[0-9]+)', "带v前缀的版本")                  # 匹配带v/V前缀的版本
        ]

        # 3. 版本提取关键词
        self.VERSION_KEYWORDS = ['version', 'Version', '版本', '版本号']

        self.logger and self.logger.debug("初始化版本匹配模式完成")

    async def check_version(self, package_name, url, version_pattern_regex=None, **kwargs):
        """使用Playwright检查上游版本 - 每次创建独立实例

        Args:
            package_name: 软件包名称
            url: 网页URL
            version_pattern_regex: 版本匹配正则表达式（可选）
            **kwargs: 额外参数，可包含：
                - version_extract_key: 版本提取关键字（可选）
                - aur_version: AUR版本号（可选），用于格式验证
                - version_pattern: 版本模式（可选），如"x.y.z"
                - no_cache: 设置为True时跳过缓存（可选）

        Returns:
            dict: 包含版本检查结果的字典
        """
        # 从kwargs中获取可选参数
        version_extract_key = kwargs.get('version_extract_key')
        aur_version = kwargs.get('aur_version')
        version_pattern = kwargs.get('version_pattern')
        no_cache = kwargs.get('no_cache', False)

        self.logger and self.logger.info(f"使用Playwright检查 {package_name} 的上游版本")
        self.logger and self.logger.debug(f"传入的版本提取关键字: {version_extract_key}")
        self.logger and self.logger.debug(f"传入的AUR版本: {aur_version}")
        self.logger and self.logger.debug(f"传入的版本模式: {version_pattern}")

        # 生成缓存键
        cache_key = f"{package_name}:{url}:{version_extract_key}:{version_pattern_regex}"
        cache_key = hashlib.md5(cache_key.encode('utf-8')).hexdigest()

        # 检查缓存
        if self.cache_enabled and not no_cache:
            cache_data = self.version_cache.get(cache_key)
            if cache_data:
                timestamp, result = cache_data
                current_time = time.time()

                # 检查缓存是否过期
                if current_time - timestamp < self.cache_ttl:
                    self.logger and self.logger.info(f"从缓存返回 {package_name} 的版本信息")
                    return result
                else:
                    self.logger and self.logger.debug(f"缓存已过期，重新获取 {package_name} 的版本")

        result = {
            "package": package_name,
            "url": url,
            "version": None,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "message": "未知错误",
            "success": False,
            "upstream_version": None
        }

        # 声明所有资源变量以便在finally块中清理
        playwright = None
        browser = None
        context = None
        page = None
        html_content = None

        try:
            # 设置合适的超时控制
            # 从配置或环境变量获取超时时间，如果没有设置则使用默认值30秒（增加默认超时）
            timeout_seconds = 30  # 增加默认超时时间

            # 如果有包特定的配置，使用它
            if hasattr(self, 'package_config') and self.package_config:
                pkg_timeout = self.package_config.get('timeout')
                if pkg_timeout and isinstance(pkg_timeout, int) and pkg_timeout > 0:
                    timeout_seconds = pkg_timeout

            self.logger and self.logger.info(f"设置检查超时: {timeout_seconds} 秒")

            async with asyncio.timeout(timeout_seconds):
                # 每次创建新的Playwright实例，确保完全隔离
                self.logger and self.logger.info(f"为 {package_name} 创建新的Playwright实例")

                # 使用模块初始化时设置的环境变量
                if browser_installed:
                    self.logger and self.logger.info("使用已初始化的Playwright浏览器")
                else:
                    # 如果初始化失败，再次尝试确保浏览器已安装
                    success = ensure_browser_installed()
                    if success:
                        self.logger and self.logger.info("已成功安装Playwright浏览器")
                    else:
                        self.logger and self.logger.warning("无法自动安装Playwright浏览器，可能会导致错误")

                # 启动Playwright
                playwright = await async_playwright().start()

                # 启动浏览器
                self.logger and self.logger.info("启动浏览器...")

                # 如果发生错误，尝试不同的启动选项
                try:
                    browser = await playwright.chromium.launch(**get_browser_launch_options())
                except Exception as e:
                    self.logger and self.logger.warning(f"使用默认选项启动失败: {str(e)}")

                    # 尝试强制安装浏览器
                    import subprocess
                    python_executable = sys.executable
                    self.logger and self.logger.info(f"尝试使用 {python_executable} 安装Playwright浏览器")

                    env_vars = os.environ.copy()
                    if in_venv:
                        env_vars["PLAYWRIGHT_BROWSERS_PATH"] = venv_cache

                    try:
                        subprocess.run(
                            [python_executable, "-m", "playwright", "install", "--force", "chromium"],
                            check=True,
                            env=env_vars
                        )
                        self.logger and self.logger.info("浏览器安装成功，重试启动")
                        browser = await playwright.chromium.launch(**get_browser_launch_options())
                    except Exception as install_error:
                        self.logger and self.logger.error(f"安装失败: {str(install_error)}")
                        raise

                # 创建浏览器上下文
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                page = await context.new_page()

                # 设置页面超时
                page.set_default_timeout(10000)  # 10秒
                page.set_default_navigation_timeout(15000)  # 15秒

                # 监听页面事件，但过滤掉资源加载错误
                def console_handler(msg):
                    # 过滤掉常见的资源加载错误
                    text = msg.text
                    if not (
                        "ERR_CONNECTION" in text or
                        "Failed to load resource" in text or
                        "404" in text
                    ):
                        self.logger and self.logger.debug(f'页面控制台: {text}')
                page.on('console', console_handler)

                # 导航到URL
                try:
                    # 使用更强大的错误处理和重试策略
                    self.logger and self.logger.info(f"开始加载页面: {url}")
                    navigation_success = False

                    for attempt in range(3):  # 增加到3次重试
                        try:
                            # 根据尝试次数采用不同策略
                            if attempt == 0:
                                # 第一次尝试: 使用标准的'domcontentloaded'
                                self.logger and self.logger.debug(f"尝试使用'domcontentloaded'加载 (尝试 {attempt+1}/3)")
                                response = await page.goto(
                                    url, 
                                    wait_until='domcontentloaded', 
                                    timeout=min(timeout_seconds * 1000 * 0.6, 20000)  # 使用较短超时
                                )
                            elif attempt == 1:
                                # 第二次尝试: 使用更基本的'commit'
                                self.logger and self.logger.debug(f"尝试使用'commit'加载 (尝试 {attempt+1}/3)")
                                response = await page.goto(
                                    url, 
                                    wait_until='commit', 
                                    timeout=min(timeout_seconds * 1000 * 0.4, 15000)  # 使用更短超时
                                )
                            else:
                                # 第三次尝试: 不等待页面事件，只确保HTTP请求完成
                                self.logger and self.logger.debug(f"尝试基本HTTP请求 (尝试 {attempt+1}/3)")
                                response = await page.goto(
                                    url, 
                                    wait_until=None,  # 不等待任何页面事件
                                    timeout=min(timeout_seconds * 1000 * 0.3, 10000)  # 使用最短超时
                                )

                            navigation_success = True
                            break
                        except Exception as nav_error:
                            self.logger and self.logger.warning(f"导航尝试 {attempt+1}/3 失败: {str(nav_error)}")
                            # 最后一次尝试失败后继续执行，尝试从任何已加载内容中提取信息
                            if attempt == 2:
                                self.logger and self.logger.warning("所有导航尝试都失败，继续处理可能的部分加载内容")

                    # 处理重定向
                    current_url = page.url
                    if current_url != url:
                        self.logger and self.logger.info(f"检测到URL重定向: {url} -> {current_url}")

                    # 更智能的等待策略，根据导航成功与否调整等待时间
                    if navigation_success:
                        # 成功导航时，使用较短的等待时间
                        wait_time = min(3000, int(timeout_seconds * 300))  # 最多3秒钟
                        self.logger and self.logger.info(f"导航成功，等待页面JavaScript加载... ({wait_time}ms)")
                        await page.wait_for_timeout(wait_time)

                        # 尝试等待页面上某些常见的版本元素，使用更短的超时
                        try:
                            await page.wait_for_selector('.version, #version, [data-version], .version-number, .current-version', 
                                                       timeout=min(2000, int(timeout_seconds * 200)))  # 最多2秒
                            self.logger and self.logger.info("找到可能的版本元素")
                        except:
                            self.logger and self.logger.info("未找到明确的版本元素，继续处理")
                    else:
                        # 导航失败时，只简单等待一小段时间
                        self.logger and self.logger.info("导航不完全成功，只短暂等待...")
                        await page.wait_for_timeout(1000)  # 只等待1秒
                        self.logger and self.logger.info("尝试从当前页面内容提取信息")

                    # 获取页面内容
                    html_content = await page.content()

                    # 只在调试模式下保存截图，节省资源
                    debug_mode = os.environ.get("DEBUG_PLAYWRIGHT", "0") == "1"
                    if debug_mode:
                        screenshot_path = f"/tmp/version_screenshot_{package_name}.png"
                        try:
                            # 只截取可见区域，使用较短的超时
                            await page.screenshot(path=screenshot_path, full_page=False, timeout=5000)
                            self.logger and self.logger.info(f"保存页面截图: {screenshot_path}")
                        except Exception as screenshot_error:
                            self.logger and self.logger.warning(f"截图失败: {str(screenshot_error)}，继续处理")
                    else:
                        self.logger and self.logger.debug("调试模式未启用，跳过截图")
                except Exception as e:
                    self.logger and self.logger.error(f"导航或获取内容失败: {str(e)}")
                    return result

                # 关闭页面和上下文，确保资源完全释放
                self.logger and self.logger.info("正在关闭页面和浏览器上下文...")
                if await self._cleanup_resources_helper(package_name, page, context):
                    self.logger and self.logger.info("页面和浏览器上下文已关闭")
                else:
                    self.logger and self.logger.warning("页面和上下文关闭可能不完整")

                # 从HTML内容中提取版本
                if html_content:
                    if version_extract_key:
                        self.logger and self.logger.info(f"传递版本提取关键字: {version_extract_key}")
                    version = await self._extract_version_from_html(html_content, version_extract_key)

                    # 设置结果
                    if version:
                        # 如果提供了AUR版本和版本模式，验证提取的版本格式是否符合要求
                        if aur_version and version_pattern and self.main_checker and hasattr(self.main_checker, "_is_version_similar"):
                            if self.main_checker._is_version_similar(version, version_pattern):
                                self.logger and self.logger.info(f"提取的版本 {version} 与版本模式 {version_pattern} 匹配")
                            else:
                                self.logger and self.logger.debug(f"提取的版本 {version} 与版本模式 {version_pattern} 不匹配，但仍然使用")

                        result["version"] = version
                        result["status"] = "success"
                        result["message"] = "版本检查成功"
                        result["success"] = True
                        result["upstream_version"] = version
                    else:
                        result["message"] = "无法提取版本信息"

        except asyncio.TimeoutError:
            result["message"] = f"检查 {package_name} 超时"
            self.logger and self.logger.warning(result["message"])

            # 尝试从部分加载的页面中提取信息
            if html_content:
                self.logger and self.logger.info("尝试从部分加载的页面中提取版本信息...")
                try:
                    version = await self._extract_version_from_html(html_content, version_extract_key)
                    if version:
                        result["version"] = version
                        result["status"] = "partial_success"
                        result["message"] = "版本检查部分成功（超时但提取到版本）"
                        result["success"] = True
                        result["upstream_version"] = version
                        self.logger and self.logger.info(f"从部分加载的页面中提取到版本: {version}")
                except Exception as ex:
                    self.logger and self.logger.debug(f"从部分加载页面提取版本失败: {str(ex)}")

        except Exception as e:
            result["message"] = f"版本检查出错: {str(e)}"
            self.logger and self.logger.error(result["message"])

            # 记录更详细的错误信息以便诊断
            import traceback
            self.logger and self.logger.debug(f"错误详情: {traceback.format_exc()}")
        finally:
            # 使用统一的资源清理辅助方法
            self.logger and self.logger.info(f"正在清理 {package_name} 的所有浏览器资源...")
            if await self._cleanup_resources_helper(package_name, page, context, browser, playwright):
                self.logger and self.logger.info(f"{package_name} 的浏览器资源已清理完毕")
            else:
                self.logger and self.logger.warning(f"{package_name} 的资源清理可能不完整")

        # 如果结果有效，更新缓存
        if self.cache_enabled and result.get("success"):
            self.logger and self.logger.debug(f"缓存 {package_name} 的版本结果")
            self.version_cache[cache_key] = (time.time(), result)

        return result

    async def _cleanup_resources_helper(self, package_name, page=None, context=None, browser=None, playwright=None):
        """统一的资源清理辅助方法，避免代码重复"""
        try:
            # 按照创建的相反顺序关闭资源
            if page:
                try:
                    await page.close()
                except Exception as e:
                    self.logger and self.logger.debug(f"关闭页面失败: {e}")
                    # 尝试再次关闭
                    try:
                        await page.close()
                    except:
                        pass

            if context:
                try:
                    await context.close()
                except Exception as e:
                    self.logger and self.logger.debug(f"关闭上下文失败: {e}")
                    # 尝试再次关闭
                    try:
                        await context.close()
                    except:
                        pass

            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    self.logger and self.logger.debug(f"关闭浏览器失败: {e}")

            if playwright:
                try:
                    await playwright.stop()
                except Exception as e:
                    self.logger and self.logger.debug(f"关闭Playwright失败: {e}")

            # 强制触发垃圾回收
            import gc
            gc.collect()

            return True
        except Exception as e:
            self.logger and self.logger.error(f"清理资源时出错: {str(e)}")
            return False
    async def _extract_version_from_html(self, html_content, version_extract_key=None):
        """从HTML内容中提取版本

        优化版本：直接从字符串解析HTML，不再使用临时文件

        Args:
            html_content: HTML内容字符串
            version_extract_key: 版本提取关键字（可选）

        Returns:
            str: 提取的版本号，如果未找到则返回None
        """
        try:
            # 处理提取键
            if not version_extract_key:
                self.logger and self.logger.info("没有提供版本提取键，尝试使用通用方法提取版本")
                version_extract_key = r"version|Version|版本|v\d+\.\d+\.\d+"
            else:
                self.logger and self.logger.info(f"使用提供的版本提取键: {version_extract_key}")

            # 直接从字符串解析HTML，避免不必要的磁盘I/O
            try:
                # 优先使用lxml解析器，速度更快，功能更丰富
                soup = BeautifulSoup(html_content, 'lxml')
                self.logger and self.logger.debug("使用lxml解析器解析HTML")
            except Exception as e:
                # 如果lxml不可用，回退到标准html解析器
                self.logger and self.logger.debug(f"lxml解析器不可用，回退到标准解析器: {str(e)}")
                soup = BeautifulSoup(html_content, 'html.parser')

            # 提取版本号
            content = None

            # 1. CSS选择器方式
            if version_extract_key and (version_extract_key.startswith('.') or version_extract_key.startswith('#')):
                elements = soup.select(version_extract_key)
                content = elements[0].text.strip() if elements else None
            else:
                # 2. 正则表达式方式
                try:
                    # 使用预定义的版本模式
                    version_patterns = self.VERSION_PATTERNS

                    html_str = str(soup)
                    # 先尝试预定义模式
                    for pattern in version_patterns:
                        match = re.search(pattern, html_str)
                        if match:
                            content = match.group(1)
                            self.logger and self.logger.info(f"使用模式 '{pattern}' 找到版本: {content}")
                            break

                    # 再尝试提取键，这是最优先的提取方式
                    if version_extract_key and version_extract_key not in ["version", "Version", "版本", r"v\d+\.\d+\.\d+"]:
                        # 优先尝试与版本号模式组合
                        try:
                            # 组合使用版本提取键和版本号模式
                            combined_pattern = fr"{version_extract_key}.*?([0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*)"
                            match = re.search(combined_pattern, html_str, re.DOTALL)
                            if match:
                                content = match.group(1)
                                self.logger and self.logger.info(f"使用组合提取键找到版本: {content}")

                            # 如果没找到标准格式版本号，尝试更宽松的格式
                            if not content:
                                combined_pattern = fr"{version_extract_key}.*?([0-9]+\.[0-9]+[a-zA-Z0-9.-]*)"
                                match = re.search(combined_pattern, html_str, re.DOTALL)
                                if match:
                                    content = match.group(1)
                                    self.logger and self.logger.info(f"使用组合提取键找到简化版本: {content}")

                            # 只有在组合模式都失败时，才尝试直接使用提取键
                            if not content:
                                match = re.search(version_extract_key, html_str)
                                if match and re.search(r'[0-9]+\.[0-9]+', match.group(0)):
                                    content = match.group(1) if match.groups() else match.group(0)
                                    self.logger and self.logger.info(f"使用提取键直接匹配找到版本: {content}")
                        except Exception as e:
                            self.logger and self.logger.warning(f"使用提取键匹配失败: {str(e)}")
                except Exception as e:
                    self.logger and self.logger.warning(f"正则匹配失败: {str(e)}")

                # 3. 关键词搜索方式
                if not content:
                    try:
                        for keyword in self.VERSION_KEYWORDS:
                            elements = soup.find_all(string=lambda text: text and keyword in text)
                            if elements:
                                text = elements[0].strip()
                                self.logger and self.logger.info(f"找到包含关键词'{keyword}'的元素: {text}")

                                # 从文本中提取版本号
                                version_match = re.search(r'([0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*)', text)
                                if version_match:
                                    content = version_match.group(1)
                                    self.logger and self.logger.info(f"从元素文本中提取版本: {content}")
                                    break
                    except Exception as e:
                        self.logger and self.logger.warning(f"查找版本元素失败: {str(e)}")

            # 清理并返回版本
            if content:
                # 优先使用main_checker中的版本模式（如果可用）
                if self.main_checker and hasattr(self.main_checker, "version_patterns"):
                    self.logger and self.logger.info("使用main_checker的版本模式")
                    main_version_patterns = self.main_checker.version_patterns

                    # 尝试使用main_checker的版本模式匹配
                    for pattern, pattern_name, _, extract_regex in main_version_patterns:
                        version_match = re.search(extract_regex, content)
                        if version_match:
                            version = version_match.group(1)
                            self.logger and self.logger.info(f"使用main_checker的{pattern_name}模式提取到版本: {version}")
                            return self.version_processor.clean_version(version)

                # 使用预定义的本地版本格式
                version_patterns = self.LOCAL_VERSION_PATTERNS

                # 遍历本地模式
                for pattern, desc in version_patterns:
                    version_match = re.search(pattern, content)
                    if version_match and (version_match.group(1) != content or desc == "标准版本格式"):
                        version = version_match.group(1)
                        self.logger and self.logger.info(f"使用本地{desc}提取到版本: {version}")
                        return self.version_processor.clean_version(version)

                # 如果所有模式都失败，则直接返回清理后的内容
                self.logger and self.logger.info(f"使用原始内容作为版本: {content}")
                return self.version_processor.clean_version(content)

            return None
        except Exception as e:
            self.logger and self.logger.error(f"提取版本失败: {str(e)}")
            return None
        finally:
            # 不再需要临时文件清理
            pass

