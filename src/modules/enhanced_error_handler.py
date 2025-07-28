# -*- coding: utf-8 -*-
"""
增强版错误处理工具模块，提供统一的错误处理、分类、监控和恢复机制
"""
import functools
import traceback
import time
import asyncio
import sys
import inspect
from enum import Enum
from typing import Any, Callable, TypeVar, cast, Optional, Dict, List, Union, Type

# 类型变量，表示任何类型的函数
F = TypeVar('F', bound=Callable[..., Any])

# 错误严重程度分类
class ErrorSeverity(Enum):
    """错误严重程度枚举"""
    CRITICAL = 0    # 致命错误，不应尝试重试
    ERROR = 1       # 一般错误，可以尝试重试
    WARNING = 2     # 警告，可能影响功能但不致命
    RECOVERABLE = 3 # 可恢复的错误，重试很可能成功


class ErrorCategory(Enum):
    """错误分类枚举"""
    NETWORK = 0      # 网络相关错误
    IO = 1           # 文件I/O错误
    API = 2          # API错误
    DATABASE = 3     # 数据库错误
    PARSING = 4      # 解析错误
    VALIDATION = 5   # 验证错误
    TIMEOUT = 6      # 超时错误
    AUTHENTICATION = 7  # 认证错误
    UNKNOWN = 99     # 未知错误类型


# 错误信息记录
class ErrorRecord:
    """错误记录类，用于存储和分析错误信息"""

    def __init__(self, exception: Exception, function_name: str, 
                 args: tuple, kwargs: dict,
                 severity: ErrorSeverity = None, 
                 category: ErrorCategory = None):
        self.timestamp = time.time()
        self.exception = exception
        self.function_name = function_name
        self.traceback = traceback.format_exc()
        self.args = args
        self.kwargs = kwargs
        self.severity = severity or self._determine_severity(exception)
        self.category = category or self._determine_category(exception)
        self.retry_count = 0
        self.resolved = False

    def _determine_severity(self, exception: Exception) -> ErrorSeverity:
        """根据异常类型确定严重程度"""
        # 网络错误通常可以重试
        if any(net_err in str(type(exception)) for net_err in 
               ['ConnectionError', 'Timeout', 'HTTPError']):
            return ErrorSeverity.RECOVERABLE

        # 文件不存在通常是致命错误
        if 'FileNotFoundError' in str(type(exception)):
            return ErrorSeverity.ERROR

        # 默认为一般错误
        return ErrorSeverity.ERROR

    def _determine_category(self, exception: Exception) -> ErrorCategory:
        """根据异常类型确定错误分类"""
        exception_type = str(type(exception))

        if any(net_err in exception_type for net_err in 
               ['ConnectionError', 'ConnectionRefused', 'HTTPError']):
            return ErrorCategory.NETWORK

        if any(timeout_err in exception_type for timeout_err in 
               ['Timeout', 'TimeoutError']):
            return ErrorCategory.TIMEOUT

        if any(io_err in exception_type for io_err in 
               ['IOError', 'FileNotFoundError', 'PermissionError']):
            return ErrorCategory.IO

        if 'asyncio.exceptions' in exception_type:
            return ErrorCategory.NETWORK if 'Timeout' in exception_type else ErrorCategory.UNKNOWN

        if any(db_err in exception_type for db_err in 
               ['DatabaseError', 'SQLError', 'SQLAlchemyError']):
            return ErrorCategory.DATABASE

        return ErrorCategory.UNKNOWN

    def should_retry(self, max_retries: int) -> bool:
        """判断是否应该重试"""
        # 致命错误不重试
        if self.severity == ErrorSeverity.CRITICAL:
            return False

        # 已达到最大重试次数
        if self.retry_count >= max_retries:
            return False

        # 根据错误类别决定是否重试
        if self.category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT, 
                            ErrorCategory.DATABASE, ErrorCategory.API]:
            return True

        # 默认情况下，ERROR和RECOVERABLE级别的错误可以重试
        return self.severity in [ErrorSeverity.ERROR, ErrorSeverity.RECOVERABLE]

    def get_retry_delay(self, base_delay: float, max_delay: float = 60.0) -> float:
        """使用指数退避算法计算重试延迟时间"""
        # 指数退避: base_delay * 2^retry_count，但不超过max_delay
        delay = min(base_delay * (2 ** self.retry_count), max_delay)

        # 对于网络错误，添加一点随机抖动避免同时重试
        if self.category == ErrorCategory.NETWORK:
            import random
            delay = delay * (0.5 + random.random())

        return delay

    def increment_retry(self):
        """增加重试计数"""
        self.retry_count += 1

    def mark_as_resolved(self):
        """标记错误已解决"""
        self.resolved = True

    def to_dict(self) -> Dict:
        """转换为字典表示"""
        return {
            'timestamp': self.timestamp,
            'exception': str(self.exception),
            'exception_type': type(self.exception).__name__,
            'function': self.function_name,
            'severity': self.severity.name if self.severity else None,
            'category': self.category.name if self.category else None,
            'retry_count': self.retry_count,
            'resolved': self.resolved,
            'traceback': self.traceback
        }


# 全局错误记录器
class ErrorRegistry:
    """错误注册表，用于全局跟踪和分析错误"""

    _instance = None

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.errors: List[ErrorRecord] = []
        self.max_records = 1000  # 最大记录数，避免内存泄漏

    def register_error(self, error_record: ErrorRecord):
        """注册一个错误记录"""
        self.errors.append(error_record)

        # 如果超过最大记录数，移除最老的记录
        if len(self.errors) > self.max_records:
            self.errors = self.errors[-self.max_records:]

    def get_errors_by_category(self, category: ErrorCategory) -> List[ErrorRecord]:
        """根据分类获取错误记录"""
        return [err for err in self.errors if err.category == category]

    def get_errors_by_severity(self, severity: ErrorSeverity) -> List[ErrorRecord]:
        """根据严重程度获取错误记录"""
        return [err for err in self.errors if err.severity == severity]

    def get_recent_errors(self, count: int = 10) -> List[ErrorRecord]:
        """获取最近的错误记录"""
        return self.errors[-count:] if self.errors else []

    def get_error_statistics(self) -> Dict:
        """获取错误统计信息"""
        stats = {
            'total_errors': len(self.errors),
            'by_category': {},
            'by_severity': {},
            'resolved_count': sum(1 for err in self.errors if err.resolved),
            'retry_counts': {}
        }

        # 按分类统计
        for category in ErrorCategory:
            count = sum(1 for err in self.errors if err.category == category)
            if count > 0:
                stats['by_category'][category.name] = count

        # 按严重程度统计
        for severity in ErrorSeverity:
            count = sum(1 for err in self.errors if err.severity == severity)
            if count > 0:
                stats['by_severity'][severity.name] = count

        # 按重试次数统计
        for retry in range(10):  # 假设最多统计到9次重试
            count = sum(1 for err in self.errors if err.retry_count == retry)
            if count > 0:
                stats['retry_counts'][retry] = count

        return stats

    def clear_resolved(self):
        """清除已解决的错误记录"""
        self.errors = [err for err in self.errors if not err.resolved]

    def clear_all(self):
        """清除所有错误记录"""
        self.errors = []


# 增强的错误处理装饰器
def error_handler(
    logger=None,
    default_return=None,
    show_traceback=True,
    retry_count=0,
    retry_delay=1.0,
    max_retry_delay=60.0,
    exponential_backoff=True,
    error_registry=None,
    error_callback=None,
    specific_exceptions: List[Type[Exception]] = None,
    report_error: bool = True
) -> Callable[[F], F]:
    """增强的统一错误处理装饰器

    Args:
        logger: 日志记录器对象，需要有error方法
        default_return: 发生错误时的默认返回值
        show_traceback: 是否显示完整的堆栈跟踪
        retry_count: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        max_retry_delay: 最大重试延迟（秒）
        exponential_backoff: 是否使用指数退避策略
        error_registry: 错误注册表实例，如果为None则使用全局实例
        error_callback: 错误发生时的回调函数，接收ErrorRecord作为参数
        specific_exceptions: 指定要捕获的异常类型列表，如果为None则捕获所有异常
        report_error: 是否向全局错误注册表报告错误

    Returns:
        装饰后的函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 获取错误注册表
            registry = error_registry or ErrorRegistry.get_instance()

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 如果指定了特定异常类型且当前异常不在其中，则重新抛出
                if specific_exceptions and not any(isinstance(e, exc) for exc in specific_exceptions):
                    raise

                # 创建错误记录
                error_record = ErrorRecord(
                    exception=e,
                    function_name=func.__name__,
                    args=args,
                    kwargs=kwargs
                )

                # 记录到错误注册表
                if report_error:
                    registry.register_error(error_record)

                # 记录日志
                error_message = f"{func.__name__} 执行出错: {str(e)}"
                if logger:
                    if show_traceback:
                        logger.error(f"{error_message}
{traceback.format_exc()}")
                    else:
                        logger.error(error_message)

                # 调用错误回调函数
                if error_callback:
                    try:
                        error_callback(error_record)
                    except Exception as callback_err:
                        if logger:
                            logger.error(f"错误回调函数执行失败: {str(callback_err)}")

                # 尝试重试
                tries = 0
                while tries < retry_count and error_record.should_retry(retry_count):
                    tries += 1
                    error_record.increment_retry()

                    # 计算重试延迟
                    if exponential_backoff:
                        current_delay = error_record.get_retry_delay(retry_delay, max_retry_delay)
                    else:
                        current_delay = retry_delay

                    if logger:
                        logger.info(f"将在 {current_delay:.2f} 秒后进行第 {tries} 次重试")

                    if current_delay > 0:
                        time.sleep(current_delay)

                    try:
                        result = func(*args, **kwargs)
                        # 重试成功，标记为已解决
                        error_record.mark_as_resolved()
                        return result
                    except Exception as retry_error:
                        # 更新错误记录
                        error_record.exception = retry_error
                        error_record.traceback = traceback.format_exc()

                        if logger:
                            logger.error(f"第 {tries} 次重试失败: {str(retry_error)}")

                # 所有重试都失败，返回默认值
                return default_return

        return cast(F, wrapper)

    return decorator


# 异步版错误处理装饰器
def async_error_handler(
    logger=None,
    default_return=None,
    show_traceback=True,
    retry_count=0,
    retry_delay=1.0,
    max_retry_delay=60.0,
    exponential_backoff=True,
    error_registry=None,
    error_callback=None,
    specific_exceptions: List[Type[Exception]] = None,
    report_error: bool = True
) -> Callable[[F], F]:
    """增强的异步函数错误处理装饰器

    Args:
        logger: 日志记录器对象，需要有error方法
        default_return: 发生错误时的默认返回值
        show_traceback: 是否显示完整的堆栈跟踪
        retry_count: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        max_retry_delay: 最大重试延迟（秒）
        exponential_backoff: 是否使用指数退避策略
        error_registry: 错误注册表实例，如果为None则使用全局实例
        error_callback: 错误发生时的回调函数，接收ErrorRecord作为参数
                specific_exceptions: 指定要捕获的异常类型列表，如果为None则捕获所有异常
        report_error: 是否向全局错误注册表报告错误

    Returns:
        装饰后的异步函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 获取错误注册表
            registry = error_registry or ErrorRegistry.get_instance()

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 如果指定了特定异常类型且当前异常不在其中，则重新抛出
                if specific_exceptions and not any(isinstance(e, exc) for exc in specific_exceptions):
                    raise

                # 创建错误记录
                error_record = ErrorRecord(
                    exception=e,
                    function_name=func.__name__,
                    args=args,
                    kwargs=kwargs
                )

                # 记录到错误注册表
                if report_error:
                    registry.register_error(error_record)

                # 记录日志
                error_message = f"{func.__name__} 执行出错: {str(e)}"
                if logger:
                    if show_traceback:
                        logger.error(f"{error_message}
{traceback.format_exc()}")
                    else:
                        logger.error(error_message)

                # 调用错误回调函数
                if error_callback:
                    try:
                        if asyncio.iscoroutinefunction(error_callback):
                            await error_callback(error_record)
                        else:
                            error_callback(error_record)
                    except Exception as callback_err:
                        if logger:
                            logger.error(f"错误回调函数执行失败: {str(callback_err)}")

                # 尝试重试
                tries = 0
                while tries < retry_count and error_record.should_retry(retry_count):
                    tries += 1
                    error_record.increment_retry()

                    # 计算重试延迟
                    if exponential_backoff:
                        current_delay = error_record.get_retry_delay(retry_delay, max_retry_delay)
                    else:
                        current_delay = retry_delay

                    if logger:
                        logger.info(f"将在 {current_delay:.2f} 秒后进行第 {tries} 次重试")

                    if current_delay > 0:
                        await asyncio.sleep(current_delay)

                    try:
                        result = await func(*args, **kwargs)
                        # 重试成功，标记为已解决
                        error_record.mark_as_resolved()
                        return result
                    except Exception as retry_error:
                        # 更新错误记录
                        error_record.exception = retry_error
                        error_record.traceback = traceback.format_exc()

                        if logger:
                            logger.error(f"第 {tries} 次重试失败: {str(retry_error)}")

                # 所有重试都失败，返回默认值
                return default_return

        return cast(F, wrapper)

    return decorator


# 为I/O操作专门设计的错误处理装饰器
def io_error_handler(
    logger=None,
    default_return=None,
    retry_count=3,
    retry_delay=1.0,
    create_dirs=False
) -> Callable[[F], F]:
    """专为I/O操作设计的错误处理装饰器

    Args:
        logger: 日志记录器对象
        default_return: 发生错误时的默认返回值
        retry_count: 重试次数
        retry_delay: 重试延迟（秒）
        create_dirs: 如果为True，在FileNotFoundError时尝试创建目录

    Returns:
        装饰后的函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(retry_count + 1):
                try:
                    return func(*args, **kwargs)
                except FileNotFoundError as e:
                    if create_dirs and attempt == 0:
                        # 尝试创建目录
                        try:
                            import os
                            # 找出可能的路径参数
                            path = None
                            for arg in args:
                                if isinstance(arg, str) and os.path.sep in arg:
                                    path = os.path.dirname(arg)
                                    break

                            if not path:
                                for k, v in kwargs.items():
                                    if isinstance(v, str) and os.path.sep in v and any(key in k.lower() for key in ['path', 'file', 'dir']):
                                        path = os.path.dirname(v)
                                        break

                            if path:
                                if logger:
                                    logger.info(f"尝试创建目录: {path}")
                                os.makedirs(path, exist_ok=True)
                                # 立即重试，不计入尝试次数
                                continue
                        except Exception as dir_err:
                            if logger:
                                logger.error(f"创建目录失败: {str(dir_err)}")

                    # 记录错误
                    if logger:
                        logger.error(f"I/O操作失败 ({attempt+1}/{retry_count+1}): {str(e)}")

                    # 最后一次尝试失败
                    if attempt >= retry_count:
                        return default_return

                    # 等待后重试
                    time.sleep(retry_delay)

                except (IOError, PermissionError) as e:
                    if logger:
                        logger.error(f"I/O操作失败 ({attempt+1}/{retry_count+1}): {str(e)}")

                    # 最后一次尝试失败
                    if attempt >= retry_count:
                        return default_return

                    # 等待后重试
                    time.sleep(retry_delay * (2 if attempt > 0 else 1))  # 第二次及以后延迟加倍

            # 不应该到达这里
            return default_return

        return cast(F, wrapper)

    return decorator


# 异步版I/O操作错误处理装饰器
async def async_io_error_handler(
    logger=None,
    default_return=None,
    retry_count=3,
    retry_delay=1.0,
    create_dirs=False
) -> Callable[[F], F]:
    """专为异步I/O操作设计的错误处理装饰器

    Args:
        logger: 日志记录器对象
        default_return: 发生错误时的默认返回值
        retry_count: 重试次数
        retry_delay: 重试延迟（秒）
        create_dirs: 如果为True，在FileNotFoundError时尝试创建目录

    Returns:
        装饰后的异步函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(retry_count + 1):
                try:
                    return await func(*args, **kwargs)
                except FileNotFoundError as e:
                    if create_dirs and attempt == 0:
                        # 尝试创建目录
                        try:
                            import os
                            # 找出可能的路径参数
                            path = None
                            for arg in args:
                                if isinstance(arg, str) and os.path.sep in arg:
                                    path = os.path.dirname(arg)
                                    break

                            if not path:
                                for k, v in kwargs.items():
                                    if isinstance(v, str) and os.path.sep in v and any(key in k.lower() for key in ['path', 'file', 'dir']):
                                        path = os.path.dirname(v)
                                        break

                            if path:
                                if logger:
                                    logger.info(f"尝试创建目录: {path}")
                                os.makedirs(path, exist_ok=True)
                                # 立即重试，不计入尝试次数
                                continue
                        except Exception as dir_err:
                            if logger:
                                logger.error(f"创建目录失败: {str(dir_err)}")

                    # 记录错误
                    if logger:
                        logger.error(f"异步I/O操作失败 ({attempt+1}/{retry_count+1}): {str(e)}")

                    # 最后一次尝试失败
                    if attempt >= retry_count:
                        return default_return

                    # 等待后重试
                    await asyncio.sleep(retry_delay)

                except (IOError, PermissionError) as e:
                    if logger:
                        logger.error(f"异步I/O操作失败 ({attempt+1}/{retry_count+1}): {str(e)}")

                    # 最后一次尝试失败
                    if attempt >= retry_count:
                        return default_return

                    # 等待后重试
                    await asyncio.sleep(retry_delay * (2 if attempt > 0 else 1))  # 第二次及以后延迟加倍

            # 不应该到达这里
            return default_return

        return cast(F, wrapper)

    return decorator


# 为网络请求专门设计的错误处理装饰器
def network_error_handler(
    logger=None,
    default_return=None,
    retry_count=5,
    retry_delay=1.0,
    max_retry_delay=60.0,
    retry_status_codes=[429, 500, 502, 503, 504],
    timeout=30.0,
    respect_retry_after=True
) -> Callable[[F], F]:
    """专为网络请求设计的错误处理装饰器

    Args:
        logger: 日志记录器对象
        default_return: 发生错误时的默认返回值
        retry_count: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        max_retry_delay: 最大重试延迟（秒）
        retry_status_codes: 需要重试的HTTP状态码列表
        timeout: 请求超时时间（秒）
        respect_retry_after: 是否遵循响应中的Retry-After头

    Returns:
        装饰后的函数
    """
    # 导入需要的库
    import random

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 如果函数支持timeout参数，设置默认值
            sig = inspect.signature(func)
            if 'timeout' in sig.parameters and 'timeout' not in kwargs:
                kwargs['timeout'] = timeout

            for attempt in range(retry_count + 1):
                try:
                    result = func(*args, **kwargs)

                    # 对于返回响应对象的函数，检查状态码
                    if hasattr(result, 'status_code') and result.status_code in retry_status_codes:
                        if attempt >= retry_count:
                            # 最后一次尝试，返回结果
                            return result

                        # 计算重试延迟
                        current_delay = min(retry_delay * (2 ** attempt), max_retry_delay)

                        # 如果响应中有Retry-After头，并且配置为遵循它
                        if respect_retry_after and hasattr(result, 'headers') and 'Retry-After' in result.headers:
                            try:
                                retry_after = int(result.headers['Retry-After'])
                                current_delay = min(retry_after, max_retry_delay)
                            except (ValueError, TypeError):
                                pass  # 忽略无效的Retry-After值

                        # 添加随机抖动
                        current_delay = current_delay * (0.75 + random.random() * 0.5)

                        if logger:
                            logger.warning(f"请求返回状态码 {result.status_code}，将在 {current_delay:.2f} 秒后第 {attempt+1} 次重试")

                        time.sleep(current_delay)
                        continue

                    # 正常返回结果
                    return result

                except Exception as e:
                    # 判断是否为网络相关异常
                    is_network_error = any(err_type in str(type(e)) for err_type in 
                                         ['ConnectionError', 'Timeout', 'HTTPError', 'SSLError', 'RequestException'])

                    if logger:
                        logger.error(f"网络请求失败 ({attempt+1}/{retry_count+1}): {str(e)}")

                    # 最后一次尝试失败
                    if attempt >= retry_count or not is_network_error:
                        return default_return

                    # 计算重试延迟
                    current_delay = min(retry_delay * (2 ** attempt), max_retry_delay)

                    # 添加随机抖动
                    current_delay = current_delay * (0.75 + random.random() * 0.5)

                    if logger:
                        logger.info(f"将在 {current_delay:.2f} 秒后进行第 {attempt+1} 次重试")

                    time.sleep(current_delay)

            # 不应该到达这里
            return default_return

        return cast(F, wrapper)

    return decorator


# 异步版网络请求错误处理装饰器
def async_network_error_handler(
    logger=None,
    default_return=None,
    retry_count=5,
    retry_delay=1.0,
    max_retry_delay=60.0,
    retry_status_codes=[429, 500, 502, 503, 504],
    timeout=30.0,
    respect_retry_after=True
) -> Callable[[F], F]:
    """专为异步网络请求设计的错误处理装饰器

    Args:
        logger: 日志记录器对象
        default_return: 发生错误时的默认返回值
        retry_count: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        max_retry_delay: 最大重试延迟（秒）
        retry_status_codes: 需要重试的HTTP状态码列表
        timeout: 请求超时时间（秒）
        respect_retry_after: 是否遵循响应中的Retry-After头

    Returns:
        装饰后的异步函数
    """
    # 导入需要的库
    import random

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 如果函数支持timeout参数，设置默认值
            sig = inspect.signature(func)
            if 'timeout' in sig.parameters and 'timeout' not in kwargs:
                kwargs['timeout'] = timeout

            for attempt in range(retry_count + 1):
                try:
                    result = await func(*args, **kwargs)

                    # 对于返回响应对象的函数，检查状态码
                    if hasattr(result, 'status') and result.status in retry_status_codes:
                        if attempt >= retry_count:
                            # 最后一次尝试，返回结果
                            return result

                        # 计算重试延迟
                        current_delay = min(retry_delay * (2 ** attempt), max_retry_delay)

                        # 如果响应中有Retry-After头，并且配置为遵循它
                        if respect_retry_after and hasattr(result, 'headers') and 'Retry-After' in result.headers:
                            try:
                                retry_after = int(result.headers['Retry-After'])
                                current_delay = min(retry_after, max_retry_delay)
                            except (ValueError, TypeError):
                                pass  # 忽略无效的Retry-After值

                        # 添加随机抖动
                        current_delay = current_delay * (0.75 + random.random() * 0.5)

                        if logger:
                            logger.warning(f"请求返回状态码 {result.status}，将在 {current_delay:.2f} 秒后第 {attempt+1} 次重试")

                        await asyncio.sleep(current_delay)
                        continue

                    # 正常返回结果
                    return result

                except Exception as e:
                    # 判断是否为网络相关异常
                    is_network_error = any(err_type in str(type(e)) for err_type in 
                                         ['ConnectionError', 'Timeout', 'HTTPError', 'SSLError', 'RequestException'])

                    if logger:
                        logger.error(f"异步网络请求失败 ({attempt+1}/{retry_count+1}): {str(e)}")

                    # 最后一次尝试失败
                    if attempt >= retry_count or not is_network_error:
                        return default_return

                    # 计算重试延迟
                    current_delay = min(retry_delay * (2 ** attempt), max_retry_delay)

                    # 添加随机抖动
                    current_delay = current_delay * (0.75 + random.random() * 0.5)

                    if logger:
                        logger.info(f"将在 {current_delay:.2f} 秒后进行第 {attempt+1} 次重试")

                    await asyncio.sleep(current_delay)

            # 不应该到达这里
            return default_return

        return cast(F, wrapper)

    return decorator


# 兼容原始错误处理接口的函数
def compatible_error_handler(
    logger=None,
    default_return=None,
    show_traceback=True,
    retry_count=0,
    retry_delay=1.0
) -> Callable[[F], F]:
    """兼容原始error_handler接口的装饰器，内部使用增强版实现

    Args:
        logger: 日志记录器对象
        default_return: 发生错误时的默认返回值
        show_traceback: 是否显示完整的堆栈跟踪
        retry_count: 重试次数
        retry_delay: 重试延迟（秒）

    Returns:
        装饰后的函数
    """
    return error_handler(
        logger=logger,
        default_return=default_return,
        show_traceback=show_traceback,
        retry_count=retry_count,
        retry_delay=retry_delay,
        exponential_backoff=False,  # 保持与原接口一致
        report_error=True
    )


def compatible_async_error_handler(
    logger=None,
    default_return=None,
    show_traceback=True,
    retry_count=0,
    retry_delay=1.0
) -> Callable[[F], F]:
    """兼容原始async_error_handler接口的装饰器，内部使用增强版实现

    Args:
        logger: 日志记录器对象
        default_return: 发生错误时的默认返回值
        show_traceback: 是否显示完整的堆栈跟踪
        retry_count: 重试次数
        retry_delay: 重试延迟（秒）

    Returns:
        装饰后的异步函数
    """
    return async_error_handler(
        logger=logger,
        default_return=default_return,
        show_traceback=show_traceback,
        retry_count=retry_count,
        retry_delay=retry_delay,
        exponential_backoff=False,  # 保持与原接口一致
        report_error=True
    )


# 为了向后兼容，保留原始的接口名称
error_handler_original = compatible_error_handler
async_error_handler_original = compatible_async_error_handler
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 获取错误注册表
            registry = error_registry or ErrorRegistry.get_instance()

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 如果指定了特定异常类型且当前异常不在其中，则重新抛出
                if specific_exceptions and not any(isinstance(e, exc) for exc in specific_exceptions):
                    raise

                # 创建错误记录
                error_record = ErrorRecord(
                    exception=e,
                    function_name=func.__name__,
                    args=args,
                    kwargs=kwargs
                )

                # 记录到错误注册表
                if report_error:
                    registry.register_error(error_record)

                # 记录日志
                error_message = f"{func.__name__} 执行出错: {str(e)}"
                if logger:
                    if show_traceback:
                        logger.error(f"{error_message}
{traceback.format_exc()}")
                    else:
                        logger.error(error_message)

                # 调用错误回调函数
                if error_callback:
                    try:
                        if asyncio.iscoroutinefunction(error_callback):
                            await error_callback(error_record)
                        else:
                            error_callback(error_record)
                    except Exception as callback_err:
                        if logger:
                            logger.error(f"错误回调函数执行失败: {str(callback_err)}")

                # 尝试重试
                tries = 0
                while tries < retry_count and error_record.should_retry(retry_count):
                    tries += 1
                    error_record.increment_retry()

                    # 计算重试延迟
                    if exponential_backoff:
                        current_delay = error_record.get_retry_delay(retry_delay, max_retry_delay)
                    else:
                        current_delay = retry_delay

                    if logger:
                        logger.info(f"将在 {current_delay:.2f} 秒后进行第 {tries} 次重试")

                    if current_delay > 0:
                        await asyncio.sleep(current_delay)

                    try:
                        result = await func(*args, **kwargs)
                        # 重试成功，标记为已解决
                        error_record.mark_as_resolved()
                        return result
                    except Exception as retry_error:
                        # 更新错误记录
                        error_record.exception = retry_error
                        error_record.traceback = traceback.format_exc()

                        if logger:
                            logger.error(f"第 {tries} 次重试失败: {str(retry_error)}")

                # 所有重试都失败，返回默认值
                return default_return

        return cast(F, wrapper)

    return decorator


# 网络错误处理装饰器
def network_error_handler(
    logger=None,
    default_return=None,
    retry_count=3,
    retry_delay=1.0,
    max_retry_delay=30.0
) -> Callable[[F], F]:
    """专门用于网络操作的错误处理装饰器

    Args:
        logger: 日志记录器对象
        default_return: 发生错误时的默认返回值
        retry_count: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        max_retry_delay: 最大重试延迟（秒）

    Returns:
        装饰后的函数
    """
    # 导入常见的网络错误类型
    import socket
    from urllib.error import URLError, HTTPError

    network_exceptions = [
        ConnectionError, 
        ConnectionRefusedError, 
        ConnectionResetError, 
        socket.timeout, 
        socket.gaierror, 
        TimeoutError,
        URLError, 
        HTTPError
    ]

    # 如果有aiohttp，添加aiohttp的异常类型
    try:
        import aiohttp.client_exceptions
        network_exceptions.extend([
            aiohttp.client_exceptions.ClientError,
            aiohttp.client_exceptions.ClientConnectionError,
            aiohttp.client_exceptions.ClientConnectorError,
            aiohttp.client_exceptions.ClientOSError,
            aiohttp.client_exceptions.ServerConnectionError,
            aiohttp.client_exceptions.ServerTimeoutError
        ])
    except ImportError:
        pass

    # 如果有requests，添加requests的异常类型
    try:
        import requests.exceptions
        network_exceptions.extend([
            requests.exceptions.RequestException,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout
        ])
    except ImportError:
        pass

    # 判断函数是否是协程函数
    if asyncio.iscoroutinefunction(logger) if callable(logger) else False:
        return async_error_handler(
            logger=logger,
            default_return=default_return,
            retry_count=retry_count,
            retry_delay=retry_delay,
            max_retry_delay=max_retry_delay,
            exponential_backoff=True,
            specific_exceptions=network_exceptions
        )
    else:
        return error_handler(
            logger=logger,
            default_return=default_return,
            retry_count=retry_count,
            retry_delay=retry_delay,
            max_retry_delay=max_retry_delay,
            exponential_backoff=True,
            specific_exceptions=network_exceptions
        )


# IO错误处理装饰器
def io_error_handler(
    logger=None,
    default_return=None,
    retry_count=2,
    retry_delay=1.0
) -> Callable[[F], F]:
    """专门用于文件I/O操作的错误处理装饰器

    Args:
        logger: 日志记录器对象
        default_return: 发生错误时的默认返回值
        retry_count: 最大重试次数
        retry_delay: 初始重试延迟（秒）

    Returns:
        装饰后的函数
    """
    io_exceptions = [
        IOError, 
        OSError, 
        PermissionError, 
        FileExistsError,
        FileNotFoundError
    ]

    # 判断函数是否是协程函数
    if asyncio.iscoroutinefunction(logger) if callable(logger) else False:
        return async_error_handler(
            logger=logger,
            default_return=default_return,
            retry_count=retry_count,
            retry_delay=retry_delay,
            specific_exceptions=io_exceptions
        )
    else:
        return error_handler(
            logger=logger,
            default_return=default_return,
            retry_count=retry_count,
            retry_delay=retry_delay,
            specific_exceptions=io_exceptions
        )


# 通过兼容性包装，保持与原有error_handler模块的兼容性
# 这样可以无缝替代原有模块
# 原有的error_handler和async_error_handler函数将调用增强版本
def legacy_error_handler(
    logger=None,
    default_return=None,
    show_traceback=True,
    retry_count=0,
    retry_delay=1.0
) -> Callable[[F], F]:
    """保持与原有error_handler的兼容性"""
    return error_handler(
        logger=logger,
        default_return=default_return,
        show_traceback=show_traceback,
        retry_count=retry_count,
        retry_delay=retry_delay,
        exponential_backoff=False
    )


def legacy_async_error_handler(
    logger=None,
    default_return=None,
    show_traceback=True,
    retry_count=0,
    retry_delay=1.0
) -> Callable[[F], F]:
    """保持与原有async_error_handler的兼容性"""
    return async_error_handler(
        logger=logger,
        default_return=default_return,
        show_traceback=show_traceback,
        retry_count=retry_count,
        retry_delay=retry_delay,
        exponential_backoff=False
    )


# 设置别名，保持向后兼容性
# 这样代码可以无需修改原有调用方式
from functools import update_wrapper

# 更新原有函数的别名，以保持向后兼容
error_handler_original = legacy_error_handler
async_error_handler_original = legacy_async_error_handler

# 更新函数包装器，使它们看起来像是原始函数
update_wrapper(error_handler_original, error_handler)
update_wrapper(async_error_handler_original, async_error_handler)
