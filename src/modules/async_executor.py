# -*- coding: utf-8 -*-
"""
异步任务执行器模块 - 精简版本

优化点:
1. 使用协程池限制并发数，防止过多请求导致资源耗尽
2. 实现请求超时和重试机制，增强网络稳定性
3. 在主线程回调前增加结果验证，防止回调参数不匹配
4. 减少代码冗余，合并相似函数
5. 优化回调处理逻辑
"""
import asyncio
import concurrent.futures
import threading
import traceback
import time
from typing import Optional, Callable, Any, Dict, List, Tuple, Union
from functools import wraps
import logging
import inspect
from collections import deque

from PySide6.QtCore import QObject, Signal, QCoreApplication, QEvent


class AsyncExecutor(QObject):
    """异步任务执行器，封装了异步任务的执行逻辑和事件循环管理"""

    task_completed = Signal(object)  # 任务完成信号
    task_failed = Signal(str)        # 任务失败信号

    def __init__(self, logger=None, max_workers=3, default_timeout=30, max_concurrency=10):
        """初始化异步执行器"""
        super().__init__()
        self.logger = logger or logging.getLogger("async_executor")
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._main_thread = threading.current_thread()
        self._default_timeout = default_timeout
        self._max_concurrency = max_concurrency

        # 重试配置
        self._max_retries = 3
        self._retry_delay = 1.0  # 基础重试延迟(秒)

        # 请求控制
        self._task_queue = deque()  # 任务队列
        self._queue_lock = threading.RLock()
        self._queue_processing = False
        self._requests_count = 0
        self._requests_lock = threading.RLock()
        self._last_reset_time = time.time()
        self._max_requests_per_minute = 60

        # 统计信息
        self._stats = {
            "completed": 0, "failed": 0, "retried": 0, "total": 0,
            "queued": 0, "avg_duration": 0, "peak_concurrency": 0, "current_concurrency": 0
        }

    def is_in_main_thread(self) -> bool:
        """检查当前是否在主线程中"""
        return threading.current_thread() == self._main_thread

    def run_coroutine(
        self,
        coro,
        callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None,
        timeout: Optional[float] = None,
        retry_on_failure: bool = True,
        validate_result: Optional[Callable[[Any], bool]] = None
    ) -> concurrent.futures.Future:
        """在线程池中运行协程"""
        if timeout is None:
            timeout = self._default_timeout

        # 检查请求限流
        if not self._check_rate_limit():
            # 将任务加入队列，延迟执行
            with self._queue_lock:
                task_info = (coro, callback, error_callback, timeout, retry_on_failure, validate_result, 0)
                self._task_queue.append(task_info)
                self._stats["queued"] += 1
                self.logger.debug(f"任务已加入队列，当前队列长度: {len(self._task_queue)}")

                # 启动队列处理
                if not self._queue_processing:
                    self._queue_processing = True
                    self._thread_pool.submit(self._process_task_queue)

                # 创建一个future来表示队列中的任务
                future = concurrent.futures.Future()
                return future

        # 记录统计
        with self._requests_lock:
            self._requests_count += 1
            self._stats["total"] += 1

        # 创建任务上下文
        task_context = {
            "retry_count": 0,
            "start_time": time.time(),
            "coro": coro,
            "callback": callback,
            "error_callback": error_callback,
            "timeout": timeout,
            "retry_on_failure": retry_on_failure,
            "validate_result": validate_result
        }

        # 提交到线程池
        return self._thread_pool.submit(self._run_task, task_context)

    def _run_task(self, task_context):
        """执行异步任务的统一方法，处理协程执行、重试和结果处理"""
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 为此事件循环创建信号量
        semaphore = asyncio.Semaphore(self._max_concurrency)

        # 创建包装的协程
        wrapped_coro = self._wrap_coroutine(
            task_context["coro"], 
            semaphore
        )

        try:
            # 使用超时机制运行协程
            task = wrapped_coro
            if task_context["timeout"]:
                task = asyncio.wait_for(wrapped_coro, timeout=task_context["timeout"])

            # 运行协程直到完成
            result = loop.run_until_complete(task)

            # 验证结果
            if task_context["validate_result"] and not task_context["validate_result"](result):
                raise ValueError("结果验证失败")

            # 记录成功统计并处理回调
            self._handle_success(task_context, result)
            return result

        except Exception as e:
            # 统一处理异常
            return self._handle_exception(task_context, e)

        finally:
            # 关闭事件循环
            self._cleanup_loop(loop)

    async def _wrap_coroutine(self, coro, semaphore):
        """包装协程，添加并发控制和统计"""
        async with semaphore:
            # 更新当前并发度统计
            with self._requests_lock:
                self._stats["current_concurrency"] += 1
                if self._stats["current_concurrency"] > self._stats["peak_concurrency"]:
                    self._stats["peak_concurrency"] = self._stats["current_concurrency"]

            try:
                # 执行原始协程
                result = await coro
                return result
            finally:
                # 减少并发计数
                with self._requests_lock:
                    self._stats["current_concurrency"] -= 1

    def _handle_success(self, task_context, result):
        """处理任务成功完成的情况"""
        # 记录成功统计
        with self._requests_lock:
            self._stats["completed"] += 1
            duration = time.time() - task_context["start_time"]
            if self._stats["completed"] > 0:
                self._stats["avg_duration"] = (
                    self._stats["avg_duration"] * (self._stats["completed"] - 1) + duration
                ) / self._stats["completed"]

        # 在主线程中调用回调
        if task_context["callback"]:
            QCoreApplication.instance().postEvent(
                self, _AsyncCallbackEvent(self._create_callback_wrapper(task_context["callback"]), result)
            )

        # 发出完成信号
        self.task_completed.emit(result)
        return result

    def _handle_exception(self, task_context, exception):
        """统一处理异常，包括重试逻辑"""
        error_msg = f"异步任务执行错误: {str(exception)}"
        if self.logger:
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")

        # 判断是否可以重试
        if task_context["retry_count"] < self._max_retries and task_context["retry_on_failure"]:
            self.logger.warning(f"任务执行出错，准备重试 (尝试 {task_context['retry_count']+1}/{self._max_retries})")
            task_context["retry_count"] += 1
            with self._requests_lock:
                self._stats["retried"] += 1

            # 计算重试延迟 (指数退避)
            retry_delay = self._retry_delay * (2 ** (task_context["retry_count"] - 1))
            time.sleep(retry_delay)

            # 递归重试
            return self._run_task(task_context)
        else:
            # 任务最终失败，调用错误回调
            if task_context["error_callback"]:
                QCoreApplication.instance().postEvent(
                    self, _AsyncCallbackEvent(task_context["error_callback"], str(exception))
                )

            # 记录失败统计
            with self._requests_lock:
                self._stats["failed"] += 1

            # 发出失败信号
            self.task_failed.emit(error_msg)
            raise exception

    def _cleanup_loop(self, loop):
        """清理事件循环资源"""
        try:
            # 取消所有待处理的任务
            pending_tasks = asyncio.all_tasks(loop)
            for task in pending_tasks:
                task.cancel()

            # 运行，直到所有任务取消
            if pending_tasks:
                loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))

            # 关闭事件循环
            loop.close()
        except Exception as e:
            if self.logger:
                self.logger.error(f"关闭事件循环时出错: {str(e)}")

    def _process_task_queue(self):
        """处理延迟任务队列"""
        while True:
            # 检查是否有任务
            with self._queue_lock:
                if not self._task_queue:
                    self._queue_processing = False
                    break

                # 检查是否可以处理下一个任务
                if not self._check_rate_limit():
                    # 等待一下再试
                    time.sleep(0.2)
                    continue

                # 获取下一个任务
                task_info = self._task_queue.popleft()
                self._stats["queued"] -= 1

            # 执行任务
            with self._requests_lock:
                self._requests_count += 1

            # 创建任务上下文并执行
            task_context = {
                "retry_count": task_info[6],  # 重试次数在索引6
                "start_time": time.time(),
                "coro": task_info[0],
                "callback": task_info[1],
                "error_callback": task_info[2],
                "timeout": task_info[3],
                "retry_on_failure": task_info[4],
                "validate_result": task_info[5]
            }

            # 在线程池中执行任务
            self._thread_pool.submit(self._run_task, task_context)

            # 小暂停防止队列处理过快
            time.sleep(0.05)

    def _check_rate_limit(self) -> bool:
        """检查并限制请求速率"""
        with self._requests_lock:
            current_time = time.time()
            # 每分钟重置计数器
            if current_time - self._last_reset_time > 60:
                self._requests_count = 0
                self._last_reset_time = current_time

            # 检查是否超过限制
            return self._requests_count < self._max_requests_per_minute

    def _create_callback_wrapper(self, callback_func):
        """创建安全的回调函数包装器"""
        @wraps(callback_func)
        def wrapper(data):
            try:
                # 获取回调函数的签名
                sig = inspect.signature(callback_func)
                param_count = len(sig.parameters)

                # 根据参数数量处理回调
                if param_count == 0:
                    return callback_func()
                elif param_count == 1:
                    return callback_func(data)
                else:
                    # 多参数情况处理
                    if isinstance(data, dict):
                        param_names = list(sig.parameters.keys())
                        kwargs = {name: data.get(name) for name in param_names if name in data}
                        if kwargs:
                            return callback_func(**kwargs)
                    elif hasattr(data, '__iter__') and not isinstance(data, (str, dict)):
                        args = list(data)[:param_count]
                        if len(args) == param_count:
                            return callback_func(*args)

                    # 默认情况
                    return callback_func(data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"回调执行错误: {str(e)}\n{traceback.format_exc()}")
                raise
        return wrapper

    def event(self, event):
        """处理自定义事件"""
        if event.type() == QEvent.Type.User and hasattr(event, 'callback') and hasattr(event, 'data'):
            try:
                event.callback(event.data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"事件回调执行错误: {str(e)}\n{traceback.format_exc()}")
            return True
        return super().event(event)

    def get_stats(self) -> Dict[str, Any]:
        """获取执行器统计信息"""
        with self._requests_lock:
            return self._stats.copy()

    def configure(self, **kwargs):
        """配置执行器参数"""
        config_changed = False

        for key, value in kwargs.items():
            if hasattr(self, f"_max_{key}") or hasattr(self, f"_{key}"):
                attr_name = f"_max_{key}" if hasattr(self, f"_max_{key}") else f"_{key}"
                setattr(self, attr_name, value)
                config_changed = True

        if self.logger and config_changed:
            self.logger.info(f"执行器配置已更新: {kwargs}")

        return config_changed

    def shutdown(self, wait=True):
        """关闭执行器及其线程池"""
        if hasattr(self, '_thread_pool') and self._thread_pool:
            self._thread_pool.shutdown(wait=wait)
            if self.logger:
                self.logger.debug("异步执行器已关闭")


# 自定义事件类，用于在主线程中调用回调
class _AsyncCallbackEvent(QEvent):
    """用于在主线程中触发回调的自定义事件"""

    def __init__(self, callback, data):
        """初始化回调事件"""
        super().__init__(QEvent.Type.User)
        self.callback = callback
        self.data = data


# 单例模式 - 全局执行器实例
_global_executor = None

def get_async_executor(logger=None, max_workers=3, default_timeout=30, max_concurrency=10):
    """获取全局异步执行器实例"""
    global _global_executor
    if _global_executor is None:
        _global_executor = AsyncExecutor(logger, max_workers, default_timeout, max_concurrency)
    return _global_executor


def run_async_task(coro, callback=None, error_callback=None, logger=None, timeout=None,
                   retry_on_failure=True, validate_result=None):
    """运行异步任务的便捷函数"""
    executor = get_async_executor(logger)
    return executor.run_coroutine(coro, callback, error_callback, timeout,
                                 retry_on_failure, validate_result)


# 便捷的装饰器
def async_task(timeout=None, error_handler=None, retry_on_failure=True, validate_result=None):
    """异步任务装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取logger
            logger = None
            if args and hasattr(args[0], 'logger'):
                logger = args[0].logger

            # 创建错误回调
            def on_error(error):
                if error_handler:
                    error_handler(error)
                elif logger:
                    logger.error(f"异步任务出错: {error}")

            # 运行异步任务
            return run_async_task(
                func(*args, **kwargs),
                error_callback=on_error,
                logger=logger,
                timeout=timeout,
                retry_on_failure=retry_on_failure,
                validate_result=validate_result
            )
        return wrapper
    return decorator

    def shutdown(self, wait=True):
        """关闭执行器及其线程池"""
        if hasattr(self, '_thread_pool') and self._thread_pool:
            self._thread_pool.shutdown(wait=wait)
            if self.logger:
                self.logger.debug("异步执行器已关闭")


# 自定义事件类，用于在主线程中调用回调
class _AsyncCallbackEvent(QEvent):
    """用于在主线程中触发回调的自定义事件"""

    def __init__(self, callback, data):
        super().__init__(QEvent.Type.User)
        self.callback = callback
        self.data = data


# 全局执行器和辅助函数
_global_executor = None

def get_async_executor(logger=None, max_workers=3, default_timeout=30, max_concurrency=10):
    """获取全局异步执行器实例"""
    global _global_executor
    if _global_executor is None:
        _global_executor = AsyncExecutor(logger, max_workers, default_timeout, max_concurrency)
    return _global_executor


def run_async_task(coro, callback=None, error_callback=None, logger=None, timeout=None,
                  retry_on_failure=True, validate_result=None):
    """运行异步任务的便捷函数"""
    executor = get_async_executor(logger)
    return executor.run_coroutine(coro, callback, error_callback, timeout,
                                 retry_on_failure, validate_result)


def async_task(timeout=None, error_handler=None, retry_on_failure=True,
              validate_result=None, max_concurrency=None):
    """异步任务装饰器，支持更多控制选项"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取logger
            logger = None
            if args and hasattr(args[0], 'logger'):
                logger = args[0].logger

            # 创建错误回调
            def on_error(error):
                if error_handler:
                    error_handler(error)
                elif logger:
                    logger.error(f"异步任务出错: {error}")

            # 配置执行器
            executor = get_async_executor(logger)
            if max_concurrency is not None:
                executor.configure(max_concurrency=max_concurrency)

            # 运行异步任务
            return run_async_task(
                func(*args, **kwargs),
                error_callback=on_error,
                logger=logger,
                timeout=timeout,
                retry_on_failure=retry_on_failure,
                validate_result=validate_result
            )
        return wrapper
    return decorator
