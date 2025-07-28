# -*- coding: utf-8 -*-
"""
日志标签页主模块
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, QTimer

from .ui_init import init_ui
from .log_operations import refresh_logs, clear_logs
from .settings import (
    on_log_level_changed, on_log_lines_changed,
    on_colored_logs_changed, on_auto_scroll_changed,
    load_settings_from_config
)

class LogsTab(QWidget):
    """日志标签页"""

    # 定义信号
    logs_cleared = Signal()

    def __init__(self, logger, config=None, parent=None):
        """初始化日志标签页

        Args:
            logger: 日志模块实例
            config: 配置对象，可选
            parent: 父窗口
        """
        super().__init__(parent)
        self.logger = logger
        self.config = config
        self.parent = parent
        self.init_ui()

        # 定时刷新日志
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.refresh_logs)
        self.log_timer.start(5000)  # 每5秒刷新一次日志

    # 从ui_init.py导入方法
    init_ui = init_ui

    # 从log_operations.py导入方法
    refresh_logs = refresh_logs
    clear_logs = clear_logs

    # 从settings.py导入方法
    on_log_level_changed = on_log_level_changed
    on_log_lines_changed = on_log_lines_changed
    on_colored_logs_changed = on_colored_logs_changed
    on_auto_scroll_changed = on_auto_scroll_changed
    load_settings_from_config = load_settings_from_config
