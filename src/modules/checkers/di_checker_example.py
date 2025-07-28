# -*- coding: utf-8 -*-
"""
依赖注入检查器示例，展示如何使用依赖容器
"""
from ..dependency_container import container, DependencyContainer
from .base_checker import BaseChecker

class DICheckerExample(BaseChecker):
    """使用依赖注入的检查器示例类

    这个类展示了如何使用依赖注入容器来获取所需的依赖，
    而不是通过构造函数参数传递。
    """

    def __init__(self, service_container=None):
        """初始化依赖注入检查器示例

        Args:
            service_container: 依赖容器实例（可选），默认使用全局容器
        """
        # 使用提供的容器或全局容器
        self.container = service_container or container

        # 从容器获取依赖
        self.logger = self.container.get("logger")
        self.config = self.container.get("config") if self.container.has("config") else None

        # 调用父类构造函数
        super().__init__(self.logger, self.config)

        self.logger.debug("依赖注入检查器示例初始化")

        # 可以按需获取其他依赖
        if self.container.has("version_processor"):
            self.version_processor = self.container.get("version_processor")

        # 延迟加载示例
        self._db = None
        self._main_checker = None

    @property
    def db(self):
        """数据库属性，懒加载示例"""
        if self._db is None and self.container.has("db"):
            self._db = self.container.get("db")
        return self._db

    @property
    def main_checker(self):
        """主检查器属性，懒加载示例"""
        if self._main_checker is None and self.container.has("main_checker"):
            self._main_checker = self.container.get("main_checker")
        return self._main_checker

    # 使用容器的inject装饰器自动注入依赖
    @container.inject
    def process_with_injection(self, package_name, result_processor=None):
        """使用自动注入处理结果

        Args:
            package_name: 包名
            result_processor: 结果处理器，会自动从容器注入（如果未提供）
        """
        self.logger.debug(f"处理包: {package_name}")
        if result_processor:
            return result_processor.process_result({"name": package_name, "status": "processed"})
        return {"name": package_name, "status": "processed without result processor"}

    async def check_version(self, package_name, url, version_extract_key=None):
        """实现抽象方法check_version

        Args:
            package_name: 软件包名称
            url: 上游URL
            version_extract_key: 版本提取键（可选）

        Returns:
            dict: 包含版本信息的字典
        """
        self.logger.info(f"使用依赖注入检查版本: {package_name}")

        # 这只是一个示例实现
        return {
            "name": package_name,
            "success": True,
            "version": "1.0.0",
            "message": "这是依赖注入示例检查器"
        }
