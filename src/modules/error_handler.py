# -*- coding: utf-8 -*-
"""
错误处理工具模块，提供统一的错误处理机制
"""
import functools
import traceback
from typing import Any, Callable, TypeVar, cast, Optional

# 类型变量，表示任何类型的函数
F = TypeVar('F', bound=Callable[..., Any])


def error_handler(
    logger=None, 
    default_return=None,
    show_traceback=True,
    retry_count=0,
    retry_delay=1.0
) -> Callable[[F], F]:
    """统一的错误处理装饰器

    Args:
        logger: 日志记录器对象，需要有error方法
        default_return: 发生错误时的默认返回值
        show_traceback: 是否显示完整的堆栈跟踪
        retry_count: 重试次数
        retry_delay: 重试延迟（秒）

    Returns:
        装饰后的函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tries = 0
            max_tries = retry_count + 1

            while tries < max_tries:
                tries += 1
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # 获取错误信息
                    error_message = f"{func.__name__} 执行出错: {str(e)}"

                    # 记录日志
                    if logger:
                        if show_traceback:
                            logger.error(f"{error_message}\n{traceback.format_exc()}")
                        else:
                            logger.error(error_message)

                    # 如果还有重试次数，则继续重试
                    if tries < max_tries:
                        if logger:
                            logger.info(f"将在 {retry_delay} 秒后进行第 {tries} 次重试")
                        if retry_delay > 0:
                            import time
                            time.sleep(retry_delay)
                        continue

                    # 返回默认值
                    return default_return

            # 不应该到达这里
            return default_return

        return cast(F, wrapper)

    return decorator


def async_error_handler(
    logger=None, 
    default_return=None,
    show_traceback=True,
    retry_count=0,
    retry_delay=1.0
) -> Callable[[F], F]:
    """异步函数的统一错误处理装饰器

    Args:
        logger: 日志记录器对象，需要有error方法
        default_return: 发生错误时的默认返回值
        show_traceback: 是否显示完整的堆栈跟踪
        retry_count: 重试次数
        retry_delay: 重试延迟（秒）

    Returns:
        装饰后的异步函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            tries = 0
            max_tries = retry_count + 1

            while tries < max_tries:
                tries += 1
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # 获取错误信息
                    error_message = f"{func.__name__} 执行出错: {str(e)}"

                    # 记录日志
                    if logger:
                        if show_traceback:
                            logger.error(f"{error_message}\n{traceback.format_exc()}")
                        else:
                            logger.error(error_message)

                    # 如果还有重试次数，则继续重试
                    if tries < max_tries:
                        if logger:
                            logger.info(f"将在 {retry_delay} 秒后进行第 {tries} 次重试")
                        if retry_delay > 0:
                            import asyncio
                            await asyncio.sleep(retry_delay)
                        continue

                    # 返回默认值
                    return default_return

            # 不应该到达这里
            return default_return

        return cast(F, wrapper)

    return decorator
