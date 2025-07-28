# -*- coding: utf-8 -*-
"""
工具函数模块，包含一些通用的工具函数
"""
import asyncio
import qasync
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QCoreApplication

# 创建线程池执行器
thread_pool = ThreadPoolExecutor()

def run_async(coroutine):
    """在主线程中运行协程
    Args:
        coroutine: 要运行的协程
    Returns:
        协程的执行结果
    """
    try:
        # 检查当前是否在主线程中
        app = QCoreApplication.instance()
        if app and app.thread() == QCoreApplication.instance().thread():
            # 在主线程中，使用qasync
            loop = qasync.QEventLoop(app)
            asyncio.set_event_loop(loop)
        else:
            # 在非主线程中，使用标准事件循环
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # 如果当前线程没有事件循环，创建一个新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
    except Exception as e:
        # 任何错误都回退到创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # 确保协程完成并返回结果
    try:
        return loop.run_until_complete(coroutine)
    except Exception as e:
        print(f"运行协程时出错: {e}")
        raise
