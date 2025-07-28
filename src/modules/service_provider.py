# -*- coding: utf-8 -*-
"""
服务提供者模块，负责初始化和注册核心服务
"""
from .dependency_container import container, DependencyContainer
from .logger import LoggerModule
from .config import ConfigModule
from .database import DatabaseModule
from .main_checker import MainCheckerModule
from .aur_checker import AurCheckerModule
from .scheduler import SchedulerModule
from .version_processor import VersionProcessor
from .result_processor import VersionResultProcessor
from .http_client import HttpClient

class ServiceProvider:
    """服务提供者类，负责初始化和注册所有核心服务"""

    @staticmethod
    def register_core_services(container: DependencyContainer, **kwargs):
        """注册核心服务

        Args:
            container: 依赖容器
            **kwargs: 其他参数，可包含:
                config_path: 配置文件路径
        """
        # 注册日志服务
        logger = LoggerModule("main")
        container.register("logger", logger)

        # 注册配置服务，如果提供了配置路径则使用它
        config_path = kwargs.get("config_path")
        config_args = {"config_path": config_path} if config_path else {}

        def config_factory(container):
            logger = container.get("logger")
            return ConfigModule(logger, **config_args)

        container.register_factory("config", config_factory)

        # 注册数据库服务
        def db_factory(container):
            logger = container.get("logger")
            config = container.get("config")
            return DatabaseModule(logger, config)

        container.register_factory("db", db_factory)

        # 注册版本处理器
        def version_processor_factory(container):
            logger = container.get("logger")
            return VersionProcessor(logger)

        container.register_factory("version_processor", version_processor_factory)

        # 注册结果处理器
        def result_processor_factory(container):
            logger = container.get("logger")
            return VersionResultProcessor(logger)

        container.register_factory("result_processor", result_processor_factory)

        # 注册AUR检查器
        def aur_checker_factory(container):
            logger = container.get("logger")
            db = container.get("db")
            return AurCheckerModule(logger, db)

        container.register_factory("aur_checker", aur_checker_factory)

        # 注册主检查器
        def main_checker_factory(container):
            logger = container.get("logger")
            db = container.get("db")
            config = container.get("config")
            return MainCheckerModule(logger, db, config)

        container.register_factory("main_checker", main_checker_factory)

        # 注册定时器
        def scheduler_factory(container):
            logger = container.get("logger")
            config = container.get("config")
            return SchedulerModule(logger, config)

        container.register_factory("scheduler", scheduler_factory)

        # 注册HTTP客户端
        def http_client_factory(container):
            logger = container.get("logger")
            config = container.get("config")

            # 创建HTTP客户端实例
            http_client = HttpClient.get_instance(logger)

            # 从配置中获取设置
            http_timeout = config.get("upstream.timeout", 30)
            http_user_agent = config.get("upstream.user_agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            http_conn_limit = config.get("upstream.conn_limit", 100)
            http_conn_limit_per_host = config.get("upstream.conn_limit_per_host", 10)

            # 配置HTTP客户端
            http_client.configure(
                timeout=http_timeout, 
                headers={"User-Agent": http_user_agent},
                conn_limit=http_conn_limit,
                conn_limit_per_host=http_conn_limit_per_host
            )

            return http_client

        container.register_factory("http_client", http_client_factory)

    @staticmethod
    def bootstrap(**kwargs):
        """初始化所有服务

        Args:
            **kwargs: 其他参数，将传递给register_core_services

        Returns:
            DependencyContainer: 已初始化的依赖容器
        """
        ServiceProvider.register_core_services(container, **kwargs)
        return container
