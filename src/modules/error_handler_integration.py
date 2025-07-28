# -*- coding: utf-8 -*-
"""
错误处理集成模块，整合原有错误处理功能与增强版错误处理功能
"""
from .error_handler import error_handler as original_error_handler
from .error_handler import async_error_handler as original_async_error_handler

try:
    from .enhanced_error_handler import (
        ErrorSeverity, 
        ErrorCategory, 
        ErrorRecord, 
        ErrorRegistry, 
        error_handler as enhanced_error_handler,
        async_error_handler as enhanced_async_error_handler,
        io_error_handler,
        network_error_handler
    )

    # 标记增强版模块加载成功
    ENHANCED_ERROR_HANDLING_AVAILABLE = True
except ImportError:
    # 回退到原始版本
    ENHANCED_ERROR_HANDLING_AVAILABLE = False

# 为了保持向后兼容性，导出原始的装饰器
error_handler = original_error_handler
async_error_handler = original_async_error_handler

# 创建对网络请求和I/O操作专门的错误处理装饰器
if ENHANCED_ERROR_HANDLING_AVAILABLE:
    # 为网络请求专用的错误处理装饰器
    def network_request_error_handler(
        logger=None,
        default_return=None,
        retry_count=5,  # 网络请求通常需要更多重试次数
        retry_delay=1.0,
        max_retry_delay=60.0,  # 最长重试延迟限制为1分钟
        show_traceback=True,
    ):
        """网络请求错误处理装饰器

        这是一个专为网络请求优化的错误处理装饰器，支持指数退避、错误分类等高级功能
        """
        return enhanced_error_handler(
            logger=logger,
            default_return=default_return,
            show_traceback=show_traceback,
            retry_count=retry_count,
            retry_delay=retry_delay,
            max_retry_delay=max_retry_delay,
            exponential_backoff=True,  # 网络请求使用指数退避
            specific_exceptions=[
                # 常见网络错误异常类型
                ConnectionError, 
                TimeoutError, 
                IOError,
                # 如果aiohttp可用，还包括其错误类型
                *([aiohttp.ClientError] if 'aiohttp' in sys.modules else [])
            ]
        )

    # 异步网络请求错误处理装饰器
    def async_network_request_error_handler(
        logger=None,
        default_return=None,
        retry_count=5,
        retry_delay=1.0,
        max_retry_delay=60.0,
        show_traceback=True,
    ):
        """异步网络请求错误处理装饰器"""
        return enhanced_async_error_handler(
            logger=logger,
            default_return=default_return,
            show_traceback=show_traceback,
            retry_count=retry_count,
            retry_delay=retry_delay,
            max_retry_delay=max_retry_delay,
            exponential_backoff=True
        )

    # I/O操作错误处理装饰器
    def file_io_error_handler(
        logger=None, 
        default_return=None, 
        retry_count=3,
        retry_delay=0.5,
        create_dirs=True  # 默认尝试创建缺失的目录
    ):
        """文件I/O错误处理装饰器"""
        return io_error_handler(
            logger=logger,
            default_return=default_return,
            retry_count=retry_count,
            retry_delay=retry_delay,
            create_dirs=create_dirs
        )
else:
    # 如果增强版本不可用，提供基本的兼容实现
    def network_request_error_handler(
        logger=None,
        default_return=None,
        retry_count=5,
        retry_delay=1.0,
        max_retry_delay=60.0,
        show_traceback=True,
    ):
        """使用原始错误处理器的网络请求错误处理装饰器"""
        return original_error_handler(
            logger=logger,
            default_return=default_return,
            show_traceback=show_traceback,
            retry_count=retry_count,
            retry_delay=retry_delay
        )

    # 异步版本
    def async_network_request_error_handler(
        logger=None,
        default_return=None,
        retry_count=5,
        retry_delay=1.0,
        max_retry_delay=60.0,
        show_traceback=True,
    ):
        """使用原始错误处理器的异步网络请求错误处理装饰器"""
        return original_async_error_handler(
            logger=logger,
            default_return=default_return,
            show_traceback=show_traceback,
            retry_count=retry_count,
            retry_delay=retry_delay
        )

    # 基本I/O错误处理
    def file_io_error_handler(
        logger=None, 
        default_return=None, 
        retry_count=3,
        retry_delay=0.5,
        create_dirs=True
    ):
        """使用原始错误处理器的文件I/O错误处理装饰器"""
        return original_error_handler(
            logger=logger,
            default_return=default_return,
            show_traceback=True,
            retry_count=retry_count,
            retry_delay=retry_delay
        )

# 便捷函数，用于获取错误注册表实例
def get_error_registry():
    """获取错误注册表实例，如果增强版不可用则返回None"""
    if ENHANCED_ERROR_HANDLING_AVAILABLE:
        return ErrorRegistry.get_instance()
    return None

# 便捷函数，获取错误统计信息
def get_error_statistics():
    """获取错误统计信息"""
    registry = get_error_registry()
    if registry:
        return registry.get_error_statistics()
    return {"error": "增强版错误处理不可用"}
