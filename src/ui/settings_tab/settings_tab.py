# -*- coding: utf-8 -*-
"""
设置标签页主模块
"""
import os
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

from .ui_init import init_ui, select_curl_path
from .config_operations import save_settings, reset_settings
from .form_controls import create_form_control
from .scheduler_settings import _load_scheduler_settings, _update_scheduler_settings, _check_now

class SettingsTab(QWidget):
    """设置标签页"""

    # 定义信号
    settings_saved = Signal()
    settings_reset = Signal()

    def __init__(self, config, logger, parent=None):
        """初始化设置标签页

        Args:
            config: 配置模块实例
            logger: 日志模块实例
            parent: 父窗口
        """
        super().__init__(parent)
        self.config = config
        self.logger = logger
        self.init_ui()

    # 从ui_init.py导入方法
    init_ui = init_ui
    select_curl_path = select_curl_path
    
    # 从config_operations.py导入方法
    save_settings = save_settings
    reset_settings = reset_settings
    
    # 从form_controls.py导入方法
    _create_form_control = create_form_control

    # 从scheduler_settings.py导入方法
    _load_scheduler_settings = _load_scheduler_settings
    _update_scheduler_settings = _update_scheduler_settings
    _check_now = _check_now
