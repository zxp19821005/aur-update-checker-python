# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtCore import QTimer

# 导入自定义标签页
from .settings_tab import SettingsTab
from .logs_tab import LogsTab

# 导入拆分后的模块
from .main_window.package_dialog import PackageDialog
from .main_window.main_window import MainWindowWrapper

# 确保所有UI组件预先加载
from .main_window.ui_buttons import UIButtons
from .main_window.ui_init import UIInitMixin
from .main_window.package_operations import PackageOperationsMixin
from .main_window.version_check import VersionCheckMixin
from .main_window.update_ui import UpdateUIMixin

# 创建线程池执行器
thread_pool = ThreadPoolExecutor()

# 创建增强版MainWindow类，修复界面延迟加载问题
class MainWindow(MainWindowWrapper):
    """增强版MainWindow类，优化界面加载过程"""
    
    def __init__(self, config, db, logger):
        # 记录依赖项但先不显示窗口
        self.config = config
        self.db = db
        self.logger = logger
        self.is_fully_initialized = False
        
        # 禁止自动显示
        self.show_window_when_ready = True
        
        # 调用父类初始化
        super().__init__(config, db, logger)
        
        # 完成所有UI组件初始化
        self.setupUIComponents()
    
    def setupUIComponents(self):
        """完成UI组件初始化准备"""
        # 强制完成所有待处理的绘图操作
        self.processEvents()
        
        # 标记完成初始化 - 此时不加载数据，由主程序控制加载时机
        self.is_fully_initialized = True
        self.logger.info("界面元素初始化完成")
    
    def processEvents(self):
        """处理待处理的事件，确保界面更新"""
        app = QApplication.instance()
        if app:
            app.processEvents()
            
    def show(self):
        """重写show方法，确保界面元素完全加载"""
        # 显示窗口
        super().show()
        
        # 立即处理事件，强制更新界面
        self.processEvents()


def run_async(coroutine):
    """在主线程中运行协程

    Args:
        coroutine: 要运行的协程
    Returns:
        协程的执行结果
    """
    try:
        # 检查当前是否在主线程中
        app = QApplication.instance()
        if app and app.thread() == QApplication.instance().thread():
            try:
                # 尝试导入qasync并使用QEventLoop
                import qasync
                loop = qasync.QEventLoop(app)
                asyncio.set_event_loop(loop)
            except (ImportError, RuntimeError):
                # 如果qasync不可用或发生错误，使用标准事件循环
                loop = asyncio.get_event_loop()
        else:
            # 在非主线程中，使用标准事件循环
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # 如果当前线程没有事件循环，创建一个新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

        # 执行协程
        return loop.run_until_complete(coroutine)
    except Exception as e:
        print(f"运行协程时出错: {e}")
        raise

# 直接定义MainWindow类，而不是从子包导入
MainWindow = MainWindowWrapper

