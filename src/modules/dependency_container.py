# -*- coding: utf-8 -*-
"""
依赖注入容器，用于解耦组件之间的依赖关系
实现了服务注册、工厂方法、懒加载和依赖解析功能
"""
from typing import Any, Callable, Dict, Optional, List, Type, Union, get_type_hints
import inspect

class ServiceNotFoundError(Exception):
    """服务未找到错误"""
    pass

class CircularDependencyError(Exception):
    """循环依赖错误"""
    pass

class DependencyContainer:
    """增强的依赖注入容器，支持工厂方法和懒加载"""

    def __init__(self):
        """初始化依赖容器"""
        self._services = {}  # 实例化的服务
        self._factories = {}  # 工厂函数
        self._singleton_factories = {}  # 单例工厂函数（懒加载）
        self._building = set()  # 正在构建中的服务，用于检测循环依赖

    def register(self, service_name: str, instance: Any) -> None:
        """注册一个服务实例

        Args:
            service_name: 服务名称
            instance: 服务实例
        """
        self._services[service_name] = instance

    def register_factory(self, service_name: str, factory: Callable, singleton: bool = True) -> None:
        """注册一个工厂函数，用于创建服务实例

        Args:
            service_name: 服务名称
            factory: 工厂函数，接受container作为参数
            singleton: 是否是单例模式，True表示只创建一次实例
        """
        if singleton:
            self._singleton_factories[service_name] = factory
        else:
            self._factories[service_name] = factory

    def register_class(self, service_name: str, cls: Type, singleton: bool = True) -> None:
        """注册一个类，容器会自动解析其依赖并创建实例

        Args:
            service_name: 服务名称
            cls: 要注册的类
            singleton: 是否是单例模式，True表示只创建一次实例
        """
        def factory(container):
            # 获取构造函数的参数
            init_signature = inspect.signature(cls.__init__)
            parameters = list(init_signature.parameters.values())[1:]  # 排除self参数

            # 准备构造函数的参数
            kwargs = {}
            for param in parameters:
                # 从容器中获取参数值
                if param.name in container._services:
                    kwargs[param.name] = container._services[param.name]
                elif param.default is not param.empty:
                    # 有默认值的参数，不做处理，使用默认值
                    pass
                else:
                    # 尝试根据参数名称从容器获取服务
                    if container.has(param.name):
                        kwargs[param.name] = container.get(param.name)

            # 创建实例
            return cls(**kwargs)

        self.register_factory(service_name, factory, singleton)

    async def get(self, service_name: str) -> Any:
        """获取一个服务实例

        Args:
            service_name: 服务名称

        Returns:
            服务实例

        Raises:
            ServiceNotFoundError: 服务未找到时抛出
            CircularDependencyError: 检测到循环依赖时抛出
        """
        # 检测循环依赖
        if service_name in self._building:
            self._building.clear()  # 重置
            raise CircularDependencyError(f"检测到循环依赖: {service_name}")

        # 如果服务已实例化，直接返回
        if service_name in self._services:
            return self._services[service_name]

        # 如果有单例工厂，使用工厂创建实例并缓存
        if service_name in self._singleton_factories:
            self._building.add(service_name)
            factory = self._singleton_factories[service_name]
            
            # 检查工厂函数是否是异步的
            if inspect.iscoroutinefunction(factory):
                instance = await factory(self)
            else:
                instance = factory(self)
                
            self._building.remove(service_name)
            self._services[service_name] = instance
            return instance

        # 如果有普通工厂，创建新实例但不缓存
        if service_name in self._factories:
            factory = self._factories[service_name]
            
            # 检查工厂函数是否是异步的
            if inspect.iscoroutinefunction(factory):
                return await factory(self)
            else:
                return factory(self)

        raise ServiceNotFoundError(f"服务未找到: {service_name}")

    def has(self, service_name: str) -> bool:
        """检查是否存在指定服务

        Args:
            service_name: 服务名称

        Returns:
            bool: 是否存在
        """
        return (service_name in self._services or 
                service_name in self._factories or 
                service_name in self._singleton_factories)

    def inject(self, func: Callable) -> Callable:
        """装饰器，用于自动注入依赖到函数

        Args:
            func: 要注入依赖的函数

        Returns:
            装饰后的函数
        """
        signature = inspect.signature(func)
        
        # 检查函数是否是异步的
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            async def async_wrapper(*args, **kwargs):
                # 准备要注入的参数
                injected_kwargs = kwargs.copy()

                # 获取还未提供的参数
                provided_params = set(kwargs.keys())
                for i, param_name in enumerate(signature.parameters):
                    if i < len(args):  # 已经通过位置参数提供
                        provided_params.add(param_name)

                # 注入未提供的参数
                for param_name, param in signature.parameters.items():
                    if param_name not in provided_params and self.has(param_name):
                        injected_kwargs[param_name] = await self.get(param_name)

                # 调用原始函数
                return await func(*args, **injected_kwargs)

            return async_wrapper
        else:
            def wrapper(*args, **kwargs):
                # 准备要注入的参数
                injected_kwargs = kwargs.copy()

                # 获取还未提供的参数
                provided_params = set(kwargs.keys())
                for i, param_name in enumerate(signature.parameters):
                    if i < len(args):  # 已经通过位置参数提供
                        provided_params.add(param_name)

                # 注入未提供的参数 - 对于同步函数，我们不能使用异步的get方法
                # 只能注入已经实例化的服务
                for param_name, param in signature.parameters.items():
                    if param_name not in provided_params and self.has(param_name):
                        if param_name in self._services:  # 只注入已实例化的服务
                            injected_kwargs[param_name] = self._services[param_name]

                # 调用原始函数
                return func(*args, **injected_kwargs)

            return wrapper

# 全局依赖容器实例
container = DependencyContainer()
