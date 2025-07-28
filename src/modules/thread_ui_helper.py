# -*- coding: utf-8 -*-
"""
UI线程安全助手模块，确保所有UI操作都在主线程中执行
提供后台任务优化支持，避免阻塞UI
"""
from typing import Any, Callable, Dict, List, Optional, Union, TypeVar, cast
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QThread, Qt, QMetaObject, Q_ARG
from PySide6.QtWidgets import QApplication
import functools
import threading
import queue
import time
import traceback
import logging

# 线程任务优先级
class TaskPriority:
    """任务优先级定义"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class ThreadSafeUI:
    """UI线程安全助手类，确保所有UI操作都在主线程中执行"""

    @staticmethod
    def is_main_thread() -> bool:
        """检查当前是否在主线程中

        Returns:
            bool: 如果在主线程中返回True，否则返回False
        """
        return QThread.currentThread() == QApplication.instance().thread()

    @staticmethod
    def run_in_main_thread(func: Callable, *args, **kwargs) -> None:
        """确保函数在主线程中运行

        如果当前在主线程，则直接执行函数
        否则，通过QMetaObject.invokeMethod在主线程中执行

        Args:
            func: 要在主线程中执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
        """
        if ThreadSafeUI.is_main_thread():
            # 如果已经在主线程中，直接执行
            func(*args, **kwargs)
        else:
            # 否则，使用invokeMethod在主线程中调用
            # 将函数和参数包装成一个无参数的lambda
            wrapped_func = lambda: func(*args, **kwargs)

            # 找到应用程序实例并在其线程上调用
            QMetaObject.invokeMethod(
                QApplication.instance(),
                wrapped_func,
                Qt.ConnectionType.QueuedConnection
            )

    @staticmethod
    def ui_safe(func: Callable) -> Callable:
        """装饰器，确保函数在主线程中执行

        Args:
            func: 需要保证在主线程执行的函数

        Returns:
            函数的线程安全版本
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if ThreadSafeUI.is_main_thread():
                return func(*args, **kwargs)
            else:
                # 使用队列在线程间传递结果
                result_queue = queue.Queue()

                # 在主线程中执行并将结果放入队列
                def exec_in_main_thread():
                    try:
                        result = func(*args, **kwargs)
                        result_queue.put((True, result))
                    except Exception as e:
                        result_queue.put((False, e))

                # 在主线程中执行
                ThreadSafeUI.run_in_main_thread(exec_in_main_thread)

                # 等待并返回结果
                success, result = result_queue.get()
                if success:
                    return result
                else:
                    raise result

        return wrapper


class DelayedUIUpdater:
    """延迟UI更新器，避免频繁更新UI导致的性能问题"""

    def __init__(self, update_func: Callable, delay_ms: int = 50, logger=None):
        """初始化延迟更新器

        Args:
            update_func: 实际执行更新的函数
            delay_ms: 延迟更新的毫秒数
            logger: 日志记录器
        """
        self.update_func = update_func
        self.delay_ms = delay_ms
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._do_update)
        self.pending_update = False
        self.update_data = None
        self.logger = logger or logging.getLogger(__name__)

    def schedule_update(self, *args, **kwargs) -> None:
        """安排一次延迟更新

        Args:
            *args: 传递给更新函数的位置参数
            **kwargs: 传递给更新函数的关键字参数
        """
        # 保存更新数据
        self.update_data = (args, kwargs)
        self.pending_update = True

        # 如果定时器未激活，启动它
        if not self.timer.isActive():
            self.timer.start(self.delay_ms)

    def force_update(self) -> None:
        """强制立即更新，取消任何待处理的定时器"""
        if self.pending_update:
            self.timer.stop()
            self._do_update()

    def _do_update(self) -> None:
        """执行实际的更新操作"""
        if not self.pending_update:
            return

        try:
            args, kwargs = self.update_data
            # 确保在主线程中执行
            ThreadSafeUI.run_in_main_thread(self.update_func, *args, **kwargs)
        except Exception as e:
            if self.logger:
                self.logger.error(f"UI更新出错: {str(e)}")
                self.logger.debug(traceback.format_exc())
        finally:
            self.pending_update = False
            self.update_data = None


class BackgroundTaskManager(QObject):
    """后台任务管理器，管理非UI线程执行的任务"""

    # 任务状态信号
    task_started = Signal(str)      # 任务ID
    task_completed = Signal(str, object)  # 任务ID, 结果
    task_failed = Signal(str, str)  # 任务ID, 错误消息
    task_progress = Signal(str, int, int)  # 任务ID, 当前进度, 总进度

    def __init__(self, max_workers: int = 4, parent=None, logger=None):
        """初始化后台任务管理器

        Args:
            max_workers: 最大工作线程数
            parent: 父QObject
            logger: 日志记录器
        """
        super().__init__(parent)
        self.logger = logger or logging.getLogger(__name__)
        self.max_workers = max_workers

        # 任务队列和结果字典
        self._task_queue = queue.PriorityQueue()
        self._active_tasks = {}  # task_id -> task_info
        self._results = {}  # task_id -> result
        self._lock = threading.RLock()

        # 工作线程
        self._workers = []
        self._stop_event = threading.Event()

        # 启动工作线程
        self._start_workers()

    def _start_workers(self) -> None:
        """启动工作线程"""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"BackgroundWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
            if self.logger:
                self.logger.debug(f"启动工作线程 {worker.name}")

    def _worker_loop(self) -> None:
        """工作线程主循环"""
        while not self._stop_event.is_set():
            try:
                # 从队列获取任务，最多等待1秒
                try:
                    priority, task_id, task_func, args, kwargs = self._task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # 发出任务开始信号
                self.task_started.emit(task_id)

                try:
                    # 执行任务
                    result = task_func(*args, **kwargs)

                    # 存储结果
                    with self._lock:
                        self._results[task_id] = result

                    # 发出完成信号
                    self.task_completed.emit(task_id, result)

                except Exception as e:
                    # 记录错误
                    error_msg = f"任务 {task_id} 执行失败: {str(e)}"
                    if self.logger:
                        self.logger.error(error_msg)
                        self.logger.debug(traceback.format_exc())

                    # 发出失败信号
                    self.task_failed.emit(task_id, str(e))

                finally:
                    # 任务完成，从活动任务中移除
                    with self._lock:
                        if task_id in self._active_tasks:
                            del self._active_tasks[task_id]

                    # 标记队列任务完成
                    self._task_queue.task_done()

            except Exception as e:
                # 工作线程异常处理
                if self.logger:
                    self.logger.error(f"工作线程异常: {str(e)}")
                    self.logger.debug(traceback.format_exc())
                time.sleep(1.0)  # 避免过度循环消耗CPU

    def schedule_task(self, task_func: Callable, *args, 
                     task_id: str = None, 
                     priority: int = TaskPriority.NORMAL,
                     **kwargs) -> str:
        """安排后台任务

        Args:
            task_func: 要执行的任务函数
            *args: 函数参数
            task_id: 任务ID，如果为None则自动生成
            priority: 任务优先级，默认为普通
            **kwargs: 函数关键字参数

        Returns:
            str: 任务ID
        """
        # 生成任务ID
        if task_id is None:
            task_id = f"task_{time.time()}_{threading.get_ident()}"

        # 添加到活动任务
        with self._lock:
            self._active_tasks[task_id] = {
                'func': task_func.__name__ if hasattr(task_func, '__name__') else str(task_func),
                'start_time': time.time(),
                'priority': priority
            }

        # 添加到队列
        self._task_queue.put((priority, task_id, task_func, args, kwargs))

        if self.logger:
            self.logger.debug(f"安排任务 {task_id}, 优先级={priority}")

        return task_id

    def get_result(self, task_id: str, remove: bool = True) -> Any:
        """获取任务结果

        Args:
            task_id: 任务ID
            remove: 是否在获取后删除结果

        Returns:
            任务结果，如果任务未完成则返回None
        """
        with self._lock:
            if task_id in self._results:
                result = self._results[task_id]
                if remove:
                    del self._results[task_id]
                return result
            return None

    def is_task_running(self, task_id: str) -> bool:
        """检查任务是否正在运行

        Args:
            task_id: 任务ID

        Returns:
            bool: 如果任务正在运行返回True，否则返回False
        """
        with self._lock:
            return task_id in self._active_tasks

    def cancel_all_tasks(self) -> None:
        """取消所有待处理的任务

        注意：已经在执行的任务无法取消
        """
        # 清空队列
        while not self._task_queue.empty():
            try:
                self._task_queue.get(block=False)
                self._task_queue.task_done()
            except queue.Empty:
                break

        if self.logger:
            self.logger.info("已取消所有待处理任务")

    def shutdown(self, wait: bool = True) -> None:
        """关闭任务管理器

        Args:
            wait: 是否等待所有任务完成
        """
        if wait:
            # 等待队列中的所有任务完成
            self._task_queue.join()

        # 发出停止信号
        self._stop_event.set()

        # 等待所有工作线程退出
        for worker in self._workers:
            if worker.is_alive():
                worker.join(timeout=1.0)

        if self.logger:
            self.logger.info("后台任务管理器已关闭")


# 全局任务管理器实例
_global_task_manager = None

def get_task_manager(logger=None, max_workers=None) -> BackgroundTaskManager:
    """获取全局任务管理器实例

    Args:
        logger: 日志记录器
        max_workers: 最大工作线程数

    Returns:
        BackgroundTaskManager: 全局任务管理器实例
    """
    global _global_task_manager
    if _global_task_manager is None:
        _global_task_manager = BackgroundTaskManager(
            max_workers=max_workers or 4,
            logger=logger
        )
    return _global_task_manager


# 便捷函数，用于在UI组件中更新状态
def update_ui_safely(ui_object, update_func: Callable, *args, **kwargs) -> None:
    """安全地更新UI组件

    Args:
        ui_object: UI对象，用于确定是否需要延迟更新
        update_func: 更新函数
        *args: 函数参数
        **kwargs: 函数关键字参数
    """
    # 如果对象有正在绘制的标志，延迟更新
    if hasattr(ui_object, 'isVisible') and ui_object.isVisible():
        # 创建延迟更新器
        updater = getattr(ui_object, '_ui_updater', None)
        if updater is None:
            updater = DelayedUIUpdater(update_func)
            setattr(ui_object, '_ui_updater', updater)

        # 安排更新
        updater.schedule_update(*args, **kwargs)
    else:
        # 否则直接更新
        ThreadSafeUI.run_in_main_thread(update_func, *args, **kwargs)


# 装饰器，确保UI方法在主线程中执行
def ui_thread_safe(func: Callable) -> Callable:
    """装饰器，确保函数在主线程中执行

    用法示例:
    @ui_thread_safe
    def update_table(self, data):
        # 更新表格的代码
        pass

    Args:
        func: 需要在主线程中执行的函数

    Returns:
        函数的线程安全版本
    """
    return ThreadSafeUI.ui_safe(func)


# 装饰器，将函数标记为后台任务
def background_task(priority=TaskPriority.NORMAL, task_id=None):
    """装饰器，将函数标记为后台任务

    用法示例:
    @background_task(priority=TaskPriority.HIGH)
    def process_data(self, data):
        # 处理数据的代码
        return result

    Args:
        priority: 任务优先级
        task_id: 任务ID，如果为None则自动生成

    Returns:
        装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取logger
            logger = None
            if args and hasattr(args[0], 'logger'):
                logger = args[0].logger

            # 获取任务管理器
            task_manager = get_task_manager(logger)

            # 生成任务ID
            _task_id = task_id
            if _task_id is None and args and hasattr(args[0], '__class__'):
                # 使用类名和方法名作为任务ID前缀
                prefix = f"{args[0].__class__.__name__}.{func.__name__}"
                _task_id = f"{prefix}_{time.time()}"

            # 安排任务
            return task_manager.schedule_task(
                func, *args,
                task_id=_task_id,
                priority=priority,
                **kwargs
            )
        return wrapper
    return decorator
